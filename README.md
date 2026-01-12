# Station Chief

A comprehensive Git repository management system with web and CLI interfaces.

[![CI](https://github.com/yourusername/station-chief/workflows/CI/badge.svg)](https://github.com/yourusername/station-chief/actions/workflows/ci.yml)

## Features

- **Web Interface**: Modern web-based UI for repository management
- **CLI Tool**: Command-line interface for automation and scripting
- **Server API**: RESTful API for programmatic access
- **Repository Adapters**: Integration with various Git hosting platforms
- **Data Management**: Robust data persistence and querying

## Quick Start

### Prerequisites

- Python 3.11 or higher
- `uv` package manager (recommended) or `pip`

### Installation

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e ".[dev]"
```

### Verification

```bash
# Test import
python -c "import station_chief; print(station_chief.__version__)"

# Run tests
pytest

# Type checking
mypy src/station_chief

# Linting
ruff check src/station_chief
```

## Project Structure

```
station-chief/
├── src/station_chief/
│   ├── server/          # API and server components
│   ├── cli/             # Command-line interface
│   ├── web/             # Web interface components
│   ├── adapters/        # Integration adapters
│   └── data/            # Data models and database
├── tests/               # Test suite
├── pyproject.toml       # Project configuration
└── README.md            # This file
```

## Development

### Running Tests

```bash
pytest

# With coverage
pytest --cov=src/station_chief
```

### Type Checking

```bash
mypy src/station_chief
```

### Code Quality

```bash
# Linting
ruff check src/station_chief

# Formatting
black src/station_chief
ruff check --fix src/station_chief

# Organize imports
isort src/station_chief
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please ensure:
- All tests pass: `pytest`
- Type checking passes: `mypy src/station_chief`
- Code is formatted: `ruff format . && black .`
