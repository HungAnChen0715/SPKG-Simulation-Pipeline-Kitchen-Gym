"""Tests for the Resolver — SceneSpec → USD Stage assembly."""

import json
import tempfile
from pathlib import Path

import pytest
from pxr import Sdf, Usd, UsdGeom, UsdPhysics

from spkg.core.resolver import load_scenespec, resolve, validate_scenespec


GOLDEN_PATH = Path(__file__).parent.parent / "examples" / "golden_kitchen.scenespec.json"


@pytest.fixture
def golden_spec():
    """Load the golden kitchen SceneSpec."""
    with open(GOLDEN_PATH) as f:
        return json.load(f)


@pytest.fixture
def minimal_spec():
    """A minimal valid SceneSpec for testing."""
    return {
        "schema_version": "1.0.0",
        "generator": {"name": "test", "version": "0.1.0"},
        "stage": {
            "default_prim": "/World",
            "metersPerUnit": 0.01,
            "upAxis": "Y",
            "timeCodesPerSecond": 60,
        },
        "assets": [
            {
                "asset_id": "test/box",
                "asset_ref": "./assets/test/box.usd",
            }
        ],
        "objects": [
            {
                "object_id": "obj_box_0001",
                "asset_id": "test/box",
                "prim_path": "/World/Props/Box_0001",
                "transform": {
                    "translate_m": [1.0, 0.0, 0.5],
                    "rotate_quat_wxyz": [1.0, 0.0, 0.0, 0.0],
                    "scale": [1.0, 1.0, 1.0],
                },
                "physics_metadata": {
                    "rigid_body": "dynamic",
                    "collision": "convexHull",
                    "mass_kg": 2.5,
                    "static_friction": 0.5,
                    "dynamic_friction": 0.4,
                    "restitution": 0.1,
                },
            }
        ],
    }


class TestValidateSceneSpec:
    """Tests for SceneSpec validation."""

    def test_valid_spec_passes(self, minimal_spec):
        errors = validate_scenespec(minimal_spec)
        assert errors == []

    def test_missing_key_fails(self, minimal_spec):
        del minimal_spec["stage"]
        errors = validate_scenespec(minimal_spec)
        assert any("stage" in e for e in errors)

    def test_invalid_asset_ref_fails(self, minimal_spec):
        minimal_spec["objects"][0]["asset_id"] = "nonexistent/asset"
        errors = validate_scenespec(minimal_spec)
        assert any("nonexistent/asset" in e for e in errors)


class TestResolverEmpty:
    """Test resolver with an empty scene."""

    def test_empty_objects(self):
        spec = {
            "schema_version": "1.0.0",
            "generator": {"name": "test", "version": "0.1.0"},
            "stage": {
                "default_prim": "/World",
                "metersPerUnit": 1.0,
                "upAxis": "Y",
            },
            "assets": [{"asset_id": "test/a", "asset_ref": "./a.usd"}],
            "objects": [],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve(spec, tmpdir)
            assert result.exists()
            stage = Usd.Stage.Open(str(result))
            assert stage.GetDefaultPrim().GetName() == "World"


class TestResolverSingleObject:
    """Test resolver with a single object."""

    def test_single_object_placement(self, minimal_spec):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve(minimal_spec, tmpdir)

            # Open the resulting stage
            stage = Usd.Stage.Open(str(result))

            # Check stage metrics
            assert UsdGeom.GetStageMetersPerUnit(stage) == 0.01
            assert UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.y

            # Check object prim exists
            prim = stage.GetPrimAtPath("/World/Props/Box_0001")
            assert prim.IsValid()

            # Check transform was applied
            xformable = UsdGeom.Xformable(prim)
            xform_ops = xformable.GetOrderedXformOps()
            assert len(xform_ops) == 3  # translate, orient, scale

    def test_physics_applied(self, minimal_spec):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve(minimal_spec, tmpdir)
            stage = Usd.Stage.Open(str(result))
            prim = stage.GetPrimAtPath("/World/Props/Box_0001")

            # Check RigidBodyAPI
            assert prim.HasAPI(UsdPhysics.RigidBodyAPI)

            # Check CollisionAPI
            assert prim.HasAPI(UsdPhysics.CollisionAPI)

            # Check MassAPI
            assert prim.HasAPI(UsdPhysics.MassAPI)
            mass_api = UsdPhysics.MassAPI(prim)
            assert mass_api.GetMassAttr().Get() == 2.5

    def test_sublayer_structure(self, minimal_spec):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve(minimal_spec, tmpdir)

            # Check sublayer files exist
            output_dir = Path(tmpdir)
            assert (output_dir / "layout.usda").exists()
            assert (output_dir / "physics.usda").exists()
            assert (output_dir / "chaos.usda").exists()
            assert (output_dir / "world.usda").exists()

            # Check sublayer ordering in root
            root_layer = Sdf.Layer.FindOrOpen(str(result))
            sub_paths = list(root_layer.subLayerPaths)
            # Strongest first: chaos, physics, layout
            assert sub_paths == ["./chaos.usda", "./physics.usda", "./layout.usda"]


class TestResolverGolden:
    """Test resolver with the golden kitchen SceneSpec."""

    def test_golden_kitchen_resolves(self, golden_spec):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve(golden_spec, tmpdir)
            stage = Usd.Stage.Open(str(result))

            # Should have 5 objects from golden kitchen
            world_prim = stage.GetDefaultPrim()
            props = stage.GetPrimAtPath("/World/Props")
            assert props.IsValid()

            # Count object prims
            children = [c for c in props.GetChildren()]
            assert len(children) == 5  # 2 cabinets + 1 table + 2 cups

    def test_golden_deterministic_order(self, golden_spec):
        """Two resolves should produce identical prim ordering."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            resolve(golden_spec, tmpdir1)
            stage1 = Usd.Stage.Open(str(Path(tmpdir1) / "world.usda"))
            prims1 = [
                c.GetName()
                for c in stage1.GetPrimAtPath("/World/Props").GetChildren()
            ]

        with tempfile.TemporaryDirectory() as tmpdir2:
            resolve(golden_spec, tmpdir2)
            stage2 = Usd.Stage.Open(str(Path(tmpdir2) / "world.usda"))
            prims2 = [
                c.GetName()
                for c in stage2.GetPrimAtPath("/World/Props").GetChildren()
            ]

        assert prims1 == prims2

    def test_static_vs_dynamic_physics(self, golden_spec):
        """Cabinets should be static, cups should be dynamic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolve(golden_spec, tmpdir)
            stage = Usd.Stage.Open(str(Path(tmpdir) / "world.usda"))

            # Cabinet is static — should NOT have RigidBodyAPI
            cabinet = stage.GetPrimAtPath("/World/Props/Cabinet_0001")
            assert not cabinet.HasAPI(UsdPhysics.RigidBodyAPI)

            # Cup is dynamic — SHOULD have RigidBodyAPI
            cup = stage.GetPrimAtPath("/World/Props/Cup_0001")
            assert cup.HasAPI(UsdPhysics.RigidBodyAPI)
