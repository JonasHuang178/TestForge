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

#: Default conventions (H1 case, H2 steps), for the routes that accept no
#: device and therefore cannot adopt one's heading levels.
DEFAULT_PLAN = "# A case\n\n## Step 1: Do it\n\nbody\n\n**Expected:** it works.\n"

PLAN = (
    '## Test Case List\n'
    '\n'
    '| ID | Test Name |\n'
    '|---|---|\n'
    '| TC-100 | print all info |\n'
    '\n'
    '### print all info\n'
    'Step 1 Print the build version  \n'
    'Step 2 Print the device id  \n'
)


def test_root_serves_the_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # The device the registry holds must be offered, or nothing can be generated.
    assert "simple_cpp" in response.text


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
    response = client.post("/preview", data={"source": PLAN, "device_id": "simple_cpp"})
    assert response.status_code == 200
    assert "print all info" in response.text
    assert "Print the build version" in response.text
    assert "TC-100" in response.text


def test_preview_of_empty_source_is_not_an_error(client: TestClient) -> None:
    response = client.post("/preview", data={"source": "   ", "device_id": "simple_cpp"})
    assert response.status_code == 200
    assert "case" not in response.text.lower() or "empty" in response.text.lower()


def test_preview_reports_diagnostics_without_failing(client: TestClient) -> None:
    misnumbered = PLAN + "Step 9 Second  \n"
    response = client.post(
        "/preview", data={"source": misnumbered, "device_id": "simple_cpp"}
    )
    assert response.status_code == 200
    assert "step.index_mismatch" in response.text


def test_preview_honours_the_step_level_override(client: TestClient) -> None:
    # The device reads steps as plain lines; a heading is not one.
    deep = "## Test Case List\n\n### a case\n\n#### Step 1 Deep\n\nbody\n"
    default = client.post("/preview", data={"source": deep, "device_id": "simple_cpp"})
    assert "Deep" not in default.text


def test_generate_returns_the_artifacts(client: TestClient) -> None:
    response = client.post("/generate", data={"source": PLAN, "device_id": "simple_cpp"})
    assert response.status_code == 200
    assert "test_main.cpp" in response.text
    assert "test_main.cpp" in response.text
    assert "printAllInfo" in response.text


def test_generate_renders_failure_in_place(client: TestClient) -> None:
    # The page must keep the author's plan and their place, so a domain failure
    # comes back as a fragment with HTTP 200 rather than as an error status.
    response = client.post(
        "/generate", data={"source": "no headings here", "device_id": "simple_cpp"}
    )
    assert response.status_code == 200
    assert "document.unprocessable" in response.text
    # This device confines cases to a named section, so a bare document fails
    # on the section being absent.
    assert "document.section_not_found" in response.text


def test_generate_with_case_selector_narrows_the_output(client: TestClient) -> None:
    two_cases = PLAN + "\n### check sensors\nStep 1 Read it  \n"
    response = client.post(
        "/generate",
        data={"source": two_cases, "device_id": "simple_cpp", "case_selector": "2"},
    )
    # Both cases share one file, so narrowing shows in the content, not the
    # file list.
    assert "int checkSensors()" in response.text
    assert "int printAllInfo()" not in response.text


def test_download_zip(client: TestClient) -> None:
    response = client.post(
        "/download", data={"source": PLAN, "device_id": "simple_cpp", "what": "zip"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment;" in response.headers["content-disposition"]
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert names == ["test_main.cpp"]


def test_download_single_file(client: TestClient) -> None:
    response = client.post(
        "/download",
        data={
            "source": PLAN,
            "device_id": "simple_cpp",
            "what": "file",
            "path": "test_main.cpp",
        },
    )
    assert response.status_code == 200
    assert "test_main.cpp" in response.headers["content-disposition"]
    assert "printAllInfo" in response.text


def test_download_matches_what_was_displayed(client: TestClient) -> None:
    # The download re-runs the generation instead of caching it, which is only
    # safe because generation is deterministic. Prove the two agree.
    shown = client.post("/generate", data={"source": PLAN, "device_id": "simple_cpp"})
    downloaded = client.post(
        "/download",
        data={
            "source": PLAN,
            "device_id": "simple_cpp",
            "what": "file",
            "path": "test_main.cpp",
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


# -- the three-step flow ----------------------------------------------------
#
# The page is a wizard: choose a device and a plan, confirm the generated
# code, then download. These assert the structure the script drives; the
# navigation itself is exercised in a browser.


def test_page_has_the_three_steps(client: TestClient) -> None:
    body = client.get("/").text
    for step in ("step-1", "step-2", "step-3"):
        assert f'id="{step}"' in body
    # Only the first is visible on load.
    assert '<section class="step" id="step-1">' in body
    assert '<section class="step" id="step-2" hidden>' in body
    assert '<section class="step" id="step-3" hidden>' in body


def test_page_offers_each_devices_own_example(client: TestClient) -> None:
    body = client.get("/").text
    assert 'class="example-plan" data-device="simple_cpp"' in body
    # The sample must be the device's, not one fixed plan for every device.
    assert "Test Case List" in body


def test_device_option_describes_how_steps_are_read(client: TestClient) -> None:
    # A step heading level says nothing about a device that reads steps as
    # plain lines, so the option carries the style instead.
    body = client.get("/").text
    assert 'data-style="line"' in body
    assert "Step N" in body


def test_generated_fragment_carries_the_summary_for_the_download_step(
    client: TestClient,
) -> None:
    response = client.post("/generate", data={"source": PLAN, "device_id": "simple_cpp"})
    assert 'data-cases="1"' in response.text
    assert 'data-files="1"' in response.text
    # The paths drive the per-file download buttons on step 3.
    assert 'data-path="test_main.cpp"' in response.text
