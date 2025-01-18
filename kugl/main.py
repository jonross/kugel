"""
Command-line entry point.
"""
import argparse
import os
from argparse import ArgumentParser
import sys
from sqlite3 import DatabaseError
from types import SimpleNamespace
from typing import List, Union

from kugl.impl.registry import Registry
from kugl.impl.engine import Engine, CHECK, NEVER_UPDATE, ALWAYS_UPDATE, CacheFlag
from kugl.impl.config import UserInit, parse_file, Settings
from kugl.util import Age, fail, debug_features, kugl_home, kube_home, ConfigPath, debugging, KuglError, kube_context, Query

# Register built-ins immediately because they're needed for command-line parsing
import kugl.builtins.resources
import kugl.builtins.schemas.kubernetes


def main() -> None:
    main1(sys.argv[1:])


def main1(argv: List[str]):

    if "KUGL_UNIT_TESTING" in os.environ and "KUGL_MOCKDIR" not in os.environ:
        # Never enter main in tests unless test_home fixture is in use, else we could read
        # the user's init file.
        sys.exit("Unit test state error")

    try:
        return main2(argv)
    except KuglError as e:
        # These are raised by fail(), we only want the error message.
        severe, exc = False, e
    except DatabaseError as e:
        # DB errors are common when writing queries, don't make them look like a crash.
        severe, exc = False, e
    except Exception as e:
        severe, exc = True, e
    if severe or debugging() or "KUGL_UNIT_TESTING" in os.environ:
        raise exc
    print(exc, file=sys.stderr)
    sys.exit(1)


def main2(argv: List[str]):

    kugl_home().mkdir(exist_ok=True)
    if not argv:
        fail("Missing sql query")

    # Load init file.
    init_file = ConfigPath(kugl_home() / "init.yaml")
    init, errors = parse_file(UserInit, init_file)
    if errors:
        fail("\n".join(errors))

    ap = ArgumentParser()
    Registry.get().augment_cli(ap)
    args, cache_flag = parse_args(argv, ap, init.settings)

    if args.schema:
        print(Registry.get().printable_schema(args.sql))
        return

    # Check for shortcut and reparse, because they can contain command-line options.
    if " " not in args.sql:
        if not (new_argv := init.shortcuts.get(argv[-1])):
            fail(f"No shortcut named '{argv[-1]}' is defined in ~/.kugl/init.yaml")
        return main1(argv[:-1] + new_argv)

    if args.debug:
        debug_features(args.debug.split(","))
    if debug := debugging("init"):
        debug(f"settings: {init.settings}")

    engine = Engine(args, cache_flag, init.settings)
    print(engine.query_and_format(Query(args.sql)))


def parse_args(argv: list[str], ap: ArgumentParser, settings: Settings) -> tuple[argparse.Namespace, CacheFlag]:
    """Add stock arguments to parser, parse the command line, and override settings."""
    ap.add_argument("-D", "--debug", type=str)
    ap.add_argument("-c", "--cache", default=False, action="store_true")
    ap.add_argument("-r", "--reckless", default=False, action="store_true")
    ap.add_argument("--schema", default=False, action="store_true")
    ap.add_argument("-t", "--timeout", type=str)
    ap.add_argument("-u", "--update", default=False, action="store_true")
    ap.add_argument("sql")
    args = ap.parse_args(argv)
    if args.cache and args.update:
        fail("Cannot use both -c/--cache and -u/--update")
    if args.timeout:
        settings.cache_timeout = Age(args.timeout)
    if args.reckless:
        settings.reckless = True
    return args, (ALWAYS_UPDATE if args.update else NEVER_UPDATE if args.cache else CHECK)


if __name__ == "__main__":
    main()