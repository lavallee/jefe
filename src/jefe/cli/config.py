"""CLI configuration management with XDG-compliant storage."""

import json
from pathlib import Path
from typing import Any


def get_config_dir() -> Path:
    """Get XDG-compliant config directory for jefe.

    Returns:
        Path to ~/.config/jefe/
    """
    config_home = Path.home() / ".config"
    config_dir = config_home / "jefe"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    """Get path to config file.

    Returns:
        Path to ~/.config/jefe/config.json
    """
    return get_config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    """Load configuration from file.

    Returns:
        Dictionary of configuration values, or empty dict if file doesn't exist.
    """
    config_file = get_config_file()
    if not config_file.exists():
        return {}

    with config_file.open("r") as f:
        data: dict[str, Any] = json.load(f)
        return data


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to file.

    Args:
        config: Dictionary of configuration values to save.
    """
    config_file = get_config_file()
    with config_file.open("w") as f:
        json.dump(config, f, indent=2)


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a single configuration value.

    Args:
        key: Configuration key to retrieve.
        default: Default value if key doesn't exist.

    Returns:
        Configuration value or default.
    """
    config = load_config()
    return config.get(key, default)


def set_config_value(key: str, value: Any) -> None:
    """Set a single configuration value.

    Args:
        key: Configuration key to set.
        value: Value to store.
    """
    config = load_config()
    config[key] = value
    save_config(config)
