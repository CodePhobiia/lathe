# Environment Modules

Environment modules are Scene Graph source vocabulary for place-making:
room shells, floor tiles, wall and ceiling segments, arches, platforms,
stairs, background silhouettes, and terrain chunks. They are validated
for snap-grid metadata and boundary-shell presence before downstream
mesh/runtime work claims final assets.

## Catalog

| Module | Asset | Kind | Snap Profile | Snap Points | Boundary |
| --- | --- | --- | --- | --- | --- |
| `env_room_shell` | `architecture_room_shell` | scene_boundary | grid_1m | 4 | required |
| `env_floor_tile` | `architecture_floor` | floor | grid_1m | 4 | member |
| `env_wall_segment` | `architecture_wall` | wall | grid_1m | 4 | member |
| `env_ceiling_segment` | `architecture_ceiling` | ceiling | grid_1m | 4 | member |
| `env_arch_segment` | `architecture_arch` | threshold | grid_1m | 4 | member |
| `env_platform_module` | `architecture_platform` | platform | grid_1m | 4 | member |
| `env_stair_module` | `architecture_stair` | stair | grid_1m | 4 | member |
| `env_background_silhouette` | `environment_structure` | background | grid_2m | 2 | member |
| `env_terrain_chunk` | `natural_terrain_chunk` | terrain | grid_1m | 4 | member |

## Validation

- Environment modules are Scene Graph objects tagged with `env_module`.
- `state.snap_grid` controls deterministic x/y placement alignment.
- `state.snap_point_count` records authored connection points for downstream module assembly.
- A room-like environment module scene must include a `scene_boundary` module.
- The committed `environment_module_showcase` example validates these contracts without claiming final mesh runtime proof.
