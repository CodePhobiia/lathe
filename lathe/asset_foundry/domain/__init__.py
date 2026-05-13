"""Phase 3 procedural domain libraries.

Per northstar §11 Phase 3 (6-9 months horizon), the Foundry expands
into production-multiplier domains:

  - vegetation.py     SpeedTree-inspired vocabulary
  - terrain.py        heightfield + erosion + material zones
  - wfc.py            Wave Function Collapse modular assembly
  - cga.py            CGA-shape style assembly (extends authoring.cga_assembly)
  - opensubdiv.py     subdivision finishing scaffold
  - scatter.py        scatter + surface scatter
  - trim_sheets.py    trim sheets + UDIM authoring
  - sdf_extraction.py F-Rep/SDF sharper extraction
"""

from __future__ import annotations

from .opensubdiv import (
    OPENSUBDIV_VERSION,
    SubdivisionRequest,
    SubdivisionResult,
    plan_opensubdiv_refinement,
)
from .scatter import (
    SCATTER_VERSION,
    ScatterInstance,
    ScatterRequest,
    ScatterResult,
    scatter_on_surface,
)
from .sdf_extraction import (
    SDF_EXTRACTION_VERSION,
    SdfExtractionRequest,
    SdfExtractionResult,
    plan_sdf_extraction,
)
from .terrain import (
    TERRAIN_VERSION,
    HeightField,
    TerrainMaterialZone,
    TerrainParameters,
    apply_erosion,
    build_height_field,
)
from .trim_sheets import (
    TRIM_SHEETS_VERSION,
    TrimSheet,
    TrimSheetSlot,
    bind_part_to_trim_slot,
)
from .vegetation import (
    VEGETATION_VERSION,
    BranchParameters,
    LeafCluster,
    TreeStructure,
    build_tree_structure,
)
from .wfc import (
    WFC_VERSION,
    WfcConstraintSet,
    WfcSolverResult,
    WfcTile,
    solve_wfc_grid,
)

__all__ = [
    "OPENSUBDIV_VERSION",
    "SubdivisionRequest",
    "SubdivisionResult",
    "plan_opensubdiv_refinement",
    "SCATTER_VERSION",
    "ScatterInstance",
    "ScatterRequest",
    "ScatterResult",
    "scatter_on_surface",
    "SDF_EXTRACTION_VERSION",
    "SdfExtractionRequest",
    "SdfExtractionResult",
    "plan_sdf_extraction",
    "TERRAIN_VERSION",
    "HeightField",
    "TerrainMaterialZone",
    "TerrainParameters",
    "apply_erosion",
    "build_height_field",
    "TRIM_SHEETS_VERSION",
    "TrimSheet",
    "TrimSheetSlot",
    "bind_part_to_trim_slot",
    "VEGETATION_VERSION",
    "BranchParameters",
    "LeafCluster",
    "TreeStructure",
    "build_tree_structure",
    "WFC_VERSION",
    "WfcConstraintSet",
    "WfcSolverResult",
    "WfcTile",
    "solve_wfc_grid",
]
