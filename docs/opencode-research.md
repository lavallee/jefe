# OpenCode Configuration Research

## Overview

OpenCode is an AI coding agent built for the terminal. This document details the configuration format, file locations, and structure based on official documentation and local installation inspection.

## Configuration File Formats

OpenCode accepts both **JSON** and **JSONC** (JSON with Comments) formats for all configuration files.

## Configuration Locations & Precedence

OpenCode implements a hierarchical configuration system where settings are **merged rather than replaced**. The precedence order (lowest to highest):

1. **Remote config** – From `.well-known/opencode` endpoint; serves organizational defaults
2. **Global config** – Located at `~/.config/opencode/opencode.json` for user-wide preferences
3. **Custom config** – Specified via `OPENCODE_CONFIG` environment variable
4. **Project config** – `opencode.json` in project root; highest precedence among standard files
5. **`.opencode` directories** – For agents, commands, and plugins
6. **Inline config** – `OPENCODE_CONFIG_CONTENT` env var for runtime overrides

### Alternative Config Locations

Additionally, OpenCode searches for:
- `$HOME/.opencode.json`
- `$XDG_CONFIG_HOME/opencode/.opencode.json`
- `./.opencode.json` (local directory)

### Merging Behavior

Non-conflicting settings from all configs are preserved. Later configs override only conflicting keys, allowing a project config to add settings without replacing global defaults entirely.

## Configuration Structure

The configuration file supports these main sections:

### Core Settings
- `data.directory` – Storage path for SQLite conversations and sessions
- `providers` – API keys for OpenAI, Anthropic, Copilot, Groq, etc.
- `agents` – Model assignments for coder, task, title roles
- `shell` – Path and arguments for shell execution
- `debug` – Debug flags
- `autoCompact` – Auto-compaction settings

### UI and Display
- `tui` – Scroll speed, diff style
- `themes` – Color schemes and appearance

### Server Configuration
- `server.port` – Port number (default varies)
- `server.hostname` – Hostname (default: "127.0.0.1")
- `server.mdns` – mDNS service discovery
- `server.cors` – CORS domain allowlist

### Tools and Permissions
- `tools` – Enable/disable specific tools
- `permission` – Access control for operations (allow/deny/ask)
- `formatters` – Code formatting settings

### External Integrations
- `mcpServers` – Model Context Protocol server configurations
- `lsp` – Language server protocol settings
- `plugins` – Plugin configurations

### Custom Extensions
- `instructions` – Custom rules and guidelines
- `commands` – Custom command definitions
- `keybinds` – Keyboard shortcuts

### Provider Configuration
- `provider.allowlist` – Limit allowed providers
- `provider.blocklist` – Block specific providers

## Configuration Variables

Configurations support substitution patterns:
- **Environment variables**: `{env:VARIABLE_NAME}`
- **File contents**: `{file:path/to/file}` (supports relative and absolute paths with `~` expansion)

## Directory Structure

### Global Directories
- `~/.config/opencode/` – Main configuration directory
- `~/.local/share/opencode/` – Data directory
  - `~/.local/share/opencode/auth.json` – Authentication credentials
  - `~/.local/share/opencode/bin/` – Binaries
  - `~/.local/share/opencode/log/` – Log files
  - `~/.local/share/opencode/storage/` – Session and data storage

### Project Directories
- `.opencode/` – Project-specific configuration root
- `.opencode/commands/` – Custom commands (markdown files)
- `.opencode/agent/` – Agent definitions (markdown files)
- `.opencode/skill/` – Skill definitions (SKILL.md files)

## Skills Configuration

### Skills Directory Structure

Skills are organized in dedicated folders, each containing a `SKILL.md` file. OpenCode searches four locations in order:

1. **Project-local**: `.opencode/skill/<name>/SKILL.md`
2. **Global config**: `~/.config/opencode/skill/<name>/SKILL.md`
3. **Claude-compatible project**: `.claude/skills/<name>/SKILL.md`
4. **Claude-compatible global**: `~/.claude/skills/<name>/SKILL.md`

### SKILL.md Format

Each `SKILL.md` file requires YAML frontmatter with these recognized fields:

```yaml
---
name: skill-name                    # Required: unique identifier
description: Purpose of the skill   # Required: 1-1,024 characters
license: MIT                        # Optional: licensing terms
compatibility: ">=1.0.0"            # Optional: version compatibility
metadata:                           # Optional: custom key-value pairs
  author: "name"
  version: "1.0.0"
---

Skill content and instructions go here.
```

### Skill Name Validation Rules

Valid skill names must:
- Contain 1–64 characters
- Use only lowercase alphanumeric characters and single hyphens as separators
- Not begin or end with hyphens
- Avoid consecutive hyphens
- Match their parent directory name
- Match regex pattern: `^[a-z0-9]+(-[a-z0-9]+)*$`

### Skills Discovery Mechanism

For project paths, OpenCode traverses upward from the current working directory until reaching the git worktree root, loading all matching skill files along the way. Global definitions load from the home directory configuration paths.

### Skills Permission Control

Skills are managed via pattern-based permissions in `opencode.json`:

```json
{
  "permission": {
    "skill": {
      "internal-*": "allow",      // Immediate access
      "experimental-*": "ask",    // User approval required
      "deprecated-*": "deny"      // Hidden from agents
    }
  }
}
```

Three permission levels:
- **allow**: Immediate access
- **deny**: Hidden from agents
- **ask**: User approval required

### Skills Tool Integration

Agents discover available skills through the native `skill` tool, which lists names and descriptions. Agents load skills by calling `skill({ name: "skill-name" })`.

## Agent Configuration

### Agent Directory Locations

Agents can be defined via markdown files in two locations:

- **Global**: `~/.config/opencode/agent/`
- **Per-project**: `.opencode/agent/`

### Agent File Structure

Markdown agent files use YAML frontmatter for configuration, followed by the agent's system prompt as the body content.

### Agent Naming Convention

The markdown file name becomes the agent name:
- `review.md` → `review` agent
- `specialized/coder.md` → `specialized/coder` agent
- Nested paths create namespaced agent names

### Agent Configuration Options

The frontmatter supports these key options:

```yaml
---
description: Agent purpose here    # Required: explains the agent's purpose
mode: subagent                     # Optional: subagent, primary, or all
model: provider/model-name         # Optional: override default model
temperature: 0.1                   # Optional: 0.0-1.0, control randomness
tools:                             # Optional: enable/disable capabilities
  write: false
  bash: false
  read: true
permission:                        # Optional: access controls
  edit: deny
  bash: ask
maxSteps: 10                       # Optional: limit agentic iterations
hidden: false                      # Optional: hide from autocomplete (subagents only)
---

Actual system prompt instructions go here.
The body contains the agent's system prompt.
```

### Available Agent Tools

Tools that can be enabled/disabled in agent configuration:
- `bash` – Execute shell commands
- `read` – Read files
- `write` – Write/create files
- `edit` – Edit existing files
- `list` – List directories
- `glob` – Pattern-based file search
- `grep` – Search file contents
- `webfetch` – Fetch web content
- `task` – Task management
- `todowrite` – Write todos
- `todoread` – Read todos

### Agent Modes

- `primary` – Top-level agents that users interact with directly
- `subagent` – Helper agents called by other agents
- `all` – Can function as both

### Built-in Agents

OpenCode includes these built-in agents:
- `build` (primary) – Build and compilation tasks
- `compaction` (primary) – Session compaction
- `explore` (subagent) – Codebase exploration
- `general` (subagent) – General-purpose tasks
- `plan` (primary) – Planning and design
- `summary` (primary) – Summarization
- `title` (primary) – Title generation

## Commands Configuration

### Commands Directory Structure

Custom commands are stored as markdown files:

- **User commands**: `$XDG_CONFIG_HOME/opencode/commands/` or `$HOME/.opencode/commands/`
- **Project commands**: `<PROJECT_DIR>/.opencode/commands/`

Commands are organized as Markdown files in subdirectories, with IDs prefixed as `user:` or `project:`.

### Named Arguments for Commands

Commands support placeholders like `$ISSUE_NUMBER` within command definitions for parameterized workflows.

## Environment Variables

### Core Variables
- `OPENCODE_CONFIG` – Path to custom config file
- `OPENCODE_CONFIG_DIR` – Custom configuration directory
- `OPENCODE_CONFIG_CONTENT` – Inline configuration (highest precedence)

### API Keys
- `ANTHROPIC_API_KEY` – Anthropic Claude API
- `OPENAI_API_KEY` – OpenAI API
- `GEMINI_API_KEY` – Google Gemini API
- `GITHUB_TOKEN` – GitHub integration
- `LOCAL_ENDPOINT` – Custom endpoint URL

### Feature Flags
- `OPENCODE_DISABLE_CLAUDE_CODE` – Prevents reading from `.claude` directories
- `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` – Disables loading `.claude/skills` subdirectories

## CLI Commands

### Agent Management
- `opencode agent list` – List all available agents
- `opencode agent create` – Create a new agent interactively
  - `--path <dir>` – Directory path for agent file
  - `--description <text>` – Agent purpose
  - `--mode <all|primary|subagent>` – Agent mode
  - `--tools <comma-separated>` – Enable specific tools
  - `--model <provider/model>` – Specify model

### Configuration Management
- `opencode auth` – Manage credentials
- `opencode models [provider]` – List available models

### Session Management
- `opencode session list` – Display all sessions (table or JSON format)
- `opencode export [sessionID]` – Export session as JSON
- `opencode import <file>` – Import session from JSON

### MCP Server Management
- `opencode mcp add` – Interactive MCP server setup
- `opencode mcp list` – Show MCP server connection status

### Server Commands
- `opencode serve` – Start headless server
- `opencode web` – Start web server
- `opencode attach <url>` – Attach to running server

### Other Commands
- `opencode [project]` – Start TUI (default)
- `opencode run [message..]` – Run with a message
- `opencode stats` – Show token usage and cost statistics
- `opencode upgrade [target]` – Upgrade to latest or specific version
- `opencode uninstall` – Uninstall and remove all files
- `opencode completion` – Generate shell completion script

## Schema Validation

Configuration can be validated against the official schema:
- Schema URL: `https://opencode.ai/config.json`

## Authentication

Authentication credentials are stored separately from configuration:
- Location: `~/.local/share/opencode/auth.json`
- Loaded from: credentials file + environment variables + `.env` files in projects

## Data Storage

OpenCode uses SQLite for persistent storage:
- Conversations and sessions stored in data directory (default: `.opencode`)
- Configurable via `data.directory` in config file

## References

### Official Documentation
- [CLI Documentation](https://opencode.ai/docs/cli/)
- [Configuration Guide](https://opencode.ai/docs/config/)
- [Skills Documentation](https://opencode.ai/docs/skills/)
- [Agents Documentation](https://opencode.ai/docs/agents/)
- [Commands Documentation](https://opencode.ai/docs/commands/)
- [Models Documentation](https://opencode.ai/docs/models/)
- [Introduction](https://opencode.ai/docs/)

### GitHub Repositories
- [opencode-ai/opencode](https://github.com/opencode-ai/opencode) – Primary repository
- [sst/opencode](https://github.com/sst/opencode) – Open source variant

### Community Resources
- [Setting Up OpenCode with Local Models](https://theaiops.substack.com/p/setting-up-opencode-with-local-models)
- [malhashemi/opencode-skills](https://github.com/malhashemi/opencode-skills) – Community skills collection
- [zenobi-us/opencode-skillful](https://github.com/zenobi-us/opencode-skillful) – Skills plugin for lazy loading

---

**Research Date**: 2026-01-13
**OpenCode Version Tested**: Installed locally via Homebrew at `/opt/homebrew/bin/opencode`
**Plugin Version**: @opencode-ai/plugin@1.0.220
