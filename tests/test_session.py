import json
import time
from unittest.mock import patch

import pytest

from cli_cache.session import (
    _create_session,
    _read_session_key,
    check_session,
    expire_session,
    get_session_key,
    show_session_status,
)


def test_create_session_returns_key(tmp_path):
    session_key = _create_session(session_ttl=3600, cache_dir=tmp_path)
    assert len(session_key) == 32


def test_read_session_key_after_create(tmp_path):
    session_key = _create_session(session_ttl=3600, cache_dir=tmp_path)
    loaded = _read_session_key(cache_dir=tmp_path)
    assert loaded == session_key


def test_read_session_key_no_file(tmp_path):
    assert _read_session_key(cache_dir=tmp_path) is None


def test_read_session_key_expired(tmp_path):
    _create_session(session_ttl=-1, cache_dir=tmp_path)
    assert _read_session_key(cache_dir=tmp_path) is None


def test_get_session_key_no_password_when_valid(tmp_path):
    _create_session(session_ttl=3600, cache_dir=tmp_path)
    with patch("getpass.getpass") as mock_getpass:
        key = get_session_key(session_ttl=3600, cache_dir=tmp_path)
        mock_getpass.assert_not_called()
    assert len(key) == 32


def test_get_session_key_prompts_when_no_session(tmp_path):
    with patch("getpass.getpass", return_value="password") as mock_getpass:
        key = get_session_key(session_ttl=3600, cache_dir=tmp_path)
        mock_getpass.assert_called_once()
    assert len(key) == 32


def test_get_session_key_prompts_when_expired(tmp_path):
    _create_session(session_ttl=-1, cache_dir=tmp_path)
    with patch("getpass.getpass", return_value="password") as mock_getpass:
        key = get_session_key(session_ttl=3600, cache_dir=tmp_path)
        mock_getpass.assert_called_once()
    assert len(key) == 32


def test_expire_session(tmp_path, capsys):
    _create_session(session_ttl=3600, cache_dir=tmp_path)
    expire_session(cache_dir=tmp_path)
    assert not (tmp_path / ".session").exists()
    assert "Session destroyed" in capsys.readouterr().out


def test_show_session_status_active(tmp_path, capsys):
    _create_session(session_ttl=3600, cache_dir=tmp_path)
    show_session_status(cache_dir=tmp_path)
    assert "remaining" in capsys.readouterr().out


def test_show_session_status_no_session(tmp_path, capsys):
    show_session_status(cache_dir=tmp_path)
    assert "No active session" in capsys.readouterr().out


def test_check_session_valid(tmp_path):
    _create_session(session_ttl=3600, cache_dir=tmp_path)
    assert check_session(cache_dir=tmp_path) is True


def test_check_session_no_session(tmp_path):
    assert check_session(cache_dir=tmp_path) is False


def test_check_session_expired(tmp_path):
    _create_session(session_ttl=-1, cache_dir=tmp_path)
    assert check_session(cache_dir=tmp_path) is False


def test_show_session_status_expired(tmp_path, capsys):
    sf = tmp_path / ".session"
    sf.write_text(json.dumps({"session_key": "aa" * 32, "expires_at": time.time() - 1}))
    show_session_status(cache_dir=tmp_path)
    assert "expired" in capsys.readouterr().out
