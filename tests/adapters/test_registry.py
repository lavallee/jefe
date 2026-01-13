"""Tests for adapter registry."""

from pathlib import Path

from jefe.adapters import registry
from jefe.adapters.base import ConfigScope, DiscoveredConfig, HarnessAdapter


class DummyAdapter(HarnessAdapter):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def display_name(self) -> str:
        return "Dummy"

    def discover_global(self) -> list[DiscoveredConfig]:
        return []

    def discover_project(
        self,
        _project_path: Path,
        _project_id: int | None = None,
        _project_name: str | None = None,
    ) -> list[DiscoveredConfig]:
        return []

    def parse_config(self, _path: Path) -> dict[str, object] | str:
        return {}

    def get_skills_path(self, _scope: ConfigScope, project_path: Path | None = None) -> Path:
        return project_path or Path(".")

    def install_skill(
        self, skill: Path, _scope: ConfigScope, _project_path: Path | None = None
    ) -> Path:
        return Path("installed") / skill.name

    def uninstall_skill(self, _installed_path: Path) -> bool:
        return True


def test_registry_register_and_list(monkeypatch) -> None:
    monkeypatch.setattr(registry, "_ADAPTERS", {})

    adapter = DummyAdapter()
    registry.register_adapter(adapter)

    adapters = registry.list_adapters()
    assert adapters == [adapter]
    assert registry.get_adapter("dummy") is adapter
    assert registry.get_adapter("missing") is None
