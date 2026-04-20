import json
import time
from unittest.mock import patch

import pytest

from cli_cache.session import (
    _create_session,
    _load_session,
    expire_session,
    show_session_status,
)


def test_create_and_load_session(tmp_path):
    session_key = _create_session("password", session_ttl=3600, cache_dir=tmp_path)
    assert len(session_key) == 32

    loaded = _load_session("password", cache_dir=tmp_path)
    assert loaded == session_key


def test_load_session_wrong_password(tmp_path):
    _create_session("password", session_ttl=3600, cache_dir=tmp_path)
    loaded = _load_session("wrong", cache_dir=tmp_path)
    assert loaded is None


def test_load_session_expired(tmp_path):
    _create_session("password", session_ttl=-1, cache_dir=tmp_path)
    loaded = _load_session("password", cache_dir=tmp_path)
    assert loaded is None


def test_load_session_no_file(tmp_path):
    loaded = _load_session("password", cache_dir=tmp_path)
    assert loaded is None


def test_expire_session(tmp_path, capsys):
    _create_session("password", session_ttl=3600, cache_dir=tmp_path)
    expire_session(cache_dir=tmp_path)
    assert not (tmp_path / ".session").exists()
    out = capsys.readouterr().out
    assert "Session destroyed" in out


def test_show_session_status_active(tmp_path, capsys):
    _create_session("password", session_ttl=3600, cache_dir=tmp_path)
    show_session_status(cache_dir=tmp_path)
    out = capsys.readouterr().out
    assert "remaining" in out


def test_show_session_status_no_session(tmp_path, capsys):
    show_session_status(cache_dir=tmp_path)
    out = capsys.readouterr().out
    assert "No active session" in out


def test_show_session_status_expired(tmp_path, capsys):
    sf = tmp_path / ".session"
    sf.write_text(json.dumps({"expires_at": time.time() - 1}))
    show_session_status(cache_dir=tmp_path)
    out = capsys.readouterr().out
    assert "expired" in out
