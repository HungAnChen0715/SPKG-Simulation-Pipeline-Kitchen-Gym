"""Tests for SceneSpec JSON Schema validation."""

import json
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "scenespec.schema.json"
GOLDEN_PATH = Path(__file__).parent.parent / "examples" / "golden_kitchen.scenespec.json"


@pytest.fixture
def schema():
    """Load the SceneSpec JSON Schema."""
    with open(SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture
def golden_scene():
    """Load the golden kitchen SceneSpec."""
    with open(GOLDEN_PATH) as f:
        return json.load(f)


def test_golden_kitchen_validates(schema, golden_scene):
    """The golden kitchen example must pass schema validation."""
    import jsonschema

    jsonschema.validate(instance=golden_scene, schema=schema)


def test_schema_rejects_missing_version(schema):
    """SceneSpec without schema_version must fail validation."""
    import jsonschema

    invalid = {
        "generator": {"name": "test", "version": "0.1"},
        "stage": {"default_prim": "/World", "metersPerUnit": 0.01, "upAxis": "Y"},
        "assets": [{"asset_id": "test/a", "asset_ref": "./a.usd"}],
        "objects": [],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=schema)


def test_schema_rejects_invalid_object_id(schema):
    """Object IDs must match the pattern '^obj_[a-z0-9_]+$'."""
    import jsonschema

    invalid = {
        "schema_version": "1.0.0",
        "generator": {"name": "test", "version": "0.1"},
        "stage": {"default_prim": "/World", "metersPerUnit": 0.01, "upAxis": "Y"},
        "assets": [{"asset_id": "test/a", "asset_ref": "./a.usd"}],
        "objects": [
            {
                "object_id": "INVALID-ID",
                "asset_id": "test/a",
                "prim_path": "/World/Test",
                "transform": {"translate_m": [0, 0, 0]},
            }
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=schema)


def test_schema_rejects_invalid_up_axis(schema):
    """upAxis must be 'Y' or 'Z'."""
    import jsonschema

    invalid = {
        "schema_version": "1.0.0",
        "generator": {"name": "test", "version": "0.1"},
        "stage": {"default_prim": "/World", "metersPerUnit": 0.01, "upAxis": "X"},
        "assets": [{"asset_id": "test/a", "asset_ref": "./a.usd"}],
        "objects": [],
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid, schema=schema)
