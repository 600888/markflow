import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config

from app.core.template_manager import TemplateManager
from app.db import CustomTemplateRepository, Database
from app.db.models import CustomTemplateEntity
from app.models.templates import ConversionOptions
from app.services.template_artifact_store import TemplateArtifactStore
from app.services.template_generator import TemplateGenerator
from app.services.template_service import TemplateService


def _service(tmp_path: Path) -> tuple[TemplateService, CustomTemplateRepository]:
    data_dir = tmp_path / "data"
    database = Database(data_dir)
    database.initialize()
    repository = CustomTemplateRepository(database.session_factory)
    service = TemplateService(
        builtin_manager=TemplateManager(tmp_path / "builtins"),
        repository=repository,
        artifact_store=TemplateArtifactStore(data_dir),
        generator=TemplateGenerator(tmp_path / "builtins"),
    )
    return service, repository


def _definition() -> dict:
    return {
        "name": "Team report",
        "slug": "team-report",
        "description": "Shared style",
        "author": "MarkFlow",
        "version": "1.0.0",
        "target_formats": ["docx"],
        "styles": {"body": {"font": "Arial", "size": 11}},
    }


def test_custom_template_is_stored_in_database_and_resolved(tmp_path: Path) -> None:
    service, repository = _service(tmp_path)

    created = service.create_custom_template(_definition())

    stored = repository.get_by_slug("team-report")
    assert stored is not None
    assert stored.id == created.id
    assert stored.styles_json["body"]["font"] == "Arial"
    args = service.build_extra_args(ConversionOptions(template_slug="team-report"))
    reference_path = Path(args[args.index("--reference-doc") + 1])
    assert reference_path.is_file()
    assert "template-artifacts" in reference_path.parts


def test_missing_artifact_is_rebuilt_from_database(tmp_path: Path) -> None:
    service, repository = _service(tmp_path)
    created = service.create_custom_template(_definition())
    stored = repository.get_by_slug(created.slug)
    assert stored is not None
    artifact = tmp_path / "data" / str(stored.artifact_relative_path)
    artifact.unlink()

    resolved = service.resolve(created.slug)

    assert resolved is not None
    assert resolved.reference_doc is not None
    assert resolved.reference_doc.is_file()


def test_artifact_store_rejects_path_outside_data_directory(tmp_path: Path) -> None:
    store = TemplateArtifactStore(tmp_path / "data")

    with pytest.raises(ValueError, match="路径越界"):
        store.resolve("../outside.docx")


def test_legacy_yaml_import_is_idempotent(tmp_path: Path) -> None:
    service, repository = _service(tmp_path)
    legacy = tmp_path / "legacy" / "team-report"
    legacy.mkdir(parents=True)
    legacy.joinpath("template.yaml").write_text(
        """name: Team report
slug: team-report
styles:
  body:
    font: Arial
    size: 11
""",
        encoding="utf-8",
    )

    assert service.import_legacy_templates([legacy.parent]) == (1, 0)
    assert service.import_legacy_templates([legacy.parent]) == (0, 0)
    assert repository.get_by_slug("team-report") is not None


def test_revision_history_restore_and_deleted_restore(tmp_path: Path) -> None:
    service, repository = _service(tmp_path)
    created = service.create_custom_template(_definition())

    changed = _definition()
    changed["styles"] = {"body": {"font": "Calibri", "size": 12}}
    updated = service.update_custom_template(
        created.slug,
        changed,
        expected_revision=1,
    )
    assert updated.revision == 2
    assert [item.operation for item in service.list_revisions(created.id)] == [
        "updated",
        "created",
    ]

    restored = service.restore_revision(created.id, 1)
    assert restored.revision == 3
    assert restored.styles_json["body"]["font"] == "Arial"
    assert service.list_revisions(created.id)[0].operation == "restored"

    assert service.delete_custom_template(created.slug) is True
    assert repository.get_by_slug(created.slug) is None
    revisions_after_delete = service.list_revisions(created.id)
    assert revisions_after_delete[0].operation == "deleted"
    assert revisions_after_delete[0].revision == 4

    revived = service.restore_revision(created.id, 2)
    assert revived.id == created.id
    assert revived.revision == 5
    assert revived.styles_json["body"]["font"] == "Calibri"
    assert service.list_revisions(created.id)[0].operation == "restored"


def test_cleanup_removes_only_expired_unreferenced_artifacts(tmp_path: Path) -> None:
    service, repository = _service(tmp_path)
    created = service.create_custom_template(_definition())
    stored = repository.get_by_slug(created.slug)
    assert stored is not None
    referenced = tmp_path / "data" / str(stored.artifact_relative_path)

    store = TemplateArtifactStore(tmp_path / "data")
    orphan_relative, _ = store.save(str(uuid4()), b"orphan")
    orphan = tmp_path / "data" / orphan_relative
    temporary = store.root / ".stale.tmp"
    temporary.write_bytes(b"partial")
    old = 1_600_000_000
    os.utime(referenced, (old, old))
    os.utime(orphan, (old, old))
    os.utime(temporary, (old, old))

    result = store.cleanup(
        repository.referenced_artifact_paths(),
        now=old + 8 * 24 * 60 * 60,
    )

    assert result["orphan_files"] == 1
    assert result["temporary_files"] == 1
    assert referenced.is_file()
    assert not orphan.exists()
    assert not temporary.exists()


def test_template_snapshot_contains_complete_definition(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)
    created = service.create_custom_template(_definition())

    snapshot = service.get_template_snapshot(created.slug)

    assert snapshot is not None
    assert snapshot["id"] == created.id
    assert snapshot["revision"] == 1
    assert snapshot["styles"]["body"]["font"] == "Arial"
    assert snapshot["is_custom"] is True
    assert json.loads(json.dumps(snapshot))["revision"] == 1


def test_0003_migration_backfills_existing_template_revision(tmp_path: Path) -> None:
    database = Database(tmp_path / "data")
    config = Config()
    config.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parents[2] / "migrations"),
    )
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.path.as_posix()}")
    command.upgrade(config, "0002_custom_templates")

    now = datetime.now(UTC)
    with database.session_factory.begin() as session:
        session.add(
            CustomTemplateEntity(
                id=str(uuid4()),
                slug="preexisting",
                name="Preexisting",
                description="",
                author="MarkFlow",
                version="1.0.0",
                target_formats_json=["docx"],
                styles_json={"body": {"font": "Arial"}},
                schema_version=1,
                revision=3,
                created_at=now,
                updated_at=now,
            )
        )
    command.upgrade(config, "head")

    repository = CustomTemplateRepository(database.session_factory)
    entity = repository.get_by_slug("preexisting")
    assert entity is not None
    revisions = repository.list_revisions(entity.id)
    assert len(revisions) == 1
    assert revisions[0].revision == 3
    assert revisions[0].operation == "migrated"
    assert revisions[0].definition_json["styles"]["body"]["font"] == "Arial"
    database.close()
