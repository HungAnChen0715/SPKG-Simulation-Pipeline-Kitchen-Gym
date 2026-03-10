"""Resolver — assembles a SceneSpec JSON into a layered USD Stage.

This is the core of Layer 2: reads a SceneSpec, creates a layered USD stage
(via LayerComposer), places objects using References, and applies physics
metadata to the physics sublayer.

End-to-end flow:
    SceneSpec JSON → validate → create layered stage → place objects
    → apply physics → save all layers → world.usda ready for Isaac Sim
"""

from __future__ import annotations

import json
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

from spkg.core.layer_composer import (
    create_layered_stage,
    get_edit_target,
    save_all_layers,
)
from spkg.core.stage_manager import configure_stage


def load_scenespec(path: str | Path) -> dict:
    """Load and return a SceneSpec JSON file.

    Args:
        path: Path to the .scenespec.json file.

    Returns:
        Parsed SceneSpec dict.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    path = Path(path)
    with open(path) as f:
        return json.load(f)


def validate_scenespec(spec: dict) -> list[str]:
    """Basic structural validation of a SceneSpec.

    For full JSON Schema validation, use jsonschema externally.
    This performs quick runtime checks.

    Returns:
        List of error messages (empty = valid).
    """
    errors = []
    required_keys = ["schema_version", "generator", "stage", "assets", "objects"]
    for key in required_keys:
        if key not in spec:
            errors.append(f"Missing required key: '{key}'")

    if "stage" in spec:
        stage = spec["stage"]
        for key in ["default_prim", "metersPerUnit", "upAxis"]:
            if key not in stage:
                errors.append(f"Missing stage key: '{key}'")

    # Check that all object asset_ids reference valid assets
    if "assets" in spec and "objects" in spec:
        valid_asset_ids = {a["asset_id"] for a in spec["assets"]}
        for obj in spec["objects"]:
            if obj.get("asset_id") not in valid_asset_ids:
                errors.append(
                    f"Object '{obj.get('object_id', '?')}' references "
                    f"unknown asset_id '{obj.get('asset_id', '?')}'"
                )

    return errors


def _build_asset_map(assets: list[dict]) -> dict[str, str]:
    """Build a mapping from asset_id → asset_ref (file path)."""
    return {a["asset_id"]: a["asset_ref"] for a in assets}


def _apply_transform(prim: Usd.Prim, transform: dict) -> None:
    """Apply transform from SceneSpec to a USD prim.

    Args:
        prim: The USD prim to transform.
        transform: Dict with translate_m, rotate_quat_wxyz, scale.
    """
    xformable = UsdGeom.Xformable(prim)

    # Clear existing xform ops
    xformable.ClearXformOpOrder()

    # Translation (in meters from SceneSpec, USD will handle units)
    translate = transform["translate_m"]
    xformable.AddTranslateOp().Set(Gf.Vec3d(*translate))

    # Rotation (quaternion wxyz)
    quat = transform.get("rotate_quat_wxyz", [1.0, 0.0, 0.0, 0.0])
    w, x, y, z = quat
    xformable.AddOrientOp().Set(Gf.Quatf(w, x, y, z))

    # Scale
    scale = transform.get("scale", [1.0, 1.0, 1.0])
    xformable.AddScaleOp().Set(Gf.Vec3f(*scale))


def _apply_physics(prim: Usd.Prim, physics_meta: dict) -> None:
    """Apply physics metadata from SceneSpec to a USD prim.

    Args:
        prim: The USD prim to apply physics to.
        physics_meta: Dict with rigid_body, collision, mass_kg, friction, etc.
    """
    rigid_body_type = physics_meta.get("rigid_body", "static")

    # Apply RigidBodyAPI
    if rigid_body_type in ("dynamic", "kinematic"):
        rb_api = UsdPhysics.RigidBodyAPI.Apply(prim)
        if rigid_body_type == "kinematic":
            rb_api.CreateKinematicEnabledAttr(True)

    # Apply CollisionAPI
    collision_type = physics_meta.get("collision", "none")
    if collision_type != "none":
        UsdPhysics.CollisionAPI.Apply(prim)
        # Note: collision approximation (convexHull, etc.) is configured
        # through additional APIs in Isaac Sim / PhysX, not base UsdPhysics.
        # We store the collision type as a custom attribute for downstream use.
        prim.CreateAttribute(
            "spkg:collisionApproximation", Sdf.ValueTypeNames.String
        ).Set(collision_type)

    # Apply MassAPI for dynamic bodies
    mass_kg = physics_meta.get("mass_kg")
    if mass_kg is not None:
        mass_api = UsdPhysics.MassAPI.Apply(prim)
        mass_api.CreateMassAttr(mass_kg)

    # Apply material properties
    static_friction = physics_meta.get("static_friction")
    dynamic_friction = physics_meta.get("dynamic_friction")
    restitution = physics_meta.get("restitution")

    if any(v is not None for v in (static_friction, dynamic_friction, restitution)):
        # Create a physics material and bind it
        mat_path = prim.GetPath().AppendChild("PhysicsMaterial")
        mat_prim = prim.GetStage().DefinePrim(mat_path, "Material")
        mat_api = UsdPhysics.MaterialAPI.Apply(mat_prim)

        if static_friction is not None:
            mat_api.CreateStaticFrictionAttr(static_friction)
        if dynamic_friction is not None:
            mat_api.CreateDynamicFrictionAttr(dynamic_friction)
        if restitution is not None:
            mat_api.CreateRestitutionAttr(restitution)

        # Bind material to prim
        binding_api = UsdPhysics.MaterialAPI.Apply(prim)


def resolve(
    scenespec: dict,
    output_dir: str | Path,
    asset_base_dir: str | Path | None = None,
) -> Path:
    """Resolve a SceneSpec into a layered USD stage.

    This is the main entry point for the resolver. It:
    1. Creates the layered stage (world.usda + sublayers)
    2. Configures stage metrics (metersPerUnit, upAxis, etc.)
    3. Places objects in the layout layer (using References)
    4. Applies physics in the physics layer
    5. Saves all layers

    Args:
        scenespec: Parsed SceneSpec dict.
        output_dir: Directory to write USD files to.
        asset_base_dir: Base directory for resolving relative asset paths.
            Defaults to the current working directory.

    Returns:
        Path to the root world.usda file.

    Raises:
        ValueError: If SceneSpec validation fails.
    """
    output_dir = Path(output_dir)
    asset_base_dir = Path(asset_base_dir) if asset_base_dir else Path.cwd()

    # Validate SceneSpec
    errors = validate_scenespec(scenespec)
    if errors:
        raise ValueError(f"SceneSpec validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    # 1. Create layered stage
    stage, layers = create_layered_stage(output_dir)

    # 2. Configure stage metrics (writes to root layer)
    configure_stage(stage, scenespec["stage"])
    stage.GetRootLayer().Save()

    # 3. Build asset ID → file path mapping
    asset_map = _build_asset_map(scenespec["assets"])

    # 4. Place objects in layout layer
    get_edit_target(stage, layers, "layout")

    # Determine canonical object ordering
    objects = scenespec["objects"]
    determinism = scenespec.get("determinism", {})
    sort_strategy = determinism.get("canonical_object_sort", "object_id_lex")

    if sort_strategy == "object_id_lex":
        objects = sorted(objects, key=lambda o: o["object_id"])

    for obj in objects:
        prim_path = obj["prim_path"]
        asset_id = obj["asset_id"]
        asset_ref = asset_map.get(asset_id)

        # Create prim and add reference to asset
        prim = stage.DefinePrim(prim_path, "Xform")

        if asset_ref:
            # Resolve asset path relative to asset_base_dir
            resolved_path = asset_base_dir / asset_ref
            if resolved_path.exists():
                prim.GetReferences().AddReference(str(resolved_path))
            else:
                # Add reference as-is (will resolve at load time)
                prim.GetReferences().AddReference(asset_ref)

        # Apply transform
        _apply_transform(prim, obj["transform"])

    save_all_layers(layers)

    # 5. Apply physics in physics layer
    get_edit_target(stage, layers, "physics")

    for obj in objects:
        prim_path = obj["prim_path"]
        prim = stage.GetPrimAtPath(prim_path)

        if prim and obj.get("physics_metadata"):
            _apply_physics(prim, obj["physics_metadata"])

    save_all_layers(layers)

    # Save root stage
    stage.GetRootLayer().Save()

    return output_dir / "world.usda"
