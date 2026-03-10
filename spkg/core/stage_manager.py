"""Stage Manager — enforces stage-level metrics and USD conventions.

Handles metersPerUnit, upAxis, default prim, and timeCodesPerSecond
configuration from SceneSpec stage settings.
"""

from __future__ import annotations

from pathlib import Path

from pxr import Sdf, Usd, UsdGeom


def configure_stage(stage: Usd.Stage, stage_config: dict) -> None:
    """Apply SceneSpec stage settings to a USD stage.

    Args:
        stage: The USD stage to configure.
        stage_config: The "stage" dict from SceneSpec JSON with keys:
            - default_prim (str): e.g. "/World"
            - metersPerUnit (float): e.g. 0.01 for centimeters
            - upAxis (str): "Y" or "Z"
            - timeCodesPerSecond (float, optional): default 60
    """
    # Set metersPerUnit
    meters_per_unit = stage_config["metersPerUnit"]
    UsdGeom.SetStageMetersPerUnit(stage, meters_per_unit)

    # Set upAxis
    up_axis = stage_config["upAxis"]
    axis_token = UsdGeom.Tokens.y if up_axis == "Y" else UsdGeom.Tokens.z
    UsdGeom.SetStageUpAxis(stage, axis_token)

    # Set timeCodesPerSecond
    tcps = stage_config.get("timeCodesPerSecond", 60)
    stage.SetTimeCodesPerSecond(tcps)

    # Create and set default prim
    default_prim_path = stage_config["default_prim"]
    root_prim = stage.DefinePrim(default_prim_path, "Xform")
    stage.SetDefaultPrim(root_prim)


def validate_stage_metrics(stage: Usd.Stage) -> list[str]:
    """Validate that a stage has required metrics set.

    Returns a list of error messages (empty = valid).
    """
    errors = []

    if not UsdGeom.GetStageMetersPerUnit(stage):
        errors.append("STAGE-001: metersPerUnit is not set")

    up_axis = UsdGeom.GetStageUpAxis(stage)
    if up_axis not in (UsdGeom.Tokens.y, UsdGeom.Tokens.z):
        errors.append(f"STAGE-002: upAxis is '{up_axis}', expected 'Y' or 'Z'")

    if not stage.GetDefaultPrim():
        errors.append("STAGE-003: No default prim set")

    return errors
