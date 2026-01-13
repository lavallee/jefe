"""Tests for adapter auto-registration system."""

from __future__ import annotations

import importlib
from pathlib import Path

from jefe.adapters import get_adapter, get_adapters
from jefe.adapters.registry import _ADAPTERS, list_adapters, register_adapter


class TestAdapterAutoDiscovery:
    """Test automatic adapter discovery and registration."""

    def test_auto_discovery_registers_all_adapters(self) -> None:
        """Auto-discovery should find and register all adapter modules."""
        adapters = get_adapters()

        # Should have all 4 adapters: claude-code, codex_cli, gemini_cli, opencode
        assert len(adapters) >= 4, f"Expected at least 4 adapters, got {len(adapters)}"

        adapter_names = {a.name for a in adapters}
        expected_names = {"claude-code", "codex_cli", "gemini_cli", "opencode"}
        assert expected_names.issubset(adapter_names), (
            f"Missing adapters: {expected_names - adapter_names}"
        )

    def test_get_adapter_by_name(self) -> None:
        """Should be able to retrieve adapters by name."""
        adapter = get_adapter("claude-code")
        assert adapter is not None
        assert adapter.name == "claude-code"
        assert adapter.display_name == "Claude Code"

    def test_get_nonexistent_adapter(self) -> None:
        """Should return None for nonexistent adapters."""
        adapter = get_adapter("nonexistent-adapter")
        assert adapter is None

    def test_list_adapters_returns_all(self) -> None:
        """list_adapters should return all registered adapters."""
        adapters = list_adapters()
        assert len(adapters) >= 4
        assert all(hasattr(a, "name") for a in adapters)
        assert all(hasattr(a, "display_name") for a in adapters)

    def test_adapters_have_required_properties(self) -> None:
        """All adapters should have required properties."""
        for adapter in get_adapters():
            assert hasattr(adapter, "name")
            assert hasattr(adapter, "display_name")
            assert hasattr(adapter, "version")
            assert isinstance(adapter.name, str)
            assert isinstance(adapter.display_name, str)
            assert isinstance(adapter.version, str)

    def test_adapters_have_required_methods(self) -> None:
        """All adapters should implement required methods."""
        required_methods = [
            "discover_global",
            "discover_project",
            "parse_config",
            "get_skills_path",
            "install_skill",
            "uninstall_skill",
        ]

        for adapter in get_adapters():
            for method_name in required_methods:
                assert hasattr(adapter, method_name), (
                    f"Adapter {adapter.name} missing method {method_name}"
                )
                assert callable(getattr(adapter, method_name))

    def test_adapter_names_are_unique(self) -> None:
        """Each adapter should have a unique name."""
        adapters = get_adapters()
        names = [a.name for a in adapters]
        assert len(names) == len(set(names)), "Duplicate adapter names found"

    def test_specific_adapters_registered(self) -> None:
        """Test that each specific adapter is registered correctly."""
        # Claude Code
        claude = get_adapter("claude-code")
        assert claude is not None
        assert claude.display_name == "Claude Code"

        # Codex CLI
        codex = get_adapter("codex_cli")
        assert codex is not None
        assert codex.display_name == "Codex CLI"

        # Gemini CLI
        gemini = get_adapter("gemini_cli")
        assert gemini is not None
        assert gemini.display_name == "Gemini CLI"

        # OpenCode
        opencode = get_adapter("opencode")
        assert opencode is not None
        assert opencode.display_name == "OpenCode"


class TestManualRegistration:
    """Test manual adapter registration functionality."""

    def test_register_adapter_manually(self) -> None:
        """Should be able to manually register an adapter."""
        from jefe.adapters.base import HarnessAdapter

        class TestAdapter(HarnessAdapter):
            @property
            def name(self) -> str:
                return "test-adapter"

            @property
            def display_name(self) -> str:
                return "Test Adapter"

            def discover_global(self) -> list:
                return []

            def discover_project(self, _project_path: Path, **_kwargs) -> list:
                return []

            def parse_config(self, _path: Path) -> dict | str:
                return {}

            def get_skills_path(self, _scope, _project_path=None) -> Path:
                return Path.home() / ".test"

            def install_skill(self, skill: Path, _scope, _project_path=None) -> Path:
                return Path.home() / ".test" / skill.name

            def uninstall_skill(self, _installed_path: Path) -> bool:
                return True

        test_adapter = TestAdapter()
        register_adapter(test_adapter)

        # Should be able to retrieve it
        retrieved = get_adapter("test-adapter")
        assert retrieved is not None
        assert retrieved.name == "test-adapter"

    def test_registry_state_preserved(self) -> None:
        """Registry state should be preserved between calls."""
        adapters_first = get_adapters()
        adapters_second = get_adapters()

        # Should return the same adapters
        assert len(adapters_first) == len(adapters_second)
        names_first = {a.name for a in adapters_first}
        names_second = {a.name for a in adapters_second}
        assert names_first == names_second


class TestAdapterDiscovery:
    """Test the discovery mechanism itself."""

    def test_auto_discovery_only_runs_once(self) -> None:
        """Auto-discovery should only run once and cache results."""
        from jefe.adapters.registry import _AUTO_DISCOVERED

        # First call triggers discovery
        get_adapters()
        assert _AUTO_DISCOVERED is True

        # Subsequent calls should use cached results
        initial_count = len(_ADAPTERS)
        get_adapters()
        assert len(_ADAPTERS) == initial_count

    def test_adapter_modules_exist(self) -> None:
        """All adapter modules should exist and be importable."""
        adapter_modules = [
            "jefe.adapters.claude_code",
            "jefe.adapters.codex_cli",
            "jefe.adapters.gemini_cli",
            "jefe.adapters.opencode",
        ]

        for module_name in adapter_modules:
            # Should be able to import without error
            module = importlib.import_module(module_name)
            assert module is not None
