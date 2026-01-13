# Gemini CLI Configuration Research

Research conducted: 2026-01-13

## Overview

Google's Gemini CLI is an open-source AI agent that brings Gemini directly into the terminal. It's available as an npm package (`@google/gemini-cli`) and includes built-in tools for file operations, shell commands, web fetching, and Google Search grounding.

## Configuration File Locations

Gemini CLI uses a hierarchical configuration system with JSON files in multiple locations:

### 1. System Defaults File (Lowest Precedence)
- **macOS**: `/Library/Application Support/GeminiCli/system-defaults.json`
- **Linux**: `/etc/gemini-cli/system-defaults.json`
- **Windows**: `C:\ProgramData\gemini-cli\system-defaults.json`

### 2. User Settings (Medium Precedence)
- **Location**: `~/.gemini/settings.json`
- **Scope**: Applies to all sessions for the current user
- **Format**: JSON

### 3. Project Settings (Higher Precedence)
- **Location**: `.gemini/settings.json` (in project root)
- **Scope**: Project-specific overrides
- **Use Case**: Checked into version control for team-wide settings

### 4. System Settings (Highest Precedence)
- **macOS**: `/Library/Application Support/GeminiCli/settings.json`
- **Linux**: `/etc/gemini-cli/settings.json`
- **Windows**: `C:\ProgramData\gemini-cli\settings.json`
- **Scope**: Overrides all other settings files

## Configuration File Format

Settings use a **nested JSON structure** organized into top-level categories:

### Core Configuration Categories

```json
{
  "general": {},        // behavior preferences (vim mode, update settings)
  "output": {},         // text or JSON format selection
  "ui": {},             // theming, visibility toggles, accessibility
  "ide": {},            // IDE integration mode settings
  "privacy": {},        // usage statistics collection
  "model": {},          // model selection, session turn limits
  "modelConfigs": {},   // named presets and model configuration aliases
  "context": {},        // memory file discovery and filtering
  "tools": {},          // sandbox, shell, auto-approval, tool restrictions
  "mcp": {},            // Model-Context Protocol server connections
  "security": {},       // YOLO mode, authentication, env var redaction
  "advanced": {},       // DNS, memory configuration, excluded variables
  "experimental": {},   // preview features (agents, extensions, skills)
  "skills": {},         // disabled skills list
  "hooks": {},          // event handlers for tool/model/session lifecycle
  "admin": {},          // enterprise restrictions
  "mcpServers": {},     // custom MCP server definitions
  "telemetry": {}       // logging and metrics configuration
}
```

### Example User Settings File

```json
{
  "theme": "Default",
  "selectedAuthType": "oauth-personal"
}
```

### Environment Variable References

String values support dynamic resolution:
```json
{
  "key": "$VAR_NAME"
  // or
  "key": "${VAR_NAME}"
}
```

These are automatically expanded at load time.

## Custom Instructions (GEMINI.md)

Context files provide project-specific instructions to the model.

### Default Filename
- **Default**: `GEMINI.md`
- **Configurable via**: `context.fileName` (can be string or array)

### Hierarchical Loading

Context files are loaded from multiple locations and concatenated:

1. **Global Context**: `~/.gemini/GEMINI.md` (applies to all projects)
2. **Project Ancestry**: Files in current directory and parent directories up to project root (identified by `.git` folder)
3. **Subdirectories**: Files discovered in subdirectories below current working directory (limited to 200 directories by default)

### Content Features

- **Modular Imports**: Use `@path/to/file.md` syntax to reference other Markdown files
- **View Loaded Context**: Use `/memory show` command to inspect concatenated context
- **Refresh from Disk**: Use `/memory refresh` command
- **Status Display**: CLI footer shows count of loaded context files

### Initialization

Use `/init` command to generate a starting GEMINI.md file for your project.

## Skills & Custom Commands

### Skills Configuration

Skills are experimental features managed through settings:

```json
{
  "experimental": {
    "skills": true  // Enable Agent Skills (experimental)
  },
  "skills": {
    "disabled": ["skill-name-1", "skill-name-2"]  // Disable specific skills
  }
}
```

**Note**: Changes to skills require CLI restart.

### Custom Commands (Slash Commands)

Custom commands let you save and reuse prompts as personal shortcuts.

#### File Locations

1. **User commands (global)**: `~/.gemini/commands/`
   - Available in any project
2. **Project commands (local)**: `<project-root>/.gemini/commands/`
   - Project-specific, can be version controlled
   - Override identically-named global commands

#### File Format: TOML

Custom commands use `.toml` files with this structure:

```toml
# Required
prompt = """
Your prompt text here
"""

# Optional
description = "Brief one-line description for /help menu"
```

#### Naming Convention

File paths determine command names:
- `test.toml` → `/test`
- `git/commit.toml` → `/git:commit`

Path separators convert to colons in command names.

#### Argument Handling

**1. Context-Aware Injection with `{{args}}`**

```toml
prompt = """
Analyze this code: {{args}}
"""
```

- **Raw injection** (outside shell blocks): Arguments inserted exactly as typed
- **Shell injection** (inside `!{...}`): Arguments automatically shell-escaped for security

**2. Default Behavior (without `{{args}}`)**

If no `{{args}}` placeholder is present and arguments are provided, the CLI appends the full command to the prompt (separated by two newlines).

**3. Shell Command Execution with `!{...}`**

```toml
prompt = """
Analyze this git diff:
```diff
!{git diff --staged}
```
"""
```

Features:
- Executes shell commands and injects output
- Commands execute after confirmation prompt
- Balanced braces required within `!{...}` blocks
- If command fails, stderr and exit code are injected
- Arguments within shell blocks are automatically escaped

**4. File Content Injection with `@{...}`**

```toml
prompt = """
Review this file:
@{path/to/file.txt}
"""
```

Features:
- `@{path/to/file.txt}` → file contents
- `@{path/to/dir}` → directory listing (respects `.gitignore`/`.geminiignore`)
- Supports multimodal injection (images, PDFs, audio, video)
- Processed before shell commands and argument substitution

#### Complete Example

```toml
description = "Generates a commit message from staged changes"
prompt = """
Create a conventional commit message for:

```diff
!{git diff --staged}
```
"""
```

### Custom Tool Commands

For advanced tool integration:

```json
{
  "tools": {
    "discoveryCommand": "path/to/discovery-script",
    "callCommand": "path/to/call-script"
  }
}
```

Both accept custom executables that handle tool invocation through stdin/stdout JSON communication.

## MCP (Model-Context Protocol) Integration

The `mcpServers` section enables discovering and using custom tools by connecting to MCP servers:

```json
{
  "mcpServers": {
    "server-name": {
      "command": "node",
      "args": ["path/to/server.js"],
      "env": {
        "API_KEY": "$MY_API_KEY"
      }
    }
  }
}
```

Configurable parameters include:
- Commands and arguments
- URLs for remote servers
- Environment variables
- Tool filtering options

## Environment Files

The CLI automatically loads environment variables from `.env` files:

**Search Order**:
1. Current directory and parent directories
2. Stops at project root (identified by `.git` folder) or home directory
3. Falls back to `~/.env` if not found

## CLI Commands Reference

**Configuration-related commands**:
- `/init` - Generate starting GEMINI.md file
- `/memory show` - View concatenated context
- `/memory refresh` - Reload context from disk
- `/help` - View available commands

**Command-line flags**:
- `-m, --model` - Select model (default: "gemini-2.5-pro")
- `-p, --prompt` - Provide prompt directly
- `-s, --sandbox` - Run in sandbox
- `-y, --yolo` - Auto-approve all actions
- `-a, --all_files` - Include all files in context
- `-c, --checkpointing` - Enable file edit checkpointing
- `--telemetry` - Enable telemetry

## Implementation Notes

For Claude Code integration:

1. **Config Location**: User settings at `~/.gemini/settings.json`
2. **Project Context**: Use `.gemini/` directory for project-specific settings
3. **Custom Commands**: Store in `~/.gemini/commands/` (global) or `.gemini/commands/` (project)
4. **Skills Location**: Configured via `experimental.skills` and `skills.disabled` in settings.json
5. **File Format**: JSON for settings, TOML for custom commands, Markdown for context
6. **Environment Variables**: Supported in settings files using `$VAR` or `${VAR}` syntax

## Sources

- [Gemini CLI Configuration Documentation](https://github.com/google-gemini/gemini-cli/blob/main/docs/get-started/configuration.md)
- [Gemini CLI Configuration Reference](https://geminicli.com/docs/get-started/configuration/)
- [Custom Commands Documentation](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/custom-commands.md)
- [Custom Commands Guide](https://geminicli.com/docs/cli/custom-commands/)
- [Gemini CLI Tutorial: Custom Slash Commands](https://medium.com/google-cloud/gemini-cli-tutorial-series-part-7-custom-slash-commands-64c06195294b)
- [Gemini CLI Tutorial: Configuration Settings](https://medium.com/google-cloud/gemini-cli-tutorial-series-part-3-configuration-settings-via-settings-json-and-env-files-669c6ab6fd44)
- [Official Gemini CLI GitHub Repository](https://github.com/google-gemini/gemini-cli)
- [Gemini CLI Official Website](https://geminicli.com/)
- [Google Cloud Documentation: Gemini CLI](https://docs.cloud.google.com/gemini/docs/codeassist/gemini-cli)
