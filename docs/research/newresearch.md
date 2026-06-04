My blunt read: we should **not** try to make the current “Manifold boolean after every op” pipeline 10× faster as-is. That path will keep punishing us with intermediate mesh copies, topology churn, material loss, and face-count blowups.

The right architecture is:

**Lathe intent → typed morphology graph → anchor/constraint placement → lazy feature/CSG DAG → batched boolean/arrangement compiler → deferred bevel/sweep/features → zone-preserving mesh → UV/material/LOD compiler → render-based validators.**

Manifold can still be useful, but it should be an **execution backend**, not the core representation of the asset.

Implementation support snapshot - 2026-05-14:

- Typed/lazy graph support is now represented by `lathe.asset_foundry.op_graph.GeometryOpGraph`, spatial `OpGraphCluster` planning, and `BooleanClusterPlan` records. The current execution mode remains `serial_reference_plan_only` until an arrangement backend lands.
- Category evidence is represented by `lathe.validators.class_anchor` plus `asset_quality_diagnostics` class-anchor findings and deterministic repair routes.
- Foundry category-anchor scoring is represented by `lathe.asset_foundry.certificates.category_anchor_score` and `validators.topology_class_compliance.evaluate_category_anchor_compliance`, so weak category evidence caps promotion before aesthetic polish.
- Capability truth tiers are represented by `lathe.asset_foundry.capability_matrix.claim_level` and `counts_by_claim_level`; static rows currently allow zero `product_complete` claims without asset-specific evidence.
- Local pure-Python feature progress: `op.distribute` now has aggregate `along_path` lowering evidence, and `op.weld_seam` lowers to visible seam-bead records rather than metadata-only claims.
- Graph-level repair evidence is represented by `repair_target_layer="shape_ir_patch"` traces, `build_repair_history_evidence()`, and `.lthpkg` `repair-history.json` sidecars. The no-mesh probe package `.tmp_repair_history_probe/pkg/synthetic_crate_repair_evidence.lthpkg` proves diagnostic-to-ShapeIR repair metadata while keeping mesh rebuild and preview approval unverified.
- Runtime asset-contract support is represented by real JSON render mesh, collision proxy, and LOD artifacts for the violet crystal cluster, with `.lthpkg` runtime sidecars preserving `real` versus `not_verified` visual claims.
- Collision proxy support now includes per-component convex AABB decomposition for prismatic Golden Assets, with runtime manifests recording `decomposition_strategy` and `proxy_component_count`.
- Runtime readiness is now gated by render mesh, collision, LOD, and material-zone evidence; missing material slots keep engine readiness unsupported.
- External backends remain explicit blockers: `occt_backend_not_configured`, `opensubdiv_backend_not_configured`, `openvdb_backend_not_configured`, `materialx_serializer_not_configured`, and `usd_writer_not_configured`.
- `.lthpkg` package evidence now carries those backend blockers in `external_backend_evidence`, so Web Studio can inspect typed-contract limits without mistaking them for generated files.
- The Web Studio path is now verified at the package-evidence level: `lathe-web-viewer` can load the generated violet crystal `.lthpkg` manifest through `?manifest=...`, surface semantic parts/material slots/certificate metrics/backend blockers, and keep missing rendered GLB/visual approval labeled `not_verified`.

1\. Geometry representation
---------------------------

### Best substrate for mid-volume procedural game assets

For our target—hard-surface procedural game props with watertight booleans, semantic parts, materials, bevels, and LODs—the right substrate is a **hybrid**, not pure CSG, not pure B-rep, and not pure SDF.

SubstrateStrengthsFailure modeMy take for us**CSG / mesh booleans**Simple, expressive for hard-surface kitbash logic, good for deterministic watertight propsExpensive if evaluated per op; loses feature identity; bevel/material zones become hard after fusionGood as an authoring algebra, bad as the full production representation**Parametric B-rep**Best for true CAD features: fillets, chamfers, shelling, selected faces/edges, editable featuresExpensive to implement; topology naming is hard; still needs game mesh exportWe should borrow its concepts: persistent faces, edges, features, provenance**SDF + meshing**Robust many-op union/difference, great for organic damage/blending/noisy wearResolution-bound, hard edges/UV seams/material zones are painfulUse selectively for damage, erosion, soft blends—not core crates/doors/panels**Hybrid feature graph**Keeps semantic identity, supports batching, materials, anchors, feature rules, LODMore compiler work upfrontThis is the production path

Manifold’s design goal is robust manifold triangle-mesh operations with arbitrary vertex properties/material mapping and guaranteed manifold output, which is valuable for us. But that does not make “one mesh boolean per Lathe op” the right architecture. ([manifoldcad.org](https://manifoldcad.org/docs/html/)) CGAL’s Nef polyhedra show the opposite end of the spectrum: mathematically closed boolean representations, but heavier than what we want for fast procedural game assets. ([doc.cgal.org](https://doc.cgal.org/latest/Nef_3/index.html)) OpenVDB-style CSG is excellent when we can accept level-set resolution and remeshing tradeoffs, but it is not naturally good at crisp CAD-like feature boundaries and material-zone preservation. ([openvdb.org](https://www.openvdb.org/documentation/doxygen/codeExamples.html))

### Boolean frontier

The frontier is not “which library is fastest?” It is **when evaluation happens** and **how much provenance survives**.

**Manifold** is the practical default for robust watertight triangle booleans. It breaks down for us when we repeatedly convert meshes, repeatedly materialize intermediate results, and force every feature into final topology too early.

**libigl mesh arrangements** are the conceptual model I would study for scaling to many operations: build an arrangement once, classify cells/windings, then extract the result. The libigl variadic boolean interface explicitly supports boolean expressions over multiple meshes through winding-number filters, which is much closer to what we want than serial binary booleans. ([alecjacobson.com](https://alecjacobson.com/weblog/4568.html)) Mesh-arrangement work also directly addresses robustness on messy triangle inputs, while noting that many earlier algorithms require overly strict mesh assumptions. ([Columbia Computer Science](https://www.cs.columbia.edu/cg/mesh-arrangements/mesh-arrangements-for-solid-geometry-siggraph-2016-compressed-zhou-et-al.pdf))

**CGAL Nef polyhedra** are the robustness reference, not the production-speed target. They are closed under boolean operations and regularization, but the cost and complexity are not aligned with fast game-asset generation. ([doc.cgal.org](https://doc.cgal.org/latest/Nef_3/index.html))

**OpenVDB CSG** is excellent for many unions/differences and organic effects, especially when exact sharp topology is less important. But transforms, resampling, and grid resolution become architectural concerns. ([openvdb.org](https://www.openvdb.org/documentation/doxygen/codeExamples.html))

**Learned geometry** is not a boolean kernel replacement. It can propose shapes, priors, parameter values, and visual critiques, but I would not trust it as the source of deterministic watertight production topology.

### Kernel architecture for 200 ops per asset

For our case—origin-watertight hard-surface booleans, ~20 ops today, wanting ~200 ops without per-op manifold copies—we need a **lazy batched compiler**.

The design:

1.  **Keep a lazy CSG/feature DAG.**Lathe ops should not immediately become final meshes. They should become typed nodes: box, cylinder, cut, union, inset, bracket, bevel rule, material zone, decal anchor.
    
2.  **Cache primitive tessellations and analytic descriptors.**A cylinder primitive should not regenerate or re-enter from\_trimesh every time. It should have a stable primitive ID, transform, tessellation policy, and semantic role.
    
3.  **Broadphase spatial clustering.**Most ops do not interact. A crate body, four corner guards, handles, hinges, and decal plates can be clustered by bounding boxes. Only overlapping clusters need expensive arrangements.
    
4.  **Evaluate booleans variadically per cluster.**Instead of 200 serial binary booleans, compile all interacting meshes in a cluster, build one arrangement, classify by the boolean expression, and extract once. The libigl variadic boolean model is the right mental model here. ([alecjacobson.com](https://alecjacobson.com/weblog/4568.html))
    
5.  **Carry provenance through the kernel.**Every output face needs source\_part\_id, source\_face\_role, material\_class, uv\_policy, feature\_role, and zone\_id. Without that, material zones and validators will always be bolted on too late.
    
6.  **Defer bevels and fillets.**Do not bevel primitive edges before booleans unless the bevel is structurally required. Run booleans on simpler forms, then select final edges by semantic/topological rules and apply bevels with a budget.
    
7.  **Do not fuse everything early.**Some pieces should remain separate submeshes or instances: bolts, handles, corner brackets, trim strips, hinge barrels. A single watertight fused mesh is sometimes the wrong output for game assets.
    
8.  **Add an optional SDF branch.**Use it for dents, chipped paint masks, eroded corners, soft damage—not for every hard-surface feature.
    

This lets us scale from “20 expensive mesh operations” to “200 authored feature operations” because most authored ops will not become full topology operations.

2\. Spatial composition / placement
-----------------------------------

Our current suffix/name heuristic placement is a dead end. The canonical formulation is an **attributed shape grammar plus a constraint/anchor system**.

CGA/CityEngine is the obvious reference for grammar-driven architecture: shapes have scopes, components can be split into faces/edges/vertices, and rules operate over geometry-derived selectors. ([ArcGIS](https://doc.arcgis.com/en/cityengine/latest/cga/cityengine-cga-introduction.htm)) ([ArcGIS](https://doc.arcgis.com/en/cityengine/2025.0/help/help-component-split.htm)) Houdini’s production pattern is different but equally important: attributes on points/primitives drive copying, variation, and procedural instancing. ([SideFX](https://www.sidefx.com/docs/houdini/copy/tutorial_stamping.html))

The clean separation should be:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   Semantic relation:    metal_corner_guard attaches_to crate.corner[NE]    hinge attaches_to door.long_edge[left]    handle aligned_with door.front_face at ergonomic_height  Numeric realization:    resolve host anchor frame    choose candidate orientation    apply offsets/clearances    validate collision/support/orientation    emit transform   `

The boundary lives at an **anchor contract**.

Example:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   anchor Crate.corner[i]:    role: exterior_corner    frame: {origin, normal_x, normal_y, normal_z}    bounds: local_bbox    affordances: [attach_plate, wrap_around, reinforce]    capacity: 1 corner_guard  feature MetalCornerBracket:    requires: anchor.role == exterior_corner    relation: wraps_around    valid_orientations: 4    clearance: 0.5cm    material_class: metal_trim   `

For “8 corners × 4 brackets × valid orientations,” we should not jump to ML. The correct implementation is:

1.  Generate candidates exhaustively.
    
2.  Reject invalid candidates with hard constraints.
    
3.  Score survivors with soft constraints.
    
4.  Pick deterministically or sample from weighted valid candidates.
    
5.  Use beam search only when the combinatorics become scene-scale.
    

For asset-level placement, exhaustive expansion plus constraints is enough. For room/world layout, constraint solving becomes more important. Infinigen Indoors uses a constraint-based arrangement DSL and solver for indoor procedural scenes, while Holodeck-style systems use spatial relational constraints and layout optimization from language prompts. ([arXiv](https://arxiv.org/abs/2406.11824)) ([CVF Open Access](https://openaccess.thecvf.com/content/CVPR2024/html/Yang_Holodeck_Language_Guided_Generation_of_3D_Embodied_AI_Environments_CVPR_2024_paper.html))

3\. Asset-class priors without family dispatch
----------------------------------------------

The right substrate is a **typed morphology graph with feature-template inheritance**.

We should stop encoding this:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   kind -> aspect  env_module -> flat  hard_surface_prop -> box   `

And move to this:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   bounded_volume    features:      primary_volume      exterior_faces      support_base  container extends bounded_volume    features:      access_plane      lid_or_door      interior_hint      closure_detail  crate extends container    features:      reinforced_corners      side_panels      slats_or_ribs      grip_handles      label_or_decal_zone      material_split: body + trim  industrial_crate extends crate    features:      metal_corner_guards      latch_or_lock      stamped_warning_label      grime/wear masks   `

For a door:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   door extends panel    required:      hinge_line on long_vertical_edge      handle around ergonomic_height      front/back faces      frame_relation optional    constraints:      handle opposite hinge side      hinge barrels align vertically      panel thickness within range   `

This is not per-class branching. It is **declarative feature composition**.

Each asset class should declare:

*   required features,
    
*   optional features,
    
*   anchor generators,
    
*   relation constraints,
    
*   material zones,
    
*   UV policies,
    
*   LOD importance,
    
*   visual validators.
    

ShapeAssembly is a useful mental model here because it represents shapes as editable programs made of cuboid part proxies, hierarchical attachment, symmetry, and learned parameter correlations. It is not production-ready for our exact pipeline, but the idea of combining procedural editability with learned priors is right. ([arXiv](https://arxiv.org/abs/2009.08026)) Houdini Digital Assets are the production packaging analogy: reusable node networks with promoted parameters and randomized procedural elements. ([SideFX](https://www.sidefx.com/docs/houdini/assets/intro.html)) Marmoset-style asset libraries are useful for curated material/object presets, but they are not morphology systems. ([Marmoset Toolbag Documentation](https://docs.marmoset.co/docs/introduction-to-the-library/))

4\. Feature modeling: bevels, fillets, sweeps
---------------------------------------------

Our current op.bevel is too blunt. “Bevel all sharp edges uniformly” is why the visible result feels subtle and generic.

The right model is **edge/face feature tagging**.

Example:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   edge.role = body_outer_corner  edge.exposure = silhouette  edge.material_boundary = wood_to_metal  edge.bevel = {    type: chamfer,    radius: 0.006m,    segments: 1,    normal: hard_break,    lod_min: 0  }   `

Versus:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   edge.role = painted_panel_soft_edge  edge.bevel = {    type: round,    radius: 0.002m,    segments: 3,    normal: smooth,    lod_min: 0  }   `

Houdini PolyBevel is the reference production behavior: edge/group selection, size, divisions, profile, and control over which geometry receives the bevel. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/sop/polybevel.html)) OpenSubdiv’s semi-sharp creases are useful as a render/subdivision-control concept, but they are not a substitute for explicit low-poly bevel geometry when we need game-ready silhouettes and baked normals. ([Takahito Tejima](https://takahito-tejima.github.io/OpenSubdivJpDoc/mod_notes.html)) Plasticity/CAD-style fillet behavior is the higher-end reference: variable distances, G2 continuity, conic controls, and edge-selected surface fillets. ([Plasticity Manual](https://doc.plasticity.xyz/solid/fillet-shell))

For procedural pipelines, the rule is:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   Do not author bevels per edge.  Author edge-selection rules.   `

Good edge-selection rules:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   select edges where:    role in [outer_corner, handle_edge, metal_guard_edge]    angle > 35deg    and exposed == true    and feature_scale > threshold   `

Then assign bevel policies:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   outer crate silhouette -> 0.6cm chamfer, 1 segment, hard normal  painted panel edge -> 0.2cm round, 2-3 segments, smooth normal  metal trim border -> 0.3cm chamfer, material seam preserved  tiny screw slot -> no geometry bevel; use normal map   `

### Profile sweeps

Profile sweeps should be a first-class op in v2.

A production-quality sweep needs:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   path:    curve/polyline/NURBS    may be non-planar  frame_policy:    parallel_transport / rotation-minimizing frame    optional up-vector constraint    twist control  profile:    2D cross-section    scale/rotation/material attributes along path  joins:    miter / bevel / round / capped / welded  validation:    self-intersection detection    curvature-radius check    minimum segment length    collision policy  output:    separate submesh or boolean-fused mesh   `

Houdini’s Sweep SOP is the practical reference: it copies cross-section geometry along a backbone curve, supports cross-section/spine concepts, and uses point attributes to control behavior. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/sop/sweep.html))

Important decision: **not every sweep should be boolean-fused**. Trim strips, pipes, cables, raised borders, rails, and handles can often remain separate submeshes with shared anchors. That is cheaper, cleaner for materials, and easier for LOD.

5\. Surface/material binding to geometry zones
----------------------------------------------

The current “one fused trimesh with one material region” is incompatible with production assets. We need geometry to carry semantic surface data all the way through.

The right join is:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   procedural geometry emits semantic zones  semantic zones map to material classes  material classes instantiate concrete materials  UV compiler creates islands according to zone policy  renderer/exporter binds slots/subsets/masks   `

Every generated face should know something like:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   part_id: corner_guard_03  zone_id: metal_corner_reinforcement  material_class: worn_painted_metal  uv_policy: trim_sheet_metal_edges  mask_tags: convex_wear, edge_grime  decal_allowed: false   `

And for the body:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   part_id: body_panel_front  zone_id: wooden_front_panel  material_class: oak_plank_body  uv_policy: world_scale_box_projected  mask_tags: dirt_lower, edge_wear  decal_allowed: true   `

Houdini’s material workflow is a good reference because materials can be assigned to primitives/subsets and driven by attributes or patterns. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/lop/assignmaterial.html)) Houdini material stylesheets also show the broader production idea: target geometry using conditions and override material parameters procedurally, including on instanced geometry. ([SideFX](https://www.sidefx.com/docs/houdini/shade/stylesheets.html)) Substance Designer is the material-side analogy: node-based, procedural, parametric, non-destructive materials with exposed controls and baked outputs. ([Experience League](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/getting-started/overview/overview))

For “crate metal corner reinforcements automatically inherit metal,” the class template should declare it:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   feature MetalCornerReinforcement:    material_class: metal_trim    uv_policy: trim_sheet    wear_mask: convex_edges  feature WoodenBodyPanel:    material_class: wood_body    uv_policy: world_scale_grain    grain_direction: longest_axis   `

Texel density should not be normalized by raw surface area alone. Use:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   texel_weight = world_area × feature_importance × expected_visibility   `

Base rule: pixels per meter. Overrides: hero/front/label/decal zones get higher density; undersides and hidden interiors get lower density; repeating trims use trim sheets. Houdini’s texel-density tooling reflects this production concern directly: calculate/correct density per primitive in pixels per meter and scale UVs accordingly. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/sop/labs--texel_density.html))

6\. Polygon budget
------------------

A 1m crate at 125k faces is not a geometry achievement; it is a pipeline smell.

The waste usually comes from:

1.  **Primitive tessellation defaults**Cylinders, bevel arcs, spheres, screw heads, and curves are oversegmented.
    
2.  **Serial boolean fragmentation**Each cut creates extra triangles and slivers, especially on coplanar or near-coplanar surfaces.
    
3.  **Premature bevels**Beveling before booleans multiplies topology.
    
4.  **Uniform bevel divisions**A tiny internal edge gets the same treatment as a hero silhouette edge.
    
5.  **Fusing instanced parts**Four identical brackets become four fully unique triangulated regions.
    
6.  **No planar merge pass**Flat panels remain triangulated soup.
    

Canonical mitigation:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   primitive tessellation budgets  deferred beveling  coplanar merge / planar region recovery  feature-aware bevel segment allocation  instancing until export  material-zone-preserving simplification  normal-map baking for tiny detail  LOD generated from the feature graph   `

For procedural-to-LOD, the winning answer is **both**, but not equally.

*   **LOD0/LOD1 should be generated from feature rules.**Remove small bolts, reduce bevel segments, collapse tiny brackets, simplify trim patterns, swap geometry grooves for normal maps.
    
*   **Decimation should clean up residual topology.**It should not be responsible for understanding what a crate is.
    

Simplygon is the industry-style reference for automated LOD/HLOD/batch optimization. ([Simplygon](https://www.simplygon.com/features/scripting)) Houdini Labs has one-node procedural LOD creation workflows, including baking/polyreduction/cleanup/UV/export. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/sop/labs--lod_create-2.0.html)) Houdini’s USD LOD tools also use PolyReduce-style generated variants and distance-based selection. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/lop/createlod.html))

Feature-preserving decimation is constrained simplification:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   preserve:    silhouette edges    material seams    UV seams    hard normals    bevel support edges    decal boundaries    anchor-critical geometry  collapse aggressively:    coplanar interior triangles    hidden backsides    repeated small detail    tiny bevels below screen threshold   `

CGAL’s surface simplification is the research/reference version: edge-collapse simplification with user-defined cost, placement, and constraints. ([doc.cgal.org](https://doc.cgal.org/latest/Surface_mesh_simplification/group__PkgSurfaceMeshSimplificationRef.html))

My target for a 1m crate:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   LOD0 hero:      8k–25k tris  LOD1 gameplay: 3k–8k tris  LOD2 distant:  500–2k tris  LOD3 impostor: card/proxy/baked   `

125k should be reserved for extreme close-up hero assets, not routine procedural crates.

7\. Measurement: objective visible-quality validators
-----------------------------------------------------

Our validators are currently geometry validators, not asset-quality validators. We need three layers:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   1. geometric validity     manifold, watertight, no catastrophic intersections, face budget, scale  2. semantic validity     does the asset contain required class features and relations?  3. visual validity     does it read as the intended object from rendered views?   `

For a crate, semantic validators should check:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   has bounded volume  has visible front/side/top panels  has reinforcement or readable construction detail  has material contrast between body and trim  has plausible scale  has no feature floating without support  has silhouette consistent with container/crate   `

Automated visible-quality measurement is still imperfect. Recent evaluation work for text-to-3D explicitly notes that human-aligned assessment remains underdeveloped, and newer benchmarks split quality into dimensions such as text fidelity, appearance, surface quality, material realism, and part-level/local realism. ([arXiv](https://arxiv.org/html/2502.16915v1)) ([arXiv](https://arxiv.org/html/2508.05609v1)) Gen3DEval-style work also argues that common metrics like CLIP/FID-like signals are not enough for robust 3D evaluation and proposes multi-dimensional, human-aligned scoring over rendered views and geometry signals.

For us, the practical validator stack should be:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   render 8 canonical views:    front, back, left, right, top, 3/4 views  render auxiliary passes:    normal, depth, material_id, part_id, silhouette  score:    CLIP/VLM class match    silhouette similarity to archetype bank    semantic-part presence    material-zone correctness    face-count and LOD budget    scale plausibility    visual clutter / tiny-detail ratio   `

A/B testing generator changes:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   same prompts  same seeds  old generator vs new generator  paired renders  automated scores  human review of disagreement cases  track win rate, failure modes, diversity, controllability   `

We should build a held-out benchmark set:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   25 crate prompts  25 doors  25 sci-fi panels  25 industrial machines  25 furniture pieces  25 modular environment pieces   `

For each, we store expected features, acceptable variation bands, reference silhouettes, material expectations, and human rubric labels.

The PCG Benchmark project is worth studying because it formalizes quality, diversity, and controllability as separate evaluation dimensions for procedural generation problems. ([arXiv](https://arxiv.org/html/2503.21474v1)) That split maps directly to us.

8\. Authoring & variation
-------------------------

For non-programmers, the right authoring layer is not only .lth.

We need three layers:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   1. Declarative DSL     precise, diffable, reproducible, machine-editable  2. Visual graph / template editor     non-programmer control, exposed parameters, previewable nodes  3. Natural-language / sketch assistant     fast intent capture, edits DSL/graph, proposes variants   `

The DSL remains the source of truth. The visual layer makes it usable. AI makes it faster, not magical.

Houdini Digital Assets are the reference for packaging procedural logic into reusable, parameterized tools. ([SideFX](https://www.sidefx.com/docs/houdini/assets/intro.html)) Substance Designer is the material-side analogy: graph-based, procedural, parameterized, and non-destructive. ([Experience League](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/getting-started/overview/overview))

For 100 distinct industrial crates from one .lth, we need **correlated semantic variation**, not independent random sliders.

Good variation axes:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   proportion:    squat / tall / long / stackable  construction:    slatted / paneled / welded / bolted / reinforced  reinforcement:    corner guards / edge bands / cross braces / frame cage  access:    hinged lid / removable lid / side latch / front panel  material:    wood+metal / painted steel / plastic body / worn composite  wear:    clean / chipped / dusty / oily / rusted  labeling:    warning decal / serial plate / barcode / faction mark  manufacturing style:    military / warehouse / sci-fi / dieselpunk / luxury industrial   `

Bad variation:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   randomly move handle anywhere  randomly remove all reinforcements  randomly change body silhouette until it no longer reads as container  randomly assign materials with no feature logic   `

Use constraints:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   always preserve:    bounded volume    readable access/lid/seam    scale-consistent handles/latches    corner/edge construction cues    material zones   `

Houdini PDG/TOPs and Wedge workflows are strong references for scalable variation: create work items for parameter wedges, drive networks from attributes, and batch-generate outputs. ([SideFX](https://www.sidefx.com/docs/houdini/tops/index.html)) ([SideFX](https://www.sidefx.com/docs/houdini/nodes/top/wedge.html)) Omniverse Replicator is the scene/data-generation analogy: semantic labels plus randomizers for assets, materials, lights, and cameras. ([NVIDIA Docs](https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator.html))

The product principle: **author control defines the safe manifold; procedural surprise samples inside it.**

9\. The “imagination-to-life” demo
----------------------------------

We need to stop thinking of the demo as “one prompt makes one mesh.” That puts us in direct comparison with text-to-3D systems, where we will lose on novelty and win only on editability.

The stronger demo is:

> **Natural language → editable asset family → populated mini-scene/world slice.**

Example:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   Prompt:  "Create a modular dieselpunk loading bay with 40 unique industrial crates,  metal doors, hazard decals, pipe bundles, and worn concrete floor pieces."  Output:    asset family    variations    semantic graph    material zones    LODs    decals    scene placement    validators    export package   `

This shows the thing procedural systems are actually good at: consistency, control, scale, editability, and production structure.

Pure procedural plateaus when we need broad morphology knowledge and visual taste. It can make excellent buildings, crates, modular panels, furniture families, and environments when the rule system is well-authored. But encoding every class by hand is slow.

AI adds value at the plateau by doing five specific jobs:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   1. intent parsing     prompt/sketch/reference -> structured Lathe graph  2. morphology prior proposal     "door" implies hinge line, handle height, frame, swing side  3. parameter search     choose proportions/materials/patterns that match intent  4. visual critique     render -> "does this read as an industrial crate?"  5. surface/decal ideation     labels, wear patterns, material palettes, style variants   `

AI should not be the geometry kernel. It should be the planner, prior, critic, and authoring assistant.

There are already published pipelines that cross the “looks like the thing” threshold procedurally, especially for architecture, indoor scenes, and environment-scale generation. Infinigen generates all assets procedurally from randomized mathematical rules; Infinigen Indoors extends that to furniture, architecture, appliances, and indoor arrangement with a constraint-based DSL/solver. ([arXiv](https://arxiv.org/abs/2306.09310)) ([arXiv](https://arxiv.org/abs/2406.11824)) ProcTHOR is another important reference for large-scale procedural interactive indoor environments. ([arXiv](https://arxiv.org/abs/2206.06994)) Holodeck shows the AI-augmented direction: language prompts, common-sense priors, spatial constraints, and layout optimization using existing asset sources. ([CVF Open Access](https://openaccess.thecvf.com/content/CVPR2024/html/Yang_Holodeck_Language_Guided_Generation_of_3D_Embodied_AI_Environments_CVPR_2024_paper.html))

What they have that we do not yet have:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   typed scopes  anchors  semantic constraints  material provenance  variation systems  scene-level solvers  render validators  LOD/export discipline   `

That is the gap.

10\. Reference benchmarks and systems to study
----------------------------------------------

### Study-first references by subsystem

AreaStudy firstWhyShape composition**CityEngine CGA / Infinigen Indoors**Grammar/scopes/components plus constraint-based layoutRelational placement**CityEngine component split + Houdini attributes + Infinigen constraints**The right blend of symbolic anchors and numeric transformsBoolean robustness**Manifold + libigl mesh arrangements + CGAL Nef**Practical robustness, batched-arrangement mental model, formal closure referenceFeature modeling**Houdini PolyBevel/Sweep + Plasticity/CAD fillets**Per-edge groups, profiles, sweeps, variable fillet behaviorSurface binding**Houdini USD material subsets/stylesheets + Substance Designer**Attribute-driven material binding and procedural masksVariation control**Houdini PDG/TOPs Wedge + Omniverse Replicator**Bounded parameter variation and scalable batch generationLOD**Simplygon + Houdini Labs LOD + CGAL simplification**Production automation plus constrained simplificationQuality evaluation**PCG Benchmark + Hi3DEval/T23DAQA/Gen3DEval-style metrics**Separate quality, diversity, controllability, and human alignment

### Recent papers / projects shaping the mental model

These are the ones I would put on our internal reading list:

1.  **Infinigen, CVPR 2023**Procedural generation of natural scenes and assets from randomized mathematical rules. Important because it proves large-scale procedural asset generation can work when the rule system is deep enough. ([arXiv](https://arxiv.org/abs/2306.09310))
    
2.  **Infinigen Indoors, CVPR 2024**More directly relevant to us: procedural indoor scenes, furniture, architecture, appliances, and constraint-based scene arrangement. ([arXiv](https://arxiv.org/abs/2406.11824))
    
3.  **Holodeck, CVPR 2024**Language-to-3D environment generation with object selection and spatial relational constraints. This is closer to the “imagination-to-life” direction than isolated mesh generation. ([CVF Open Access](https://openaccess.thecvf.com/content/CVPR2024/html/Yang_Holodeck_Language_Guided_Generation_of_3D_Embodied_AI_Environments_CVPR_2024_paper.html))
    
4.  **Holodeck 2.0, 2025**Uses VLMs to derive objects, spatial constraints, asset choices, and visual scene editing from images/instructions. Useful for our AI-augmentation layer. ([arXiv](https://arxiv.org/abs/2508.05899))
    
5.  **Text2CAD, NeurIPS 2024 Spotlight**Text-to-parametric CAD generation. Useful for thinking about natural language → structured CAD/feature programs, not just text → mesh. ([arXiv](https://arxiv.org/abs/2409.17106))
    
6.  **BrepGen, SIGGRAPH 2024**Direct generation of B-rep CAD models with topology/surface structure. Relevant because it shows where learned systems are moving beyond triangle soups. ([arXiv](https://arxiv.org/abs/2401.15563))
    
7.  **FutureCAD, 2026**Relevant to our feature-modeling question because it explicitly addresses how parametric CAD operations and B-rep primitives intertwine, especially for operations like fillets/chamfers that require explicit B-rep primitive selection. ([arXiv](https://arxiv.org/html/2603.11831v2))
    
8.  **ShapeAssembly, 2020**Older, but foundational for editable procedural part programs, hierarchical cuboid structure, symmetry, and learned parameter distributions. ([arXiv](https://arxiv.org/abs/2009.08026))
    
9.  **PCG Benchmark, 2025**Useful for evaluation framing: quality, diversity, and controllability should be measured separately. ([arXiv](https://arxiv.org/html/2503.21474v1))
    
10.  **T23DAQA / Hi3DEval / Gen3DEval-style 3D quality evaluation, 2025**Important because visible quality cannot be reduced to face count, manifoldness, or CLIP score. We need multi-view, part-aware, material-aware, human-aligned evaluation. ([arXiv](https://arxiv.org/html/2502.16915v1)) ([arXiv](https://arxiv.org/html/2508.05609v1))
    

The architecture I’d commit to
------------------------------

For our next serious version, I would make these changes in this order:

### 1\. Replace suffix heuristics with anchors and scopes

Build:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   Scope  Anchor  Relation  CandidatePlacement  PlacementSolver   `

Every generated feature exposes anchors. Every child feature declares required anchors.

This unlocks doors, crates, hinges, handles, brackets, trims, pipes, bolts, panels, and modular environment pieces.

### 2\. Replace per-op booleans with a lazy feature DAG

Lathe should compile to:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   FeatureGraph    primitives    transforms    relations    boolean expressions    material zones    bevel rules    sweep rules    decal rules   `

No more eager from\_trimesh per op.

### 3\. Build a batched boolean compiler

First version can still use Manifold, but per cluster:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   collect interacting primitives  convert once  apply grouped boolean expression  extract once  preserve provenance   `

Longer-term, study a libigl-style arrangement/classification pipeline for true variadic behavior.

### 4\. Make material zones first-class

Every op should emit zones, not just geometry.

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   op.corner_guard -> geometry + metal_trim zone  op.body_panel -> geometry + wood_body zone  op.decal_zone -> reserved UV/material/decal anchor   `

Exporter must output material slots/subsets, UV islands, and masks.

### 5\. Defer bevels and make them semantic

No global bevels. Use feature/edge rules:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   outer silhouette edges  material boundary edges  metal trim edges  handle grip edges  panel inset edges   `

Budget bevels by feature importance.

### 6\. Add LOD as a compiler target

LOD should be generated from feature rules first, decimation second.

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   LOD0: full geometry  LOD1: fewer bevel segments, fewer bolts  LOD2: trim baked to normals, simplified handles  LOD3: proxy/impostor   `

### 7\. Add visible-quality validators

Start with crates and doors.

For each generated asset:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   render canonical views  check class readability  check required semantic features  check material-zone correctness  check silhouette plausibility  check face budget  produce a scorecard   `

This becomes our regression harness.

Final strategic call
--------------------

The winning product is not “a faster CSG crate generator.”

The winning product is:

> **A semantic procedural asset compiler where non-programmers or AI can declare intent, the system resolves morphology and placement through typed anchors/constraints, geometry is compiled in batches, materials/UVs/LODs remain bound to meaning, and visible quality is measured from renders.**

That is the path from our current Lathe pipeline to an actual “imagination-to-life” system.

The missing piece is not “better procedural noise.” It is a **surface compiler**.

Right now our pipeline thinks:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   intent → geometry   `

It needs to think:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   intent  → morphology graph  → geometry zones  → baked geometric signals  → material/wear/decal graphs  → PBR maps  → lighting/render evaluation  → perceptual validators   `

A crate does not read as a crate because it is watertight. It reads as a crate because the geometry, edge treatment, material breakup, grime, labels, lighting response, and silhouette all agree.

11\. Surface micro-detail: the “lived-in” axis
==============================================

op.wear\_zone should not directly emit triangles. It should emit a **wear-mask recipe**.

The recipe consumes:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   curvature  convexity  concavity / AO  world-space normal  position  material class  feature role  age / condition  environment  style  random seed   `

Substance Designer’s mesh-based mask generators are the canonical production reference here. Adobe’s docs explicitly describe mask generators as black-and-white masks generated from baked maps, then used as blend masks for multi-channel materials. They also note that without baked maps “there won’t be much of a result.” ([Experience League](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/substance-graphs/nodes-reference-for-substance-graphs/node-library/mesh-based-generators/mask-generators/mask-generators)) The Metal Edge Wear node is the exact conceptual model: it uses curvature, AO, grunge, world-space normal, and position inputs, and produces scratches/chips on convex raised edges, optionally masked by AO-dark regions. ([Experience League](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/substance-graphs/nodes-reference-for-substance-graphs/node-library/mesh-based-generators/mask-generators/metal-edge-wear))

Where production wear detail lives
----------------------------------

Detail typeBest representationBreaks down whenEdge paint chipsMaterial mask + base-color/roughness/metalness changesChip removes enough volume to affect silhouetteFine scratchesRoughness + normal map + anisotropic direction noiseScratches need deep gouging or close-up hero deformationDust in seamsAO/concavity-driven mask, vertex color, or texture mapNeeds volumetric piles or gameplay interactionRust bloomMaterial-layer mask: rust color/roughness/height/normalRust changes shape, flakes, holes, or large corrosionLarge dentsGeometry or displacement/height depending on platformNormal map alone looks fake under silhouette/grazing anglesMud/paint splatterDecal layer or texture maskNeeds thick accumulation or physical dripsFastener grimeRadial AO/concavity masks around fastener anchorsFasteners are not semantically knownWorn handles/gripsContact-frequency mask driven by feature roleNo semantic “touch area” exists

So yes: **all of the above**—vertex paint, baked maps, procedural texture maps, decals, and geometry—are valid. The decision depends on visibility, silhouette impact, interaction, and LOD.

Can wear be one continuous axis?
--------------------------------

Yes for authoring, no for implementation.

We can expose:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   condition: 0.0 fresh → 1.0 derelict   `

But internally it must fan out into correlated parameters:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   condition drives:    paint_chipping_amount    paint_chipping_scale    exposed_metal_fraction    rust_probability    rust_depth    dust_accumulation    scratch_density    roughness_variance    decal_fade    color_desaturation    edge_darkening    fastener_staining    dirt_vertical_streaking   `

A good model:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   condition = 0.15    clean manufacturing scuffs    minor edge highlight    low dirt    no rust  condition = 0.45    visible convex-edge chips    panel scratches    dusty seams    slight decal fading  condition = 0.75    exposed metal at corners    rust around fasteners    dark concavity dirt    worn labels    roughness breakup  condition = 0.95    major corrosion    deep stains    missing paint regions    strong material discoloration   `

The scalar is a **control knob**. The real state is a vector.

How procedural noise stacks become readable wear
------------------------------------------------

The key is: **noise alone is not wear**.

Readable wear is:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   geometry signal × material rule × directional/environmental bias × noise   `

Example masks:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   convex_edge_wear =    curvature_convex    × exposed_surface    × paint_layer_present    × noise_threshold(condition)    × feature_importance  concave_dirt =    ambient_occlusion    × concavity    × bottom_gradient    × dustiness    × low_frequency_noise  rust_around_fasteners =    metal_present    × fastener_anchor_radius_mask    × humidity    × concavity_or_leak_path    × rust_noise  vertical_streaks =    rain_exposure    × downward_flow_field    × position_gradient    × streak_noise   `

So op.wear\_zone should become something like:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   op.wear_zone {    target: material_class == painted_steel    condition: 0.65    environment: humid_industrial    masks:      convex_edge_chipping: high      concave_dirt: medium      fastener_rust: medium      scratches: low      decal_fade: medium  }   `

This should compile to masks, not immediate geometry.

12\. PBR material authoring tied to procedural geometry
=======================================================

Our op.material\_zone = painted\_steel currently means almost nothing. It needs to resolve to a **material graph with exposed parameters and geometry-driven masks**.

Production PBR is map-channel based. Adobe’s PBR guide frames PBR as a methodology, not one fixed standard, and calls out the common metal/roughness and specular/glossiness workflows. ([Adobe](https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2)) Substance’s PBR Render node expects channels such as base color, normal, roughness, metallic, height, AO, opacity, anisotropy, translucency, and others. ([Experience League](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/substance-graphs/nodes-reference-for-substance-graphs/node-library/material-filters/pbr-utilities/pbr-render))

Canonical production-scale pipeline
-----------------------------------

For us, the practical pipeline should be:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   1. Generate geometry with semantic zones.  2. Preserve part_id / feature_id / material_class / zone_id.  3. Bake geometric support maps:     normal     world normal     AO     curvature     convexity/concavity     position     thickness     material ID     feature ID  4. Feed those maps into material graphs.  5. Material graphs produce:     base color     ORM / occlusion-roughness-metallic     normal     height     emissive     masks     decals  6. Atlas, trim-sheet, or bind as material slots.   `

Houdini Labs Simple Baker is a useful reference because it can bake vertex color, tangent normals, roughness, metallic, world normals, AO, curvature, thickness, position, height, and custom channels. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/sop/labs--simple_baker-2.0.html)) Marmoset similarly treats AO as a source for ambient shadowing and texturing masks, and supports bent normals for lighting approximation. ([Marmoset Toolbag Documentation](https://docs.marmoset.co/docs/map-types/))

Substance graph, Houdini COPs, code noise, or neural textures?
--------------------------------------------------------------

My recommendation:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   core production materials:    authored procedural material graphs  runtime/export representation:    baked PBR textures + optional shader params  procedural generation side:    code-side masks + graph invocation  AI/neural textures:    ideation, decals, rare custom detail, not source of truth   `

Why: deterministic procedural material graphs are controllable, styleable, and testable. Neural texture generation can help make one-off labels, alien glyphs, graffiti, or concept variations, but it is currently the wrong foundation for a reproducible asset compiler.

Substance supports exposing parameters on graphs, which is exactly what we need for condition, color, wear amount, rust amount, and style controls. ([Experience League](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/substance-graphs/manage-parameters/exposing-a-parameter)) MaterialX is also relevant as a portable shader/material graph standard; its PBR spec describes standardized shader-semantic nodes for layered rendering graphs. ([GitHub](https://github.com/AcademySoftwareFoundation/MaterialX/blob/main/documents/Specification/MaterialX.PBRSpec.md)) Houdini’s Copernicus/COP network is the code/DCC-side analogue: image/layer manipulation in a 3D-aware node context. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/cop/index.html))

How to get correlated maps
--------------------------

Do **not** generate base color, roughness, metallic, and normal independently.

Use shared masks:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   paint_mask  metal_exposure_mask  rust_mask  edge_wear_mask  dirt_mask  scratch_mask  decal_mask  oil_stain_mask   `

Then each PBR channel derives from those masks:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   base_color =    blend(paint_color, raw_metal_color, metal_exposure_mask)    + dirt_color * dirt_mask    + rust_color * rust_mask  metallic =    raw_metal_mask * metal_exposure_mask    + base_metallic_by_material  roughness =    base_roughness    + dust_roughness_boost * dirt_mask    + rust_roughness_boost * rust_mask    - polished_edge_smoothing * contact_wear_mask  normal =    baked_geometry_normal    + scratch_normal    + rust_pitting_normal    + wood_grain_normal  height =    paint_layer_height    - chip_depth * metal_exposure_mask    + rust_bloom_height * rust_mask   `

That is how “painted steel” starts to look like painted steel rather than a gray shader.

Binding between geometry-zone tags and material sets
----------------------------------------------------

Use a three-level binding:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   material_class:    painted_steel    raw_steel    oak_wood    brass_fittings    rubber_grip  material_archetype:    painted_steel.utility_industrial    painted_steel.sci_fi_clean    painted_steel.abandoned_rusty  material_instance:    concrete graph parameters for this generated asset   `

Example:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   zone body_panel_front:    material_class: painted_steel    style: utility_industrial    condition: 0.55    graph: Mat/PaintedSteel    params:      paint_color: palette.body_primary      edge_wear: from curvature      dirt: from concavity      decal_slots: allowed  zone corner_guard:    material_class: raw_steel    style: utility_industrial    condition: 0.7    graph: Mat/ExposedSteel    params:      polish_on_convex_edges: true      rust_near_fasteners: true   `

Houdini’s Material SOP shows the production pattern: assign materials to primitive groups and override material parameters per primitive. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/sop/material.html)) Houdini stylesheets go further by targeting geometry and overriding materials or material parameters at render time, including for instanced/packed geometry. ([SideFX](https://www.sidefx.com/docs/houdini/shade/stylesheets.html))

So our surface binding should be:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   geometry zone tags  → material class  → style-specific material archetype  → graph params  → baked maps / material slots / shader params   `

Not per-asset manual assignment.

13\. Lighting-aware design
==========================

Yes, procedural assets should be evaluated under standardized lighting rigs.

A bad renderer can make a good asset look bad. A flattering renderer can hide a bad asset. We need both neutral validation and presentation validation.

Evaluation rigs we should standardize
-------------------------------------

Use four fixed render setups:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   1. Neutral studio     gray background     HDRI or soft area light     no dramatic contrast     checks material honesty  2. Three-point product rig     key + fill + rim     checks silhouette, bevel readability, specular response  3. Outdoor gameplay rig     sun + sky     checks engine/world lighting plausibility  4. Low-key rim rig     dark fill, strong rim     checks silhouette and edge highlights   `

Marmoset Toolbag’s docs are a useful production reference here: its lighting system supports HDRI sky lighting with custom or preset panoramic HDR images. ([Marmoset Toolbag Documentation](https://docs.marmoset.co/docs/lighting/)) We do not have to use Marmoset specifically, but we need the same discipline: fixed cameras, fixed lights, fixed exposure, fixed FOV, fixed tonemapping.

Geometry detail vs normal-map cutoff
------------------------------------

Use a projected-size rule, not just polygon budget.

Approximate projected pixel width:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   pixels ≈ feature_world_width × screen_height_px           / (2 × camera_distance × tan(vertical_fov / 2))   `

For a 1080p render, 60° vertical FOV, camera at 2m:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   0.6cm chamfer:    0.006 × 1080 / (2 × 2 × tan(30°))    ≈ 2.8 px  0.2cm round:    0.002 × 1080 / (2 × 2 × tan(30°))    ≈ 0.9 px   `

My rule:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   < 1 px:    texture/normal/roughness only  1–2 px:    depends on silhouette, material gloss, hero distance  > 2 px:    geometry if visible, exposed, or specularly important  silhouette feature:    geometry even if small, when it affects object outline  flat internal surface detail:    normal/height/roughness unless hero-close   `

This lines up with common game-art practice: large bevels that affect silhouette should be modeled, while smaller detail can be baked or represented through maps. A Polycount discussion summarizes the practical rule: if the bevel is large enough in real life or viewed close enough in game, preserve the silhouette with geometry; smaller objects/details can rely more on baking. ([polycount](https://polycount.com/discussion/215555/bevel-chamfer-edges-vs-normal-map-bake))

Smoothing, normals, and why chamfers read
-----------------------------------------

A hard cube with no bevel has no highlight-catching face. A smoothed cube without geometry has fake rounded shading but the same square silhouette. A good game prop usually needs:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   actual small bevel face  + controlled vertex normals  + correct hard/soft edge policy  + normal map detail  + roughness breakup   `

Modo’s vertex-normal docs capture the principle: vertex normals and hard/soft edges control mesh shading, help low-resolution meshes appear higher-poly, and reduce hard-angle artifacts. ([Foundry Learn](https://learn.foundry.com/modo/content/help/pages/uving/vertex_map_tools.html))

For us:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   silhouette bevel:    geometry chamfer + weighted/controlled normals  tiny panel-line bevel:    normal map + AO crease  material seam:    hard normal or split if needed for shading/UV/material correctness  large soft industrial edge:    geometry bevel with 2–3 segments if close/hero  distant LOD:    collapse bevel geometry, bake highlight into normal/roughness   `

A chamfer “reads” at 2m when it catches a stable highlight. That usually means it has at least one bevel face large enough to occupy multiple pixels and a material roughness low enough for the highlight to be visible.

14\. Visual identity / art direction without an art director
============================================================

We cannot replace art direction with random seeds. We need a **style codex**.

A style codex is a machine-readable art bible:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   style: utility_industrial    silhouettes:      blocky      rectangular      functional protrusions      low ornament    proportions:      thick frames      reinforced corners      visible fasteners      panelized surfaces    materials:      painted steel      raw steel      rubber      warning decals      concrete dust    palette:      desaturated yellow      dark gray      worn black      hazard orange    wear:      convex edge chipping      dust in seams      rust near fasteners      oil stains near moving parts    motifs:      bolts      stamped labels      warning stripes      latches      handles   `

And another:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   style: alien_grove    silhouettes:      organic asymmetry      bulbous growth      ribbed arcs    materials:      bark-like shell      translucent resin      bioluminescent seams    palette:      moss green      violet shadows      warm inner glow    wear:      pollen dust      organic scars      damp crevices    motifs:      tendrils      vein patterns      seed pods      radial symmetry   `

Substitute for an art director
------------------------------

We need three things:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   1. Reference library     images, existing assets, materials, palette boards  2. Style codex     explicit constraints and allowed motifs  3. Style validator     render-based scoring against class + style expectations   `

Reference images help discover and tune parameter ranges. They should not be the live source of truth. The source of truth should be a style rule set.

CityEngine’s CGA styles are a useful formal analogy: a style is a saved set of attribute values that can be managed and reused for a rule. ([ArcGIS](https://doc.arcgis.com/en/cityengine/2024.1/help/help-rules-styles.htm)) Omniverse Replicator is useful as a randomization analogy: it varies scene parameters such as pose, scale, lighting, color, texture, and material appearance within a controlled simulation setup. ([NVIDIA Docs](https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator/randomizer_details.html))

Maintaining consistency across hundreds of assets
-------------------------------------------------

Production consistency comes from central systems:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   central palette  central material library  central trim sheets  central decal library  shared motifs  shared proportion rules  style-specific wear rules  validator gates  review queue for outliers   `

For us:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   AssetClass = what the object is.  StyleCodex = what world it belongs to.  Condition = how new/old/damaged it is.  Generator = how to instantiate that combination.   `

Class shape rules vs style overlay rules
----------------------------------------

Separate them strictly.

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   crate class rules:    bounded volume    panels    access/lid/seam    reinforcement    stackability cues    handles/latches optional    material zones  industrial style overlay:    metal corners    hazard decals    welded seams    bolted plates    yellow/gray palette    chipped paint  fantasy style overlay:    wood planks    brass straps    carved symbols    leather handles    warm palette  sci-fi style overlay:    inset panels    emissive strips    beveled plates    hex fasteners    clean material separation  abandoned condition overlay:    dust    rust    chipped labels    dark concavities    broken/missing pieces   `

The style overlay can modify feature choices, materials, motifs, and wear. It should not violate class invariants. A sci-fi crate still needs to read as a crate.

15\. Perceptual measurement: “does this look like a crate?”
===========================================================

A flat-shaded watertight cube should fail. Not because it is geometrically invalid, but because it lacks category evidence.

We need a **category-conditioned visual rubric**.

What works in practice
----------------------

MetricUseful forFailure modeCLIP similarity to “crate”Cheap first-pass class signalOften shallow; can reward texture/label over structureLPIPS / perceptual diffRegression against fixed golden rendersBad for valid variationSilhouette comparisonShape family consistencyMisses materials/featuresVLM rubric scoringCategory, style, material, feature judgmentNeeds prompt discipline and calibrationHuman pairwise votingGold standard for generator changesSlow/costlyAesthetic classifierGeneral polishNot class-specificSemantic segmentation / part detectionRequired feature presenceRequires training or strong heuristics

The current research trend supports multi-dimensional evaluation rather than one magic scalar. T23DAQA explicitly frames text-to-3D asset evaluation around subjective ratings for quality, authenticity, and text-asset correspondence, using 969 validated 3D assets from 170 prompts. ([arXiv](https://arxiv.org/abs/2502.16915)) Gen3DEval evaluates text fidelity, appearance, and surface quality from rendered views and surface normals, and reports better alignment with user preferences than task-agnostic models. ([CVF Open Access](https://openaccess.thecvf.com/content/CVPR2025/html/Maiti_Gen3DEval_Using_vLLMs_for_Automatic_Evaluation_of_Generated_3D_Objects_CVPR_2025_paper.html)) Eval3D similarly uses multiple interpretable dimensions such as geometric inconsistency, structural consistency, semantic consistency, text-3D alignment, and aesthetics. ([Eval3D](https://eval3d.github.io/)) 3DGen-Bench is also relevant because it builds a human-preference dataset and automated scoring models aligned with human judgments. ([arXiv](https://arxiv.org/html/2503.21745v1))

Is there a published “score this as a crate” metric?
----------------------------------------------------

Not in the exact form we need.

The closest anchors are:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   T23DAQA:    multi-dimensional asset quality / authenticity / text correspondence  Gen3DEval:    rendered-view + surface-normal quality evaluation  Eval3D:    interpretable multi-aspect 3D generation evaluation  3DGen-Bench:    human-preference-based scoring for generated 3D models   `

But I would not rely on any of them as a crate-readability oracle. We need to build our own category-conditioned evaluator.

For crates, the rubric should be:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   crate_readability:    0 = cube/box only; no crate cues    1 = box with minor surface detail    2 = recognizable container, weak construction detail    3 = clear crate: panels/reinforcement/handles/latches/materials    4 = strong production asset: class + style + wear + material zones  required_feature_presence:    bounded volume    panel breakup    reinforcement    access/lid/seam cue    plausible scale    material separation  style_compliance:    industrial / sci-fi / fantasy / abandoned etc.  surface_quality:    non-sterile but not noisy    readable PBR    believable wear placement  geometry_quality:    no slivers, bad normals, broken bevels, floating pieces  budget_quality:    acceptable tris, UVs, texture density, LODs   `

CI-level visual regression
--------------------------

Use three layers:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   1. Deterministic golden checks     same seed, same generator, compare:       silhouette       normals       material IDs       depth       rendered image       face count       UV density  2. Perceptual regression     compare canonical renders using:       LPIPS / DreamSim-like image distance       silhouette IoU       normal-map difference       material-zone difference  3. Rubric scoring     VLM/classifier/human spot checks:       "Does this read as an industrial crate?"       "Are the metal reinforcements metal?"       "Is wear placed on plausible edges/seams?"   `

Important: golden-image comparison catches accidental breakage. It does **not** measure generator improvement. For improvement, use paired A/B testing:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   same prompts  same seeds  old generator vs new generator  multi-view renders  rubric score  human review for disagreement cases   `

16\. Geometry-detail vs surface-detail boundary
===============================================

This is the rule we should encode:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   A feature becomes geometry if it affects silhouette, contact, shadow, parallax,  interaction, collision, or close-range specular highlights.  A feature becomes texture/normal/roughness if it is sub-pixel, repeated,  surface-local, non-interactive, and does not change the outline.   `

Polygon budget matters, but it is not the primary rule. **Silhouette and lighting response matter more.**

Practical decision table
------------------------

FeatureLOD0 / closeLOD1 / gameplayLOD2+ / distanceCrate lid seamGeometry inset if readableNormal + AO crease or simplified grooveAlbedo/roughness/AO lineLarge handleGeometryGeometry simplifiedProxy or baked silhouette if distantCorner bracketGeometry, separate submeshGeometry simplifiedNormal/trim-sheet impressionRivet headGeometry if large/edge/heroNormal stamp if smallTexture dot or removedScrew slotNormal/heightNormal/roughnessRemovedFine scratchesRoughness + normalRoughness onlyRemoved/noisePaint chipsMaterial maskMaterial maskSimplified maskDust in seamsAO/concavity maskAO/roughnessBaked darkeningRust around fastenerMaterial mask + height/normalMaterial maskColor/roughness onlyDeep dentGeometry or displacementNormal/heightRemoved or dark patchDecalTexture/decal planeTexture/decal atlasMerged/bakedCable/pipeGeometrySimplified geometryRemoved/proxy unless silhouette-importantEmbossed logoGeometry if heroNormal/heightTexture only

Lid seam: geometry, normal line, or AO crease?
----------------------------------------------

For our crate:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   LOD0:    geometric inset or groove if seam is class-defining  LOD1:    shallow groove or normal-map seam  LOD2:    normal/AO line  LOD3:    albedo/roughness line or removed   `

A lid seam is semantically important because it tells the viewer “this is a container that opens.” So it deserves geometry at close range even if it is small.

Rivet: geometry or normal bump?
-------------------------------

Decision rule:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   if projected diameter > 2 px and visible on silhouette/grazing surface:    geometry  if projected diameter 1–2 px:    geometry only for hero/front/interaction zones  if projected diameter < 1 px:    normal/height/roughness stamp  if repeated many times:    use trim sheet / normal stamps / instancing  if collision/interaction relevant:    geometry   `

Rivets along a crate’s front edge may need geometry because they catch rim light. Tiny rivets on a rear panel do not.

Can the boundary be inferred automatically?
-------------------------------------------

Partly.

We can infer it if each feature carries metadata:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   feature:    role: rivet    physical_size: 0.012m    class_importance: medium    style_importance: high    silhouette_relevance: maybe    interaction: none    material_boundary: false    expected_camera_distance: 2m    lod_policy: auto   `

Then the compiler computes:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   projected_px  silhouette_overlap  expected_visibility  material/gloss importance  feature count  budget pressure  LOD target   `

And chooses:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   geometry  normal stamp  height map  roughness/base-color only  remove   `

But the policy still needs human/product decisions at the class/style level. The compiler can decide “this rivet is too small for geometry,” but only the class/style system can know that “visible fasteners are important to industrial style.”

So the right model is:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   human/authored policy:    which feature types matter for class/style  automatic compiler:    how each feature is represented at this LOD/camera/budget   `

What we should build next
=========================

We should add a **Surface & Perception Compiler** next to the Geometry Compiler.

New core data carried by every face/feature
-------------------------------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   part_id  feature_id  zone_id  material_class  style_role  wear_role  uv_policy  lod_importance  decal_allowed  contact_role  exposure_role   `

Required baked maps
-------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   normal  world_normal  ambient_occlusion  curvature  convexity  concavity  position  thickness  material_id  feature_id  zone_id  object_space_gradient   `

New op semantics
----------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   op.material_zone:    assigns material class and graph params  op.wear_zone:    emits wear mask recipe  op.decal_zone:    reserves UV/decal placement surface  op.surface_detail:    declares scratches, dents, dust, rust, paint chips  op.lighting_eval:    declares required render rigs  op.style:    binds class morphology to visual language   `

Example:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   op.material_zone {    target: body_panels    material_class: painted_steel    graph: PaintedSteel    params:      paint_color: style.palette.body_primary      roughness: 0.58  }  op.wear_zone {    target: body_panels    condition: 0.62    rules:      convex_edge_chipping: 0.7      concave_dirt: 0.5      vertical_streaking: 0.25      scratch_density: 0.35  }  op.material_zone {    target: corner_reinforcements    material_class: raw_steel    graph: WornSteel    params:      edge_polish: 0.4      rust_near_fasteners: 0.5  }   `

The new asset scorecard
-----------------------

Every generated crate should produce:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   geometry:    watertight / non-watertight intentional    triangle count by LOD    bad normal count    bevel count    planar waste  surface:    material zone coverage    PBR map completeness    texel density    edge wear plausibility    concavity dirt plausibility    decal placement validity  visual:    class readability    style compliance    silhouette readability    non-sterility score    over-noise score    lighting response score   `

Houdini’s texel-density tool is a good operational reference: it computes texel density per primitive in pixels per meter and can scale UVs to match a target, which is exactly the kind of compiler-level consistency we need. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/sop/labs--texel_density.html))

Final strategic call
====================

We should stop treating “looks like a crate” as a geometry problem.

The next version should be:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   semantic geometry  + zone-aware material binding  + baked geometric support maps  + procedural PBR graph generation  + condition/style wear masks  + LOD-aware geometry-vs-texture decisions  + standardized render rigs  + category-conditioned perceptual validators   `

op.wear\_zone should compile to masks.op.material\_zone should compile to real PBR maps.op.style should constrain silhouette, motifs, palette, materials, and wear.The renderer should become part of validation, not an afterthought.

That is how we move from **CAD-clean procedural boxes** to **production-readable game assets**.

My answer: **Lathe’s next move is to make the construction graph executable.**

Right now Lathe has the right _objects_—typed nodes, typed edges, knowledge packs, staged compiler, evidence validators—but the graph is still too descriptive. The decisive shift is:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   intent graph as metadata  → executable semantic construction graph  → placement bindings  → feature programs  → zone-preserving topology  → engine/runtime contract   `

The no-family-dispatch constraint is fine. We do **not** need if family == "door". But family-blind cannot mean morphology-blind. The morphology has to live in declarative packs that the generic synthesizer executes.

The next four contracts we should add
=====================================

I would add these before chasing more visual polish:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   1. lathe.shape.placement_binding_v1     Turns construction-graph edges into authoritative transforms, anchors, cuts, and proof.  2. lathe.knowledge.morphology_profile_v1     Adds typed body/part/anchor expectations to FamilyAlias / CompositionPolicy without code branches.  3. lathe.surface.zone_binding_v1     Preserves intent zones through topology into material subsets, UV groups, decals, and PBR maps.  4. lathe.runtime.asset_contract_v1     Carries LODs, interfaces, rigs, physics, sockets, nav/audio/light metadata, and engine adapters.   `

Everything else should hang off these.

1\. Make Stage 5/6 honor typed edges as placement constraints
=============================================================

Stage 5 and 6 should stop emitting “geometry with edge metadata” and start emitting **placement bindings**.

The right split:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   Stage 5: emit_node_ops    - create symbolic geometry    - create local scopes    - emit candidate anchors    - emit face/edge/corner roles    - emit material/wear/physics/rig intent tags  Stage 6: emit_edge_ops    - resolve typed graph edges into transforms    - choose source/target anchors    - validate orientation, clearance, support, penetration    - emit boolean dependencies if needed    - emit placement proof   `

The canonical formulation is: **CGA-style component/face decomposition for anchor generation, finite-domain constraint solving for placement resolution.** CityEngine’s CGA component split is the right mental reference because it decomposes shapes into geometric components and applies operations to those components; Houdini’s instancing model is the right numeric reference because point attributes such as transform/orient/N/up/pscale drive placement of copied geometry. ([ArcGIS](https://doc.arcgis.com/en/cityengine/2025.0/help/help-component-split.htm?utm_source=chatgpt.com))

The contract for an edge
------------------------

An attached\_to edge should lower to this:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "edge_id": "edge_bracket_07_to_body",    "relation": "attached_to",    "source_node": "bracket_07",    "target_node": "primary_volume",    "source_anchor_selector": {      "role": "mounting_back_face"    },    "target_anchor_selector": {      "role": "exterior_corner",      "index": 3    },    "constraints": {      "normal_policy": "opposed",      "clearance_m": 0.002,      "allow_penetration_m": 0.0005,      "orientation_candidates": 4,      "support_required": true    },    "result": {      "source_anchor_id": "bracket_07.back",      "target_anchor_id": "body.corner_NE_top",      "transform_world": "...",      "constraint_residual_m": 0.0001,      "valid": true    }  }   `

So the edge does not directly say “place this at X.” It says:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   source anchor must satisfy relation to target anchor  → resolver chooses anchor pair + orientation  → emits transform + proof   `

Relation semantics
------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   attached_to:    source attachment plane touches target anchor plane.    Normals usually oppose. Optional penetration for weld/seam.  inset_into:    source face/volume occupies a bounded region on host face.    Usually creates cut dependency or panel groove.  wraps_around:    source feature binds to multiple adjacent anchors/faces.    Example: L-corner bracket wraps around two or three body faces.  aligned_with:    source axis/frame aligns with target axis/frame.    Does not necessarily imply contact.  mirrors:    source placement is derived from another placement through a mirror plane.  supports:    source must be below/supporting target with load path proof.  cuts:    source volume participates in boolean difference against target.   `

Solver choice
-------------

For asset-level synthesis, use this order:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   1. exhaustive candidate generation  2. hard constraint rejection  3. soft scoring  4. deterministic tie-break or seeded sample   `

Do **not** start with beam search for crates, doors, panels, terminals. It is overkill. Beam search belongs at scene scale when the number of possible layouts explodes.

2\. Extend FamilyAlias with typed morphology, not family branches
=================================================================

The key line: **family-blind does not mean family-ignorant.**

Today:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   FamilyAlias:    family → style, policies, domain   `

Extend it to:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   FamilyAlias:    family → style, policies, domain, morphology_profile_id   `

Then MorphologyProfile carries typed morphology:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "id": "swing_door_morphology_v1",    "body": {      "archetype": "vertical_panel",      "expected_aspect": {        "long_axis": "Z",        "width_m": [0.7, 1.3],        "height_m": [1.8, 2.4],        "thickness_m": [0.04, 0.18]      }    },    "parts_ladder": [      {"role": "primary_panel", "required": true},      {"role": "hinge_line", "required": true},      {"role": "handle", "required": true},      {"role": "frame", "required": false},      {"role": "lock_plate", "required": false}    ],    "anchor_emitters": [      {        "role": "hinge_anchor",        "selector": "long_vertical_edge",        "side_candidates": ["left", "right"]      },      {        "role": "handle_anchor",        "selector": "front_face",        "height_m": [0.85, 1.15],        "opposite_of": "hinge_anchor"      }    ],    "default_relations": [      {        "source_role": "hinge",        "relation": "attached_to",        "target_role": "hinge_anchor"      },      {        "source_role": "handle",        "relation": "attached_to",        "target_role": "handle_anchor"      }    ]  }   `

The synthesizer remains generic. It only knows how to execute:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   body archetypes  part ladders  anchor emitters  relation templates  placement constraints  style overlays   `

It never needs:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   if family == "door":      ...   `

Crate becomes another profile:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "id": "container_crate_morphology_v1",    "body": {      "archetype": "bounded_volume",      "expected_aspect": {        "long_axis": "X_or_Y",        "height_fraction": [0.35, 0.9]      }    },    "parts_ladder": [      {"role": "primary_volume", "required": true},      {"role": "side_panels", "required": true},      {"role": "corner_reinforcement", "required": true},      {"role": "lid_seam", "required": true},      {"role": "handle_or_latch", "required": false},      {"role": "label_zone", "required": false}    ],    "anchor_emitters": [      {"role": "exterior_corner", "selector": "all_box_corners"},      {"role": "side_face_center", "selector": "major_side_faces"},      {"role": "lid_seam_path", "selector": "top_face_inset_loop"}    ]  }   `

This is the correct replacement for \_KIND\_ASPECT.

3\. ShapeIR v2: next-tier feature ops
=====================================

We should not add “full CAD fillets everywhere” first. With manifold3d as the lowering target, the next ops should create **authored-grade hard-surface structure** while keeping lowering tractable.

The priority ops:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   op.scope_split  op.face_component_split  op.anchor_emit  op.panel_inset  op.panel_extrude  op.edge_group_select  op.weighted_bevel  op.trim_sweep  op.profile_sweep  op.fastener_pattern  op.boolean_group  op.material_subset  op.decal_project  op.lod_policy   `

The must-have geometry ops
--------------------------

### op.panel\_inset

This is more important than variable-radius fillets.

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "op": "op.panel_inset",    "target": "body.front_face",    "margin_m": 0.04,    "depth_m": 0.015,    "bevel_policy": "panel_soft",    "material_zone": "painted_body_panel"  }   `

This creates doors, crates, sci-fi panels, terminals, crates lids, access panels, and mechanical housings.

### op.edge\_group\_select

Beveling should be driven by selected semantic edge groups, not “all sharp edges.”

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "op": "op.edge_group_select",    "name": "hero_silhouette_edges",    "where": {      "angle_gt_deg": 35,      "exposed": true,      "role_in": ["outer_corner", "panel_border", "handle_edge"]    }  }   `

### op.weighted\_bevel

Houdini PolyBevel is the reference behavior here: selected edge/group input, divisions, profile, and separate groups for generated bevel faces. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/sop/polybevel.html?utm_source=chatgpt.com))

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "op": "op.weighted_bevel",    "edge_group": "hero_silhouette_edges",    "radius_m": 0.006,    "segments": 1,    "profile": "chamfer",    "normal_policy": "hard_break",    "zone_policy": "inherit_or_boundary"  }   `

### op.profile\_sweep / op.trim\_sweep

Houdini Sweep is the right production reference: cross-section curve + spine curve → surface. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/sop/sweep.html?utm_source=chatgpt.com))

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "op": "op.trim_sweep",    "path": "lid_seam_path",    "profile": "u_channel_small",    "frame_policy": "parallel_transport",    "join_policy": "miter",    "material_zone": "brass_trim",    "fuse_policy": "separate_submesh"  }   `

Important: trims, cables, handles, rails, and decorative sweeps should often remain **separate submeshes**, not boolean-fused. That keeps lowering cheaper and material zones cleaner.

### op.boolean\_group

Instead of serial booleans:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   body = (((box - cut1) - cut2) - cut3) ...   `

emit:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "op": "op.boolean_group",    "target": "body",    "operation": "difference",    "cutters": ["cut_01", "cut_02", "cut_03", "cut_04"],    "evaluation": "batched"  }   `

Manifold is still useful because it is designed for robust manifold triangle-mesh booleans and material/property mapping, but Lathe should reduce the number of times it materializes intermediate meshes. ([ManifoldCAD](https://manifoldcad.org/docs/html/?utm_source=chatgpt.com)) A libigl-style arrangement mindset is also worth studying because it resolves triangle intersections into a unified mesh arrangement before classifying the result, and variadic booleans can reduce many inputs to one call. ([libigl](https://libigl.github.io/tutorial/?utm_source=chatgpt.com))

What not to prioritize yet
--------------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   full variable-radius CAD fillets:    high value, high kernel pain  true B-rep shelling:    high value, probably not compatible with current manifold lowering  freeform loft networks:    useful, but lower priority than panels/sweeps/edge groups   `

For now, we want **weighted chamfers, panel insets, swept trims, fastener patterns, and batched booleans**.

4\. Polygon waste: where it lives and what to do
================================================

A 1m crate at 125k faces means several stages are leaking budget.

Likely sources:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   shape stage:    primitive tessellation defaults too high  topology stage:    serial booleans create slivers and fragmented planar regions  feature stage:    bevel segments applied uniformly  execution stage:    repeated manifold conversion/copy/materialization  optimize stage:    decimation arrives too late and has no feature semantics   `

The canonical mitigation
------------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   1. Primitive tessellation budget by LOD and projected size.  2. Batch booleans by spatial cluster.  3. Defer bevels until after booleans.  4. Use semantic edge groups for bevels.  5. Keep repeated details instanced or separate.  6. Merge coplanar planar regions.  7. Generate LODs from ShapeProgram first, decimate second.   `

Do **not** rely on topology-stage decimation of one fused mesh to make LOD0–3. That loses feature intent. The correct approach is:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   synth emits per-LOD ShapeProgram variants  → topology compiles each LOD  → decimator cleans residual topology   `

Houdini’s LOD tooling and Unity’s LOD systems both reflect the production split: LODs are alternative representations that engines select by distance/screen size, while tools can also use poly-reduction to generate lower detail versions. ([SideFX](https://www.sidefx.com/docs/houdini/nodes/lop/createlod.html?utm_source=chatgpt.com)) Simplygon’s docs also distinguish richer “LOD recipe” workflows from simple reduction interfaces, which supports the idea that LOD should be authored/configured, not just blindly decimated. ([Simplygon](https://documentation.simplygon.com/SimplygonSDK_10.2.8400.0/ue5/quickstarts/createlods/lodoverview.html?utm_source=chatgpt.com))

LOD policy example
------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "lod_policy": {      "LOD0": {        "bevel_segments": 2,        "fasteners": "geometry",        "panel_grooves": "geometry",        "target_tris": 18000      },      "LOD1": {        "bevel_segments": 1,        "fasteners": "normal_stamp",        "panel_grooves": "shallow_geometry",        "target_tris": 6000      },      "LOD2": {        "bevel_segments": 0,        "fasteners": "texture",        "panel_grooves": "normal_ao",        "target_tris": 1500      },      "LOD3": {        "representation": "proxy_or_impostor",        "target_tris": 300      }    }  }   `

The synthesizer should own this because it knows which features are class-critical.

5\. Material zones must survive topology
========================================

op.material\_zone and op.decal\_zone cannot remain post-fusion wishes. They need to become **face provenance and subset instructions**.

The topology stage should preserve:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   source_node_id  source_feature_id  source_face_role  zone_id  material_class  uv_policy  decal_allowed  wear_role   `

Then the surface stage groups final faces by:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   (material_class, material_instance, uv_policy, decal_policy)   `

For USD, this maps naturally to UsdGeomSubset, which encodes face subsets and can have materials bound to those subsets. ([OpenUSD](https://openusd.org/dev/api/class_usd_geom_subset.html?utm_source=chatgpt.com)) For glTF, the practical export target is separate mesh primitives or submeshes with material indices; glTF is a runtime asset delivery format with nodes, meshes, materials, transforms, cameras, and animations, and mesh primitives reference materials. ([Khronos Registry](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html?utm_source=chatgpt.com))

Example: painted steel + brass brackets + warning decal
-------------------------------------------------------

Input intent:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "zones": [      {        "target": "primary_volume.body_panels",        "material_class": "painted_steel",        "uv_policy": "box_projected_worldscale"      },      {        "target": "corner_brackets",        "material_class": "aged_brass",        "uv_policy": "trim_sheet_metal"      },      {        "target": "front_face.warning_marker",        "material_class": "decal_warning",        "uv_policy": "decal_patch"      }    ]  }   `

Output:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   mesh primitive / USD subset 0:    painted steel body    PBR maps: basecolor, normal, ORM, curvature/AO-derived wear  mesh primitive / USD subset 1:    brass brackets    PBR maps: brass base, roughness tarnish, edge polish  mesh primitive / USD subset 2:    decal zone    decal atlas region, alpha/mask, dirt/fade overlay   `

Use existing surface substrate like this
----------------------------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   surface_backend:    invokes map generators / graph backends  surface_policy:    maps material_class + visual_language + condition to graph params  decal_library:    maps decal_role + style + asset scale to decal candidates   `

Substance Designer’s mesh-based generators are the correct reference model because they process baked maps such as normal, curvature, and ambient occlusion; Substance mask generators use those baked maps as blend masks for multi-channel materials. ([Experience League](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/substance-graphs/nodes-reference-for-substance-graphs/node-library/mesh-based-generators/mesh-based-generators?utm_source=chatgpt.com)) Exposed graph parameters are also important because Lathe needs to drive material condition, color, rust, dirt, and wear from deterministic pack data. ([Experience League](https://experienceleague.adobe.com/en/docs/substance-3d-designer/using/substance-graphs/manage-parameters/exposing-a-parameter?utm_source=chatgpt.com))

The rule: **surface maps derive from shared masks**, not independent noise.

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   edge_wear_mask  concavity_dirt_mask  rust_mask  paint_chip_mask  decal_fade_mask  scratch_mask   `

Those masks drive base color, roughness, metallic, normal, and height together.

6\. Validators must test category evidence, not only geometry
=============================================================

The current failure is predictable: a featureless cube can be geometrically valid and still fail as an asset.

Lathe needs a **Class Anchor Validator**.

For a crate, it should require evidence like:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   bounded volume  panel breakup  lid/access seam  corner or edge reinforcement  material separation  scale plausibility  nontrivial silhouette or surface construction cues   `

For a door:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   vertical panel  hinge side or hinge anchors  handle/knob/pull at plausible height  front/back orientation  frame or mounting relation if applicable   `

This should happen before CLIP. A featureless cube should fail on missing semantic evidence even if a generic image model vaguely says “box.”

Render-based validation rig
---------------------------

Each asset should render:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   8 RGB views  8 silhouette views  8 normal views  8 depth views  8 material-id views  8 part-id views   `

Then score:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   semantic_feature_presence  class_readability  silhouette_archetype_match  material_zone_correctness  style_compliance  surface_detail_plausibility  face_budget  normal/shading quality   `

CLIP is useful as a weak broad signal because it supports zero-shot image/text matching through natural language supervision, but it should not be the primary validator. ([arXiv](https://arxiv.org/abs/2103.00020?utm_source=chatgpt.com)) The newer 3D-evaluation direction is multi-dimensional: Gen3DEval evaluates text fidelity, appearance, and surface quality; Eval3D emphasizes interpretable, fine-grained assessment across complementary criteria; 3DGen-Bench uses human preferences to benchmark generated 3D models. ([CVF Open Access](https://openaccess.thecvf.com/content/CVPR2025/html/Maiti_Gen3DEval_Using_vLLMs_for_Automatic_Evaluation_of_Generated_3D_Objects_CVPR_2025_paper.html?utm_source=chatgpt.com))

CI-level check
--------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   golden regression:    same seed, same pack versions, same renderer → no unintended visual drift  category validator:    current output meets class anchor minimum  paired A/B:    old generator vs new generator on same seeds  repair signal:    validator emits missing evidence, not just score   `

Validator output should look like:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "validator": "class_anchor.crate_v1",    "pass": false,    "evidence": {      "bounded_volume": true,      "panel_breakup": false,      "corner_reinforcement": false,      "lid_seam": false,      "material_separation": false    },    "suggested_repairs": [      {"op": "insert_feature", "role": "corner_reinforcement"},      {"op": "panelize_faces", "target": "major_side_faces"},      {"op": "insert_feature", "role": "lid_seam"},      {"op": "assign_material_zone", "target": "reinforcement", "material_class": "metal_trim"}    ]  }   `

That is how the repair loop becomes useful.

7\. Art direction belongs in a VisualLanguage pack
==================================================

Do not put art direction directly in FamilyAlias. Also do not bury it entirely inside StyleKnowledge.

I would add:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   VisualLanguage   `

Then wire packs like this:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   FamilyAlias:    family → domain, composition_policy_id, default_style_id, morphology_profile_id  CompositionPolicy:    class-structural rules    e.g. panelized_hard_surface_object, bounded_container, hinged_panel  MorphologyProfile:    typed body/part/anchor expectations    e.g. swing_door, industrial_crate, fantasy_weapon_guardrail  StyleKnowledge:    material and surface recipes    e.g. industrial_pbr_v1  VisualLanguage:    cross-class art direction    e.g. steampunk, brutalist, alien_grove, clean_sci_fi   `

CityEngine’s CGA style system is a useful precedent: styles are saved sets of attribute values for rules, and a style can be reused/managed independently of the rule itself. ([ArcGIS](https://doc.arcgis.com/en/cityengine/2024.1/help/help-rules-styles.htm?utm_source=chatgpt.com)) Houdini Digital Assets are another useful reference for packaging complex procedural networks behind reusable interfaces. ([SideFX](https://www.sidefx.com/docs/houdini/assets/intro.html?utm_source=chatgpt.com))

What VisualLanguage should contain
----------------------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "id": "steampunk_workshop_v1",    "silhouette_bias": {      "forms": ["rounded_rectangular", "layered", "mechanical"],      "avoid": ["clean_flat_unbroken_surfaces"]    },    "motifs": {      "preferred": ["brass_trim", "rivets", "pressure_gauge", "leather_grip"],      "rare": ["emissive_strip"],      "forbidden": ["holographic_panel"]    },    "palette": {      "body": ["dark_walnut", "aged_copper", "warm_black"],      "accent": ["brass", "cream_label"]    },    "materials": {      "metal_trim": "aged_brass",      "body_panel": "dark_varnished_wood",      "fastener": "oxidized_steel"    },    "wear": {      "edge_polish": 0.5,      "dust_in_seams": 0.7,      "paint_chipping": 0.1,      "oil_staining": 0.4    },    "feature_weight_overrides": {      "visible_fasteners": 1.4,      "decorative_trim": 1.3,      "clean_inset_panels": 0.5    }  }   `

Separation:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   class rules:    what makes it a crate, door, panel, weapon  visual language:    what world it belongs to  condition:    how new/old/damaged it is   `

So:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   industrial crate  fantasy crate  sci-fi crate  abandoned crate   `

all share crate morphology, but differ in style overlays, materials, motifs, wear, and feature weights.

8\. mesh\_program{} and synth should compose through graph nodes
================================================================

The authored path and synth path should not be separate universes.

mesh\_program{} should emit **locked construction-graph nodes with exported anchors**.

Example:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   mesh_program body {    role: primary_volume    locked_geometry: true    export_face front {      role: front_face      material_zone: painted_body      anchors: [        { role: handle_mount_region },        { role: warning_decal_region }      ]    }    export_edges vertical_edges {      role: exterior_corner_edge      anchors: corner_reinforcement_candidates    }  }  synth augment {    apply_policy: bounded_container_reinforcement_v1    target: body  }   `

The synth then adds:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   corner brackets  lid seam  handles  warning decals  fasteners  wear  material assignments  LOD policy  collision/rig/interface metadata   `

Conflict rule:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   authored mesh_program geometry > explicit intent > morphology profile > composition policy > style overlay > seeded variation   `

This is how mature procedural tools work in spirit: authored control and procedural expansion coexist. Houdini’s Digital Asset model is relevant because it packages reusable procedural logic behind parameters rather than forcing every result to be entirely hand-modeled or entirely generated. ([SideFX](https://www.sidefx.com/docs/houdini/assets/intro.html?utm_source=chatgpt.com))

9\. World generation: use a KitGraph, not 100 standalone files
==============================================================

For a world of:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   50 crates  20 doors  30 panels  10 terminals   `

the right authoring layer is:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   WorldProgram    references KitGraph      references asset archetypes        reference morphology/style/policy packs   `

Not:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   100 separate .lth files   `

And not only:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   one .lth + 100 raw seeds   `

Use this structure:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   VisualLanguage:    industrial_pbr_v1 / brutalist_bunker_v1 / alien_grove_v1  KitGraph:    compatible crate, door, panel, terminal archetypes    shared interfaces    shared material palette    shared decal library    shared texel density    shared wear/condition distribution  SceneProgram:    places instances    controls density, repetition limits, clustering, gameplay roles   `

Example:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   kit industrial_loading_bay_v1 {    visual_language: utility_industrial_v1    material_palette: warehouse_yellow_gray_v1    texel_density: 512px_per_meter    archetypes {      crate: industrial_crate_hero.lth      door: mechanical_door_heavy.lth      wall_panel: hard_surface_panel.lth      terminal: service_terminal.lth    }    variation {      crate.count: 50      crate.seed_strategy: stratified      crate.repetition_limit: 3      crate.condition_distribution: [0.2, 0.8]    }  }   `

Houdini PDG/TOPs Wedge is the practical production analogy: it creates work items for variations of specified attributes, which is exactly the kind of controlled fan-out Lathe needs at world scale. ([SideFX](https://www.sidefx.com/docs/houdini/tops/wedge.html?utm_source=chatgpt.com))

10\. Asset-to-asset attachment needs interface signatures
=========================================================

interfaces/ and interface\_connections.py should become the docking system.

Every asset exports interface ports:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "interface_id": "crate.bottom.stack_mount_v1",    "kind": "support_footprint",    "frame": "...",    "bounds_m": [1.0, 0.8, 0.05],    "snap_points": ["corner_0", "corner_1", "corner_2", "corner_3"],    "load_capacity_kg": 120,    "texel_density": 512,    "material_transition": "allow_contact_shadow",    "collision_policy": "compound_hull"  }   `

A pallet exports:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "interface_id": "pallet.top.crate_slots_v1",    "kind": "support_surface_grid",    "slot_bounds_m": [1.0, 0.8, 0.1],    "slot_count": 4,    "snap_policy": "grid_aligned"  }   `

Docking rule:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   compatible kind  compatible dimensions  compatible load/support  compatible orientation  compatible clearance  compatible style/material policy   `

Result:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   transform  snap proof  optional transition geometry  shared texel scale  material continuity policy  physics connection   `

For engine export, these interfaces should also become sockets/attachments where supported. Unreal sockets are explicit attach points in a skeleton hierarchy; Houdini Engine for Unreal also supports mesh socket creation through point groups/detail attributes, which is close to the kind of metadata Lathe should emit. ([Epic Games Developers](https://dev.epicgames.com/documentation/unreal-engine/skeletal-mesh-sockets-in-unreal-engine?utm_source=chatgpt.com))

11\. Rigs and moving parts: rigid constraints first, bones second
=================================================================

For crates, doors, terminals, panels, and mechanical props, most moving parts should not be skinned. They should be **rigid node hierarchies with constraint metadata**.

Use bones/skinning for deforming meshes. Use transform nodes/constraints for doors, latches, knobs, levers, drawers, buttons, and panels. glTF supports scenes with node hierarchies and animations, and its skin model uses joints and inverse bind matrices for skinned animation. ([Khronos Registry](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html?utm_source=chatgpt.com))

Hinge edge → rig contract
-------------------------

Construction graph edge:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "relation": "attached_to",    "source": "door_leaf",    "target": "door_frame",    "metadata": {      "joint": "hinge",      "axis": "Z",      "limits_deg": [-5, 105],      "default_angle_deg": 0,      "motorized": false    }  }   `

Rig stage output:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "rig_type": "rigid_constraint",    "bodies": [      {"id": "door_frame", "role": "static_parent"},      {"id": "door_leaf", "role": "dynamic_child"}    ],    "joints": [      {        "type": "hinge",        "parent": "door_frame",        "child": "door_leaf",        "pivot_world": "...",        "axis_world": "...",        "limits_deg": [-5, 105]      }    ],    "animations": [      {"name": "open", "joint": "hinge", "from": 0, "to": 95}    ]  }   `

Engine adapters lower this differently:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   glTF:    node hierarchy + animation clip + extras for hinge metadata  USD:    Xform hierarchy + optional UsdPhysics joint/collision schemas  Roblox:    Attachments + HingeConstraint  Unity:    GameObject hierarchy + HingeJoint/AnimationClip  Unreal:    Blueprint/Actor components, sockets, constraints, animation or timeline   `

Roblox’s HingeConstraint specifically constrains two attachments to rotate about one axis, which maps cleanly from Lathe’s hinge edge metadata. ([Creator Hub](https://create.roblox.com/docs/physics/constraints/hinge?utm_source=chatgpt.com)) USD Physics is also relevant as an interchange schema, but USD schemas describe data models; they do not provide a physics engine by themselves. ([OpenUSD](https://openusd.org/dev/api/usd_physics_page_front.html?utm_source=chatgpt.com))

12\. Physics should derive from construction graph nodes
========================================================

The canonical procedural collision mesh is **compound collision derived from semantic parts**.

Not:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   final visual mesh → decimate → hope collision is okay   `

Instead:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   construction graph nodes → physics roles → collision primitives/hulls   `

Physics roles:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   primary_volume:    box or convex hull  panel:    thin box or no collision depending on gameplay role  handle:    simplified capsule/box if interactable, otherwise no collision  corner_bracket:    no collision or merged into parent hull  door_leaf:    rigid body hull linked to hinge  terminal_button:    trigger volume  decorative_fastener:    no collision   `

Unity explicitly supports compound colliders and recommends compound convex colliders when accurate collision is needed in concave parts; Unreal distinguishes simple collision primitives/convex hulls from complex collision; Roblox exposes collision fidelity levels for MeshPart/PartOperation behavior. ([Unity Documentation](https://docs.unity3d.com/6000.3/Documentation/Manual/compound-colliders.html?utm_source=chatgpt.com))

PhysicsIR
---------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "physics": {      "bodies": [        {          "node": "crate_body",          "body_type": "static_or_dynamic",          "collision": {            "type": "compound",            "parts": [              {"shape": "box", "source": "primary_volume"},              {"shape": "box", "source": "left_handle", "enabled": false}            ]          },          "mass_kg": 18,          "material": "metal_wood_mix"        }      ]    }  }   `

Collision should be generated before optimize/package, validated against gameplay constraints, and exported through target-specific adapters.

13\. Engine targeting: add RuntimeMetadata before package
=========================================================

USD/GLTF/OBJ packages are not enough for game-ready assets. Lathe needs a target-aware metadata layer:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   execution  → rig  → interfaces  → physics  → optimize  → validate  → runtime_metadata  → package  → publish   `

runtime\_metadata should not replace USD/GLTF. It should declare what the engine adapter must create.

Common runtime contract
-----------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "asset_id": "industrial_crate_042",    "lods": ["LOD0", "LOD1", "LOD2", "LOD3"],    "materials": "...",    "colliders": "...",    "interfaces": "...",    "rig": "...",    "sockets": "...",    "nav_hints": "...",    "audio_emitters": "...",    "light_probe_anchors": "...",    "streaming_group": "warehouse_props_A",    "semantic_tags": ["crate", "container", "cover_object"]  }   `

For Roblox
----------

Needed:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   Model hierarchy  MeshParts  CollisionFidelity choices  Attachments  HingeConstraints  Model.LevelOfDetail / streaming behavior  tags / attributes  scripts or ModuleScript metadata for interactions   `

Roblox Studio’s Importer supports .fbx, .gltf, and .obj; Roblox also has Model level-of-detail behavior for streaming-enabled experiences, collision fidelity settings, and HingeConstraint/Attachment-based mechanics. ([Creator Hub](https://create.roblox.com/docs/studio/importer?utm_source=chatgpt.com))

For Unity
---------

Needed:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   GameObject hierarchy  LODGroup or Mesh LOD  MeshRenderers/submeshes/materials  colliders / compound colliders  joints  light probe / reflection probe anchors  AudioSource slots  NavMesh modifiers or areas  Addressables/streaming group metadata   `

Unity’s LOD features include Mesh LOD and LODGroup, and Unity supports light-probe proxy volumes for large dynamic GameObjects and AudioSource components for sound emitters. ([Unity Documentation](https://docs.unity3d.com/6000.4/Documentation/Manual/LevelOfDetail.html?utm_source=chatgpt.com))

For Unreal
----------

Needed:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   StaticMesh/SkeletalMesh or Actor Blueprint  LODs  simple/complex collision  sockets  constraints  reflection capture hints  Nav Modifier Volumes  AudioComponents  HLOD/streaming metadata   `

Unreal documents simple versus complex collision, static mesh LODs, reflection capture actors, audio components, and navigation modifier volumes. ([Epic Games Developers](https://dev.epicgames.com/documentation/unreal-engine/simple-versus-complex-collision-in-unreal-engine?utm_source=chatgpt.com))

For USD/glTF
------------

USD should carry richer authoring/interchange data:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   variants for LOD/style/material  GeomSubsets for material zones  UsdLux for validation/demo lighting  UsdPhysics for physics metadata  proxy/render purpose for lightweight representations   `

USD variant sets are designed for alternative representations such as model shapes/materials/LODs, and USD purpose can distinguish proxy and render representations. ([NVIDIA Docs](https://docs.nvidia.com/learn-openusd/latest/composition-basics/variant-sets.html?utm_source=chatgpt.com)) UsdLux provides an interchange schema for lights. ([OpenUSD](https://openusd.org/dev/api/usd_lux_page_front.html?utm_source=chatgpt.com))

glTF should carry runtime delivery:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   node hierarchy  mesh primitives/materials  PBR textures  animations  skins if needed  extras/extensions for Lathe metadata   `

glTF is explicitly designed for efficient runtime transmission/loading of 3D scenes and models. ([The Khronos Group](https://www.khronos.org/gltf/?utm_source=chatgpt.com))

14\. Determinism vs creative variation
======================================

Lathe’s determinism model is correct:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   shape is probabilistic  everything downstream deterministic   `

But we need a hierarchy of seeds:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   world_seed    kit_seed      asset_archetype_seed        asset_instance_seed          surface_micro_seed          decal_seed          wear_seed   `

And a reproducibility manifest:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "lathe_version": "x.y.z",    "shape_contract": "lathe.shape.intent_mesh_handoff_v1",    "knowledge_pack_versions": {      "FamilyAlias": "...",      "CompositionPolicy": "...",      "StyleKnowledge": "...",      "VisualLanguage": "..."    },    "world_seed": 192331,    "asset_seed": 4102,    "shape_graph_hash": "...",    "compiled_ir_hash": "...",    "provider_proposals": []  }   `

Determinism gradient
--------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   CI / regression:    fixed packs, fixed seeds, fixed renderer, fixed target profile  offline production:    seed sampling allowed, outputs frozen after publish  runtime:    choose from prebuilt variants    allow cheap parameter overrides only  live procedural generation:    only for server/editor/sandbox, not critical path for shipped client   `

For a game world, I would not generate heavy geometry live on the client. Use Lathe ahead-of-time for geometry, hybrid for material parameters/visibility/animation states.

15\. Runtime loading contract: Lathe should be AOT-first, hybrid-capable
========================================================================

For 1000s of assets, Lathe should primarily be **ahead-of-time**.

Ship:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   prebaked LOD chain  material maps / atlases  collision  rig metadata  interfaces  runtime tags  streaming chunks  engine adapter manifests   `

Allow runtime overrides only for safe dimensions:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   material tint  decal choice  wear intensity  open/closed state  visibility of optional small features  animation state  damage decal overlay   `

Do not require runtime boolean generation for normal play. That makes performance, QA, and networking much harder.

AssetRuntimeContract
--------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "asset_id": "crate_industrial_042",    "render": {      "lods": {        "LOD0": "crate_042_lod0.glb",        "LOD1": "crate_042_lod1.glb",        "LOD2": "crate_042_lod2.glb",        "LOD3": "crate_042_proxy.glb"      },      "materials": ["painted_steel_body", "brass_trim", "warning_decal"],      "texture_sets": ["body_2k", "trim_1k", "decal_512"]    },    "physics": {      "collider_set": "compound_v1"    },    "interfaces": [      "crate.bottom.stack_mount_v1",      "crate.top.stack_receive_v1"    ],    "rig": null,    "runtime_params": {      "wear_multiplier": [0.0, 1.0],      "decal_variant": ["A", "B", "C"],      "body_tint": "palette_bound"    },    "streaming": {      "chunk": "warehouse_props_A",      "memory_budget_mb": 12    }  }   `

For USD, variants can hold LOD/style/material alternatives. For glTF, be careful: LOD is not a universally core glTF feature; MSFT\_lod exists as a vendor extension, but engine support varies. ([GitHub](https://github.com/KhronosGroup/glTF/blob/master/extensions/2.0/Vendor/MSFT_lod/README.md?utm_source=chatgpt.com)) So Lathe should export LODs plus a sidecar/engine adapter manifest rather than assuming every runtime will honor a glTF LOD extension.

16\. Perceptual repair loop: repair the graph, not the mesh
===========================================================

For “this asset doesn’t look game-ready,” the repair loop must mutate the **intent/policy graph**, not the final mesh.

Bad repair:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   take fused cube mesh  try to add random surface noise   `

Good repair:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   validator detects missing class evidence  → repair planner inserts semantic feature ops  → shape/topology/surface rerun deterministically  → validator re-renders and rescans   `

Canonical repair operator set
-----------------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   insert_required_feature(role)    e.g. corner_reinforcement, lid_seam, handle, hinge, latch  panelize_face(target_face)    creates inset panels / split surfaces / grooves  add_reinforcement_pattern(anchor_set)    corners, edges, bands, brackets, cross braces  strengthen_silhouette(role)    promote trim/bracket/handle to geometry  assign_material_zone(target, material_class)    body vs trim vs decal vs fastener  add_decal_zone(target, decal_role)    warning marker, serial plate, faction mark  increase_bevel_readability(edge_group)    bigger chamfer, harder normal break, better material response  add_surface_wear(target, wear_role)    edge chips, dirt in seams, rust around fasteners  promote_detail_to_geometry(feature)    if too flat / silhouette weak  demote_detail_to_texture(feature)    if over budget  adjust_style_weights(visual_language)    more steampunk, less sterile, more brutalist massing  resample_variation(seed_scope)    only within failed feature family, not whole asset   `

Example repair loop
-------------------

Initial output:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   featureless cube   `

Validator:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   {    "class": "industrial_crate",    "pass": false,    "failures": [      "no_panel_breakup",      "no_lid_or_access_seam",      "no_reinforcement",      "single_material_slot",      "sterile_surface"    ]  }   `

Repair plan:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   [    {"op": "panelize_face", "target": "major_side_faces"},    {"op": "insert_required_feature", "role": "corner_reinforcement"},    {"op": "insert_required_feature", "role": "lid_seam"},    {"op": "assign_material_zone", "target": "body", "material_class": "painted_steel"},    {"op": "assign_material_zone", "target": "reinforcement", "material_class": "raw_or_brass_metal"},    {"op": "add_surface_wear", "target": "convex_edges", "wear_role": "edge_chipping"},    {"op": "add_decal_zone", "target": "front_face", "decal_role": "warning_marker"}  ]   `

Second render should now show visible class evidence. If not, the validator raises feature strength:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   increase panel depth  increase trim contrast  make reinforcement larger  promote seam from normal map to geometry   `

This is how Lathe’s evidence-based validators become a creative engine, not just a QA gate.

The decisive build order
========================

I would not start with more ShapeIR ops. I would start with the contracts that make current ops meaningful.

Milestone 1: Executable placement
---------------------------------

Build:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   Anchor  Scope  PlacementCandidate  PlacementBinding  RelationResolver  PlacementProof   `

Then make Stage 5 emit anchors and Stage 6 resolve edges. This immediately fixes the “typed edges ignored” problem.

Milestone 2: MorphologyProfile pack
-----------------------------------

Add:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   lathe.knowledge.morphology_profile_v1   `

Move \_KIND\_ASPECT knowledge into declarative morphology profiles. Door/crate/panel/terminal become data, not code branches.

Milestone 3: Zone-preserving topology
-------------------------------------

Make every final face carry provenance:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   node_id  feature_id  zone_id  material_class  uv_policy   `

Then export USD GeomSubsets / glTF mesh primitives.

Milestone 4: Feature ops that matter
------------------------------------

Add, in order:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   op.panel_inset  op.edge_group_select  op.weighted_bevel  op.trim_sweep  op.profile_sweep  op.fastener_pattern  op.boolean_group  op.lod_policy   `

This moves us from primitive unions to authored hard-surface composition.

Milestone 5: VisualLanguage pack
--------------------------------

Add:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   VisualLanguage   `

Keep family morphology, composition policy, style/materials, and art direction separate.

Milestone 6: RuntimeAssetContract
---------------------------------

Add target-aware metadata for:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   LOD  collision  rig  interfaces  sockets  nav hints  audio emitters  light/probe anchors  streaming groups  engine adapters   `

This is what makes Lathe game-ready rather than just model-export-ready.

Milestone 7: Class Anchor Validator + repair operators
------------------------------------------------------

Make “featureless cube” fail for crates, doors, panels, terminals, and fantasy weapon guardrails.

Final strategic call
====================

Given Lathe’s architecture, the next move is:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   Do not add family branches.  Do not trust suffix placement.  Do not fuse away intent zones.  Do not decimate your way into LOD.  Do not validate only geometry.   `

Build this instead:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   FamilyAlias    → MorphologyProfile    → CompositionPolicy    → VisualLanguage    → executable construction graph    → PlacementBinding    → feature-aware ShapeProgram    → zone-preserving topology    → material/PBR/decal binding    → per-LOD compilation    → runtime asset contract    → perceptual validator    → graph-level repair   `

The most important single change: **Stage 6 must become a relation resolver that turns typed construction-graph edges into transforms, anchors, cuts, sockets, rigs, physics, and proof.**

Once that exists, Lathe’s “procedural is the product” bet becomes coherent. The learned providers can propose, but the procedural graph owns truth, repeatability, packaging, and repair.
