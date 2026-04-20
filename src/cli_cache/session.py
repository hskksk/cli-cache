import getpass
import json
import os
import secrets
import sys
import time
from pathlib import Path

from cli_cache.crypto import AES_KEY_BITS, SALT_BYTES, _derive_key, _decrypt, _encrypt

_DEFAULT_CACHE_DIR = Path(os.environ.get("CLI_CACHE_DIR", Path.home() / ".cache" / "cli-cache"))


def _session_file(cache_dir: Path) -> Path:
    return cache_dir / ".session"


def _ensure_cache_dir(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.chmod(0o700)


def _load_session(password: str, cache_dir: Path = _DEFAULT_CACHE_DIR) -> bytes | None:
    sf = _session_file(cache_dir)
    if not sf.exists():
        return None
    try:
        data = json.loads(sf.read_text())
        if time.time() > data["expires_at"]:
            sf.unlink(missing_ok=True)
            return None
        salt = bytes.fromhex(data["salt"])
        enc_key = _derive_key(password, salt)
        return _decrypt(bytes.fromhex(data["session_key_enc"]), enc_key)
    except Exception:
        return None


def _create_session(password: str, session_ttl: int, cache_dir: Path = _DEFAULT_CACHE_DIR) -> bytes:
    _ensure_cache_dir(cache_dir)
    session_key = secrets.token_bytes(AES_KEY_BITS // 8)
    salt = secrets.token_bytes(SALT_BYTES)
    enc_key = _derive_key(password, salt)
    data = {
        "salt": salt.hex(),
        "session_key_enc": _encrypt(session_key, enc_key).hex(),
        "expires_at": time.time() + session_ttl,
    }
    sf = _session_file(cache_dir)
    sf.write_text(json.dumps(data))
    sf.chmod(0o600)
    return session_key


def get_session_key(session_ttl: int, cache_dir: Path = _DEFAULT_CACHE_DIR) -> bytes:
    sf = _session_file(cache_dir)
    if sf.exists():
        password = getpass.getpass("Master password: ", stream=sys.stderr)
        session_key = _load_session(password, cache_dir)
        if session_key is not None:
            return session_key
        print("Session expired. Creating a new session.", file=sys.stderr)
    else:
        password = getpass.getpass("Master password (new session): ", stream=sys.stderr)

    session_key = _create_session(password, session_ttl, cache_dir)
    print(f"Session created (TTL: {session_ttl}s)", file=sys.stderr)
    return session_key


def expire_session(cache_dir: Path = _DEFAULT_CACHE_DIR) -> None:
    _session_file(cache_dir).unlink(missing_ok=True)
    print("Session destroyed.")


def show_session_status(cache_dir: Path = _DEFAULT_CACHE_DIR) -> None:
    sf = _session_file(cache_dir)
    if not sf.exists():
        print("No active session.")
        return
    try:
        data = json.loads(sf.read_text())
        remaining = data["expires_at"] - time.time()
        if remaining <= 0:
            print("Session has expired.")
        else:
            m, s = divmod(int(remaining), 60)
            print(f"Session remaining: {m}m{s:02d}s")
    except Exception:
        print("Failed to read session file.", file=sys.stderr)
