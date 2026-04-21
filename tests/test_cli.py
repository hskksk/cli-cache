import sys
from unittest.mock import MagicMock, patch

import pytest

from cli_cache.cli import build_parser, split_args


def test_split_args_with_separator():
    our, cmd = split_args(["--session-ttl", "300", "--", "echo", "hello"])
    assert our == ["--session-ttl", "300"]
    assert cmd == ["echo", "hello"]


def test_split_args_without_separator():
    our, cmd = split_args(["--session-status"])
    assert our == ["--session-status"]
    assert cmd == []


def test_split_args_empty():
    our, cmd = split_args([])
    assert our == []
    assert cmd == []


def test_parser_defaults():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.session_ttl == 3600
    assert args.clear is False
    assert args.clear_all is False
    assert args.session_expire is False
    assert args.session_status is False


def test_parser_session_ttl():
    parser = build_parser()
    args = parser.parse_args(["--session-ttl", "300"])
    assert args.session_ttl == 300


def test_integration_cache_check_miss():
    """--cache-check exits 1 when session is valid but no cache exists."""
    from cli_cache.cli import main

    dummy_key = b"\x00" * 32
    with (
        patch("cli_cache.cli.check_session", return_value=True),
        patch("cli_cache.cli.get_session_key", return_value=(dummy_key, 9999999999.0)),
        patch("cli_cache.cli.check_cache", return_value=False),
        patch("sys.argv", ["cli-cache", "--cache-check", "--", "echo", "hello"]),
    ):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1


def test_integration_cache_check_hit():
    """--cache-check exits 0 when a valid cache entry exists."""
    from cli_cache.cli import main

    dummy_key = b"\x00" * 32
    with (
        patch("cli_cache.cli.check_session", return_value=True),
        patch("cli_cache.cli.get_session_key", return_value=(dummy_key, 9999999999.0)),
        patch("cli_cache.cli.check_cache", return_value=True),
        patch("sys.argv", ["cli-cache", "--cache-check", "--", "echo", "hello"]),
    ):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0


def test_integration_cache_check_no_session():
    """--cache-check exits 2 when no valid session exists."""
    from cli_cache.cli import main

    with (
        patch("cli_cache.cli.check_session", return_value=False),
        patch("sys.argv", ["cli-cache", "--cache-check", "--", "echo", "hello"]),
    ):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2


def test_integration_cache_hit(tmp_path):
    """Full round-trip: first call misses (runs command), second call hits cache."""
    from cli_cache.cli import main

    with (
        patch("cli_cache.session._DEFAULT_CACHE_DIR", tmp_path),
        patch("cli_cache.cache._DEFAULT_CACHE_DIR", tmp_path),
        patch("getpass.getpass", return_value="testpass"),
        patch("sys.argv", ["cli-cache", "--", "echo", "hello"]),
    ):
        out_lines = []
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.write = lambda s: out_lines.append(s)
            main()  # cache miss — runs echo
        assert "hello" in "".join(out_lines)

        out_lines2 = []
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.write = lambda s: out_lines2.append(s)
            main()  # cache hit
        assert "hello" in "".join(out_lines2)
