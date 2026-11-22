from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

PLAN = (
    "## Test Case List\n\n"
    "### print all info\n\n"
    "- ID: TC-100\n\n"
    "#### Step 1 Print the build version\n\n"
    "Call the version helper and write it to stdout.\n\n"
    "**Expected:** A non-empty version string is printed.\n"
)

#: Default conventions (H1 case, H2 steps), for the endpoints that accept no
#: device and therefore cannot adopt one's heading levels.
DEFAULT_PLAN = "# A case\n\n## Step 1: Do it\n\nbody\n\n**Expected:** it works.\n"


def test_health(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["devices"] == 1


def test_list_and_get_device(client: TestClient) -> None:
    listed = client.get("/api/v1/devices").json()["devices"]
    assert [d["id"] for d in listed] == ["simple_cpp"]

    detail = client.get("/api/v1/devices/simple_cpp").json()
    assert detail["step_heading_level"] == 4
    assert detail["anchor"]["begin"] == "// === TESTFORGE:{name}:BEGIN ==="


def test_unknown_device_is_404_with_the_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/devices/ghost")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "device_not_found"
    assert body["error"]["details"]["known"] == ["simple_cpp"]
    assert body["diagnostics"] == []


def test_parse_returns_ir_and_diagnostics(client: TestClient) -> None:
    response = client.post(
        "/api/v1/parse", json={"source": PLAN, "device_id": "simple_cpp"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["cases"][0]["id"] == "TC-100"
    assert (
        body["cases"][0]["steps"][0]["expected"]
        == "A non-empty version string is printed."
    )


def test_parse_needs_no_device(client: TestClient) -> None:
    # Without a device the default conventions apply, which is the point: a
    # client can preview a plan before choosing a target.
    assert client.post("/api/v1/parse", json={"source": DEFAULT_PLAN}).status_code == 200


def test_parse_warnings_still_return_200(client: TestClient) -> None:
    # A misnumbered step is recoverable: it must not fail the request.
    source = DEFAULT_PLAN + "\n## Step 9: Second\n\nDo more.\n\n**Expected:** fine.\n"
    response = client.post("/api/v1/parse", json={"source": source})
    assert response.status_code == 200
    assert "step.index_mismatch" in [d["code"] for d in response.json()["diagnostics"]]


def test_unusable_plan_is_422_carrying_diagnostics(client: TestClient) -> None:
    response = client.post("/api/v1/parse", json={"source": "nothing here"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "document.unprocessable"
    assert [d["code"] for d in body["diagnostics"]] == ["document.no_test_case"]


def test_generation_returns_201_and_artifacts(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations", json={"source": PLAN, "device_id": "simple_cpp"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["generation_id"].startswith("gen_")
    assert [a["path"] for a in body["artifacts"]] == ["test_main.cpp"]
    assert "int printAllInfo()" in body["artifacts"][0]["content"]
    assert all(a["mode"] == "created" for a in body["artifacts"])


def test_existing_files_round_trip_reports_updated(client: TestClient) -> None:
    first = client.post(
        "/api/v1/generations", json={"source": PLAN, "device_id": "simple_cpp"}
    ).json()
    existing = [{"path": a["path"], "content": a["content"]} for a in first["artifacts"]]
    second = client.post(
        "/api/v1/generations",
        json={"source": PLAN, "device_id": "simple_cpp", "existing_files": existing},
    ).json()
    assert [a["mode"] for a in second["artifacts"]] == ["updated"]
    assert [a["content"] for a in second["artifacts"]] == [
        a["content"] for a in first["artifacts"]
    ]


def test_existing_file_without_anchors_is_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations",
        json={
            "source": PLAN,
            "device_id": "simple_cpp",
            "existing_files": [{"path": "test_main.cpp", "content": "// empty\n"}],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "anchor.missing"


def test_unknown_field_is_400_not_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations",
        json={"source": PLAN, "device_id": "simple_cpp", "nameing_pattern": "x"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "request_invalid"


def test_oversized_source_is_413(client: TestClient) -> None:
    response = client.post(
        "/api/v1/generations",
        json={"source": "x" * 1_000_001, "device_id": "simple_cpp"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "source_too_large"


def test_validation_error_does_not_echo_the_submitted_source(client: TestClient) -> None:
    marker = "SECRET-PLAN-TEXT"
    response = client.post(
        "/api/v1/generations",
        json={"source": f"# Test Case: {marker}\n", "device_id": 123, "zzz": 1},
    )
    assert response.status_code == 400
    assert marker not in response.text


def test_zip_format_is_deterministic(client: TestClient) -> None:
    payload = {"source": PLAN, "device_id": "simple_cpp"}
    first = client.post("/api/v1/generations?format=zip", json=payload)
    second = client.post("/api/v1/generations?format=zip", json=payload)
    assert first.status_code == 200
    assert first.headers["content-type"] == "application/zip"
    assert "attachment;" in first.headers["content-disposition"]
    assert first.content == second.content  # fixed zip timestamps
    names = zipfile.ZipFile(io.BytesIO(first.content)).namelist()
    assert names == ["test_main.cpp"]


def test_file_format_returns_the_single_artifact(client: TestClient) -> None:
    # This device emits one file per plan, so the single-file representation
    # is exactly what it should return.
    response = client.post(
        "/api/v1/generations?format=file", json={"source": PLAN, "device_id": "simple_cpp"}
    )
    assert response.status_code == 200
    assert "test_main.cpp" in response.headers["content-disposition"]
    assert "int printAllInfo()" in response.text


def test_openapi_documents_every_route(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert sorted(paths) == [
        "/api/v1/devices",
        "/api/v1/devices/{device_id}",
        "/api/v1/generations",
        "/api/v1/health",
        "/api/v1/parse",
    ]
