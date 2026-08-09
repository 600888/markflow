"""自定义模板数据库仓储。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update

from app.db.models import CustomTemplateEntity, CustomTemplateRevisionEntity


class CustomTemplateRepository:
    """封装自定义模板的事务性 CRUD。"""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def list_all(self) -> list[CustomTemplateEntity]:
        """按最近更新时间列出全部自定义模板。"""
        with self._session_factory() as session:
            return list(
                session.scalars(
                    select(CustomTemplateEntity).order_by(
                        CustomTemplateEntity.updated_at.desc(),
                        CustomTemplateEntity.name.asc(),
                    )
                )
            )

    def get_by_slug(self, slug: str) -> CustomTemplateEntity | None:
        """按 slug 获取模板。"""
        with self._session_factory() as session:
            return session.scalar(
                select(CustomTemplateEntity).where(CustomTemplateEntity.slug == slug)
            )

    def get_by_id(self, template_id: str) -> CustomTemplateEntity | None:
        """按稳定 UUID 获取当前模板。"""
        with self._session_factory() as session:
            return session.get(CustomTemplateEntity, template_id)

    def list_revisions(self, template_id: str) -> list[CustomTemplateRevisionEntity]:
        """按倒序列出模板的全部不可变修订。"""
        with self._session_factory() as session:
            return list(
                session.scalars(
                    select(CustomTemplateRevisionEntity)
                    .where(CustomTemplateRevisionEntity.template_id == template_id)
                    .order_by(CustomTemplateRevisionEntity.revision.desc())
                )
            )

    def get_revision(
        self,
        template_id: str,
        revision: int,
    ) -> CustomTemplateRevisionEntity | None:
        """读取指定修订，包括已删除模板的历史。"""
        with self._session_factory() as session:
            return session.scalar(
                select(CustomTemplateRevisionEntity).where(
                    CustomTemplateRevisionEntity.template_id == template_id,
                    CustomTemplateRevisionEntity.revision == revision,
                )
            )

    def list_deleted_heads(self) -> list[CustomTemplateRevisionEntity]:
        """列出当前记录已不存在的模板的最新历史事件。"""
        current_ids = {entity.id for entity in self.list_all()}
        with self._session_factory() as session:
            revisions = session.scalars(
                select(CustomTemplateRevisionEntity).order_by(
                    CustomTemplateRevisionEntity.created_at.desc(),
                    CustomTemplateRevisionEntity.revision.desc(),
                )
            )
            heads: dict[str, CustomTemplateRevisionEntity] = {}
            for revision in revisions:
                if revision.template_id not in current_ids:
                    heads.setdefault(revision.template_id, revision)
            return list(heads.values())

    def create(  # noqa: PLR0913
        self,
        *,
        template_id: str,
        slug: str,
        name: str,
        description: str,
        author: str,
        version: str,
        target_formats: list[str],
        styles: dict,
        artifact_relative_path: str,
        artifact_sha256: str,
        artifact_generator_version: str,
    ) -> CustomTemplateEntity:
        """创建模板及其当前派生文件索引。"""
        now = datetime.now(UTC)
        entity = CustomTemplateEntity(
            id=template_id,
            slug=slug,
            name=name,
            description=description,
            author=author,
            version=version,
            target_formats_json=target_formats,
            styles_json=styles,
            schema_version=1,
            revision=1,
            artifact_relative_path=artifact_relative_path,
            artifact_sha256=artifact_sha256,
            artifact_generator_version=artifact_generator_version,
            artifact_updated_at=now,
            created_at=now,
            updated_at=now,
        )
        with self._session_factory.begin() as session:
            session.add(entity)
            session.add(self._revision_from_entity(entity, operation="created", created_at=now))
        return entity

    def update(  # noqa: PLR0913
        self,
        slug: str,
        *,
        expected_revision: int,
        name: str,
        description: str,
        author: str,
        version: str,
        target_formats: list[str],
        styles: dict,
        artifact_relative_path: str,
        artifact_sha256: str,
        artifact_generator_version: str,
        operation: str = "updated",
    ) -> CustomTemplateEntity | None:
        """按 revision 乐观锁更新模板。"""
        now = datetime.now(UTC)
        with self._session_factory.begin() as session:
            result = session.execute(
                update(CustomTemplateEntity)
                .where(
                    CustomTemplateEntity.slug == slug,
                    CustomTemplateEntity.revision == expected_revision,
                )
                .values(
                    name=name,
                    description=description,
                    author=author,
                    version=version,
                    target_formats_json=target_formats,
                    styles_json=styles,
                    revision=CustomTemplateEntity.revision + 1,
                    artifact_relative_path=artifact_relative_path,
                    artifact_sha256=artifact_sha256,
                    artifact_generator_version=artifact_generator_version,
                    artifact_updated_at=now,
                    updated_at=now,
                )
            )
            if result.rowcount == 0:
                return None
            entity = session.scalar(
                select(CustomTemplateEntity).where(CustomTemplateEntity.slug == slug)
            )
            if entity is None:
                return None
            session.add(self._revision_from_entity(entity, operation=operation, created_at=now))
            return entity

    def update_artifact(
        self,
        slug: str,
        *,
        artifact_relative_path: str,
        artifact_sha256: str,
        artifact_generator_version: str,
    ) -> CustomTemplateEntity | None:
        """自愈派生文件，不改变用户可见定义的 revision。"""
        now = datetime.now(UTC)
        with self._session_factory.begin() as session:
            session.execute(
                update(CustomTemplateEntity)
                .where(CustomTemplateEntity.slug == slug)
                .values(
                    artifact_relative_path=artifact_relative_path,
                    artifact_sha256=artifact_sha256,
                    artifact_generator_version=artifact_generator_version,
                    artifact_updated_at=now,
                )
            )
            entity = session.scalar(
                select(CustomTemplateEntity).where(CustomTemplateEntity.slug == slug)
            )
            if entity is not None:
                session.execute(
                    update(CustomTemplateRevisionEntity)
                    .where(
                        CustomTemplateRevisionEntity.template_id == entity.id,
                        CustomTemplateRevisionEntity.revision == entity.revision,
                    )
                    .values(
                        artifact_relative_path=artifact_relative_path,
                        artifact_sha256=artifact_sha256,
                        artifact_generator_version=artifact_generator_version,
                    )
                )
            return entity

    def delete(self, slug: str) -> CustomTemplateEntity | None:
        """硬删除模板记录并返回删除前的数据。"""
        with self._session_factory.begin() as session:
            entity = session.scalar(
                select(CustomTemplateEntity).where(CustomTemplateEntity.slug == slug)
            )
            if entity is None:
                return None
            deleted_revision = self._revision_from_entity(
                entity,
                operation="deleted",
                created_at=datetime.now(UTC),
            )
            deleted_revision.revision = entity.revision + 1
            session.add(deleted_revision)
            session.execute(delete(CustomTemplateEntity).where(CustomTemplateEntity.slug == slug))
            return entity

    def restore_deleted(
        self,
        *,
        template_id: str,
        definition: dict,
        artifact_relative_path: str,
        artifact_sha256: str,
        artifact_generator_version: str,
    ) -> CustomTemplateEntity:
        """从历史修订恢复已删除模板，并延续原 revision 序列。"""
        now = datetime.now(UTC)
        with self._session_factory.begin() as session:
            latest_revision = session.scalar(
                select(func.max(CustomTemplateRevisionEntity.revision)).where(
                    CustomTemplateRevisionEntity.template_id == template_id
                )
            )
            entity = CustomTemplateEntity(
                id=template_id,
                slug=definition["slug"],
                name=definition["name"],
                description=definition.get("description", ""),
                author=definition.get("author", "MarkFlow"),
                version=definition.get("version", "1.0.0"),
                target_formats_json=definition.get("target_formats", ["docx"]),
                styles_json=definition["styles"],
                schema_version=1,
                revision=int(latest_revision or 0) + 1,
                artifact_relative_path=artifact_relative_path,
                artifact_sha256=artifact_sha256,
                artifact_generator_version=artifact_generator_version,
                artifact_updated_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(entity)
            session.add(self._revision_from_entity(entity, operation="restored", created_at=now))
            return entity

    def referenced_artifact_paths(self) -> set[str]:
        """返回当前模板和全部历史修订仍引用的 artifact 路径。"""
        with self._session_factory() as session:
            current = session.scalars(
                select(CustomTemplateEntity.artifact_relative_path).where(
                    CustomTemplateEntity.artifact_relative_path.is_not(None)
                )
            )
            revisions = session.scalars(
                select(CustomTemplateRevisionEntity.artifact_relative_path).where(
                    CustomTemplateRevisionEntity.artifact_relative_path.is_not(None)
                )
            )
            return {str(path) for path in [*current, *revisions] if path}

    @staticmethod
    def _revision_from_entity(
        entity: CustomTemplateEntity,
        *,
        operation: str,
        created_at: datetime,
    ) -> CustomTemplateRevisionEntity:
        return CustomTemplateRevisionEntity(
            template_id=entity.id,
            slug=entity.slug,
            revision=entity.revision,
            operation=operation,
            definition_json={
                "name": entity.name,
                "slug": entity.slug,
                "description": entity.description,
                "author": entity.author,
                "version": entity.version,
                "target_formats": entity.target_formats_json,
                "styles": entity.styles_json,
            },
            artifact_relative_path=entity.artifact_relative_path,
            artifact_sha256=entity.artifact_sha256,
            artifact_generator_version=entity.artifact_generator_version,
            created_at=created_at,
        )
