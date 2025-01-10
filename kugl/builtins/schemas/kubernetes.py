"""
Built-in table definitions for Kubernetes.

NOTE: This is not a good example of how to write user-defined tables.
FIXME: Remove references to non-API imports.
FIXME: Don't use ArgumentParser in the API.
"""
import json
import os
from argparse import ArgumentParser
from threading import Thread

from ..helpers import Limits, ItemHelper, PodHelper, JobHelper
from kugl.api import table, fail, resource, run, parse_utc, Resource
from kugl.util import WHITESPACE, kube_context


@resource("kubernetes", schema_defaults=["kubernetes"])
class KubernetesResource(Resource):

    namespaced: bool = True
    _all_ns: bool
    _ns: str

    @classmethod
    def add_cli_options(cls, ap: ArgumentParser):
        ap.add_argument("-a", "--all-namespaces", default=False, action="store_true")
        ap.add_argument("-n", "--namespace", type=str)

    def handle_cli_options(self, args):
        if args.all_namespaces and args.namespace:
            fail("Cannot use both -a/--all-namespaces and -n/--namespace")
        if args.all_namespaces:
            # FIXME: engine.py and testing.py still use this
            self._ns = "__all"
            self._all_ns = True
        else:
            self._ns = args.namespace or "default"
            self._all_ns = False

    def cache_path(self) -> str:
        return f"{kube_context()}/{self._ns}.{self.name}.json"

    def get_objects(self) -> dict:
        """Fetch resources from Kubernetes using kubectl.

        :return: JSON as output by "kubectl get {self.name} -o json"
        """
        unit_testing = "KUGL_UNIT_TESTING" in os.environ
        namespace_flag = ["--all-namespaces"] if self._all_ns else ["-n", self._ns]
        if self.name == "pods":
            pod_statuses = {}
            # Kick off a thread to get pod statuses
            def _fetch():
                _, output, _ = run(["kubectl", "get", "pods", *namespace_flag])
                pod_statuses.update(self._pod_status_from_pod_list(output))
            status_thread = Thread(target=_fetch, daemon=True)
            status_thread.start()
            # In unit tests, wait for pod status here so the log order is deterministic.
            if unit_testing:
                status_thread.join()
        if self.namespaced:
            _, output, _ = run(["kubectl", "get", self.name, *namespace_flag, "-o", "json"])
        else:
            _, output, _ = run(["kubectl", "get", self.name, "-o", "json"])
        data = json.loads(output)
        if self.name == "pods":
            # Add pod status to pods
            if not unit_testing:
                status_thread.join()
            def pod_with_updated_status(pod):
                metadata = pod["metadata"]
                status = pod_statuses.get(f"{metadata['namespace']}/{metadata['name']}")
                if status:
                    pod["kubectl_status"] = status
                    return pod
                return None
            data["items"] = list(filter(None, map(pod_with_updated_status, data["items"])))
        return data

    def _pod_status_from_pod_list(self, output) -> dict[str, str]:
        """
        Convert the tabular output of 'kubectl get pods' to JSON.
        :return: a dict mapping "namespace/name" to status
        """
        rows = [WHITESPACE.split(line.strip()) for line in output.strip().split("\n")]
        if len(rows) < 2:
            return {}
        header, rows = rows[0], rows[1:]
        name_index = header.index("NAME")
        status_index = header.index("STATUS")
        # It would be nice if 'kubectl get pods' printed the UID, but it doesn't, so use
        # "namespace/name" as the key.  (Can't use a tuple since this has to be JSON-dumped.)
        if self._all_ns:
            namespace_index = header.index("NAMESPACE")
            return {f"{row[namespace_index]}/{row[name_index]}": row[status_index] for row in rows}
        else:
            return {f"{self._ns}/{row[name_index]}": row[status_index] for row in rows}


@table(schema="kubernetes", name="nodes", resource="nodes")
class NodesTable:

    @property
    def ddl(self):
        return """
            name TEXT,
            uid TEXT,
            cpu_alloc REAL,
            gpu_alloc REAL,
            mem_alloc INTEGER,
            cpu_cap REAL,
            gpu_cap REAL,
            mem_cap INTEGER
        """

    def make_rows(self, context) -> list[tuple[dict, tuple]]:
        for item in context.data["items"]:
            node = ItemHelper(item)
            yield item, (
                node.name,
                node.metadata.get("uid"),
                *Limits.extract(node["status"]["allocatable"], debug=context.debug).as_tuple(),
                *Limits.extract(node["status"]["capacity"], debug=context.debug).as_tuple(),
            )


@table(schema="kubernetes", name="pods", resource="pods")
class PodsTable:

    @property
    def ddl(self):
        return """
            name TEXT,
            uid TEXT,
            is_daemon INTEGER,
            namespace TEXT,
            node_name TEXT,
            creation_ts INTEGER,
            command TEXT,
            phase TEXT,
            status TEXT,
            cpu_req REAL,
            gpu_req REAL,
            mem_req INTEGER,
            cpu_lim REAL,
            gpu_lim REAL,
            mem_lim INTEGER
        """

    def make_rows(self, context) -> list[tuple[dict, tuple]]:
        for item in context.data["items"]:
            pod = PodHelper(item)
            yield item, (
                pod.name,
                pod.metadata.get("uid"),
                1 if pod.is_daemon else 0,
                pod.namespace,
                pod["spec"].get("nodeName"),
                parse_utc(pod.metadata["creationTimestamp"]),
                pod.command,
                pod["status"]["phase"],
                pod["kubectl_status"],
                *pod.resources("requests", debug=context.debug).as_tuple(),
                *pod.resources("limits", debug=context.debug).as_tuple(),
            )


@table(schema="kubernetes", name="jobs", resource="jobs")
class JobsTable:

    @property
    def ddl(self):
        return """
            name TEXT,
            uid TEXT,
            namespace TEXT,
            status TEXT,
            cpu_req REAL,
            gpu_req REAL,
            mem_req INTEGER,
            cpu_lim REAL,
            gpu_lim REAL,
            mem_lim INTEGER
        """

    def make_rows(self, context) -> list[tuple[dict, tuple]]:
        for item in context.data["items"]:
            job = JobHelper(item)
            yield item, (
                job.name,
                job.metadata.get("uid"),
                job.namespace,
                job.status,
                *job.resources("requests", debug=context.debug).as_tuple(),
                *job.resources("limits", debug=context.debug).as_tuple(),
            )


class LabelsTable:
    """Base class for all built-in label tables; subclasses need only define UID_FIELD."""

    @property
    def ddl(self):
        return f"""
            {self.UID_FIELD} TEXT,
            key TEXT,
            value TEXT
        """

    def make_rows(self, context) -> list[tuple[dict, tuple]]:
        for item in context.data["items"]:
            thing = ItemHelper(item)
            for key, value in thing.labels.items():
                yield item, (thing.metadata.get("uid"), key, value)


@table(schema="kubernetes", name="node_labels", resource="nodes")
class NodeLabelsTable(LabelsTable):
    UID_FIELD = "node_uid"


@table(schema="kubernetes", name="pod_labels", resource="pods")
class PodLabelsTable(LabelsTable):
    UID_FIELD = "pod_uid"


@table(schema="kubernetes", name="job_labels", resource="jobs")
class JobLabelsTable(LabelsTable):
    UID_FIELD = "job_uid"