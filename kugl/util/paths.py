import os
from pathlib import Path

import funcy as fn
import yaml

from .age import Age
from .debug import debugging
from .misc import fail
from ..util import clock as clock


class KPath(type(Path())):
    """It would be nice if Path were smarter, so do that."""

    def is_world_writeable(self) -> bool:
        return self.stat().st_mode & 0o2 == 0o2

    def parse_json(self):
        return json.loads(self.read_text())

    def parse_yaml(self):
        return yaml.safe_load(self.read_text())

    def set_age(self, age: Age):
        time = clock.CLOCK.now() - age.value
        os.utime(str(self), times=(time, time))


class ConfigPath(KPath):
    """Same as a KPath but adds debug statements"""

    def parse_json(self):
        if debug := debugging("config"):
            debug(f"loading {self}")
        return super().parse_json()

    def parse_yaml(self):
        if debug := debugging("config"):
            debug(f"loading {self}")
        return super().parse_yaml()


def kugl_home() -> KPath:
    # KUGL_HOME override is for unit tests, not for users (as least for now)
    if "KUGL_HOME" in os.environ:
        return KPath(os.environ["KUGL_HOME"])
    return KPath.home() / ".kugl"


def kube_home() -> KPath:
    # KUGL_HOME override is for unit tests, not for users (as least for now)
    if "KUGL_HOME" in os.environ:
        return KPath(os.environ["KUGL_HOME"]) / ".kube"
    return KPath.home() / ".kube"


@fn.memoize
def kube_context() -> str:
    """Return the current kubernetes context."""
    kube_config = kube_home() / "config"
    if not kube_config.exists():
        fail(f"Missing {kube_config}, can't determine current context")
    current_context = (yaml.safe_load(kube_config.read_text()) or {}).get("current-context")
    if not current_context:
        fail("No current context, please run kubectl config use-context ...")
    return current_context
