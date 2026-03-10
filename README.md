# SPKG — Simulation-Pipeline Kitchen Gym

> **LLM → SceneSpec → USD Assembly → Physics Validation → Isaac Sim**

用自然語言描述一個廚房場景，自動組裝、驗證、物理注入，直接在 Isaac Sim 中跑物理仿真和合成數據。

## ⚡ Quick Start

```bash
# Install
pip install -e ".[dev]"

# Generate a scene from natural language
spkg generate "一個有 L 型櫥櫃、方桌和杯子的廚房"

# Build layered USD from SceneSpec
spkg build kitchen_scene.scenespec.json --output ./outputs/kitchen/

# Validate physics & semantics
spkg validate ./outputs/kitchen/world.usda --report html
```

## 🏗️ Architecture

```
Layer 0: Houdini HDA → Parametric USD assets
Layer 1: LLM Planner → SceneSpec JSON (structured output)
Layer 2: Resolver    → Layered USD Stage (layout + physics sublayers)
Layer 3: Validator   → ⭐ Physics validation + auto-fix (core differentiator)
Layer 4: Isaac Sim   → PhysX simulation + synthetic data
```

## 📁 Project Structure

```
spkg/
├── pyproject.toml
├── schemas/scenespec.schema.json   # SceneSpec v1.0 contract
├── spkg/
│   ├── cli.py                      # CLI: generate, build, validate
│   ├── core/                       # Resolver + layer composition
│   ├── physics/                    # Physics injection + collision
│   ├── semantics/                  # Semantic labeling
│   ├── validator/                  # ⭐ Rule engine + auto-fix
│   ├── replicator/                 # Domain randomization + data output
│   └── llm/                        # LLM scene generation
├── assets/kitchen_min/             # Houdini HDA output
├── examples/                       # Golden test SceneSpecs
├── tests/                          # Unit + integration tests
└── docs/                           # Architecture docs
```

## 🔑 Key Design Decisions

1. **LLM is a planner, not a compiler** — it outputs SceneSpec JSON (machine-verifiable contract), not raw USD
2. **Physics/layout separation** — sublayer architecture ensures physics properties survive art updates
3. **Systematic validation** — the Validator is the core differentiator vs. existing LLM→3D projects

## 📜 License

MIT
