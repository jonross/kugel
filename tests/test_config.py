"""
Tests for user configuration file content.
"""

from kugel.model.config import Settings, UserConfig, parse_model, ExtendTable, CreateTable, Config, UserInit

import yaml

from kugel.model import Age


def test_settings_defaults():
    s = Settings()
    assert s.cache_timeout == Age(120)
    assert s.reckless == False


def test_settings_custom():
    s = Settings(cache_timeout=Age(5), reckless=True)
    assert s.cache_timeout == Age(5)
    assert s.reckless == True


def test_empty_config():
    c = UserConfig()
    assert c.extend == []
    assert c.create == []


def test_empty_init():
    c = UserInit()
    assert c.settings.cache_timeout == Age(120)
    assert c.settings.reckless == False
    assert c.alias == {}


def test_config_with_table_extension():
    c, e = parse_model(UserConfig, yaml.safe_load("""
        extend:
        - table: pods
          columns:
          - name: foo
            path: metadata.name
          - name: bar
            type: integer
            path: metadata.creationTimestamp
    """))
    assert e is None
    c = Config.collate(UserInit(), c)
    columns = c.extend["pods"].columns
    assert columns[0].name == "foo"
    assert columns[0].type == "text"
    assert columns[0].path == "metadata.name"
    assert columns[1].name == "bar"
    assert columns[1].type == "integer"
    assert columns[1].path == "metadata.creationTimestamp"


def test_config_with_table_creation():
    c, e = parse_model(UserConfig, yaml.safe_load("""
        create:
        - table: pods
          resource: pods
          columns:
          - name: foo
            path: metadata.name
          - name: bar
            type: integer
            path: metadata.creationTimestamp
    """))
    assert e is None
    c = Config.collate(UserInit(), c)
    pods = c.create["pods"]
    assert pods.resource == "pods"
    columns = pods.columns
    assert columns[0].name == "foo"
    assert columns[0].type == "text"
    assert columns[0].path == "metadata.name"
    assert columns[1].name == "bar"
    assert columns[1].type == "integer"
    assert columns[1].path == "metadata.creationTimestamp"


def test_unknown_type():
    _, errors = parse_model(ExtendTable, yaml.safe_load("""
        table: xyz
        columns:
        - name: foo
          type: unknown_type
          path: metadata.name
    """))
    assert errors == ["columns.0.type: Input should be 'text', 'integer' or 'real'"]


def test_missing_fields_for_create():
    _, errors = parse_model(CreateTable, yaml.safe_load("""
        table: xyz
        columns:
        - name: foo
          path: metadata.name
    """))
    assert set(errors) == set([
        "resource: Field required",
    ])


def test_unexpected_keys():
    _, errors = parse_model(ExtendTable, yaml.safe_load("""
        table: xyz
        columns:
        - name: foo
          path: metadata.name
          unexpected: 42
    """))
    assert errors == ["columns.0.unexpected: Extra inputs are not permitted"]


def test_invalid_jmespath():
    _, errors = parse_model(ExtendTable, yaml.safe_load("""
        table: xyz
        columns:
        - name: foo
          path: ...name
    """))
    assert errors == ["columns.0: Value error, invalid JMESPath expression ...name"]


def test_cannot_have_both_path_and_label():
    _, errors = parse_model(ExtendTable, yaml.safe_load("""
        table: xyz
        columns:
        - name: foo
          type: text
          path: xyz
          label: xyz
    """))
    assert errors == ["columns.0: Value error, cannot specify both path and label"]


def test_must_specify_path_or_label():
    _, errors = parse_model(ExtendTable, yaml.safe_load("""
        table: xyz
        columns:
        - name: foo
    """))
    assert errors == ["columns.0: Value error, must specify either path or label"]