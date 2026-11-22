"""Tests for the server-rendered page.

These assert the contract the browser depends on — which fragment comes back,
what it contains, and that a domain failure is rendered rather than raised.
They deliberately do not assert on wording or markup detail, which is free to
change.
"""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

PLAN = (
    "# Test Case: Sensor Init\n\n- ID: TC-001\n\n"
    "## Step 1: Power on\n\nDrive the enable line high.\n\n"
    "**Expected:** READY within 500 ms.\n"
)


def test_root_serves_the_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # The device the registry holds must be offered, or nothing can be generated.
    assert "example_device" in response.text


def test_static_assets_are_served(client: TestClient) -> None:
    for path in ("/static/app.css", "/static/app.js"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.content


def test_page_has_no_external_asset_references(client: TestClient) -> None:
    # The tool is used beside test benches on isolated networks, so the page
    # must not depend on a CDN being reachable.
    body = client.get("/").text
    assert "//cdn" not in body
    assert "http://" not in body.replace("http://www.w3.org", "")
    assert "https://" not in body


def test_preview_returns_the_outline(client: TestClient) -> None:
    response = client.post("/preview", data={"source": PLAN, "device_id": "example_device"})
    assert response.status_code == 200
    assert "Sensor Init" in response.text
    assert "Power on" in response.text
    assert "TC-001" in response.text


def test_preview_of_empty_source_is_not_an_error(client: TestClient) -> None:
    response = client.post("/preview", data={"source": "   ", "device_id": "example_device"})
    assert response.status_code == 200
    assert "case" not in response.text.lower() or "empty" in response.text.lower()


def test_preview_reports_diagnostics_without_failing(client: TestClient) -> None:
    misnumbered = PLAN + "\n## Step 9: Second\n\nDo more.\n\n**Expected:** fine.\n"
    response = client.post(
        "/preview", data={"source": misnumbered, "device_id": "example_device"}
    )
    assert response.status_code == 200
    assert "step.index_mismatch" in response.text


def test_preview_honours_the_step_level_override(client: TestClient) -> None:
    deep = "# Test Case: C\n\n### Step 1: Deep\n\nbody\n"
    default = client.post("/preview", data={"source": deep, "device_id": "example_device"})
    assert "Deep" not in default.text

    overridden = client.post(
        "/preview", data={"source": deep, "device_id": "example_device", "step_level": "3"}
    )
    assert "Deep" in overridden.text


def test_generate_returns_the_artifacts(client: TestClient) -> None:
    response = client.post("/generate", data={"source": PLAN, "device_id": "example_device"})
    assert response.status_code == 200
    assert "test_sensor_init.h" in response.text
    assert "test_sensor_init.cpp" in response.text
    assert "TestStep_01_PowerOn" in response.text


def test_generate_renders_failure_in_place(client: TestClient) -> None:
    # The page must keep the author's plan and their place, so a domain failure
    # comes back as a fragment with HTTP 200 rather than as an error status.
    response = client.post(
        "/generate", data={"source": "no headings here", "device_id": "example_device"}
    )
    assert response.status_code == 200
    assert "document.unprocessable" in response.text
    assert "document.no_test_case" in response.text


def test_generate_with_case_selector_narrows_the_output(client: TestClient) -> None:
    two_cases = PLAN + "\n# Test Case: Second\n\n## Step 1: Reset\n\nbody\n"
    response = client.post(
        "/generate",
        data={"source": two_cases, "device_id": "example_device", "case_selector": "2"},
    )
    assert "test_second.cpp" in response.text
    assert "test_sensor_init.cpp" not in response.text


def test_download_zip(client: TestClient) -> None:
    response = client.post(
        "/download", data={"source": PLAN, "device_id": "example_device", "what": "zip"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment;" in response.headers["content-disposition"]
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert names == ["test_sensor_init.h", "test_sensor_init.cpp"]


def test_download_single_file(client: TestClient) -> None:
    response = client.post(
        "/download",
        data={
            "source": PLAN,
            "device_id": "example_device",
            "what": "file",
            "path": "test_sensor_init.cpp",
        },
    )
    assert response.status_code == 200
    assert "test_sensor_init.cpp" in response.headers["content-disposition"]
    assert "TestStep_01_PowerOn" in response.text


def test_download_matches_what_was_displayed(client: TestClient) -> None:
    # The download re-runs the generation instead of caching it, which is only
    # safe because generation is deterministic. Prove the two agree.
    shown = client.post("/generate", data={"source": PLAN, "device_id": "example_device"})
    downloaded = client.post(
        "/download",
        data={
            "source": PLAN,
            "device_id": "example_device",
            "what": "file",
            "path": "test_sensor_init.h",
        },
    )
    for line in downloaded.text.splitlines():
        stripped = line.strip()
        if stripped.startswith("void TestStep_"):
            assert stripped in shown.text.replace("&amp;", "&")


def test_unknown_device_on_download_is_a_domain_error(client: TestClient) -> None:
    response = client.post(
        "/download", data={"source": PLAN, "device_id": "ghost", "what": "zip"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "device_not_found"


def test_web_routes_are_absent_from_the_api_schema(client: TestClient) -> None:
    # The HTML surface is not part of the published API contract.
    paths = client.get("/openapi.json").json()["paths"]
    assert "/" not in paths
    assert "/generate" not in paths
    assert "/preview" not in paths
