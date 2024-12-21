"""
Assorted utility functions / classes with no obvious home.
"""
import os
import re
import subprocess as sp
import sys
from pathlib import Path
from typing import Optional, Union

import arrow

WHITESPACE = re.compile(r"\s+")
DEBUG_FLAGS = {}


def run(args: Union[str, list[str]], error_ok=False):
    """
    Invoke an external command, which may be a list or a string; in the latter case it will be
    interpreted using bash -c.  Returns exit status, stdout and stderr.
    """
    if isinstance(args, str):
        args = ["bash", "-c", args]
    p = sp.run(args, stdout=sp.PIPE, stderr=sp.PIPE, encoding="utf-8")
    if p.returncode != 0 and not error_ok:
        print(f"Failed to run [{' '.join(args)}]:", file=sys.stderr)
        print(p.stderr, file=sys.stderr, end="")
        sys.exit(p.returncode)
    return p.returncode, p.stdout, p.stderr


def parse_utc(utc_str: str) -> int:
    return arrow.get(utc_str).int_timestamp


def to_utc(epoch: int) -> str:
    return arrow.get(epoch).to('utc').format('YYYY-MM-DDTHH:mm:ss') + 'Z'


def warn(message: str):
    print(message, file=sys.stderr)


def fail(message: str, e: Optional[Exception] = None):
    if e is not None:
        raise KugelError(message) from e
    raise KugelError(message)


class KugelError(Exception):
    pass


def debug(features: list[str], on: bool = True):
    """Turn debugging on or off for a set of features.

    :param features: list of feature names, parsed from the --debug command line option;
        "all" means everything.
    """
    for feature in features:
        if feature == "all" and not on:
            DEBUG_FLAGS.clear()
        else:
            DEBUG_FLAGS[feature] = on


def debugging(feature: str = None) -> bool:
    """Check if a feature is being debugged."""
    if feature is None:
        return len(DEBUG_FLAGS) > 0
    return DEBUG_FLAGS.get(feature) or DEBUG_FLAGS.get("all")


def dprint(feature, *args, **kwargs):
    """Print a debug message if the given feature is being debugged."""
    if debugging(feature):
        print(*args, **kwargs)


class KPath(type(Path())):
    """It would be nice if Path were smarter, so do that."""

    def is_world_writeable(self) -> bool:
        return self.stat().st_mode & 0o2 == 0o2


def kugel_home() -> KPath:
    if "KUGEL_HOME" in os.environ:
        return KPath(os.environ["KUGEL_HOME"])
    return KPath.home() / ".kugel"


def kube_home() -> KPath:
    if "KUGEL_HOME" in os.environ:
        return KPath(os.environ["KUGEL_HOME"]) / ".kube"
    return KPath.home() / ".kube"


def set_parent(item: dict, parent: dict):
    item["__parent"] = parent


def parent(item: dict):
    parent = item.get("__parent")
    if parent is None:
        warn("Item parent is missing")
    return parent
