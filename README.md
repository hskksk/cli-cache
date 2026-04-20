# cli-cache

Wrap any CLI command and cache its stdout output to an encrypted local file.

Useful when a command (e.g. a secrets manager CLI) is slow and its output needs to be reused multiple times within a session.

## Installation

```bash
pip install git+https://github.com/hskksk/cli-cache.git
```

## Usage

```
cli-cache [OPTIONS] -- <command> [args...]
```

The `--` separator strictly delimits cli-cache's own options from the wrapped command.

```bash
# Basic usage — prompts for a master password on first run
cli-cache -- secret-tool get my-api-key

# Custom cache TTL (5 minutes)
cli-cache --ttl 300 -- secret-tool get my-api-key

# Custom session TTL (30 minutes)
cli-cache --ttl 300 --session-ttl 1800 -- secret-tool get my-api-key

# Delete cache for a specific command
cli-cache --clear -- secret-tool get my-api-key

# Delete all cache entries
cli-cache --clear-all

# Check remaining session time
cli-cache --session-status

# Manually expire the session
cli-cache --session-expire
```

## Options

| Option | Default | Description |
|---|---|---|
| `--ttl SEC` | 3600 | Cache entry TTL in seconds |
| `--session-ttl SEC` | 3600 | Session validity duration in seconds |
| `--clear` | — | Delete cache for the specified command, then exit |
| `--clear-all` | — | Delete all cache entries, then exit |
| `--session-expire` | — | Destroy the current session, then exit |
| `--session-status` | — | Print remaining session time, then exit |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CLI_CACHE_DIR` | `~/.cache/cli-cache` | Override the cache and session directory |

## How It Works

On the first run (or after session expiry), cli-cache prompts for a master password to create a new session. Subsequent invocations within the session TTL require no password — the session key is read directly from `~/.cache/cli-cache/.session` (chmod 600).

Cache files are stored as AES-256-GCM encrypted blobs under `~/.cache/cli-cache/`, keyed by SHA-256 of the full command string.

```
~/.cache/cli-cache/    (chmod 700)
├── .session           (chmod 600)  Session file
└── <sha256hex>        (chmod 600)  One file per cached command
```

## Security

- Cache files are encrypted with AES-256-GCM using a per-session key
- The session key is stored in `~/.cache/cli-cache/.session` (chmod 600)
- Master password is only required when creating a new session
- Expired sessions invalidate all existing cache entries (new session = new key)

## Development

```bash
# Install with dev dependencies
uv sync

# Run tests
uv run pytest
```
