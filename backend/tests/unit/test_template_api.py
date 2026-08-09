from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import get_gen, get_mgr, router
from app.core.template_manager import TemplateManager
from app.db import CustomTemplateRepository, Database
from app.services.template_artifact_store import TemplateArtifactStore
from app.services.template_generator import TemplateGenerator
from app.services.template_service import TemplateService


def _client(tmp_path: Path) -> TestClient:
    database = Database(tmp_path / "data")
    database.initialize()
    generator = TemplateGenerator(tmp_path / "builtins")
    service = TemplateService(
        builtin_manager=TemplateManager(tmp_path / "builtins"),
        repository=CustomTemplateRepository(database.session_factory),
        artifact_store=TemplateArtifactStore(tmp_path / "data"),
        generator=generator,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_gen] = lambda: generator
    app.dependency_overrides[get_mgr] = lambda: service
    return TestClient(app)


def _payload(name: str = "Team report") -> dict:
    return {
        "name": name,
        "slug": "team-report",
        "description": "Shared report style",
        "target_formats": ["docx"],
        "styles": {
            "heading1": {"font": "Arial", "size": "三号", "bold": True},
            "body": {"font": "Calibri", "size": "小四", "line_spacing": 1.5},
            "table": {"header_background": "#EDE9FE", "header_bold": True},
        },
    }


def test_template_resource_lifecycle(tmp_path: Path) -> None:
    client = _client(tmp_path)

    created = client.post("/templates", json=_payload())
    assert created.status_code == 201
    assert created.json()["slug"] == "team-report"
    template_id = created.json()["id"]

    detail = client.get("/templates/team-report")
    assert detail.status_code == 200
    assert detail.json()["styles"]["table"]["header_background"] == "#EDE9FE"
    assert detail.json()["revision"] == 1

    duplicate = client.post("/templates", json=_payload())
    assert duplicate.status_code == 409

    listed = client.get("/templates")
    assert listed.status_code == 200
    custom = next(item for item in listed.json()["templates"] if item["slug"] == "team-report")
    assert custom["is_custom"] is True
    assert custom["revision"] == 1

    update_payload = _payload("Updated report")
    update_payload["revision"] = detail.json()["revision"]
    updated = client.put("/templates/team-report", json=update_payload)
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated report"
    assert updated.json()["revision"] == 2

    stale = client.put("/templates/team-report", json=update_payload)
    assert stale.status_code == 409

    revisions = client.get(f"/templates/{template_id}/revisions")
    assert revisions.status_code == 200
    assert [item["revision"] for item in revisions.json()["revisions"]] == [2, 1]
    first_revision = client.get(f"/templates/{template_id}/revisions/1")
    assert first_revision.status_code == 200
    assert first_revision.json()["definition"]["name"] == "Team report"

    preview = client.post("/templates/preview", json=_payload())
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument",
    )
    assert preview.content.startswith(b"PK")

    deleted = client.delete("/templates/team-report")
    assert deleted.status_code == 204

    missing = client.delete("/templates/team-report")
    assert missing.status_code == 404

    deleted_histories = client.get("/template-revisions/deleted")
    assert deleted_histories.status_code == 200
    assert deleted_histories.json()["revisions"][0]["template_id"] == template_id

    restored = client.post(f"/templates/{template_id}/revisions/1/restore")
    assert restored.status_code == 200
    assert restored.json()["revision"] == 4
    assert client.get("/templates/team-report").status_code == 200


def test_update_rejects_mismatched_slug(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.put("/templates/another-slug", json=_payload())

    assert response.status_code == 400
