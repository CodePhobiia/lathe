# Tutorial

A progressive ladder from a clean checkout to reading the specs in a useful order. Total time: about an hour end-to-end.

1. **[60-second quickstart](../quickstart.md)** — bootstrap, `doctor`, `build`. Three commands.
2. **[Author your first `.lth` asset](first_asset.md)** — ~15 min. Build [`examples/tutorial_bookshelf.lth`](https://github.com/talmerri/lathe/blob/main/examples/tutorial_bookshelf.lth) from scratch. Covers `profile`, `contract`, `critic`, `asset`, `variant`, `check` / `plan` / `build`, and seed-driven determinism.
3. **[Reconstruct from reference views](second_asset_reconstruct.md)** — ~20 min. Uses the shipped `examples/reconstruct_courier_from_views.lth`. Covers `reference_set`, `reconstruct_policy`, the reconstruct-specific validators, and a `generate` vs `reconstruct` comparison.
4. **[Deep dive reading order](deep_dive.md)** — a map of spec documents with suggested reading order and pointers into the architecture pages.

Before the tutorial, make sure `python -m lathe.cli doctor` runs cleanly. See [Local golden path](../local_golden_path.md) if you need a richer setup with real Hunyuan / VGGT runtime configs.
