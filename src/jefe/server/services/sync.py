"""Sync service for handling client-server synchronization."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jefe.data.models.harness_config import HarnessConfig
from jefe.data.models.installed_skill import InstalledSkill
from jefe.data.models.project import Project
from jefe.data.models.skill import Skill
from jefe.server.schemas.sync import (
    ConflictResolution,
    EntityType,
    ServerHarnessConfigItem,
    ServerInstalledSkillItem,
    ServerProjectItem,
    ServerSkillItem,
    SyncConflictInfo,
    SyncHarnessConfigItem,
    SyncInstalledSkillItem,
    SyncProjectItem,
    SyncPullRequest,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncSkillItem,
)


class SyncService:
    """Service for handling sync operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the sync service.

        Args:
            session: Database session
        """
        self.session = session

    async def push(self, request: SyncPushRequest) -> SyncPushResponse:
        """Handle a push request from a client.

        Implements last-write-wins conflict resolution.

        Args:
            request: The push request with dirty items

        Returns:
            SyncPushResponse with results and any conflicts
        """
        conflicts: list[SyncConflictInfo] = []
        server_id_mappings: dict[str, dict[int, int]] = {}
        projects_synced = 0
        skills_synced = 0
        installed_skills_synced = 0
        harness_configs_synced = 0

        # Process projects
        project_mappings, project_conflicts, project_count = await self._process_projects(
            request.projects
        )
        server_id_mappings["project"] = project_mappings
        conflicts.extend(project_conflicts)
        projects_synced = project_count

        # Process skills
        skill_mappings, skill_conflicts, skill_count = await self._process_skills(request.skills)
        server_id_mappings["skill"] = skill_mappings
        conflicts.extend(skill_conflicts)
        skills_synced = skill_count

        # Process installed skills
        installed_mappings, installed_conflicts, installed_count = (
            await self._process_installed_skills(request.installed_skills)
        )
        server_id_mappings["installed_skill"] = installed_mappings
        conflicts.extend(installed_conflicts)
        installed_skills_synced = installed_count

        # Process harness configs
        config_mappings, config_conflicts, config_count = await self._process_harness_configs(
            request.harness_configs
        )
        server_id_mappings["harness_config"] = config_mappings
        conflicts.extend(config_conflicts)
        harness_configs_synced = config_count

        await self.session.commit()

        return SyncPushResponse(
            success=True,
            projects_synced=projects_synced,
            skills_synced=skills_synced,
            installed_skills_synced=installed_skills_synced,
            harness_configs_synced=harness_configs_synced,
            conflicts=conflicts,
            server_id_mappings=server_id_mappings,
        )

    async def pull(self, request: SyncPullRequest) -> SyncPullResponse:
        """Handle a pull request from a client.

        Args:
            request: The pull request with last_synced timestamp

        Returns:
            SyncPullResponse with changed items
        """
        since = request.last_synced
        entity_types = request.entity_types

        projects: list[ServerProjectItem] = []
        skills: list[ServerSkillItem] = []
        installed_skills: list[ServerInstalledSkillItem] = []
        harness_configs: list[ServerHarnessConfigItem] = []

        # Get projects if requested
        if entity_types is None or EntityType.PROJECT in entity_types:
            projects = await self._get_changed_projects(since)

        # Get skills if requested
        if entity_types is None or EntityType.SKILL in entity_types:
            skills = await self._get_changed_skills(since)

        # Get installed skills if requested
        if entity_types is None or EntityType.INSTALLED_SKILL in entity_types:
            installed_skills = await self._get_changed_installed_skills(since)

        # Get harness configs if requested
        if entity_types is None or EntityType.HARNESS_CONFIG in entity_types:
            harness_configs = await self._get_changed_harness_configs(since)

        return SyncPullResponse(
            success=True,
            server_time=datetime.now(UTC),
            projects=projects,
            skills=skills,
            installed_skills=installed_skills,
            harness_configs=harness_configs,
        )

    async def _process_projects(
        self, items: list[SyncProjectItem]
    ) -> tuple[dict[int, int], list[SyncConflictInfo], int]:
        """Process pushed projects.

        Args:
            items: List of projects to process

        Returns:
            Tuple of (local_id -> server_id mappings, conflicts, count synced)
        """
        mappings: dict[int, int] = {}
        conflicts: list[SyncConflictInfo] = []
        count = 0

        for item in items:
            conflict, server_id = await self._process_project(item)
            if conflict:
                conflicts.append(conflict)
            if server_id:
                mappings[item.local_id] = server_id
                count += 1

        return mappings, conflicts, count

    async def _process_project(
        self, item: SyncProjectItem
    ) -> tuple[SyncConflictInfo | None, int | None]:
        """Process a single project.

        Args:
            item: The project item to process

        Returns:
            Tuple of (conflict if any, server_id if created/updated)
        """
        if item.server_id:
            # Update existing
            result = await self.session.execute(
                select(Project).where(Project.id == item.server_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Check for conflict (last-write-wins)
                server_updated = existing.updated_at or datetime.min.replace(tzinfo=UTC)
                if server_updated.tzinfo is None:
                    server_updated = server_updated.replace(tzinfo=UTC)

                client_updated = item.updated_at
                if client_updated.tzinfo is None:
                    client_updated = client_updated.replace(tzinfo=UTC)

                if server_updated > client_updated:
                    # Server wins - don't update
                    return (
                        SyncConflictInfo(
                            entity_type=EntityType.PROJECT,
                            local_id=item.local_id,
                            server_id=item.server_id,
                            local_updated_at=client_updated,
                            server_updated_at=server_updated,
                            resolution=ConflictResolution.SERVER_WINS,
                        ),
                        item.server_id,
                    )

                # Client wins - update
                existing.name = item.name
                existing.description = item.description
                self.session.add(existing)
                return None, existing.id
        else:
            # Create new
            project = Project(
                name=item.name,
                description=item.description,
            )
            self.session.add(project)
            await self.session.flush()
            return None, project.id

        return None, None

    async def _process_skills(
        self, items: list[SyncSkillItem]
    ) -> tuple[dict[int, int], list[SyncConflictInfo], int]:
        """Process pushed skills.

        Args:
            items: List of skills to process

        Returns:
            Tuple of (local_id -> server_id mappings, conflicts, count synced)
        """
        mappings: dict[int, int] = {}
        conflicts: list[SyncConflictInfo] = []
        count = 0

        for item in items:
            conflict, server_id = await self._process_skill(item)
            if conflict:
                conflicts.append(conflict)
            if server_id:
                mappings[item.local_id] = server_id
                count += 1

        return mappings, conflicts, count

    async def _process_skill(
        self, item: SyncSkillItem
    ) -> tuple[SyncConflictInfo | None, int | None]:
        """Process a single skill.

        Args:
            item: The skill item to process

        Returns:
            Tuple of (conflict if any, server_id if created/updated)
        """
        if item.server_id:
            result = await self.session.execute(select(Skill).where(Skill.id == item.server_id))
            existing = result.scalar_one_or_none()

            if existing:
                server_updated = existing.updated_at or datetime.min.replace(tzinfo=UTC)
                if server_updated.tzinfo is None:
                    server_updated = server_updated.replace(tzinfo=UTC)

                client_updated = item.updated_at
                if client_updated.tzinfo is None:
                    client_updated = client_updated.replace(tzinfo=UTC)

                if server_updated > client_updated:
                    return (
                        SyncConflictInfo(
                            entity_type=EntityType.SKILL,
                            local_id=item.local_id,
                            server_id=item.server_id,
                            local_updated_at=client_updated,
                            server_updated_at=server_updated,
                            resolution=ConflictResolution.SERVER_WINS,
                        ),
                        item.server_id,
                    )

                existing.name = item.name
                existing.display_name = item.display_name
                existing.description = item.description
                existing.version = item.version
                existing.author = item.author
                self.session.add(existing)
                return None, existing.id
        else:
            # For new skills, we need a source_id
            if item.source_id is None:
                # Skip skills without a source
                return None, None

            skill = Skill(
                source_id=item.source_id,
                name=item.name,
                display_name=item.display_name,
                description=item.description,
                version=item.version,
                author=item.author,
            )
            self.session.add(skill)
            await self.session.flush()
            return None, skill.id

        return None, None

    async def _process_installed_skills(
        self, items: list[SyncInstalledSkillItem]
    ) -> tuple[dict[int, int], list[SyncConflictInfo], int]:
        """Process pushed installed skills.

        Args:
            items: List of installed skills to process

        Returns:
            Tuple of (local_id -> server_id mappings, conflicts, count synced)
        """
        mappings: dict[int, int] = {}
        conflicts: list[SyncConflictInfo] = []
        count = 0

        for item in items:
            conflict, server_id = await self._process_installed_skill(item)
            if conflict:
                conflicts.append(conflict)
            if server_id:
                mappings[item.local_id] = server_id
                count += 1

        return mappings, conflicts, count

    async def _process_installed_skill(
        self, item: SyncInstalledSkillItem
    ) -> tuple[SyncConflictInfo | None, int | None]:
        """Process a single installed skill.

        Args:
            item: The installed skill item to process

        Returns:
            Tuple of (conflict if any, server_id if created/updated)
        """
        if item.server_id:
            result = await self.session.execute(
                select(InstalledSkill).where(InstalledSkill.id == item.server_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                server_updated = existing.updated_at or datetime.min.replace(tzinfo=UTC)
                if server_updated.tzinfo is None:
                    server_updated = server_updated.replace(tzinfo=UTC)

                client_updated = item.updated_at
                if client_updated.tzinfo is None:
                    client_updated = client_updated.replace(tzinfo=UTC)

                if server_updated > client_updated:
                    return (
                        SyncConflictInfo(
                            entity_type=EntityType.INSTALLED_SKILL,
                            local_id=item.local_id,
                            server_id=item.server_id,
                            local_updated_at=client_updated,
                            server_updated_at=server_updated,
                            resolution=ConflictResolution.SERVER_WINS,
                        ),
                        item.server_id,
                    )

                existing.installed_path = item.installed_path
                existing.pinned_version = item.pinned_version
                self.session.add(existing)
                return None, existing.id
        else:
            # For new installed skills, we need skill_id and harness_id
            if item.skill_id is None or item.harness_id is None:
                return None, None

            # Import here to avoid circular imports
            from jefe.data.models.installed_skill import InstallScope as DbInstallScope

            installed = InstalledSkill(
                skill_id=item.skill_id,
                harness_id=item.harness_id,
                scope=DbInstallScope(item.scope),
                project_id=item.project_id,
                installed_path=item.installed_path,
                pinned_version=item.pinned_version,
            )
            self.session.add(installed)
            await self.session.flush()
            return None, installed.id

        return None, None

    async def _process_harness_configs(
        self, items: list[SyncHarnessConfigItem]
    ) -> tuple[dict[int, int], list[SyncConflictInfo], int]:
        """Process pushed harness configs.

        Args:
            items: List of harness configs to process

        Returns:
            Tuple of (local_id -> server_id mappings, conflicts, count synced)
        """
        mappings: dict[int, int] = {}
        conflicts: list[SyncConflictInfo] = []
        count = 0

        for item in items:
            conflict, server_id = await self._process_harness_config(item)
            if conflict:
                conflicts.append(conflict)
            if server_id:
                mappings[item.local_id] = server_id
                count += 1

        return mappings, conflicts, count

    async def _process_harness_config(
        self, item: SyncHarnessConfigItem
    ) -> tuple[SyncConflictInfo | None, int | None]:
        """Process a single harness config.

        Args:
            item: The harness config item to process

        Returns:
            Tuple of (conflict if any, server_id if created/updated)
        """
        if item.server_id:
            result = await self.session.execute(
                select(HarnessConfig).where(HarnessConfig.id == item.server_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                server_updated = existing.updated_at or datetime.min.replace(tzinfo=UTC)
                if server_updated.tzinfo is None:
                    server_updated = server_updated.replace(tzinfo=UTC)

                client_updated = item.updated_at
                if client_updated.tzinfo is None:
                    client_updated = client_updated.replace(tzinfo=UTC)

                if server_updated > client_updated:
                    return (
                        SyncConflictInfo(
                            entity_type=EntityType.HARNESS_CONFIG,
                            local_id=item.local_id,
                            server_id=item.server_id,
                            local_updated_at=client_updated,
                            server_updated_at=server_updated,
                            resolution=ConflictResolution.SERVER_WINS,
                        ),
                        item.server_id,
                    )

                existing.kind = item.kind
                existing.path = item.path
                existing.content = item.content
                existing.content_hash = item.content_hash
                self.session.add(existing)
                return None, existing.id
        else:
            # For new configs, we need harness_id
            if item.harness_id is None:
                return None, None

            # Import here to avoid circular imports
            from jefe.data.models.harness_config import ConfigScope as DbConfigScope

            config = HarnessConfig(
                harness_id=item.harness_id,
                scope=DbConfigScope(item.scope),
                kind=item.kind,
                path=item.path,
                content=item.content,
                content_hash=item.content_hash,
                project_id=item.project_id,
            )
            self.session.add(config)
            await self.session.flush()
            return None, config.id

        return None, None

    async def _get_changed_projects(
        self, since: datetime | None
    ) -> list[ServerProjectItem]:
        """Get projects changed since a timestamp.

        Args:
            since: Timestamp to get changes since (None = all)

        Returns:
            List of changed projects
        """
        stmt = select(Project)
        if since is not None:
            stmt = stmt.where(Project.updated_at > since)

        result = await self.session.execute(stmt)
        projects = result.scalars().all()

        return [
            ServerProjectItem(
                server_id=p.id,
                name=p.name,
                description=p.description,
                updated_at=p.updated_at or datetime.now(UTC),
            )
            for p in projects
        ]

    async def _get_changed_skills(
        self, since: datetime | None
    ) -> list[ServerSkillItem]:
        """Get skills changed since a timestamp.

        Args:
            since: Timestamp to get changes since (None = all)

        Returns:
            List of changed skills
        """
        stmt = select(Skill)
        if since is not None:
            stmt = stmt.where(Skill.updated_at > since)

        result = await self.session.execute(stmt)
        skills = result.scalars().all()

        items = []
        for s in skills:
            items.append(
                ServerSkillItem(
                    server_id=s.id,
                    source_id=s.source_id,
                    name=s.name,
                    display_name=s.display_name,
                    description=s.description,
                    version=s.version,
                    author=s.author,
                    tags=[],  # Tags are stored in a relationship, simplify for now
                    metadata={},  # Metadata is stored separately
                    updated_at=s.updated_at or datetime.now(UTC),
                )
            )
        return items

    async def _get_changed_installed_skills(
        self, since: datetime | None
    ) -> list[ServerInstalledSkillItem]:
        """Get installed skills changed since a timestamp.

        Args:
            since: Timestamp to get changes since (None = all)

        Returns:
            List of changed installed skills
        """
        stmt = select(InstalledSkill)
        if since is not None:
            stmt = stmt.where(InstalledSkill.updated_at > since)

        result = await self.session.execute(stmt)
        installed = result.scalars().all()

        return [
            ServerInstalledSkillItem(
                server_id=i.id,
                skill_id=i.skill_id,
                harness_id=i.harness_id,
                scope=i.scope.value,
                project_id=i.project_id,
                installed_path=i.installed_path,
                pinned_version=i.pinned_version,
                updated_at=i.updated_at or datetime.now(UTC),
            )
            for i in installed
        ]

    async def _get_changed_harness_configs(
        self, since: datetime | None
    ) -> list[ServerHarnessConfigItem]:
        """Get harness configs changed since a timestamp.

        Args:
            since: Timestamp to get changes since (None = all)

        Returns:
            List of changed harness configs
        """
        stmt = select(HarnessConfig)
        if since is not None:
            stmt = stmt.where(HarnessConfig.updated_at > since)

        result = await self.session.execute(stmt)
        configs = result.scalars().all()

        return [
            ServerHarnessConfigItem(
                server_id=c.id,
                harness_id=c.harness_id,
                scope=c.scope.value,
                kind=c.kind,
                path=c.path,
                content=c.content,
                content_hash=c.content_hash,
                project_id=c.project_id,
                updated_at=c.updated_at or datetime.now(UTC),
            )
            for c in configs
        ]
