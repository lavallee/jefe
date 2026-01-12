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
python -c "import jefe; print(jefe.__version__)"

# Run tests
pytest

# Type checking
mypy src/jefe

# Linting
ruff check src/jefe
```

## Project Structure

```
station-chief/
├── src/jefe/
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
pytest --cov=src/jefe
```

### Type Checking

```bash
mypy src/jefe
```

### Code Quality

```bash
# Linting
ruff check src/jefe

# Formatting
black src/jefe
ruff check --fix src/jefe

# Organize imports
isort src/jefe
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please ensure:
- All tests pass: `pytest`
- Type checking passes: `mypy src/jefe`
- Code is formatted: `ruff format . && black .`
