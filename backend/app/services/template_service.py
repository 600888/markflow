"""内置模板与数据库自定义模板的统一业务服务。"""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from uuid import uuid4

import yaml
from sqlalchemy.exc import IntegrityError

from app.core.log import log
from app.core.template_manager import TemplateManager
from app.db.models import CustomTemplateEntity, CustomTemplateRevisionEntity
from app.db.template_repository import CustomTemplateRepository
from app.models.templates import ConversionOptions, ResolvedTemplate, TemplateInfo
from app.services.template_artifact_store import TemplateArtifactStore
from app.services.template_generator import TemplateGenerator

TEMPLATE_GENERATOR_VERSION = "1"


class TemplateConflictError(Exception):
    """模板 slug 或 revision 冲突。"""


class TemplateNotFoundError(Exception):
    """自定义模板不存在。"""


class TemplateService:
    """以 SQLite 为事实来源管理自定义模板，并兼容内置模板。"""

    def __init__(
        self,
        builtin_manager: TemplateManager,
        repository: CustomTemplateRepository,
        artifact_store: TemplateArtifactStore,
        generator: TemplateGenerator,
    ) -> None:
        self._builtin = builtin_manager
        self._repository = repository
        self._artifact_store = artifact_store
        self._generator = generator
        self._locks_guard = Lock()
        self._materialize_locks: dict[str, Lock] = {}

    def list_templates(self) -> list[TemplateInfo]:
        """合并内置模板与数据库自定义模板。"""
        builtins = [item for item in self._builtin.list_templates() if not item.is_custom]
        customs = [self._to_info(entity) for entity in self._repository.list_all()]
        return builtins + customs

    def get_template(self, slug: str) -> TemplateInfo | None:
        """按 slug 获取统一模板元数据。"""
        builtin = self._builtin.get_template(slug)
        if builtin is not None and not builtin.is_custom:
            return builtin
        entity = self._repository.get_by_slug(slug)
        return self._to_info(entity) if entity is not None else None

    def get_custom_template(self, slug: str) -> dict | None:
        """读取可编辑的自定义模板定义。"""
        entity = self._repository.get_by_slug(slug)
        return self._to_definition(entity) if entity is not None else None

    def get_template_snapshot(self, slug: str) -> dict | None:
        """返回可直接写入转换历史的完整 JSON 模板快照。"""
        entity = self._repository.get_by_slug(slug)
        if entity is not None:
            definition = self._to_definition(entity)
            definition["updated_at"] = entity.updated_at.isoformat()
            return {
                **definition,
                "is_custom": True,
                "schema_version": entity.schema_version,
            }
        info = self._builtin.get_template(slug)
        if info is None or info.is_custom:
            return None
        return {
            "id": None,
            "name": info.name,
            "slug": info.slug,
            "description": info.description,
            "author": info.author,
            "target_formats": info.target_formats,
            "version": info.version,
            "styles": self._builtin.get_styles_config(slug),
            "revision": None,
            "is_custom": False,
            "schema_version": 1,
        }

    def list_revisions(self, template_id: str) -> list[CustomTemplateRevisionEntity]:
        """列出指定模板 ID 的全部修订和删除事件。"""
        return self._repository.list_revisions(template_id)

    def get_revision(
        self,
        template_id: str,
        revision: int,
    ) -> CustomTemplateRevisionEntity | None:
        """读取指定模板修订。"""
        return self._repository.get_revision(template_id, revision)

    def list_deleted_template_histories(self) -> list[CustomTemplateRevisionEntity]:
        """列出可从历史恢复的已删除模板。"""
        return self._repository.list_deleted_heads()

    def restore_revision(
        self,
        template_id: str,
        revision: int,
    ) -> CustomTemplateEntity:
        """将历史定义恢复为新的当前修订，也支持恢复已删除模板。"""
        historical = self._repository.get_revision(template_id, revision)
        if historical is None:
            raise TemplateNotFoundError(f"模板修订 {template_id}@{revision} 不存在")
        definition = historical.definition_json
        content = self._generator.generate_reference(definition["styles"])
        relative_path, digest = self._artifact_store.save(template_id, content)
        current = self._repository.get_by_id(template_id)
        if current is None:
            slug_owner = self._repository.get_by_slug(definition["slug"])
            if slug_owner is not None:
                raise TemplateConflictError(
                    f"模板 slug '{definition['slug']}' 已被其他模板占用"
                )
            try:
                return self._repository.restore_deleted(
                    template_id=template_id,
                    definition=definition,
                    artifact_relative_path=relative_path,
                    artifact_sha256=digest,
                    artifact_generator_version=TEMPLATE_GENERATOR_VERSION,
                )
            except IntegrityError as exc:
                raise TemplateConflictError(
                    f"模板 slug '{definition['slug']}' 已被其他模板占用"
                ) from exc

        updated = self._repository.update(
            current.slug,
            expected_revision=current.revision,
            name=definition["name"],
            description=definition.get("description", ""),
            author=definition.get("author", "MarkFlow"),
            version=definition.get("version", "1.0.0"),
            target_formats=definition.get("target_formats", ["docx"]),
            styles=definition["styles"],
            artifact_relative_path=relative_path,
            artifact_sha256=digest,
            artifact_generator_version=TEMPLATE_GENERATOR_VERSION,
            operation="restored",
        )
        if updated is None:
            raise TemplateConflictError("模板已在其他窗口中更新，请重试恢复操作")
        return updated

    def cleanup_orphan_artifacts(self) -> dict[str, int]:
        """清理不被当前模板或历史修订引用的过期文件。"""
        return self._artifact_store.cleanup(self._repository.referenced_artifact_paths())

    def create_custom_template(self, definition: dict) -> CustomTemplateEntity:
        """生成 artifact 并创建数据库模板。"""
        slug = str(definition["slug"])
        if self.get_template(slug) is not None:
            raise TemplateConflictError(f"模板 slug '{slug}' 已存在")

        template_id = str(uuid4())
        content = self._generator.generate_reference(definition["styles"])
        relative_path, digest = self._artifact_store.save(template_id, content)
        try:
            return self._repository.create(
                template_id=template_id,
                slug=slug,
                name=definition["name"],
                description=definition.get("description", ""),
                author=definition.get("author", "MarkFlow"),
                version=definition.get("version", "1.0.0"),
                target_formats=definition.get("target_formats", ["docx"]),
                styles=definition["styles"],
                artifact_relative_path=relative_path,
                artifact_sha256=digest,
                artifact_generator_version=TEMPLATE_GENERATOR_VERSION,
            )
        except IntegrityError as exc:
            raise TemplateConflictError(f"模板 slug '{slug}' 已存在") from exc

    def update_custom_template(
        self,
        slug: str,
        definition: dict,
        *,
        expected_revision: int | None,
    ) -> CustomTemplateEntity:
        """生成新 artifact，并按 revision 更新数据库模板。"""
        current = self._repository.get_by_slug(slug)
        if current is None:
            raise TemplateNotFoundError(f"自定义模板 '{slug}' 不存在")
        revision = expected_revision if expected_revision is not None else current.revision

        content = self._generator.generate_reference(definition["styles"])
        relative_path, digest = self._artifact_store.save(current.id, content)
        updated = self._repository.update(
            slug,
            expected_revision=revision,
            name=definition["name"],
            description=definition.get("description", ""),
            author=definition.get("author", "MarkFlow"),
            version=definition.get("version", "1.0.0"),
            target_formats=definition.get("target_formats", ["docx"]),
            styles=definition["styles"],
            artifact_relative_path=relative_path,
            artifact_sha256=digest,
            artifact_generator_version=TEMPLATE_GENERATOR_VERSION,
        )
        if updated is None:
            raise TemplateConflictError("模板已在其他窗口中更新，请重新加载后再保存")
        return updated

    def delete_custom_template(self, slug: str) -> bool:
        """删除数据库模板；artifact 留待延迟回收。"""
        return self._repository.delete(slug) is not None

    def resolve(self, slug: str) -> ResolvedTemplate | None:
        """解析转换所需的样式、reference doc 和 filters。"""
        builtin = self._builtin.get_template(slug)
        if builtin is not None and not builtin.is_custom:
            template_dir = self._builtin.resolve_template_dir(slug)
            if template_dir is None:
                return None
            reference_doc = template_dir / "reference.docx"
            filters_dir = template_dir / "filters"
            return ResolvedTemplate(
                slug=slug,
                styles=self._builtin.get_styles_config(slug),
                reference_doc=reference_doc if reference_doc.is_file() else None,
                lua_filters=sorted(filters_dir.glob("*.lua")) if filters_dir.is_dir() else [],
            )

        entity = self._repository.get_by_slug(slug)
        if entity is None:
            return None
        reference_doc = self._materialize(entity)
        return ResolvedTemplate(
            slug=slug,
            styles=entity.styles_json,
            reference_doc=reference_doc,
            is_custom=True,
            revision=entity.revision,
        )

    def build_extra_args(self, options: ConversionOptions | None = None) -> list[str]:
        """为 Pandoc 组装模板与通用转换参数。"""
        options = options or ConversionOptions()
        resolved = self.resolve(options.template_slug)
        generic_options = options.model_copy(update={"template_slug": "__no_template__"})
        args = self._builtin.build_extra_args(generic_options)
        if resolved is None:
            return args
        template_args: list[str] = []
        if resolved.reference_doc is not None:
            template_args.extend(["--reference-doc", str(resolved.reference_doc.resolve())])
        for lua_filter in resolved.lua_filters:
            template_args.extend(["--lua-filter", str(lua_filter.resolve())])
        return template_args + args

    def get_table_config(self, slug: str) -> dict | None:
        """读取表格样式配置。"""
        return self._get_style_section(slug, "table")

    def get_header_config(self, slug: str) -> dict | None:
        """读取页眉样式配置。"""
        return self._get_style_section(slug, "header")

    def get_styles_config(self, slug: str) -> dict:
        """读取完整样式配置。"""
        resolved = self.resolve(slug)
        return resolved.styles if resolved is not None else {}

    def import_legacy_templates(self, roots: list[Path]) -> tuple[int, int]:
        """从旧 custom 目录幂等导入模板，返回成功数和失败数。"""
        imported = 0
        failed = 0
        seen: set[Path] = set()
        for root in roots:
            resolved_root = root.resolve()
            if resolved_root in seen or not resolved_root.is_dir():
                continue
            seen.add(resolved_root)
            for entry in sorted(resolved_root.iterdir()):
                yaml_path = entry / "template.yaml"
                if not entry.is_dir() or not yaml_path.is_file():
                    continue
                try:
                    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                    definition = self._validate_legacy_definition(data, entry.name)
                    if self.get_template(definition["slug"]) is not None:
                        continue
                    self.create_custom_template(definition)
                    imported += 1
                    log.info(f"已导入旧自定义模板: {definition['slug']}")
                except Exception as exc:
                    failed += 1
                    log.warning(f"导入旧自定义模板失败: {yaml_path} - {exc}")
        return imported, failed

    def _materialize(self, entity: CustomTemplateEntity) -> Path:
        lock = self._lock_for(entity.slug)
        with lock:
            latest = self._repository.get_by_slug(entity.slug)
            if latest is None:
                raise TemplateNotFoundError(f"自定义模板 '{entity.slug}' 不存在")
            if (
                latest.artifact_generator_version == TEMPLATE_GENERATOR_VERSION
                and self._artifact_store.is_valid(
                    latest.artifact_relative_path,
                    latest.artifact_sha256,
                )
            ):
                return self._artifact_store.resolve(latest.artifact_relative_path or "")

            content = self._generator.generate_reference(latest.styles_json)
            relative_path, digest = self._artifact_store.save(latest.id, content)
            repaired = self._repository.update_artifact(
                latest.slug,
                artifact_relative_path=relative_path,
                artifact_sha256=digest,
                artifact_generator_version=TEMPLATE_GENERATOR_VERSION,
            )
            if repaired is None:
                raise TemplateNotFoundError(f"自定义模板 '{entity.slug}' 不存在")
            return self._artifact_store.resolve(relative_path)

    def _get_style_section(self, slug: str, section: str) -> dict | None:
        entity = self._repository.get_by_slug(slug)
        if entity is not None:
            value = entity.styles_json.get(section)
            return value if isinstance(value, dict) else None
        return (
            self._builtin.get_table_config(slug)
            if section == "table"
            else self._builtin.get_header_config(slug)
        )

    def _lock_for(self, slug: str) -> Lock:
        with self._locks_guard:
            return self._materialize_locks.setdefault(slug, Lock())

    @staticmethod
    def _to_info(entity: CustomTemplateEntity) -> TemplateInfo:
        return TemplateInfo(
            id=entity.id,
            slug=entity.slug,
            name=entity.name,
            version=entity.version,
            description=entity.description,
            author=entity.author,
            target_formats=entity.target_formats_json,
            has_reference_doc=bool(entity.artifact_relative_path),
            has_lua_filters=False,
            is_custom=True,
            revision=entity.revision,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def _to_definition(entity: CustomTemplateEntity) -> dict:
        return {
            "id": entity.id,
            "name": entity.name,
            "slug": entity.slug,
            "description": entity.description,
            "author": entity.author,
            "target_formats": entity.target_formats_json,
            "version": entity.version,
            "styles": entity.styles_json,
            "revision": entity.revision,
            "updated_at": entity.updated_at,
        }

    @staticmethod
    def _validate_legacy_definition(data: object, fallback_slug: str) -> dict:
        if not isinstance(data, dict):
            raise TypeError("template.yaml 顶层必须是对象")
        slug = str(data.get("slug", fallback_slug))
        if not slug or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in slug):
            raise ValueError(f"无效的模板 slug: {slug}")
        styles = data.get("styles")
        if not isinstance(styles, dict) or not styles:
            raise ValueError("模板缺少 styles")
        target_formats = data.get("target_formats", ["docx"])
        if not isinstance(target_formats, list) or not all(
            isinstance(item, str) for item in target_formats
        ):
            raise ValueError("target_formats 必须是字符串数组")
        return {
            "name": str(data.get("name", slug)),
            "slug": slug,
            "description": str(data.get("description", "")),
            "author": str(data.get("author", "MarkFlow")),
            "target_formats": target_formats,
            "version": str(data.get("version", "1.0.0")),
            "styles": styles,
        }
