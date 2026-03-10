"""Layer Composer — manages the sublayer architecture for USD stages.

Implements the three-layer sublayer strategy:
  - layout.usda (weakest) — object placement and asset references
  - physics.usda (stronger) — RigidBody, Collider, Mass properties
  - chaos.usda (strongest) — Domain Randomization overrides

The sublayer ordering ensures physics properties are never overridden
by art updates (physics sublayer is stronger than layout).
"""

from __future__ import annotations

from pathlib import Path

from pxr import Sdf, Usd


# Layer names in order from WEAKEST to STRONGEST
LAYER_ORDER = ["layout", "physics", "chaos"]


def create_layered_stage(output_dir: Path) -> tuple[Usd.Stage, dict[str, Sdf.Layer]]:
    """Create a root USD stage with sublayer architecture.

    The root stage (world.usda) references sublayers in strength order:
      subLayers = [@./chaos.usda@, @./physics.usda@, @./layout.usda@]

    In USD, earlier entries in subLayers are STRONGER, so:
      chaos > physics > layout

    Args:
        output_dir: Directory to create USD files in.

    Returns:
        Tuple of (root_stage, dict mapping layer_name → Sdf.Layer).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create individual sublayers
    layers = {}
    for name in LAYER_ORDER:
        layer_path = str(output_dir / f"{name}.usda")
        layer = Sdf.Layer.CreateNew(layer_path)
        layers[name] = layer

    # Create root stage
    root_path = str(output_dir / "world.usda")
    root_layer = Sdf.Layer.CreateNew(root_path)

    # Add sublayers in REVERSE order (strongest first in the list)
    for name in reversed(LAYER_ORDER):
        layer_path = f"./{name}.usda"
        root_layer.subLayerPaths.append(layer_path)

    root_layer.Save()

    # Open as a stage for further configuration
    stage = Usd.Stage.Open(root_layer)

    return stage, layers


def get_edit_target(stage: Usd.Stage, layers: dict[str, Sdf.Layer], layer_name: str) -> None:
    """Set the edit target to a specific sublayer.

    Args:
        stage: The USD stage.
        layers: Dict mapping layer_name → Sdf.Layer.
        layer_name: Which layer to target ("layout", "physics", or "chaos").
    """
    if layer_name not in layers:
        raise ValueError(f"Unknown layer: {layer_name}. Must be one of {list(layers.keys())}")

    stage.SetEditTarget(Usd.EditTarget(layers[layer_name]))


def save_all_layers(layers: dict[str, Sdf.Layer]) -> None:
    """Save all sublayers to disk."""
    for layer in layers.values():
        layer.Save()
