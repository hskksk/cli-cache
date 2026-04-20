# cli-cache Design Document

## Overview

`cli-cache` is a Python CLI tool that wraps arbitrary shell commands and caches their stdout output to encrypted local files. It is designed for use cases where a command (e.g. a secrets manager CLI) is slow to execute and the output needs to be reused multiple times within a session.

The tool is distributed as a Python package installable via `pip`, and exposes a single `cli-cache` entry point command.

---

## User-Facing Interface

### Syntax

```
cli-cache [OPTIONS] -- <command> [args...]
```

The `--` separator strictly delimits cli-cache's own options from the wrapped command and its arguments. Everything after `--` is treated as the command to execute and cache.

### Subcommand-less Design

There are no subcommands. All operations are controlled by flags passed before `--`.

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--ttl SEC` | int | 3600 | Cache entry TTL in seconds |
| `--session-ttl SEC` | int | 3600 | Session validity duration in seconds |
| `--clear` | flag | - | Delete cache for the specified command, then exit (requires `--`) |
| `--clear-all` | flag | - | Delete all cache entries (session file preserved), then exit |
| `--session-expire` | flag | - | Manually destroy the current session, then exit |
| `--session-status` | flag | - | Print remaining session time, then exit |

### Usage Examples

```bash
# Basic usage (prompts for master password on first run)
cli-cache -- secret-tool get my-api-key

# With custom TTL (5 minutes)
cli-cache --ttl 300 -- secret-tool get my-api-key

# With custom TTL and session TTL (30 minutes session)
cli-cache --ttl 300 --session-ttl 1800 -- secret-tool get my-api-key

# Delete cache for a specific command
cli-cache --clear -- secret-tool get my-api-key

# Delete all cache entries
cli-cache --clear-all

# Check session status
cli-cache --session-status

# Manually expire the session
cli-cache --session-expire
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CLI_CACHE_DIR` | `~/.cache/cli-cache` | Override cache and session directory |

---

## File Layout

```
~/.cache/cli-cache/            (chmod 700)
├── .session                   (chmod 600)  Session file
└── <sha256hex>                (chmod 600)  One file per cached command
```

All files are stored in a single flat directory. There are no subdirectories.

---

## Security Model

### Session

The session provides a short-lived in-memory equivalent for the master password. The user enters the master password once per session; subsequent invocations within the TTL do not require a password prompt.

**Session file format** (`~/.cache/cli-cache/.session`, JSON):

```json
{
  "salt": "<16 bytes, hex-encoded>",
  "session_key_enc": "<nonce(12B) + ciphertext, hex-encoded>",
  "expires_at": 1234567890.0
}
```

- `salt`: Random 16-byte salt used for PBKDF2 key derivation
- `session_key_enc`: A randomly generated 32-byte session key, encrypted with the master-password-derived key using AES-256-GCM
- `expires_at`: Unix timestamp (float) after which the session is considered expired

**Session lifecycle:**

1. On invocation, if `.session` exists, the user is prompted for the master password
2. PBKDF2 derives a key from the password + stored salt; AES-GCM decrypts the session key
3. If decryption succeeds and `expires_at` is in the future → session is valid, session key is used
4. If decryption fails or `expires_at` is past → session is expired; user is prompted again and a new session is created
5. If `.session` does not exist → first run; user is prompted with a "new session" message and a session is created

Note: wrong password causes AES-GCM authentication tag failure, which Python's `cryptography` library raises as an exception. This is caught and treated as an invalid session (same as expiry).

### Cache Entries

**Cache file format** (binary):

```
[nonce: 12 bytes][ciphertext: variable]
```

The ciphertext decrypts (AES-256-GCM with the session key) to a UTF-8 JSON payload:

```json
{
  "value": "<captured stdout of the wrapped command>",
  "expires_at": 1234567890.0
}
```

**Cache key:** `SHA-256(command_string)` where `command_string = " ".join(cmd_parts)` for the full command including all arguments. This ensures identical commands always hit the same cache entry and any change (different flag, different argument) produces a different key.

### Cryptographic Parameters

| Parameter | Value | Rationale |
|---|---|---|
| KDF | PBKDF2-HMAC-SHA256 | Standard, widely supported |
| KDF iterations | 480,000 | OWASP 2024 recommendation for PBKDF2-SHA256 |
| Key size | 256 bits | AES-256 |
| Salt size | 16 bytes (128 bits) | Sufficient for PBKDF2 |
| AEAD cipher | AES-256-GCM | Authenticated encryption; detects tampering |
| Nonce size | 12 bytes | GCM standard nonce size |
| Nonce generation | `secrets.token_bytes(12)` | Cryptographically secure random |

**Dependency:** `cryptography` (PyPI) — only external dependency.

---

## Argument Parsing

The `--` separator is handled manually before invoking `argparse`:

```python
def split_args(argv: list[str]) -> tuple[list[str], list[str]]:
    try:
        sep = argv.index("--")
        return argv[:sep], argv[sep + 1:]
    except ValueError:
        return argv, []
```

`argparse` only sees the portion before `--`. The portion after `--` is stored as `cmd_parts: list[str]`. This avoids any conflict between cli-cache options and the wrapped command's options.

---

## Execution Flow

### Normal Cache Flow

```
cli-cache [opts] -- <cmd>
         │
         ▼
   split_args(sys.argv[1:])
         │
         ├─ our_argv → argparse
         └─ cmd_parts → list[str]
                │
                ▼
         get_session_key(session_ttl)
                │
         ┌──────┴──────┐
    .session exists?  No → prompt "new session"
         │                → create_session() → return session_key
        Yes
         │
         ▼
    prompt password
    → load_session(password)
         │
    ┌────┴────┐
  valid?     No → prompt again → create_session()
    │
    ▼
  session_key
         │
         ▼
   read_cache(cmd_parts, session_key)
         │
    ┌────┴────┐
  hit?       No
    │         │
    ▼         ▼
  print    run_command(cmd_parts)
  stdout        │
           write_cache(...)
                │
           print stdout
```

### --clear Flow

```
cli-cache --clear -- <cmd>
  → delete_cache(cmd_parts)  # no password required
  → print result
  → exit
```

Note: `--clear` does not require a session or password, since it only removes a file by its SHA-256-derived filename.

### --clear-all Flow

```
cli-cache --clear-all
  → iterate CACHE_DIR, unlink all files except .session
  → print count
  → exit
```

### --session-expire / --session-status

No command (`--`) required. Operate directly on the `.session` file.

---

## Wrapped Command Execution

```python
result = subprocess.run(cmd_parts, capture_output=True, text=True)
if result.returncode != 0:
    sys.stderr.write(result.stderr)
    sys.exit(result.returncode)
return result.stdout
```

- `capture_output=True`: stdout is captured for caching; stderr is not captured
- On non-zero exit: stderr is forwarded to the caller's stderr and the process exits with the same return code
- The cached value is the **raw stdout string** (including trailing newline, if any)
- On cache hit: `sys.stdout.write(value)` (not `print`) to preserve the original output exactly

---

## Package Structure

```
cli-cache/
├── pyproject.toml
├── README.md
├── src/
│   └── cli_cache/
│       ├── __init__.py
│       ├── __main__.py       # python -m cli_cache support
│       ├── cli.py            # argument parsing, entry point (main())
│       ├── session.py        # session create/load/expire/status
│       ├── cache.py          # read/write/delete/clear cache entries
│       ├── crypto.py         # _derive_key, _encrypt, _decrypt
│       └── runner.py         # run_command()
└── tests/
    ├── test_crypto.py
    ├── test_cache.py
    ├── test_session.py
    └── test_cli.py
```

### `pyproject.toml` Requirements

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cli-cache"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["cryptography"]

[project.scripts]
cli-cache = "cli_cache.cli:main"
```

- Entry point: `cli_cache.cli:main`
- `python -m cli_cache` should also work (via `__main__.py` calling `main()`)
- Minimum Python version: 3.12 (uses `match` statement)

---

## Module Responsibilities

### `crypto.py`

Pure functions, no I/O, no state.

```python
def _derive_key(password: str, salt: bytes) -> bytes: ...
def _encrypt(plaintext: bytes, key: bytes) -> bytes: ...
def _decrypt(blob: bytes, key: bytes) -> bytes: ...
```

### `session.py`

Reads/writes `~/.cache/cli-cache/.session`. Handles password prompting via `getpass`.

```python
def get_session_key(session_ttl: int) -> bytes: ...
def expire_session() -> None: ...
def show_session_status() -> None: ...
# internal:
def _load_session(password: str) -> bytes | None: ...
def _create_session(password: str, session_ttl: int) -> bytes: ...
```

### `cache.py`

Reads/writes encrypted cache files under `CACHE_DIR`.

```python
def read_cache(cmd_parts: list[str], session_key: bytes) -> str | None: ...
def write_cache(cmd_parts: list[str], value: str, session_key: bytes, ttl: int) -> None: ...
def delete_cache(cmd_parts: list[str]) -> bool: ...
def clear_all_cache() -> int: ...
# internal:
def _command_cache_key(cmd_parts: list[str]) -> str: ...  # SHA-256
def _cache_path(cache_key: str) -> Path: ...
def _ensure_cache_dir() -> None: ...
```

### `runner.py`

```python
def run_command(cmd_parts: list[str]) -> str: ...
```

### `cli.py`

```python
def split_args(argv: list[str]) -> tuple[list[str], list[str]]: ...
def build_parser() -> argparse.ArgumentParser: ...
def main() -> None: ...
```

---

## Error Handling

| Situation | Behavior |
|---|---|
| Wrong master password | AES-GCM raises exception → treated as expired session → prompt again and create new session |
| Wrapped command exits non-zero | Forward stderr to caller's stderr, exit with same return code |
| Cache file corrupted / unreadable | Treat as cache miss, proceed to run command |
| `.session` file corrupted | Treat as no session, prompt for new session |
| `--clear` on non-existent cache | Print "not found" message, exit 0 |
| `--` missing when required | `argparse.error()` with usage hint |

---

## Testing Notes

- `crypto.py` is fully unit-testable with no filesystem dependency
- `session.py` and `cache.py` should accept an injectable `cache_dir: Path` parameter (or use a module-level variable that tests can override) to enable testing under `tmp_path`
- `getpass.getpass` should be patchable (inject via parameter or mock) for session tests
- `runner.py` should be testable by mocking `subprocess.run`
- Integration test: full round-trip with `cli-cache -- echo hello` verifying cache hit on second invocation
