"""
Tests for the nodes and taints tables.
"""

from kugl.util import features_debugged, kugl_home, fail
from .testing import make_node, kubectl_response, assert_query, Taint, assert_by_line


def test_node_query(test_home):
    kugl_home().prep().joinpath("kubernetes.yaml").write_text("""
        extend:
          - table: nodes
            columns:
              - name: instance_type
                label:
                  - node.kubernetes.io/instance-type
                  - beta.kubernetes.io/instance-type
            
    """)
    kubectl_response("nodes", {
        "items": [
            make_node("node-1", labels={"node.kubernetes.io/instance-type": "a40"}),
            make_node("node-2", labels={"beta.kubernetes.io/instance-type": "a40"}),
        ]
    })
    assert_query("SELECT * FROM nodes ORDER BY name", """
        name    uid           cpu_alloc    gpu_alloc     mem_alloc    cpu_cap    gpu_cap       mem_cap  instance_type
        node-1  uid-node-1           93            4  807771639808         96          4  810023981056  a40
        node-2  uid-node-2           93            4  807771639808         96          4  810023981056  a40
    """)


def test_taint_query(test_home, capsys):
    kubectl_response("nodes", {
        "items": [
            make_node("node-1"),
            make_node("node-2", taints=[Taint(key="node.kubernetes.io/unschedulable", effect="NoSchedule"),
                                        Taint(key="node.kubernetes.io/unreachable", effect="NoExecute")
                                        ]),
            make_node("node-3", taints=[Taint(key="mycompany.com/priority", effect="NoSchedule", value="true")
                                        ]),
        ]
    })
    with features_debugged("itemize"):
        assert_query("""
            SELECT n.name, nt.key, nt.effect
            FROM nodes n join node_taints nt on nt.node_uid = n.uid
            ORDER BY 1, 2
        """, """
            name    key                               effect
            node-2  node.kubernetes.io/unreachable    NoExecute
            node-2  node.kubernetes.io/unschedulable  NoSchedule
            node-3  mycompany.com/priority            NoSchedule
        """)
        out, err = capsys.readouterr()
        assert_by_line(err, """
            itemize: begin itemization with [{"items": [{"apiVersion": "v1", "kind": "Node", "metadata": {"creationTimestamp": "2023-03-01T23:04...
            itemize: pass 1, row_source selector = items
            itemize: add {"apiVersion": "v1", "kind": "Node", "metadata": {"creationTimestamp": "2023-03-01T23:04:15Z", "labe...
            itemize: add {"apiVersion": "v1", "kind": "Node", "metadata": {"creationTimestamp": "2023-03-01T23:04:15Z", "labe...
            itemize: add {"apiVersion": "v1", "kind": "Node", "metadata": {"creationTimestamp": "2023-03-01T23:04:15Z", "labe...
            itemize: pass 2, row_source selector = spec.taints
            itemize: add {"key": "node.kubernetes.io/unschedulable", "effect": "NoSchedule"}
            itemize: add {"key": "node.kubernetes.io/unreachable", "effect": "NoExecute"}
            itemize: add {"key": "mycompany.com/priority", "effect": "NoSchedule", "value": "true"}
        """)


def test_node_labels(test_home):
    kubectl_response("nodes", {
        "items": [
            make_node("node-1", labels=dict(foo="bar")),
            make_node("node-2", labels=dict(a="b", c="d", e="f")),
            make_node("node-3", labels=dict()),
            make_node("node-4", labels=dict(one="two", three="four")),
        ]
    })
    assert_query("SELECT node_uid, key, value FROM node_labels ORDER BY 2, 1", """
        node_uid    key    value
        uid-node-2  a      b
        uid-node-2  c      d
        uid-node-2  e      f
        uid-node-1  foo    bar
        uid-node-4  one    two
        uid-node-4  three  four
    """)
