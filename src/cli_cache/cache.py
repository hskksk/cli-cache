import hashlib
import json
import os
import time
from pathlib import Path

from cli_cache.crypto import _decrypt, _encrypt

_DEFAULT_CACHE_DIR = Path(os.environ.get("CLI_CACHE_DIR", Path.home() / ".cache" / "cli-cache"))


def _ensure_cache_dir(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.chmod(0o700)


def _command_cache_key(cmd_parts: list[str]) -> str:
    return hashlib.sha256(" ".join(cmd_parts).encode()).hexdigest()


def _cache_path(cache_key: str, cache_dir: Path) -> Path:
    return cache_dir / cache_key


def read_cache(cmd_parts: list[str], session_key: bytes, cache_dir: Path = _DEFAULT_CACHE_DIR) -> str | None:
    key = _command_cache_key(cmd_parts)
    path = _cache_path(key, cache_dir)
    if not path.exists():
        return None
    try:
        raw = _decrypt(path.read_bytes(), session_key)
        entry = json.loads(raw)
        if time.time() > entry["expires_at"]:
            path.unlink(missing_ok=True)
            return None
        return entry["value"]
    except Exception:
        return None


def write_cache(cmd_parts: list[str], value: str, session_key: bytes, ttl: int, cache_dir: Path = _DEFAULT_CACHE_DIR) -> None:
    _ensure_cache_dir(cache_dir)
    key = _command_cache_key(cmd_parts)
    entry = json.dumps({"value": value, "expires_at": time.time() + ttl}).encode()
    path = _cache_path(key, cache_dir)
    path.write_bytes(_encrypt(entry, session_key))
    path.chmod(0o600)


def delete_cache(cmd_parts: list[str], cache_dir: Path = _DEFAULT_CACHE_DIR) -> bool:
    key = _command_cache_key(cmd_parts)
    path = _cache_path(key, cache_dir)
    if path.exists():
        path.unlink()
        return True
    return False


def clear_all_cache(cache_dir: Path = _DEFAULT_CACHE_DIR) -> int:
    count = 0
    if cache_dir.exists():
        for f in cache_dir.iterdir():
            if f.name != ".session":
                f.unlink()
                count += 1
    return count
