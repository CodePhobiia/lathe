# Tutorial

A progressive ladder from a clean checkout to reading the specs in a useful
order. Total time: about an hour end to end.

1. **[60-second quickstart](../quickstart.md)** - bootstrap, `doctor`,
   `build`. Three commands.
2. **[Author your first `.lth` asset](first_asset.md)** - about 15 minutes.
   Build `examples/tutorial_bookshelf.lth` from scratch. Covers `profile`,
   `contract`, `critic`, `asset`, `variant`, `check`, `plan`, `build`, and
   seed-driven determinism.
3. **[Reconstruct from reference views](second_asset_reconstruct.md)** - about
   20 minutes. Uses the shipped `examples/reconstruct_courier_from_views.lth`.
   Covers `reference_set`, `reconstruct_policy`, reconstruct-specific
   validators, and a generate-vs-reconstruct comparison.
4. **[Fallback provider workflow](fallback_provider.md)** - about 10 minutes.
   Builds a certified asset without external model services and teaches how to
   read honest fallback traces.
5. **[Learned provider workflow](learned_provider.md)** - about 15 minutes after
   a provider service is available. Requests Hunyuan through runtime config and
   verifies the actual provider claim in the trace.
6. **[Engine export workflow](engine_export.md)** - about 15 minutes. Builds an
   engine-oriented asset and inspects GLB/USD, engine manifests, previews, and
   validation evidence.
7. **[Deep dive reading order](deep_dive.md)** - a map of spec documents with
   suggested reading order and pointers into the architecture pages.

Before the tutorial, make sure `python -m lathe.cli doctor` runs cleanly. See
[Local golden path](../local_golden_path.md) if you need a richer setup with
real Hunyuan / VGGT runtime configs.
