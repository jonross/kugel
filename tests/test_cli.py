"""
Tests for command-line options.
"""

import sqlite3

import pytest

from kugl.main import main1
from kugl.util import KuglError, features_debugged


def test_enforce_one_cache_option(test_home):
    with pytest.raises(KuglError, match="Cannot use both -c/--cache and -u/--update"):
        main1(["-c", "-u", "select 1"])


def test_enforce_one_namespace_option(test_home):
    with pytest.raises(KuglError, match="Cannot use both -a/--all-namespaces and -n/--namespace"):
        main1(["-a", "-n", "x", "select * from pods"])


def test_no_such_table(test_home):
    with pytest.raises(sqlite3.OperationalError, match="no such table: foo"):
        main1(["select * from foo"])


def test_unknown_shortcut(test_home):
    with pytest.raises(KuglError, match="No shortcut named 'foo'"):
        main1(["foo"])


def test_missing_query(test_home):
    with pytest.raises(KuglError, match="Missing sql query"):
        main1([])


def test_shortcut_with_invalid_option(test_home, capsys):
    test_home.joinpath("init.yaml").write_text("""
        shortcuts:
          foo:
          - --badoption
          - "select * from pods"
    """)
    with pytest.raises(SystemExit):
        main1(["-a", "foo"])
    assert "unrecognized arguments: --badoption" in capsys.readouterr().err


def test_unknown_option(test_home, capsys):
    with pytest.raises(SystemExit):
        main1(["--badoption", "select 1"])
    assert "unrecognized arguments: --badoption" in capsys.readouterr().err


def test_enforce_one_cache_option_via_shortcut(test_home, capsys):
    test_home.joinpath("init.yaml").write_text("""
        shortcuts:
          foo:
          - -u
          - "select 1"
    """)
    with pytest.raises(KuglError, match="Cannot use both -c/--cache and -u/--update"):
        main1(["-c", "foo"])


def test_simple_shortcut(test_home, capsys):
    test_home.joinpath("init.yaml").write_text("""
        shortcuts:
          foo: ["select 1, 2"]
    """)
    main1(["foo"])
    out, _ = capsys.readouterr()
    assert out == "  1    2\n" * 2


@pytest.mark.skip  # FIXME re-enable without return_config hack
def test_cli_args_override_settings(test_home, capsys):
    with features_debugged("init"):
        init, _ = main1(["select 1"], return_config=True)
    assert init.settings.cache_timeout == Age(120)
    assert init.settings.reckless == False
    out, err = capsys.readouterr()
    with features_debugged("init"):
        init, _ = main1(["-t 5", "-r", "select 1"], return_config=True)
    assert init.settings.cache_timeout == Age(5)
    assert init.settings.reckless == True

