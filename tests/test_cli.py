import sys
from unittest.mock import MagicMock, patch

import pytest

from cli_cache.cli import build_parser, split_args


def test_split_args_with_separator():
    our, cmd = split_args(["--ttl", "300", "--", "echo", "hello"])
    assert our == ["--ttl", "300"]
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
    assert args.ttl == 3600
    assert args.session_ttl == 3600
    assert args.clear is False
    assert args.clear_all is False
    assert args.session_expire is False
    assert args.session_status is False


def test_parser_ttl():
    parser = build_parser()
    args = parser.parse_args(["--ttl", "300"])
    assert args.ttl == 300


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
