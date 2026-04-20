import argparse
import sys

from cli_cache.cache import clear_all_cache, delete_cache, read_cache, write_cache
from cli_cache.runner import run_command
from cli_cache.session import check_session, expire_session, get_session_key, show_session_status

DEFAULT_SESSION_TTL = 3600


def split_args(argv: list[str]) -> tuple[list[str], list[str]]:
    try:
        sep = argv.index("--")
        return argv[:sep], argv[sep + 1:]
    except ValueError:
        return argv, []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli-cache",
        description="Wrap any CLI command and cache its stdout output with encryption.",
        epilog="Example: cli-cache --session-ttl 1800 -- secret-tool get my-key",
    )
    parser.add_argument("--session-ttl", type=int, default=DEFAULT_SESSION_TTL, metavar="SEC",
                        help=f"Session (and cache) TTL in seconds (default: {DEFAULT_SESSION_TTL})")
    parser.add_argument("--clear", action="store_true",
                        help="Delete cache for the specified command, then exit (requires --)")
    parser.add_argument("--clear-all", action="store_true",
                        help="Delete all cache entries, then exit")
    parser.add_argument("--session-expire", action="store_true",
                        help="Destroy the current session, then exit")
    parser.add_argument("--session-status", action="store_true",
                        help="Print remaining session time, then exit")
    parser.add_argument("--session-check", action="store_true",
                        help="Exit 0 if session is valid, exit 1 if expired or missing (no output)")
    return parser


def main() -> None:
    our_argv, cmd_parts = split_args(sys.argv[1:])
    parser = build_parser()
    args = parser.parse_args(our_argv)

    if args.session_expire:
        expire_session()
        return

    if args.session_check:
        sys.exit(0 if check_session() else 1)

    if args.session_status:
        show_session_status()
        return

    if args.clear_all:
        n = clear_all_cache()
        print(f"Deleted {n} cache entries.")
        return

    if not cmd_parts:
        parser.error("Specify the command after --.\nExample: cli-cache -- secret-tool get my-key")

    if args.clear:
        if delete_cache(cmd_parts):
            print(f"Cache deleted: {' '.join(cmd_parts)}")
        else:
            print(f"Cache not found: {' '.join(cmd_parts)}")
        return

    session_key, session_expires_at = get_session_key(args.session_ttl)

    cached = read_cache(cmd_parts, session_key)
    if cached is not None:
        sys.stdout.write(cached)
        return

    print(f"[cache miss] running: {' '.join(cmd_parts)}", file=sys.stderr)
    value = run_command(cmd_parts)
    write_cache(cmd_parts, value, session_key, session_expires_at)
    sys.stdout.write(value)
