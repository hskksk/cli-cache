import time

import pytest

from cli_cache.cache import (
    _command_cache_key,
    check_cache,
    clear_all_cache,
    delete_cache,
    read_cache,
    write_cache,
)
from cli_cache.crypto import _derive_key


@pytest.fixture
def session_key():
    return _derive_key("testpassword", b"s" * 16)


def test_cache_key_deterministic():
    assert _command_cache_key(["echo", "hello"]) == _command_cache_key(["echo", "hello"])


def test_cache_key_differs_on_different_commands():
    assert _command_cache_key(["echo", "hello"]) != _command_cache_key(["echo", "world"])


def test_write_and_read_cache(tmp_path, session_key):
    cmd = ["echo", "hello"]
    write_cache(cmd, "hello\n", session_key, expires_at=time.time() + 3600, cache_dir=tmp_path)
    result = read_cache(cmd, session_key, cache_dir=tmp_path)
    assert result == "hello\n"


def test_read_cache_miss(tmp_path, session_key):
    result = read_cache(["nonexistent"], session_key, cache_dir=tmp_path)
    assert result is None


def test_read_cache_expired(tmp_path, session_key):
    cmd = ["echo", "hello"]
    write_cache(cmd, "hello\n", session_key, expires_at=time.time() - 1, cache_dir=tmp_path)
    result = read_cache(cmd, session_key, cache_dir=tmp_path)
    assert result is None


def test_read_cache_wrong_key(tmp_path, session_key):
    cmd = ["echo", "hello"]
    write_cache(cmd, "hello\n", session_key, expires_at=time.time() + 3600, cache_dir=tmp_path)
    wrong_key = _derive_key("wrong", b"s" * 16)
    result = read_cache(cmd, wrong_key, cache_dir=tmp_path)
    assert result is None


def test_delete_cache(tmp_path, session_key):
    cmd = ["echo", "hello"]
    write_cache(cmd, "hello\n", session_key, expires_at=time.time() + 3600, cache_dir=tmp_path)
    assert delete_cache(cmd, cache_dir=tmp_path) is True
    assert read_cache(cmd, session_key, cache_dir=tmp_path) is None


def test_delete_cache_not_found(tmp_path):
    assert delete_cache(["no", "such", "cmd"], cache_dir=tmp_path) is False


def test_check_cache_hit(tmp_path, session_key):
    cmd = ["echo", "hello"]
    write_cache(cmd, "hello\n", session_key, expires_at=time.time() + 3600, cache_dir=tmp_path)
    assert check_cache(cmd, session_key, cache_dir=tmp_path) is True


def test_check_cache_miss(tmp_path, session_key):
    assert check_cache(["nonexistent"], session_key, cache_dir=tmp_path) is False


def test_check_cache_expired(tmp_path, session_key):
    cmd = ["echo", "hello"]
    write_cache(cmd, "hello\n", session_key, expires_at=time.time() - 1, cache_dir=tmp_path)
    assert check_cache(cmd, session_key, cache_dir=tmp_path) is False


def test_check_cache_wrong_key(tmp_path, session_key):
    cmd = ["echo", "hello"]
    write_cache(cmd, "hello\n", session_key, expires_at=time.time() + 3600, cache_dir=tmp_path)
    wrong_key = _derive_key("wrong", b"s" * 16)
    assert check_cache(cmd, wrong_key, cache_dir=tmp_path) is False


def test_clear_all_cache(tmp_path, session_key):
    write_cache(["cmd1"], "out1", session_key, expires_at=time.time() + 3600, cache_dir=tmp_path)
    write_cache(["cmd2"], "out2", session_key, expires_at=time.time() + 3600, cache_dir=tmp_path)
    session_file = tmp_path / ".session"
    session_file.write_text("{}")
    count = clear_all_cache(cache_dir=tmp_path)
    assert count == 2
    assert session_file.exists()
