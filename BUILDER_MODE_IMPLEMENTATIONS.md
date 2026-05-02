# Lathe Builder Mode Implementations

## Builder Mode Operating Constraint

- Do not let Lathe become a dictionary of cool worldbuilding words. Every language word should make something, modify something, arrange something, or prepare information that soon makes, modifies, or arranges something.
- For each new Builder Mode construct, the parser must accept it, scene/world lowering must preserve intent, Scene Graph state must contain actionable controls, materialization must forward those controls into generated assets, and the procedural/runtime layer must visibly respond through geometry, materials, placement, hierarchy, or soon-used state.
- Each implementation entry must record the consequence of the construct: what it now makes, modifies, arranges, or prepares, not just the construct name.

## 2026-05-01 - World and Scene Authoring Runtime

- Added top-level `world` declarations alongside `scene`.
- Added scene-local `group`, `collection`, `instance`, `terrain`, and `array` constructs.
- Taught hand-authored scene/world source to lower directly into Scene Graph payloads without requiring embedded JSON.
- Added array expansion into concrete Scene Graph objects with per-instance transforms and state.
- Added terrain lowering as an environment-structure object.

## 2026-05-01 - Structural Geometry Motifs

- Added operator-backed geometry motifs for stairs, arches, columns, pipe runs, wheel pairs, hull keels, structural frames, and supports.
- Connected those motifs to `build.shape.detail_motifs`, style modifiers, and style packs so authored Lathe code can request broad architectural, vehicle, boat, machine, and environment structure.
- Added `architectural_world` and `vehicle_workshop` geometry style packs that expand shape generation with reusable world/building and vehicle vocabulary.

## 2026-05-01 - Procedural Asset Families

- Added procedural building family generation with floors, window bays, entry doors, roofs, columns, and stairs.
- Added procedural vehicle family generation with chassis, cabin, engine block, and paired wheel layouts.
- Added procedural boat family generation with hull, deck, cabin, engine, and mast layout.
- Added blueprint routing and family inference so Lathe author intent can select these broad asset families directly.

## 2026-05-01 - Procedural World Pieces

- Added procedural road family generation with segmented roadbeds, lane markers, lane-count controls, and sidewalks.
- Added procedural bridge family generation with deck spans, side railings, pier arrays, and abutments.
- Added procedural terrain family generation with base landforms, terraces, ridges, cliffs, platforms, and traversal paths.
- Added procedural city block family generation with street grids, lots, building masses, and roofs.
- Added procedural interior family generation with room shells, wall bays, windows, doors, and support columns.

## 2026-05-01 - Scene Composition Constructs

- Added hand-authored scene/world source blocks for `road`, `bridge`, `building`, `interior`, `city_block`, and `route`.
- Lowered those blocks to procedural-family Scene Graph objects with world-piece semantic tags and source-family metadata.
- Added endpoint-derived connector transforms so authored roads, bridges, and routes can connect named regions or objects without manually computing midpoint, yaw, or length.
- Added implicit connector relationships so route-like objects know which scene entities they connect.

## 2026-05-01 - Scene-To-Asset Procedural Control Bridge

- Added `assembly.runtime_family` inference so generated asset sources can select procedural runtime families without requiring declared family blocks.
- Taught scene asset materialization to emit procedural-family asset sources for scene-authored buildings, roads, bridges, terrain, interiors, city blocks, vehicles, and boats.
- Propagated scene-authored controls such as floors, lanes, spans, lots, bays, terraces, wheels, and masts into generated `build.shape` controls.
- Derived width, length, depth, and height proportions from Scene Graph transforms so placed scene objects can shape generated asset proportions.

## 2026-05-01 - Procedural Surface Identity

- Added rich Scene Graph `surface_overrides` values so scene-authored objects can carry material layers, decals, markings, wear stories, and per-part material zones.
- Added default surface identities for procedural terrain, roads, bridges, buildings, interiors, city blocks, vehicles, and boats.
- Taught scene asset materialization to emit generated `surface { ... }` blocks with materials, material layers, wear controls, decals/markings, and `zones.<part>` assignments.
- Expanded material palettes and semantic zone assignment for asphalt, concrete, stone, soil, moss, leather, fabric, canvas, metal, plastic, glass, emissive panels, roads, bridges, terrain, city blocks, and interiors.
- Enabled procedural asset families to use the richer PBR surface runtime path with wear masks, material layer masks, emissive maps, and decal placement metadata.

## 2026-05-01 - Scene Sockets and Attachment Interfaces

- Added hand-authored `socket` and `attach` scene/world blocks so authored worlds can declare snap points and object-to-object attachment rules.
- Lowered scene sockets into per-object composition state and lowered attachments into `snaps_to`, `attached_to`, `supports`, or `connects_to` Scene Graph relationships.
- Expanded Scene Graph object state so sockets, accepts lists, anchor lists, offsets, and interface vectors can survive lowering as structured authoring data.
- Taught scene asset materialization to emit generated `build.interfaces` sockets and anchors from procedural family defaults plus authored scene sockets/attachments.
- Propagated generated interface sockets into shape controls as `module_sockets`, and preserved socket/anchor ids in ShapeIR signatures for downstream runtime consumers.

## 2026-05-01 - Modular Kit Scene Assembly

- Added scene/world-local `module`, `kit`, and `part` blocks so authors can define reusable scene-piece templates and instantiate them as modular assemblies.
- Added kit expansion for repeated module instances, explicit kit parts, linear layouts, and radial/ring layouts.
- Added kit-local `socket` and `attach` lowering so internal snap points and attachments are remapped onto generated kit part instances.
- Propagated kit identity, module references, repeat indices, and kit layout state into generated Scene Graph objects and scene-to-asset shape controls.
- Allowed inline module sockets, anchors, and pivots to become generated `build.interfaces` entries through composition state.

## 2026-05-01 - Variant Family Generators

- Added scene/world-local `variant_family`, `option`, and `generator` blocks for higher-level object grammars.
- Added deterministic generator selection strategies for cycling, weighted cycling, reverse cycling, and mirrored/ping-pong selection over interchangeable module pools.
- Added generator expansion into concrete Scene Graph objects with generator identity, variant family identity, selected option state, compatibility tags, and source kit/variant metadata.
- Added generator-local and family-local sockets/attachments, plus automatic chain/loop attachment generation for repeated variants.
- Propagated generator counts and selection indices into scene-to-asset shape controls so generated assets can respond to authored procedural family size.

## 2026-05-01 - Constraint-Aware Object Grammars

- Added generator and variant-family `constraint` blocks for deterministic object grammar rules.
- Added selection constraints for required tokens, required compatibility, required sockets, forbidden tokens, start/end option requirements, periodic requirements, avoid-repeat rules, and forbidden adjacency.
- Taught generator selection to filter weighted/cycled variant pools by authored constraints before instantiating Scene Graph objects.
- Propagated selection constraint names and counts into generated object state and scene-to-asset shape controls.
- Let module-authored sockets, anchors, compatibility, tags, and semantic tags participate in generator constraint matching.

## 2026-05-01 - Semantic Placement Zones

- Added scene/world `placement_zone` blocks for named frontage, terrain, floor, ceiling, wall, line, and grid placement areas.
- Taught generators to target placement zones with `placement_zone`, `zone`, or inline `placement { ... }` controls instead of only using raw linear/radial coordinates.
- Added deterministic frontage, wall, floor-grid, ceiling-grid, terrain-grid, and path/line placement transforms derived from region bounds and zone controls.
- Propagated placement zone, surface, side, row/column, elevation, and placement index/count into generated Scene Graph object state.
- Propagated placement counts, rows, columns, and elevation into scene-to-asset shape controls so generated assets can respond to their placement context.

## 2026-05-01 - Biome Scatter Systems

- Added scene/world `biome` blocks as reusable environment profiles with pools, options, constraints, sockets, attachments, density, surface identity, scale variation, and scatter defaults.
- Added scene/world `scatter` blocks that expand biome or variant-family pools into concrete Scene Graph objects across named placement zones.
- Added deterministic scatter patterns for grid, natural jitter, clusters, patches, rings, and radial placement with seedable jitter, scale variation, and yaw variation.
- Propagated scatter identity, biome identity, density, pattern, seed, selection strategy, placement state, and compatibility into generated Scene Graph object state.
- Propagated scatter counts, scatter indices, biome density, scatter seeds, and scatter patterns into scene-to-asset shape controls so generated assets can respond to environment population context.

## 2026-05-01 - Biome-Aware Environment Systems

- Added scene/world `environment` blocks for higher-level terrain and world-structure generation tied to biome profiles.
- Expanded authored environments into connected terrain patches, ridges, cliffs, clearings, platforms, water features, paths, road edges, and landmark objects.
- Added deterministic world-feature placement across region or placement-zone bounds, including grid terrain patches, linear paths/ridges, and seeded landmark/clearing positions.
- Added generated environment relationships so terrain roots contain or route to generated environment features as connected world structure.
- Propagated environment identity, landform type, feature counts, terrain patch counts, ridge/cliff/clearing/path/road-edge/landmark counts, biome density, and placement state into Scene Graph object state and generated asset shape controls.

## 2026-05-01 - Terrain Landform Runtime Geometry

- Added landform-aware procedural terrain blueprint controls for terrain patches, ridges, cliffs, clearings, platforms, water features, and traversal paths.
- Added distinct assembly primitive builders for terrain ridges, cliff faces, clearings, raised platforms, and water basins/surfaces instead of routing every terrain feature through one generic terrain primitive recipe.
- Taught generated scene assets to pass `environment_feature`, `landform`, `environment_pattern`, and terrain/environment feature counts into `build.shape` controls.
- Taught procedural road blueprints to respond to environment `road_edge` and path landforms with narrower road defaults and generated curb/edge-guard structure.
- Connected biome/environment scene state to real mesh-building primitives so authored environments produce visibly different landform geometry, not just tagged Scene Graph objects.

## 2026-05-01 - Biome and Landform Surface Grammars

- Added a reusable surface grammar layer that derives materials, material layers, decals, patterns, zone overrides, and per-zone surface features from procedural family, landform, biome, density, and environment pattern controls.
- Added landform-specific surface identities for terrain patches, ridges, cliffs, clearings, raised platforms, water features, paths, trails, and road edges.
- Added biome-specific surface modifiers for forest, desert, wetland, swamp, snow, volcanic, coastal, urban, and mountain environments.
- Expanded material assignment so generated zones can keep specific basin, rim, edge, platform, water, cliff, ridge, clearing, path, and terrain materials instead of being overwritten by broad semantic fallbacks.
- Expanded the procedural bake runtime with water ripples, sand ripples, vegetation mottling, snow drifts, cracked/stratified stone, mud/silt, foam, lava crack, moss/lichen, leaf litter, trail scuff, and shoreline overlay behavior.
- Taught scene-to-asset materialization to emit grammar-derived surface materials, layers, patterns, decals, and zone assignments for generated procedural environment assets.
- Propagated surface grammar metadata and per-zone surface features into the surface manifest and texture control pack so downstream stages can consume authored surface identity.

## 2026-05-01 - Procedural Road Network Geometry

- Added procedural road controls for intersection type, junction count, branch count, crosswalk count, turnout count, and branch length.
- Expanded procedural road blueprints from straight segmented strips into junctions, four-way/T-style branches, roundabout islands, crosswalk markings, and roadside turnouts.
- Added assembly primitive builders for road junction plates, road branches, crosswalk stripes, turnout pads, and roundabout islands/rings.
- Added generated road-network parts, sockets, anchors, surface zones, and material-control aliases so scene-authored roads can produce connected network geometry.
- Expanded family inference and semantic part tags so authored junctions, intersections, branches, crosswalks, turnouts, and roundabouts resolve into the procedural road family.

## 2026-05-01 - Procedural Architecture and Interior Grammars

- Added procedural building controls for roof style, facade style, wing count, tower count, balcony count, awning count, dormer count, chimney count, and cornice count.
- Expanded building generation from simple shells into roof ridges, domes/cupolas, wings, towers, balconies, awnings, cornice bands, dormers, chimneys, entry stairs, columns, facade bays, and window grids.
- Added procedural interior controls for room count, room layout, corridor count, partition count, ceiling light count, stair core count, and alcove count.
- Expanded interior generation into room cells, circulation corridors, partition walls, partition openings, ceiling lights, stair cores, alcoves, wall bays, windows, doors, and support columns.
- Added assembly primitive builders for architectural roof ridges, domes, balconies, awnings, cornices, dormers, chimneys, towers, room cells, corridors, partitions, ceiling lights, stair cores, and alcoves.
- Added scene-to-asset aliases, generated parts, sockets, anchors, and material zones so authored scenes can drive richer procedural buildings and interiors through `build.shape` controls.

## 2026-05-01 - Procedural Weapon and Tool Family

- Added a reusable `procedural_weapon` runtime family for ranged weapons, blades, spears, axes, hammers, picks, staffs, launchers, and hand tools.
- Added procedural weapon controls for weapon type, tool type, blade count, barrel count, magazine count, sight count, guard count, and tool-head count.
- Added a procedural weapon blueprint that can assemble receivers, grips, barrels, stocks, magazines, sights, triggers, blades, tips, guards, and tool heads from shared controls.
- Added assembly primitive builders for weapon bodies, barrels, stocks, magazines, sights, triggers, and tool heads.
- Expanded family inference, blueprint resolution, self-reliant shape targeting, scene-to-asset parts, sockets, anchors, surface defaults, and semantic material assignment for procedural weapons.

## 2026-05-01 - Modular Vehicles and Machinery

- Expanded procedural vehicle controls with drive type, track count, suspension count, wing count, rotor count, turret count, cargo module count, and manipulator arm count.
- Expanded vehicle generation from chassis/cabin/wheels into tracked crawlers, drones/VTOLs, aircraft-like vehicles, cargo carriers, turreted rovers, suspension systems, and manipulator-equipped machines.
- Added a reusable `procedural_machine` runtime family for industrial machines, factory assemblers, cranes, loaders, hydraulic rigs, conveyor machines, gear-driven mechanisms, and tank/vessel assemblies.
- Added procedural machine controls for machine type, arm count, piston/hydraulic count, conveyor count, gear count, tank/vessel count, crane/boom count, and tool-head count.
- Added assembly primitive builders for tracks, suspension axles/struts, cargo modules, turrets, wings, manipulator arms, machine bases, machine columns, hydraulic pistons, conveyors, gears, tanks, and crane booms.
- Expanded family inference, blueprint resolution, scene-to-asset parts, control aliases, sockets, anchors, surface defaults, and semantic material assignment for modular vehicles and machinery.

## 2026-05-01 - Watercraft Construction Systems

- Expanded procedural boat controls with boat/hull type, propulsion, engine count, cabin count, deck levels, sail count, rigging count, pontoon count, outrigger count, cargo hold count, rail count, rudder count, propeller count, and anchor count.
- Expanded boat generation from hull/deck/cabin/engine/masts into sailboats, catamarans, trimarans, pontoons, outriggers, cargo barges, multi-deck vessels, stern-drive craft, and anchored deck vessels.
- Added assembly primitive builders for pontoons, outriggers, sails, rigging lines, cargo holds, rudders, propellers, and anchors.
- Expanded family inference, part tagging, assembly roles, adjacency inference, scene-to-asset parts, control aliases, sockets, anchors, surface defaults, surface grammar, material palettes, and semantic material assignment for procedural watercraft.

## 2026-05-01 - Procedural Furniture and Interior Equipment

- Added a reusable `procedural_furniture` runtime family for furniture kits, dining sets, office sets, bedrooms, kitchens, storage rooms, workshops, counters, appliances, lamps, and loose furnishings.
- Added furniture controls for furniture type, room role, furniture style, chair count, table/desk count, bed count, shelf/rack count, cabinet/locker count, drawer count, cushion/pillow count, counter/workbench count, appliance/fixture count, lamp count, and leg count.
- Added a procedural furniture blueprint that can assemble chairs, backs, support legs, tables, beds, mattresses, headboards, shelves, cabinets, drawers, counters, appliance bodies, lamps, and loose cushions.
- Added assembly primitive builders for furniture bases, chair seats, chair backs, furniture legs, table tops, bed frames, shelf units, cabinet bodies, drawers, cushions, counter tops, appliance bodies, and lamps.
- Expanded family inference, blueprint resolution, scene-to-asset parts, control aliases, sockets, anchors, surface defaults, surface grammar, material palettes, and semantic material assignment for room-ready furniture and interior equipment.

## 2026-05-01 - Procedural Foliage and Natural Props

- Added a reusable `procedural_foliage` runtime family for trees, forest kits, woodland kits, garden kits, bushes, grass, rocks, mushrooms, logs, vines, flowers, planters, and biome-aware natural set pieces.
- Added foliage controls for foliage type, plant type, biome, trunk/tree count, branch count, root count, canopy count, leaf-cluster count, bush/shrub count, grass-clump count, rock count, mushroom/fungi count, log count, vine count, flower/blossom count, and planter/pot count.
- Added a procedural foliage blueprint that can assemble ground patches, trunks, roots, branches, canopies, leaf clusters, bushes, grass clumps, rocks, mushrooms, fallen logs, vines, flowers, and planters.
- Added assembly primitive builders for foliage ground, tree trunks, roots, tree branches, leaf clusters, bushes, grass clumps, natural rocks, mushrooms, fallen logs, vines, flowers, and planters.
- Expanded family inference, blueprint resolution, scene-to-asset parts, control aliases, sockets, anchors, surface defaults, surface grammar, material palettes, bake colors, and semantic material assignment for natural props and foliage kits.

## 2026-05-01 - Procedural Urban Props and Street Set Dressing

- Added a reusable `procedural_urban_prop` runtime family for street kits, civic props, markets, alleys, plazas, traffic set dressing, checkpoints, and roadside detail.
- Added urban prop controls for urban/street/set-dressing type, district style, fence count, gate count, sign/signage count, streetlight/lamp-post count, bench count, trash-bin count, utility-pole count, cable/wire count, kiosk count, market-stall count, barrier count, street-crate count, and bollard count.
- Added a procedural urban prop blueprint that can assemble sidewalks and curbs, fence segments, gate panels, sign posts, streetlights, benches, bins, utility poles, cable spans, kiosks, market stalls, traffic barriers, crates, and bollards.
- Added assembly primitive builders for urban bases, fences, gates, signs, streetlights, benches, trash bins, utility poles, cable spans, kiosks, stalls, barriers, crates, and bollards.
- Expanded family inference, blueprint resolution, scene-to-asset parts, control aliases, sockets, anchors, surface defaults, surface grammar, material palettes, bake colors, and semantic material assignment for urban set dressing and street-prop kits.

## 2026-05-01 - Procedural Infrastructure Networks

- Added a reusable `procedural_infrastructure` runtime family for utility networks, factory service runs, street services, waterworks, drainage, substations, maintenance corridors, and data/power trunks.
- Added infrastructure controls for infrastructure/utility/service/network type, pipe count, duct count, conduit count, drain count, hydrant count, transformer count, junction-box count, valve count, manhole count, service-rail count, support/bracket count, and cable-tray count.
- Added a procedural infrastructure blueprint that can assemble service slabs, pipe runs, duct runs, overhead conduits, drain channels, hydrants, transformer boxes, junction boxes, valve wheels, manhole covers, service rails, support brackets, and cable trays.
- Added assembly primitive builders for infrastructure bases, pipes with couplers, ducts with inspection seams, suspended conduits, grated drains, fire hydrants, transformer cabinets, junction boxes, valve wheels, manhole covers, service rails, brackets, and cable trays with bundled cables.
- Expanded family inference, blueprint resolution, scene-to-asset parts, control aliases, sockets, anchors, surface defaults, surface grammar, material palettes, bake colors, and semantic material assignment for infrastructure networks and service geometry.

## 2026-05-01 - Procedural Access and Traversal Systems

- Added a reusable `procedural_access` runtime family for maintenance access, traversal kits, factory access, service walkways, tower access, scaffold access, tunnels, and industrial platforms.
- Added access controls for access/traversal/maintenance type, access style, catwalk count, walkway/span count, ladder count, ramp count, gantry count, elevator/lift count, platform count, tunnel count, scaffold count, guardrail count, safety-gate count, and support/column count.
- Added a procedural access blueprint that can assemble access bases, catwalk decks, walkway spans, ladders, ramps, gantry frames, elevator shafts, access platforms, tunnel segments, scaffold frames, guardrails, support columns, and safety gates.
- Added assembly primitive builders for grated catwalks, braced walkways, guardrails, ladder rungs, anti-slip ramps, gantry frames, elevator shafts, platforms, tunnel shells, scaffold frames, safety gates, and support columns.
- Expanded family inference, blueprint resolution, scene-to-asset parts, control aliases, sockets, anchors, surface defaults, surface grammar, material palettes, bake colors, and semantic material assignment for traversal and maintenance-access systems.

## 2026-05-01 - Modular Interface Connection Graphs

- Added first-class `build.interfaces.connections` payloads that can describe socket-to-anchor, socket-to-pivot, local-to-external, and scene-deferred attachment links.
- Added connection coercion for `connection(...)`, `connect(...)`, `attach(...)`, `attachment(...)`, mapping-style entries, and compact `source->target` strings.
- Expanded the interfaces runtime stage so builds emit resolved connection graphs, connection slots, compatibility scores, endpoint roles, and snap transform hints alongside sockets, pivots, and anchors.
- Added asset-graph and shape-signature propagation for authored interface connections so assembly compilation can preserve modular intent.
- Expanded scene materialization so scene relationships such as `routes_to`, `connects_to`, `attached_to`, `snaps_to`, `supports`, `opens_to`, and `contains` lower into asset interface connections.
- Expanded packaged asset manifests so runtime consumers can read interface connections and connection slots as part of the generated asset payload.

## 2026-05-01 - Connection-Aware Procedural Layout Controls

- Added a connection layout planner that derives procedural layout controls from authored interface connections and scene-lowered relationships.
- Added route, attach, support, external-endpoint, branch, segment, span, path-complexity, route-edge, and normalized layout-point summaries for connected assets.
- Fed connection-derived controls into the asset graph before procedural blueprint resolution so authored connections can drive generation without hand-setting every part count.
- Added family-specific connection layout controls for roads, bridges, access systems, infrastructure networks, interiors, buildings, city blocks, and terrain.
- Expanded shape signatures with connection layout payloads so generated geometry carries the route and snap topology that produced its repeated segments and connected regions.
- Expanded scene materialization so scene relationships influence generated shape controls before source emission, letting relationship-heavy scenes produce longer roads, bridge spans, access walkways, corridors, service runs, platforms, and lots.

## 2026-05-01 - Path-Following Procedural Geometry Profiles

- Added reusable path profiles for straight routes, curves, S-curves, switchbacks, stairs/ramps, tunnels, elevated routes, bridges, branches, and networks.
- Added path segment and branch placement data with normalized centers, extents, orientation tags, curve strength, rise, path length, and path width.
- Expanded procedural roads so roadbed segments and branch arms can follow authored route profiles instead of only forming straight strips.
- Expanded procedural bridges so spans and railings are generated as path-following span segments that can inherit bridge/elevated route profiles.
- Expanded terrain traversal paths and interior corridors so connected scenes can produce curved, meandering, rising, or networked route pieces.
- Expanded infrastructure pipe runs and access/traversal decks so service networks and maintenance routes can split into profile-following segments with path tags preserved in the generated assembly.

## 2026-05-01 - Structural Route and Facade Profiles

- Added reusable structural profile planning for route edges, curbs, barriers, sidewalls, roof ribs, portal frames, trusses, service trenches, supports, facade mullions, floor bands, buttresses, and roof edge profiles.
- Added structural path elements that can wrap path-following segments with edge rails, tunnel liners, covered corridors, bridge trusses, support posts, and crossbeams.
- Expanded procedural roads with generated curbs/barriers that follow the road path profile.
- Expanded procedural bridges with generated truss, post, crossbeam, and edge structures along path-following spans.
- Expanded terrain paths, interior corridors, infrastructure runs, and access/traversal kits with structural sidewalls, supports, roof ribs, frames, and service-trench elements.
- Expanded procedural buildings with reusable facade grids, mullions, structural floor bands, optional buttresses, and roof edge profiles driven by structural/facade controls.

## 2026-05-01 - Creative Biome, Faction, and Style Grammar

- Added a reusable creative grammar layer that turns high-level style, biome, faction, era, genre, theme, and material-intent tokens into concrete generation controls.
- Added style presets for industrial, brutalist, cyberpunk, sci-fi, battle-worn, arcane, architectural, and workshop art directions.
- Added biome presets for forest, desert, swamp, volcanic, and urban worlds that drive path profiles, structural profiles, material layers, and story decals.
- Added faction presets for military, corporate, civic, nomad, royal, and alien identities with faction marks, markings, structure choices, and wear stories.
- Wired creative grammar into asset graph construction so authored intent styles can drive procedural family shape controls, path profiles, structural profiles, style packs, facade styles, and family-specific knobs.
- Wired creative grammar into scene materialization so scene semantic tags and object state can shape generated source controls and surface authoring together.
- Wired creative grammar into surface material defaults so direct asset builds can inherit style-pack surfaces, material layers, decals, faction marks, and wear stories from high-level creative tags.
- Tightened family inference so broad style tokens such as `urban` enrich buildings and roads instead of rerouting them into generic urban props.

## 2026-05-01 - Object Grammar and Procedural Setpieces

- Added an object grammar layer that turns archetype tokens such as outpost, market, fortress, factory, harbor, hangar, and temple into concrete system controls.
- Added a reusable `procedural_setpiece` family for multi-system scene pieces that combine terrain pads, buildings, route spines, access spans, utilities, perimeter elements, props, docks, aprons, and ritual/courtyard features.
- Added setpiece controls for object archetype, layout, density, structure count, road segments, branches, access count, infrastructure count, prop count, perimeter count, gates, towers, docks, aprons, and columns.
- Added default internal setpiece parts so high-level archetype assets can compile into coordinated subsystems even when the author does not manually list every generated part.
- Wired object grammar into asset graph construction after creative grammar and before connection layout so high-level archetypes become shape controls before blueprint resolution.
- Wired object grammar into scene materialization so scene objects named or tagged as outposts, markets, factories, harbors, hangars, temples, and fortresses emit `procedural_setpiece` sources with matching parts, controls, surfaces, sockets, and anchors.
- Expanded surface defaults, surface grammar, semantic material assignment, and hero surface eligibility so generated setpieces carry material identity and story marks across their coordinated subsystems.

## 2026-05-01 - Nested Setpiece Child Modules

- Expanded object grammar presets with child-module controls for vehicles, boats, machines, conveyors, interiors, furniture clusters, foliage clusters, and module sockets.
- Expanded the default `procedural_setpiece` part vocabulary with child vehicle, boat, machine, interior, furniture, foliage, and module-socket parts.
- Expanded setpiece generation so outposts can include parked vehicles, harbors can include moored boats, factories can include machine and conveyor modules, temples can include interior/furniture/foliage clusters, and hangars can include service vehicles and machine bays.
- Added socket marker regions to generated setpieces so child modules have deterministic attachment plates for future socket-aware placement.
- Expanded scene materialization aliases, generated setpiece parts, interface defaults, surface defaults, surface grammar zones, and material zone specificity for nested child modules.

## 2026-05-01 - Socket-Addressable Child Module Layout

- Added a child-module layout planner that turns setpiece vehicle, boat, machine, interior, furniture, foliage, and generic socket controls into stable module slots.
- Added generated module sockets, anchors, mount kinds, compatibility tags, clearances, normalized placement positions, facing angles, and attach connections for each child slot.
- Fed child-module layout into asset graph construction before connection-aware layout so setpiece child slots become real interface topology and shape controls.
- Propagated child-module slot summaries and slot placement metadata into ShapeIR signatures for downstream runtime consumers.
- Taught procedural setpiece generation to place child vehicles, boats, machines, interiors, furniture, foliage, conveyors, and socket plates from named slots with socket-addressed component tags.
- Expanded scene materialization, surface grammar, and semantic material assignment so generated setpiece sources and surfaces understand module slots, mounts, parking bays, moorings, machine pads, room entries, furniture anchors, and terrain anchors.

## 2026-05-01 - Socket-Compatible Subassembly Instances

- Added reusable child-module templates for utility rovers, cargo tugs, patrol drones, work skiffs, barges, pontoon ferries, assembler stations, gantry cranes, conveyor loaders, control-room pods, barracks rooms, market table sets, workstation clusters, tree clusters, rock gardens, and generic kit attachments.
- Added slot-level module instance manifests with instance ids, runtime families, archetypes, blueprint ids, module controls, component vocabularies, and tags.
- Added authored module-template controls such as `vehicle_module`, `vehicle_modules`, `boat_module`, `machine_modules`, `furniture_module`, and `foliage_module` so scenes and generated assets can choose reusable slot contents.
- Propagated subassembly instance manifests through child-module layout summaries, ShapeIR signatures, generated connections, and scene-to-asset shape controls.
- Expanded procedural setpieces so module instances alter generated geometry: rotor drones get rotor pods, cargo tugs get cargo modules, gantry cranes get booms and hydraulics, pontoon boats get pontoons, sailboats can carry sails, rooms gain lights/alcoves, furniture modules gain chairs/shelves/lamps, and foliage modules gain bushes/grass/rocks/flowers.
- Expanded setpiece part vocabulary, surface zones, and material specificity for module-instance geometry such as rotors, cargo modules, turrets, pontoons, sails, cargo holds, hydraulics, crane booms, ceiling lights, alcoves, shelves, lamps, bushes, grass, rocks, and flowers.

## 2026-05-01 - Nested Asset Source Emission

- Added nested asset source manifests for socket-compatible child modules, turning slot instances into linked child Lathe asset sources.
- Added source generation for child vehicle, boat, machine, interior, furniture, foliage, and kit-attachment modules with runtime family, controls, parts, materials, sockets, anchors, and parent-slot attachment connections.
- Fed nested asset manifests into asset graph authoring and ShapeIR signatures while stripping source text from runtime signatures.
- Taught scene materialization to write nested child `.lth` sources under each generated parent asset and attach nested-source metadata to parent metadata and manifests.
- Extended the scene materialization manifest schema so parent asset sources can advertise nested child sources without breaking the strict contract.

## 2026-05-01 - Nested Asset Build Graphs and Hierarchical Child Builds

- Added socket-snapped placement payloads for nested child assets, including local transforms, slot ids, mount kinds, snap grids, clearances, parent endpoints, and child endpoints.
- Added nested build graph manifests with parent/child nodes, dependency edges, placement records, and package hierarchy plans for socketed child modules.
- Taught scene materialization to write child metadata files next to generated child `.lth` sources, preserving placement, dependency, package, check, and plan state per child.
- Taught `scene.materialize --build-assets` to build nested child assets under `builds/<parent>/children/<child>` and roll nested build payloads into the parent materialization manifest.
- Propagated nested child manifests into asset package manifests, optional game-asset manifests, scene build summaries, and ShapeIR/package metadata so downstream runtimes can see hierarchy instead of a flat asset list.

## 2026-05-01 - Parent-Consumable Nested Assembly Manifests

- Added a nested assembly aggregation runtime that turns parent builds plus child build outputs into parent-consumable subassembly manifests.
- Added nested assembly payloads with parent outputs, child outputs, consumable output lists, socket attachments, local transforms, package roots, build order, and aggregate package summaries.
- Taught scene materialization to write `nested_assembly_manifest.json` beside generated parent assets after child builds complete.
- Attached nested assembly references to parent metadata and nested asset manifests so scene/world consumers can load a complete parent-child assembly from one parent record.
- Added scene package source entries and materialization summary counts for nested assembly manifests so generated scene packages expose subassemblies as first-class package artifacts.

## 2026-05-01 - Nested Assembly Consumption in Scene GLB Export

- Taught scene package export to pass nested assembly manifests into the proxy GLB exporter when generated scene assets have socketed child builds.
- Added nested assembly GLB consumption that turns child build output references into placed subassembly proxy nodes under their parent Scene Graph object, with slot-class sizing and parent-relative transforms.
- Added nested subassembly records to exported object indices, including parent object id, child asset name, slot id, source URI, source-existence state, placement payload, export status, and proxy extents.
- Added report-level nested assembly export counts so scene export artifacts can distinguish flat proxy objects from placed nested child nodes.
- Preserved parent Scene Graph object identity while adding child subassembly nodes, so existing object-id based consumers still work while richer scene/world composition becomes available.

## 2026-05-01 - Scene-Authored Child Module Overrides and Surface Inheritance

- Added scene-source lowering for child-module directives such as `child_modules`, `module_overrides`, slot module maps, per-kind module templates, and module control maps on scene objects and gameplay blocks.
- Taught scene materialization to flatten scene-authored module maps into concrete shape controls before child-module slot planning, so generated setpieces can choose explicit child vehicles, boats, machines, interiors, furniture, foliage, and generic kit attachments per slot.
- Expanded child-module planning so direct asset authoring can also use mapped slot templates and mapped module controls, not only pre-flattened `vehicle_module` style keys.
- Added scene/direct controls for per-slot child positions, facing angles, and clearances so nested modules can be spatially arranged instead of only counted and selected.
- Broadened scene state value preservation so nested authoring maps can carry vector payloads such as slot positions through the Scene Graph contract.
- Propagated parent materials, style tags, and surface authoring from generated parent assets into nested child asset sources, including inherited material layers, story decals, faction markings, wear settings, and material zones.
- Extended nested child asset manifests with style tags and surface inheritance payloads so downstream scene/world consumers can understand both hierarchy and surface identity.

## 2026-05-01 - District, Room Cluster, and Street Grid Scene Macros

- Added hand-authored scene language constructs for `district`, `room_cluster`, and `street_grid`.
- Taught both parser paths to accept the new world-building constructs and lower them as scene macro objects.
- Added scene-source macro expansion that turns a district into a routed city composition with a district core, city blocks, generated buildings, and street segments.
- Added room-cluster expansion that turns one high-level interior cluster into multiple generated room interiors with containment and `opens_to` relationships.
- Added street-grid expansion that creates a navigable procedural road network with route core, east-west segments, north-south segments, and explicit connectivity relationships.
- Propagated macro style, surface, material, region, tags, and procedural state into generated child objects so downstream materialization can build city blocks, roads, interiors, and buildings with inherited authoring intent.

## 2026-05-02 - Architectural, Street, and Interior Procedural Detail Families

- Added reusable ShapeIR component builders for architectural arches, roof parapets, raised road medians, curb ramps, lane arrows, and stop-line markings.
- Expanded procedural building generation with storefronts, secondary entries, ground-floor arcades, facade signage, roof parapets, roof equipment, fire escapes, side windows, rear windows, and service doors.
- Expanded procedural road generation with medians, stop bars, lane arrows, curb ramps, bike lanes, parking bays, streetlights, and bollards.
- Expanded procedural city blocks with building entries/windows, sidewalks, alleys, plazas, crosswalks, and streetlights.
- Expanded procedural interiors with room-role furniture layouts including tables, chairs, beds, shelves, cabinets, counters, floor lamps, and cluster footprints.
- Propagated district, street-grid, and room-cluster macro state into the new procedural controls so high-level world constructs now generate richer architecture, roads, and rooms.
- Expanded scene materialization family parts, control aliases, and surface zones for the new architectural, street, city-block, and interior components.

## 2026-05-02 - Modular Vehicle, Boat, and Weapon Families

- Added reusable ShapeIR component builders for hardpoints, module sockets, crew bays, cargo bays, thrusters, antennas, and stabilizers.
- Expanded procedural vehicle generation with crew bays, payload bays, weapon hardpoints, equipment/module sockets, thrusters, stabilizers, and sensor antennas.
- Expanded procedural weapon generation with attachment rails, hardpoints, module sockets, muzzle devices, ammo/battery bays, power cells, sling mounts, stabilizers, and smart sensors.
- Expanded procedural boat generation with crew/bridge bays, payload bays, deck hardpoints, mission sockets, bow/stern thrusters, stabilizer fins, sensor masts, and mooring cleats.
- Expanded scene materialization family parts, state-control aliases, and surface zones so authored scenes can drive the new modular vehicle/boat/weapon controls and receive meaningful material identity.
- Expanded family inference and part tagging so modular terms such as `mission_socket`, `vehicle_hardpoint`, `payload_bay`, `thruster`, `smart_sensor`, and `power_cell` resolve into the right procedural families.

## 2026-05-02 - Named Procedural Loadouts and Archetypes

- Added reusable procedural loadout presets for vehicles, boats, and weapons so a single authoring value can expand into many concrete geometry controls.
- Added vehicle loadouts for patrol VTOLs, cargo rovers, scout drones, assault carriers, and aircraft interceptors, including presets for mobility, wheels/tracks/rotors/wings, crew bays, payload bays, hardpoints, sockets, thrusters, stabilizers, sensors, and proportions.
- Added boat loadouts for research vessels, patrol cutters, cargo barges, sail sloops, rescue workboats, and submersible scouts, including presets for hull type, propulsion, cabins, decks, cargo holds, rails, crew/payload bays, mission sockets, thrusters, stabilizers, sensors, cleats, sails, and rigging.
- Added weapon loadouts for railgun marksman rifles, breacher shotguns, plasma sidearms, salvage tools, ceremonial blades, and boarding pikes, including presets for barrels, blades, tool heads, rails, hardpoints, module sockets, muzzle devices, ammo/power systems, sling mounts, stabilizers, smart sensors, and proportions.
- Taught procedural blueprints to merge loadout defaults with explicit user controls, preserving direct user overrides while turning high-level archetype words into rich part layouts.
- Taught scene materialization to propagate `loadout`, `family_loadout`, `vehicle_loadout`, `boat_loadout`, `vessel_loadout`, `weapon_loadout`, `tool_loadout`, and archetype aliases into generated procedural assets.
- Expanded scene and asset family inference so loadout names such as `patrol_vtol`, `cargo_rover`, `research_vessel`, `patrol_cutter`, `railgun_marksman`, `breacher_shotgun`, and `plasma_sidearm` resolve into the right procedural generators.

## 2026-05-02 - Scene Style Packs as Procedural Visual Systems

- Added scene-local `style_pack` blocks so hand-authored scenes/worlds can define reusable visual-system payloads alongside kits, generators, variant families, biomes, and objects.
- Added built-in scene style packs for frontier outposts, civic markets, industrial vehicle yards, naval harbors, sci-fi hangars, and arcane citadels.
- Taught scene lowering to apply style packs directly to regions, placement zones, modules, objects, and arrays while propagating style-pack defaults into kits, variant families, generators, biomes, scatters, and environments.
- Style packs can now carry procedural state controls, loadouts, child/module hints, semantic tags, material layers, wear stories, decals, markings, and material bindings into generated scene objects.
- Expanded world-piece lowering so direct authored controls such as `vehicle_loadout`, `boat_loadout`, `weapon_loadout`, counts, style controls, and family knobs become Scene Graph state consumed by materialization.
- Expanded creative and object grammars so `loadout`, `family_loadout`, `vehicle_loadout`, `boat_loadout`, `vessel_loadout`, `weapon_loadout`, `tool_loadout`, `kit_style`, `visual_system`, and `theme_pack` participate in shape, surface, and archetype derivation.

## 2026-05-02 - Auto-Expanding Variant Family Grammars

- Added automatic variant-family option pools for vehicles, boats, weapons, buildings, interiors, machines, furniture, foliage, roads, infrastructure, and access systems.
- Taught `variant_family` and `generator` blocks to infer usable option pools from high-level fields such as `family`, `asset_family`, `source_family`, `procedural_family`, `pool`, `archetype`, `object_archetype`, `loadout`, `visual_system`, `kit_style`, and `theme_pack`.
- Added generated option records with concrete procedural families, asset refs, loadouts, compatibility tags, module sockets, semantic tags, and selection weights.
- Expanded generator constraints so authored rules such as `requires_loadout`, `requires_family`, `requires_style`, `requires_tag`, `requires_socket`, and `requires_compatibility` can filter generated option pools.
- Taught generator value merging to carry family-level and generator-level direct procedural controls into generated objects while preserving explicit option overrides.
- Enabled scene style packs to combine with automatic variant pools, so a style pack can theme a generated fleet, harbor set, weapon rack, market kit, machine line, or traversal/access system without hand-authoring every option.

## 2026-05-02 - Socket-Aware Generated Assemblies

- Added generator-level assembly language controls such as `assembly`, `assembly_mode`, `auto_assemble`, `assembly_target`, `anchor_object`, `anchor_asset`, `assembly_sockets`, `child_socket`, `chain_socket`, and assembly slot layout knobs.
- Taught generated variant families to become socketed systems instead of loose object lists: weapon/tool racks, boat docks and harbors, vehicle parking pads and hangars, room furniture layouts, machine lines, site plans, terrain clusters, convoys, road networks, access chains, and utility runs.
- Added automatic assembly anchors with procedural source families, inherited scene region/surface/material context, semantic assembly tags, socket inventories, service/room/site state, and generated slot positions.
- Added per-generated-object assembly state and tags so downstream materialization can identify assembly members, group membership, assembly mode, family, and slot order.
- Added automatic scene socket and attachment generation that snaps generated objects into anchor slots or chains generated members through family-appropriate sockets such as `rack_socket`, `mooring`, `hangar_bay`, `floor_grid`, `base_mount`, `road_end`, `walkway_end`, and `pipe_end`.
- Preserved explicit generator sockets and attachments while adding reusable auto-assembly behavior for broad object families.

## 2026-05-02 - Assembly-Aware Materialization and Anchor Geometry

- Taught scene materialization to turn assembly state into generated asset shape controls, including assembly mode, family, group, member role, slot counts, socket sequences, child sockets, and chain sockets.
- Added assembly-driven part vocabulary so generated assets can include assembly anchors, assembly slots, rack sockets, moorings, parking bays, hangar bays, floor grids, machine-line mounts, lot sockets, terrain anchors, and route/chain link sockets.
- Expanded generated interface authoring so assembly anchors and members receive sockets, anchors, slot-indexed interfaces, and connection metadata from scene assembly relationships.
- Added assembly surface authoring that gives racks, docks, parking pads, hangars, room layouts, machine lines, site plans, terrain clusters, route networks, access chains, utility runs, and convoys material zones and slot markings.
- Expanded procedural infrastructure generation so assembly anchors produce real socket-addressed geometry: rack frames, rack sockets, mooring/dock slots, parking pads, hangar bays, machine-line mounts, site-plan slots, and generic assembly slots.
- Preserved the existing generated asset path while making scene-level assembly language affect generated source, interfaces, surface identity, and procedural geometry.

## 2026-05-02 - Assembly-Conditioned Member Geometry

- Added shared procedural blueprint controls for `assembly_mode`, `assembly_member`, and assembly slot counts so generated members can change shape based on how they are placed in an assembly.
- Expanded vehicle generation with parking/hangar/convoy member hardware including wheel chocks, tie-down sockets, service umbilicals, and front/rear convoy links.
- Expanded weapon/tool generation with rack-conditioned clamps and rack index labels for generated armories and tool racks.
- Expanded boat generation with docking-bay mooring lines and fenders so generated vessels visibly attach to harbor/dock assemblies.
- Expanded road and access generation with route-network and access-chain couplers plus alignment marks/braces for chained traversal systems.
- Expanded furniture generation with room-layout floor pads and wall brackets so placed furniture carries explicit anchoring hardware.
- Expanded assembly surface zones and generated part vocabulary for rack clamps, rack labels, mooring lines, fenders, wheel chocks, tie-downs, service umbilicals, floor pads, wall brackets, road couplers, access couplers, and alignment braces.

## 2026-05-02 - Procedural Kit Grammars for Functional Sets

- Added built-in procedural kit grammars for armories, harbors, hangars, workshops, interior suites, road networks, and utility corridors.
- Taught `kit` blocks to infer reusable functional-set grammars from kit name, source, kind, archetype, and visual-system values.
- Kit grammars now expand into core procedural set objects plus coordinated generator families for weapons, tools, boats, vehicles, machines, rooms, buildings, roads, access chains, and utilities.
- Generators inherit kit style, material, region, placement, tags, loadouts, and procedural context while reusing assembly anchors, sockets, and chain behavior.
- Kit systems automatically link generated assembly anchors back to the kit core so a high-level functional set becomes a connected scene system.
- Inline generator constraints now support `requires_family`, `requires_loadout`, `requires_style`, and `requires_tag` so kit grammars can select subfamilies and named loadouts.

## 2026-05-02 - Circulation and Utility Scene Macros

- Added scene language constructs for `floorplan`, `road_intersection`, `infrastructure`, `service_network`, and `access`.
- `floorplan` blocks now expand into multi-floor interior systems with floor cores, corridors, rooms, stair cores, containment relationships, room-to-corridor openings, and vertical circulation links.
- `road_intersection` blocks now expand into a procedural junction core with branch approaches, lane/crosswalk/curb/stop-line controls, and explicit road connectivity relationships.
- `service_network` blocks now expand into procedural infrastructure systems with typed service runs for power, water, data, air, fuel, drains, and generic utilities, plus optional maintenance access.
- Direct `infrastructure` and `access` world pieces now map to procedural infrastructure and traversal families so scenes can author utility rooms, pipe networks, catwalks, tunnels, ladders, platforms, and service corridors.
- Procedural interior blueprints now honor `door_count`, `window_count`, `doors`, and `windows`, enabling macro-generated rooms and corridors to request real perimeter openings instead of a fixed door/window layout.

## 2026-05-02 - Building Complex Scene Macro

- Added a public `building_complex` scene construct for authoring complete buildings instead of only isolated exterior shells or room clusters.
- `building_complex` now expands into a procedural setpiece core, exterior building shell, generated multi-floor interior floorplan, entry access pieces, utility/service runs, maintenance access, and explicit relationships between all major systems.
- Building programs such as lab, factory, residential, office, market, civic, hospital, commercial, fortress, and mixed-use now choose default room-role mixes and utility-service sets.
- Building shells inherit floor, bay, entry, service-door, facade, storefront, signage, roof-equipment, fire-escape, side-window, and rear-window controls from the high-level building complex.
- Generated interiors inherit floor count, rooms per floor, room dimensions, corridor width, stair cores, and program-specific room roles.
- Authoring toggles such as `interiors = false`, `utilities = false`, and `access = false` can remove major subsystems while preserving the reusable building-complex macro.

## 2026-05-02 - Harbor and Dockyard Scene Macros

- Added public `harbor_complex` and `dockyard` scene constructs for authoring waterfront systems from one high-level block.
- Harbor macros now expand into a procedural setpiece core, water basin, quay access, piers/docks, moored procedural boats, warehouses, gantry cranes, service networks, maintenance access, and shore access routes.
- Harbor types such as cargo, industrial, dockyard, naval, fishing, marina, and research choose default vessel loadout mixes and utility-service sets.
- Piers use procedural bridge world pieces with dock, mooring, cleat, railing, and span controls.
- Moored vessels are generated as procedural boats with docking-bay assembly state so downstream boat geometry can grow mooring lines, cleats, and fenders.
- Warehouse subsystems reuse the `building_complex` macro, giving harbors connected waterfront buildings with generated shell and interior floorplan structure.
- Authoring toggles such as `boats = false`, `warehouses = false`, `cranes = false`, `utilities = false`, and `access = false` can remove major harbor subsystems while keeping the harbor macro reusable.

## 2026-05-02 - Vehicle Yard and Hangar Scene Macros

- Added public `vehicle_yard` and `hangar_complex` scene constructs for authoring ground vehicle yards, service depots, aircraft hangars, drone bays, and flightline systems.
- Vehicle-yard macros now expand into a procedural setpiece core, yard or flight-apron surface, parking/hangar bay anchors, procedural vehicles, service buildings, repair bays, service machines, utility networks, maintenance access, and approach routes.
- Vehicle yard types such as cargo, industrial, military, service, convoy, aircraft, drone, and hangar choose default vehicle loadout mixes and utility-service sets.
- Generated vehicles are procedural vehicle objects with parking or hangar assembly state, letting downstream geometry add wheel chocks, tie-downs, service umbilicals, and bay hardware.
- Service buildings reuse the `building_complex` macro, so yards and hangars can include connected repair offices, workshops, and service interiors.
- Repair bays and bay anchors use procedural infrastructure state with parking/hangar bay counts, service mounts, tie-downs, chocks, conduits, pipes, and junction boxes.
- Authoring toggles such as `vehicles = false`, `machines = false`, `repair_bays = false`, `structures = false`, `pads = false`, `utilities = false`, and `access = false` can remove major subsystems while preserving the reusable macro.

## 2026-05-02 - Factory and Production Line Scene Macros

- Added public `factory_complex` and `production_line` scene constructs for authoring industrial facilities and reusable machine-line systems.
- Factory macros expand into procedural setpiece cores, production floors, factory halls, production lines, storage buffers, loading docks, control rooms, service utilities, worker access, and connected vehicle yards.
- Production-line macros expand into machine-line anchors, station machines, conveyors, buffers, control rooms, and service runs.
- Factory types such as assembly, industrial, refinery, electronics, weapons, vehicles, food, cargo, and logistics choose machine station sequences and utility-service defaults.
- Production stations and conveyors are procedural machine objects with machine-line assembly state so downstream geometry can build service mounts, conveyors, tool heads, hydraulics, and station hardware.
- Authoring toggles such as `lines = false`, `machines = false`, `conveyors = false`, `storage = false`, `loading_docks = false`, `control_rooms = false`, `utilities = false`, `access = false`, and `vehicles = false` can remove major subsystems while preserving the reusable macro.

## 2026-05-02 - Industrial District Scene Macro

- Added a public `industrial_district` scene construct for authoring whole production districts instead of isolated factories, yards, roads, and utility pieces.
- Industrial districts expand into a district core, ground platform, internal service-grid roads, factories, warehouses, vehicle yards or hangars, harbors or dockyards, rail spurs, substations, tank farms, utility spines, and security access gates.
- District types such as cargo, logistics, refinery, chemical, energy, heavy industry, vehicles, weapons, electronics, aerospace, shipyard, dockyard, and naval choose factory mixes and service profiles.
- Factory, warehouse, yard, harbor, rail, utility, tank, substation, and gate subsystems are connected through explicit containment, routing, attachment, and service relationships.
- Authored controls such as `factories`, `warehouses`, `vehicle_yards`, `harbors`, `rail_spurs`, `service_runs`, `substations`, `storage_tanks`, `gates`, `lines_per_factory`, and `machines_per_line` shape district composition.
- Authoring toggles such as `factories = false`, `warehouses = false`, `vehicle_yards = false`, `harbors = false`, `roads = false`, `rail = false`, `utilities = false`, `substations = false`, `storage_tanks = false`, and `gates = false` can remove major district subsystems.

## 2026-05-02 - Supply Network and Transport Corridor Scene Macros

- Added public `transport_corridor` and `supply_network` scene constructs for authoring world-scale logistics and production chains.
- Transport corridors expand into corridor cores, mode-specific spines, sequential route segments, interchanges, bridges, tunnels, depots, service networks, and checkpoints.
- Corridor modes include road, rail, canal, pipeline, and utility, with mode-specific procedural state for lanes, tracks, canals, pipes, valves, pumps, conduit, cable trays, docks, signals, and loading zones.
- Supply networks expand into supply cores, industrial districts, direct producer factories, storage hubs, ports or dockyards, fleet yards, transport corridors, service spines, and goods-flow relationships.
- Network types such as cargo, logistics, refinery, chemical, energy, electronics, naval, vehicles, weapons, and aerospace choose default goods, district mixes, corridor modes, and service profiles.
- Authored controls such as `goods`, `districts`, `corridors`, `depots`, `ports`, `factories`, `vehicle_yards`, `service_runs`, `segments_per_corridor`, `factories_per_district`, `warehouses_per_district`, and `modes` shape the chain.
- Authoring toggles such as `corridors = false`, `districts = false`, `depots = false`, `ports = false`, `factories = false`, `vehicle_yards = false`, `services = false`, `roads = false`, `rail = false`, `canal = false`, and `pipeline = false` remove major logistics subsystems.

## 2026-05-02 - Civilization, Settlement, and Resource Region Scene Macros

- Added public `resource_region`, `settlement`, and `civilization` scene constructs for authoring inhabited world systems and resource-driven territories.
- Resource regions expand into resource cores, biome terrain, extractor sites, resource depots, work camps, service networks, and haul routes.
- Settlement macros expand into settlement cores, ground terrain, street grids, homes, civic buildings, markets, workshops, fields, defense rings, watchtowers, gates, utility networks, and trade routes.
- Civilization macros expand into territory cores, capital and satellite settlements, resource regions, frontier outposts, trade corridors, supply networks, and frontier defenses.
- Civilization types such as frontier, empire, trade, industrial, naval, coastal, and fortress choose settlement mixes, resource-region defaults, trade route modes, and support systems.
- Resource-region types such as forest, farmland, mining, mountain, coastal, river, desert, refinery, swamp, volcanic, and wasteland choose resource mixes and service profiles.
- Authored controls such as `settlements`, `resource_regions`, `trade_routes`, `supply_networks`, `outposts`, `defenses`, `homes`, `markets`, `workshops`, `farms`, `extractors`, `resources`, `resource_types`, `settlement_types`, and `civilization_type` shape the generated world.
- Authoring toggles such as `settlements = false`, `resource_regions = false`, `trade_routes = false`, `supply_networks = false`, `outposts = false`, `defenses = false`, `homes = false`, `markets = false`, `farms = false`, `extractors = false`, and `services = false` remove major civilization subsystems.

## 2026-05-02 - Faction, Biome, Architecture, and Object Grammar Style Systems

- Added public `faction_pack`, `biome_kit`, `architecture_grammar`, and `object_grammar` declarations that compile into reusable style-pack payloads.
- The same four constructs can be declared inside scenes/worlds and referenced by generated systems through `faction_pack`, `biome_kit`, `architecture_grammar`, and `object_grammar` fields.
- Faction packs expand high-level identity controls into faction state, motifs, palettes, materials, markings, emblems, banners, signage, decals, wear stories, and semantic tags.
- Biome kits expand biome/resource controls into landform state, terrain features, resource bias, hazards, weathering materials, decals, zones, and resource-service defaults.
- Architecture grammars expand form-language controls into facade style, roof style, structural profile, bay pattern, columns, arches, towers, trims, material zones, and architectural tags.
- Object grammars expand part-language controls into object archetype, loadout, module sockets, child sockets, handles, rails, panels, detail density, material zones, markings, and object tags.
- Scene macro children now inherit style-pack state as well as surfaces, so faction, biome, architecture, and object grammar choices flow into generated civilization, settlement, resource, district, factory, corridor, and prop systems.
- Style-pack composition now lets later explicit grammar refs override broad faction defaults while preserving authored node state when the merged pack is applied.

## 2026-05-02 - Gameplay and World Function Scene Macros

- Added public `quest`, `objective`, `interactable`, `encounter`, `traversal_gate`, `resource_economy`, and `control_zone` scene constructs for authoring functional world behavior.
- Quest macros expand into quest cores, ordered objective chains, quest-giver interactables, reward caches, progression dependencies, and track/claim affordances.
- Objective macros expand into objective cores, target markers, progress affordances, requirement dependencies, optional/timed state, and required-count controls.
- Interactable macros expand into concrete interactive anchors with action, reveal, requirement, cooldown, charges, reward state, and scene-graph affordances.
- Encounter macros expand into encounter cores, spawn anchors, cover nodes, patrol routes, loot interactables, difficulty/faction/trigger state, and encounter relationships.
- Traversal-gate macros expand into gated access, requirement locks, unlock affordances, optional bypass routes, and blocks-until-complete traversal state.
- Resource-economy macros expand into economy cores, producers, storage depots, consumers, trade routes, goods lists, production/demand state, and producer-storage-consumer flow relationships.
- Control-zone macros expand into territory cores, control boundaries, capture points, defenses, patrol encounters, faction-control state, and capture affordances.
- Macro expansion now retargets gameplay affordance and relationship references from authored macro names to generated core object names, so blocks can reveal or depend on other macro blocks directly.

## 2026-05-02 - Agent, NPC, and World Behavior Scene Macros

- Added public `npc`, `agent`, `crowd`, `schedule`, `patrol_route`, `dialogue_tree`, `inventory_loadout`, `spawn_ecology`, `faction_behavior`, and `behavior_graph` scene constructs for authoring living world systems.
- Actor macros expand into actor cores with faction, disposition, awareness, movement, home, schedule, patrol, dialogue, inventory, and behavior-profile state.
- Crowd macros expand into group cores, repeated actor members, shared routines, formations, faction tags, and actor containment relationships.
- Schedule macros expand into routine cores, activity anchors, ordered route relationships, time-window state, and activity affordances.
- Patrol-route macros expand into route cores, looped waypoint anchors, movement/detection state, and sequential route relationships.
- Dialogue-tree macros expand into conversation cores, topic interactables, speaker links, reveal relationships, tone/type state, and choose-dialogue affordances.
- Inventory-loadout macros expand into loadout cores, item interactables, capacity/currency/trade state, equipped-item state, and use-item affordances.
- Spawn-ecology macros expand into ecology cores, habitat terrain, spawn encounters per species, population/respawn state, and ecology containment relationships.
- Faction-behavior macros expand into faction behavior cores, doctrine objectives, control zones, patrol routes, squads, hostility/alliance state, and goal relationships.
- Behavior-graph macros expand into world-simulation cores, faction behavior systems, simulated crowds, spawn ecologies, schedule loops, tick-rate state, and graph containment relationships.
- Procedural materialization now forwards actor, NPC, spawn, faction, and loop counts into setpiece shape controls, and procedural setpieces can emit actor markers, loadout packs, spawn nests, and behavior nodes.

## 2026-05-02 - Stateful Event, Trigger, and Scene Mutation Macros

- Added public `event`, `event_emitter`, `trigger_volume`, `timer`, `state_machine`, `state_transition`, `conditional_spawn`, `alert_network`, `scene_state`, and `scene_mutation` scene constructs for reactive worlds.
- Event macros expand into event cores, channel listener anchors, channel/payload/priority/cooldown state, and emit affordances.
- Event-emitter macros expand into emitter cores, generated event objects, channel wiring, activation state, and emit-event affordances.
- Trigger-volume macros expand into trigger cores, bounds markers, trigger event emitters, filters, cooldown/one-shot state, and enter-trigger affordances.
- Timer macros expand into timer cores, tick anchors, completion emitters, duration/loop/start-condition state, and start/tick affordances.
- State-machine macros expand into machine cores, scene-state nodes, transition cores, ordered state routes, initial/terminal state, and event-driven transition state.
- Conditional-spawn macros expand into spawn-rule cores, condition triggers, spawn encounters, actor lists, respawn state, and trigger-to-spawn relationships.
- Alert-network macros expand into alert cores, trigger sensors, event emitters, responder encounters, faction/radius/propagation state, and sensor containment relationships.
- Scene-state and scene-mutation macros add explicit world-state nodes and conditional world-change cores with before/after states, apply affordances, emitted events, and target state payloads.
- Procedural materialization now forwards event, channel, state, transition, condition, trigger, mutation, and responder counts into shape controls, and procedural setpieces can emit state nodes, state links, event markers, and trigger-volume markers.

## 2026-05-02 - Procedural Action and Animation Scene Macros

- Added public `timeline`, `sequencer`, `animation_clip`, `action`, `action_pose`, `motion_path`, `moving_part`, `door_action`, `gate_action`, `machine_cycle`, `vfx_emitter`, and `sound_cue` scene constructs for animated and event-driven assets.
- Timeline macros expand into timeline cores, ordered animation clips, clip routes, duration/loop/start-event state, and timeline affordances.
- Sequencer macros expand into sequencer cores, ordered action steps, optional event emitters, blocking/loop state, and step relationships.
- Animation clips expand into clip cores, keyframe pose nodes, interpolation routes, duration/blend/loop state, and pose containment relationships.
- Action macros expand into action cores, optional moving parts, VFX emitters, sound cues, event emitters, duration/interrupt/requirement state, and play affordances.
- Motion paths and moving parts expand into path cores, waypoint anchors, moving-part cores, path relationships, axis/distance/angle/speed state, and move affordances.
- Door and gate actions expand into access cores, animated moving panels, optional sound cues, requirements, duration state, and open/close style affordances.
- Machine cycles expand into machine-cycle cores, timelines, per-phase moving parts, phase lists, loop/duration state, and machine motion relationships.
- VFX emitters and sound cues add language-level visual/audio action hooks with effect/sound type, duration/radius/volume/rate state, and play affordances.
- Procedural materialization now forwards timeline, clip, pose, moving-part, phase, VFX, and sound counts into shape controls, and procedural setpieces can emit animation keyframes, timeline spans, moving-part hinges/travel markers, and effect cue markers.

## 2026-05-02 - Physics and Destruction Scene Macros

- Added public `physics_body`, `physics_joint`, `hinge_joint`, `physics_constraint`, `breakable_part`, `damage_state`, `debris_field`, `rope`, `cable`, `cloth_flag`, `force_field`, and `destruction_event` scene constructs for physically reactive and destructible worlds.
- Physics-body macros expand into body cores, collider anchors, body type, mass, collision shape, gravity, damping, friction, restitution, collision-layer state, and apply-force affordances.
- Joint and constraint macros expand into joint cores, anchor nodes, body references, axes, limits, motors, stiffness, damping, break-force state, and solve affordances; hinge joints can also drive generated moving parts.
- Breakable parts expand into destructible cores, generated physics bodies, damage-state nodes, debris fields, destruction events, health, break-threshold, fracture-pattern, and damage affordances.
- Damage-state and debris-field macros add explicit damage-level surface markers, crack/dent/scorch/missing-chunk state, shard physics bodies, debris spread, lifetime, and fragment counts.
- Rope and cable macros generate flexible segment chains with dynamic physics bodies, link joints, tension/slack/break-force state, and attached segment relationships.
- Cloth flags generate cloth panels, pin constraints, wind response, tear thresholds, and cloth-pin relationships.
- Force-field and destruction-event macros add impulse/radial fields, affected layers, damage/impulse payloads, optional debris, VFX, sound cues, and detonation affordances.
- Procedural materialization now forwards physics-body, collider, joint, hinge, constraint, damage-state, debris, fragment, rope, cloth, and force-field counts into shape controls, and procedural setpieces can emit physics body markers, joint markers, debris fragments, flexible rope/cable/cloth segments, and force-field markers.

## 2026-05-02 - Damage-Aware Surface Scene Macros

- Added public `surface_layer`, `material_zone`, `decal`, `wear_pattern`, `damage_surface`, and `surface_transition` scene constructs for language-level surface identity.
- Surface-layer macros expand into material stack cores, layer swatches, material-layer surface overrides, opacity/thickness/blend state, and surface sample controls.
- Material-zone macros add zone-to-material bindings, zone masks, coverage state, material bindings, and zone surface overrides.
- Decal macros expand into decal cores and repeated decal marks with story decals, markings, decal targets, placement state, rotation variance, and decal-count controls.
- Wear-pattern macros add field-use stories, edge wear, scratches, chips, repeated wear marks, pattern controls, and wear-level surface overrides.
- Damage-surface macros add cracked/scorched/dented/scratched/broken surface identity with damage decals, exposed materials, crack/scorch/dent/scratch/chip counts, and repeated damage marks.
- Surface-transition macros add from-material/to-material transitions, exposed-edge bands, transition profiles, gradient state, and transition material layers.
- Scene materialization now forwards surface-layer, material-zone, decal, wear, damage, crack, scorch, dent, scratch, chip, and transition counts into procedural shape controls.
- Surface runtime and grammar now treat damage decals, exposed materials, transition materials, damage levels, and transition profiles as procedural surface-driving inputs.
- Procedural setpieces can emit surface layer samples, material zone markers, decal marks, wear scratches, damage cracks/scorch marks, and exposed material transition bands.

## 2026-05-02 - Environment Effects Scene Macros

- Added public `weather_system`, `atmosphere`, `wind_zone`, `liquid_body`, `puddle_field`, `fire_source`, `smoke_emitter`, `mist_volume`, `wetness_zone`, `heat_haze`, `time_of_day`, and `environment_effect` scene constructs.
- Weather systems expand into weather cores plus optional atmosphere, wind, wetness, and mist subsystems with weather type, rain/snow/fog, wetness, wind speed, and effect-count state.
- Atmosphere and time-of-day macros add sky, cloud, fog density, ambient intensity, hour, sun angle, moon phase, and lighting-state surface controls.
- Wind-zone macros add directional flow, gust counts, turbulence-style state, and wind effect controls.
- Liquid, puddle, and wetness macros add liquid type, wet materials, wetness level, puddle counts, repeated puddle markers, waterline decals, wet-streak decals, and wet-sheen material layers.
- Fire-source macros add emissive fire state and can generate smoke and heat-haze subsystems with soot, ash, heat-bloom, and scorch surface controls.
- Smoke, mist, and heat-haze macros add volumetric haze, smoke density, mist density, heat shimmer, atmosphere decals, and environment volume controls.
- Scene materialization now forwards weather, atmosphere, wind, liquid, puddle, fire, smoke, mist, wetness, heat-haze, time-of-day, and generic environment-effect counts into procedural shape controls.
- Surface runtime and surface grammar now treat wetness, liquid type, weather decals, environment decals, fog density, smoke density, and heat-haze level as surface-driving inputs.
- Procedural setpieces can emit weather effect markers, atmosphere layers, wind gusts, liquid/puddle wet regions, fire sources, smoke/mist volumes, and time-of-day lighting markers.

## 2026-05-02 - Camera and Cinematic Scene Macros

- Added public `shot`, `shot_sequence`, `camera_rail`, `look_at_target`, `focal_zone`, `cutscene_beat`, `orbit_camera`, `inspection_camera`, `focus_pull`, `camera_volume`, `presentation_rig`, and `composition_guide` scene constructs.
- Shot macros expand into camera-record scene objects with framing, target, duration, FOV, lens, focus distance, depth-of-field, optional look targets, and focal zones.
- Shot sequences expand into ordered shot cores with route relationships, duration splitting, shot counts, and generated camera records.
- Camera rails expand into rail cores, waypoint markers, ordered path relationships, rail length, speed, easing, and camera path controls.
- Look-at targets, focal zones, focus pulls, camera volumes, cutscene beats, and composition guides add reusable cinematic anchors and constraints.
- Orbit and inspection camera macros add explicit camera modes with orbit radius, orbit degrees, target, and derived camera records.
- Presentation rigs generate shot sequences, orbit cameras, and composition guides from one high-level rig construct.
- Scene lowering now derives schema-valid camera records from cinematic scene objects, so authored shots become real scene cameras instead of passive metadata.
- Scene materialization forwards shot, sequence, rail, target, focal, beat, orbit, inspection, focus-pull, camera-volume, presentation-rig, composition-guide, and camera counts into procedural shape controls.
- Procedural setpieces can emit camera frustum markers, camera rails, focal targets, camera volumes, and cutscene beat markers.

## 2026-05-02 - Audio and Acoustic Scene Macros

- Added public `ambient_bed`, `sound_zone`, `reverb_space`, `acoustic_occluder`, `sound_propagation`, `music_state`, `music_transition`, `stinger`, `foley_emitter`, `audio_bus`, `listener_zone`, and `acoustic_material` scene constructs.
- Ambient beds expand into soundscape cores with layers, bus, volume, loop, radius, and generated sound-zone layers.
- Sound zones add attenuation, occlusion, priority, volume, bus routing, and generated listener blend zones.
- Reverb spaces and acoustic occluders add room tone, reverb time, damping, wet level, absorption, transmission, and occlusion state.
- Sound propagation macros add max-distance, ray-count, attenuation, occlusion state, and propagation probe markers.
- Music states and transitions add music layers, mood, intensity, tempo, crossfade triggers, and generated transition state anchors.
- Stingers and foley emitters add event-driven audio cues with trigger, material, rate, randomization, cooldown, and sound-cue integration.
- Audio buses and listener zones add language-level mix routing, sends, listeners, ducking, priority, blend radius, and listener-mode controls.
- Acoustic materials add surface-level absorption, reflection, transmission, roughness, and acoustic profile controls.
- Scene materialization forwards audio, ambience, sound-zone, reverb, occluder, propagation, music, stinger, foley, bus, listener, and acoustic-material counts into procedural shape controls.
- Procedural setpieces can emit ambient beds, sound-zone attenuation regions, reverb volumes, acoustic occluders, propagation rays, music nodes, foley emitters, listener blend regions, and acoustic material swatches.

## 2026-05-02 - Interaction and Diegetic UI Scene Macros

- Added public `interaction_prompt`, `interaction_zone`, `affordance`, `usable`, `pickup`, `inspect_point`, `terminal`, `control_panel`, `switch`, `lever`, `button`, `door_lock`, `quest_marker`, `signage`, `map_marker`, `diegetic_hud`, and `ui_anchor` scene constructs.
- Interaction prompts and zones add world-space prompts, proximity ranges, labels, icons, actions, requirements, reveals, one-shot state, and priority controls.
- Affordance and usable macros add reusable action cores with hold time, cooldown, charges, target routing, and explicit affordance records.
- Pickup and inspect-point macros add item stacks, pickup actions, inspection text, lore reveal hooks, and optional inspection anchors.
- Terminal and control-panel macros add panel modes, channels, screen counts, generated buttons/switches, and nested interaction controls.
- Switches, levers, buttons, and door locks add toggle/press/pull/unlock controls with channels, targets, key-item requirements, locked state, and generated prompt/control children.
- Quest markers, signage, and map markers add objective tracking, readable wayfinding, map pins, route hints, and diegetic UI anchors.
- Diegetic HUDs and UI anchors add in-world widget anchors with screen/world-space flags, contextual visibility, labels, and display text.
- Scene materialization forwards prompt, zone, affordance, pickup, inspect, terminal, control, lock, quest, map, HUD, and UI-anchor counts into procedural shape controls.
- Procedural setpieces can emit prompt plaques, interaction ranges, usable nodes, pickups, inspect anchors, terminal screens, control panels, buttons, locks, quest markers, signage, map pins, HUD panels, and widget anchors.

## 2026-05-02 - Mission and Gameplay Rule Scene Macros

- Added public `mission`, `objective_chain`, `success_condition`, `failure_condition`, `reward_table`, `loot_table`, `inventory_slot`, `crafting_station`, `recipe`, `shop`, `vendor`, `currency`, `reputation_rule`, `unlock_rule`, `progression_track`, and `gameplay_rule` scene constructs.
- Mission macros add mission type, objective counts, reward counts, success/failure condition counts, repeatable/tracked state, level, XP, and generated objective chains, rewards, and condition nodes.
- Objective chains generate ordered objective cores with dependency and route relationships between steps.
- Success and failure conditions add explicit condition checks, thresholds, timers, emitted events, and evaluate affordances.
- Reward tables generate currency rewards, loot tables, and optional reputation rule children.
- Loot tables generate inventory-slot candidates with loot rolls, rarity, weights, and item lists.
- Crafting stations generate recipe nodes and optional control-panel interactions; recipes define input/output lists, station refs, craft time, and currency costs.
- Shops and vendors define stock, prices, currencies, discounts, factions, reputation requirements, and generated shop inventory slots.
- Currency, reputation, unlock, progression, and generic gameplay-rule macros add economy amounts, faction deltas, gated unlocks, level tracks, rule triggers, conditions, effects, and priority state.
- Scene materialization forwards mission, objective-chain, condition, reward, loot, inventory-slot, crafting, recipe, shop, vendor, currency, reputation, unlock, progression, and gameplay-rule counts into procedural shape controls.
- Procedural setpieces can emit mission briefing nodes, objective tasks, gameplay condition markers, reward/loot regions, inventory slots, crafting stations, shop/vendor markers, currency tokens, reputation nodes, unlock gates, and progression-track level markers.

## 2026-05-02 - AI Director and Encounter Orchestration Scene Macros

- Added public `director`, `encounter_director`, `director_intent`, `pacing_curve`, `threat_budget`, `spawn_wave`, `spawn_budget`, `combat_phase`, `stealth_phase`, `escalation_rule`, `adaptive_difficulty`, `encounter_beat`, `director_signal`, `threat_zone`, and `reinforcement_route` scene constructs.
- Director and encounter-director macros add director type, intents, pacing, threat budget, spawn waves, combat/stealth phase counts, escalation, adaptive difficulty, encounter beats, threat zones, max-active counts, difficulty, and tension ranges.
- Director macros generate pacing curves, threat budgets, adaptive difficulty nodes, escalation rules, director intents, spawn waves, phases, and threat zones from one orchestration block.
- Pacing curves generate ordered encounter beats with route relationships and tension/pressure/relief state.
- Threat budgets can generate spawn budgets with enemy types, reserves, max-active counts, and budget allocation state.
- Spawn waves generate queued spawn-point anchors and optional reinforcement routes with wave order, actors, triggers, cooldowns, and budget state.
- Combat and stealth phases add pressure, awareness, entry/exit signals, duration, and generated director signals.
- Escalation and adaptive difficulty rules add thresholds, cooldowns, added-threat/wave payloads, target pressure, min/max difficulty, adjustment rates, and metrics.
- Threat zones add radius, threat budget, cover count, spawn-point count, and generated spawn anchors.
- Scene materialization forwards director, encounter-director, intent, pacing, threat-budget, spawn-wave, phase, escalation, adaptive-difficulty, beat, signal, threat-zone, and reinforcement-route counts into procedural shape controls.
- Procedural setpieces can emit AI director brains, intent nodes, pacing beats, threat budgets, spawn wave queues, phase markers, escalation/adaptive difficulty markers, director signals, threat zones, and reinforcement routes.

## 2026-05-02 - Systemic World Simulation Scene Macros

- Added public `simulation_layer`, `heat_field`, `noise_field`, `visibility_field`, `resource_flow`, `faction_pressure`, `territory_influence`, `alarm_grid`, `patrol_density`, `hazard_field`, `sensor_grid`, `cover_map`, `flow_gate`, `world_metric`, and `simulation_probe` scene constructs.
- Simulation layers define world-state fields, resolution, tick rate, metrics, field counts, and probe counts, then generate authored heat/noise/visibility/resource/faction/territory/alarm/patrol/hazard/sensor/cover subsystems.
- Heat, noise, visibility, hazard, sensor, and cover maps add intensity, decay, diffusion, falloff, coverage, occlusion, cover score, radius, and generated probe samples.
- Resource flows add source/sink nodes, resource type, capacity, flow rate, and generated flow gates.
- Faction pressure and territory influence add faction, territory, pressure, influence, decay, and generated world metrics.
- Alarm grids add alarm state, channels, coverage, sensor grids, and director signals that can feed encounter orchestration.
- Patrol-density maps generate route-density state and reinforcement-route children for navigable patrol lanes.
- Scene materialization forwards simulation, field, resource-flow, faction-pressure, territory, alarm, patrol, hazard, sensor, cover, flow-gate, world-metric, and simulation-probe counts into procedural shape controls.
- Procedural setpieces can emit world simulation cores, field samples, resource channels, faction pressure regions, territory claims, alarm grids, patrol density routes, hazard fields, sensor grids, cover maps, flow gates, world-metric readouts, and simulation probes.

## 2026-05-02 - Civilization Culture and Social-System Scene Macros

- Added public `culture_system`, `law_code`, `policy_rule`, `economy_model`, `trade_policy`, `diplomacy_state`, `social_graph`, `social_relation`, `population_group`, `labor_system`, `ritual_calendar`, `festival`, `belief_system`, `cultural_marker`, and `civic_institution` scene constructs.
- Culture systems define culture type, faction, laws, policies, beliefs, population groups, rituals, festivals, institutions, cohesion, legitimacy, unrest, prosperity, and generated social subsystem counts.
- Culture systems can generate law codes, economy models, diplomacy state, social graphs, ritual calendars, belief systems, population groups, civic institutions, cultural markers, and policy rules from one authored block.
- Law codes generate policy rules and civic institutions; policies carry law refs, effects, thresholds, and priority.
- Economy models generate trade policies, labor systems, and resource-flow children for goods and trade resources.
- Diplomacy states and social graphs generate social-relation nodes with source/target groups, partners, relation type, relation strength, and social weight.
- Population groups generate labor systems and cultural markers with population, roles, jobs, classes, and identity state.
- Ritual calendars generate festivals; festivals and belief systems generate cultural markers for symbols, doctrine, taboos, seasons, meanings, and event identity.
- Scene materialization forwards culture, law, policy, economy, diplomacy, relation, population, labor, ritual, festival, belief, marker, institution, and social customization into procedural shape controls.
- Procedural setpieces can emit culture cores, law panels, policy edicts, economy markets, trade policies, diplomacy treaty nodes, social graphs, social ties, population groups, labor systems, ritual calendars, festivals, belief systems, cultural symbols, and civic institutions.

## 2026-05-02 - Living Biome and Ecology Scene Macros

- Added public `biome_system`, `habitat_zone`, `species_population`, `food_web`, `predator_prey_link`, `migration_route`, `nesting_site`, `resource_patch`, `resource_regeneration`, `growth_cycle`, `weather_ecology_link`, and `ecological_pressure` scene constructs.
- Biome systems define biome type, habitats, species, resources, biodiversity, stability, pressure, and generated ecological subsystem counts.
- Biome systems generate habitat zones, species populations, food webs, renewable resource patches, weather/ecology links, and ecological pressure nodes from one authored block.
- Habitat zones generate resource patches, nesting sites, and migration routes with carrying capacity, coverage, species, and resource state.
- Species populations generate nesting, growth, and migration subsystems with population, carrying capacity, birth rate, mortality, diet, and prey relationships.
- Food webs generate predator/prey links; predator/prey links expose predation pressure through world-metric nodes.
- Resource patches generate resource-regeneration and resource-flow children; regeneration systems generate growth cycles and world metrics.
- Growth cycles add seasonal stages, cycle duration, and growth-stage metrics.
- Weather ecology links connect weather systems to growth, migration, and species sensitivity.
- Ecological pressure nodes generate hazard fields and pressure metrics for scarcity, invasive species, pollution, drought, or other stressors.
- Scene materialization forwards biome, habitat, species, food-web, migration, nesting, resource, regeneration, growth, weather-link, and pressure customization into procedural shape controls.
- Procedural setpieces can emit biome cores, habitat zones, wildlife population markers, food-web nodes, predator/prey pressure links, migration paths, nesting sites, renewable resource patches, growth-cycle markers, weather-coupling nodes, and ecological stress regions.

## 2026-05-02 - Civilization and Ecology Coupling Scene Macros

- Added public `land_use_plan`, `farm_plot`, `hunting_ground`, `fishing_ground`, `grazing_range`, `extraction_site`, `pollution_source`, `conservation_zone`, `restoration_project`, `scarcity_loop`, `settlement_pressure`, `resource_claim`, `harvest_cycle`, `carrying_capacity_rule`, and `biome_impact` scene constructs.
- Land-use plans define settlement, biome, resources, land-use programs, claims, pressure, scarcity, and impact counts, then generate farms, hunting/fishing/grazing regions, extraction sites, conservation zones, restoration projects, resource claims, scarcity loops, and settlement pressure.
- Farm plots generate harvest cycles and biome impacts; harvest cycles generate growth cycles and resource-flow outputs.
- Hunting grounds, fishing grounds, and grazing ranges generate species-population links, carrying-capacity rules, and biome-impact records.
- Extraction sites generate resource claims, resource flows, pollution sources, and biome impacts.
- Pollution sources generate ecological pressure and world metrics for pollution rate.
- Conservation zones generate restoration projects, carrying-capacity rules, and biome-impact nodes.
- Scarcity loops generate resource claims and scarcity metrics from demand/supply deficits.
- Settlement pressure generates ecological pressure and carrying-capacity rules that bind population demand to biome limits.
- Resource claims generate territory influence and resource-flow routes.
- Biome impacts generate ecological pressure and world-metric impact scores.
- Scene materialization forwards land-use, agriculture, hunting, fishing, grazing, extraction, pollution, conservation, restoration, scarcity, claim, harvest, capacity, and impact controls into procedural shape controls.
- Procedural setpieces can emit land-use plans, farm plots, hunting grounds, fishing grounds, grazing ranges, extraction sites, pollution emitters, conservation reserves, restoration regions, scarcity loops, settlement pressure nodes, resource claims, harvest cycles, carrying-capacity rules, and biome-impact markers.

## 2026-05-02 - Resource Logistics and Production Chain Scene Macros

- Added public `supply_chain`, `logistics_hub`, `storage_depot`, `stockpile`, `input_buffer`, `output_buffer`, `processing_stage`, `refinery_stage`, `workshop_stage`, `assembly_stage`, `market_node`, `demand_sink`, `supply_route`, `transport_leg`, `bottleneck`, `throughput_rule`, and `failure_mode` scene constructs.
- Supply chains define goods, stages, markets, demand sinks, routes, hubs, depots, throughput, capacity, latency, loss rate, bottlenecks, and failure modes.
- Supply chains generate storage depots per good, ordered processing/refinery/workshop/assembly stages, market nodes, supply routes, bottlenecks, and failure-mode nodes.
- Logistics hubs generate storage depots plus input/output buffers for local handoff.
- Storage depots generate stockpiles and throughput rules; stockpiles expose inventory metrics.
- Processing, refinery, workshop, and assembly stages generate input buffers, output buffers, throughput rules, and failure modes.
- Market nodes generate demand sinks and stockpile links for exchange points.
- Demand sinks expose demand metrics and can feed scarcity logic.
- Supply routes generate transport legs and resource-flow children; transport legs carry resource-flow state for each mode.
- Bottlenecks generate throughput rules and metrics; failure modes expose failure-rate and recovery-time state.
- Scene materialization forwards logistics, chain, hub, depot, stockpile, buffer, stage, market, demand, route, transport, bottleneck, throughput, failure, goods, stage, mode, inventory, capacity, latency, and loss controls into procedural shape controls.
- Procedural setpieces can emit supply-chain cores, logistics hubs, depots, stockpiles, input/output buffers, processors, refineries, workshops, assemblers, markets, demand sinks, supply routes, transport legs, bottlenecks, throughput rules, and failure-mode markers.

## 2026-05-02 - Faction Production Strategy Scene Macros

- Added public `production_strategy`, `production_priority`, `quota_rule`, `allocation_rule`, `rationing_policy`, `strategic_reserve`, `trade_embargo`, `sabotage_target`, `maintenance_plan`, `repair_schedule`, `mobilization_order`, `production_mode`, `wartime_production`, `peacetime_production`, `procurement_contract`, and `readiness_level` scene constructs.
- Production strategies define priorities, quotas, allocations, reserve goods, rationing, embargo targets, sabotage targets, maintenance targets, repair intervals, mobilization levels, production modes, war state, peace focus, procurement sources, and readiness thresholds.
- Production strategies generate priority nodes, quota rules, allocation rules, strategic reserves, rationing policies, maintenance plans, production modes, mobilization orders, and optional trade embargoes.
- Production priorities generate quota and allocation rules plus supply-chain links for the selected good or strategic goal.
- Quota rules generate throughput rules and quota metrics; allocation rules generate resource-flow children and allocation metrics.
- Rationing policies generate scarcity loops, ration quotas, and ration-rate metrics.
- Strategic reserves generate stockpiles for reserve goods and readiness nodes.
- Trade embargoes generate bottlenecks and diplomacy-state pressure; sabotage targets generate failure modes and bottlenecks.
- Maintenance plans generate repair schedules, prevented failure modes, and throughput stabilizers; repair schedules expose timing metrics.
- Mobilization orders generate wartime production and readiness state; production modes branch into wartime or peacetime production systems.
- Wartime production generates strategic reserves, quota pressure, sabotage risks, and readiness levels; peacetime production generates markets, maintenance plans, and procurement contracts.
- Procurement contracts generate supplier markets, resource claims, and demand sinks; readiness levels expose readiness metrics.
- Scene materialization forwards strategy, priority, quota, allocation, rationing, reserve, embargo, sabotage, maintenance, repair, mobilization, mode, procurement, readiness, goal, war, and peace controls into procedural shape controls.
- Procedural setpieces can emit faction-production strategies, priorities, quotas, allocations, rationing markers, reserves, embargoes, sabotage targets, maintenance plans, repair schedules, mobilization orders, production modes, wartime/peacetime production nodes, procurement contracts, and readiness markers.

## 2026-05-02 - Strategic Conflict and Diplomacy Scene Macros

- Added public `conflict_system`, `strategic_objective`, `war_plan`, `battlefront`, `escalation_ladder`, `treaty`, `ceasefire`, `alliance`, `rival_claim`, `diplomatic_demand`, `negotiation_channel`, `sanction`, `espionage_cell`, `covert_operation`, `disaster_response`, and `emergency_order` scene constructs.
- Conflict systems define factions, belligerents, rivals, allies, objectives, fronts, treaty terms, ceasefire terms, demands, negotiation terms, sanction targets, intelligence targets, covert operations, disaster zones, response teams, escalation levels, emergency levels, deescalation, and casus belli.
- Conflict systems generate faction-pressure fields, strategic objectives, battlefronts, escalation ladders, negotiation channels, treaties, ceasefires, alliances, sanctions, espionage cells, and disaster response systems.
- Strategic objectives generate war plans, production strategies, and objective-progress metrics.
- War plans generate battlefronts, mobilization orders, campaign supply routes, sabotage targets, and readiness levels.
- Battlefronts generate territory influence, faction pressure, supply routes, and hazard fields.
- Escalation ladders generate diplomatic demands, sanctions, escalation metrics, and optional war plans.
- Treaties generate diplomacy states, trade policies, and stability metrics; ceasefires generate treaty terms, negotiation channels, and integrity metrics.
- Alliances generate diplomacy states, shared supply chains, and coalition readiness.
- Rival claims generate resource claims, territory influence, and diplomatic demands.
- Diplomatic demands generate negotiation channels, demand metrics, and optional sanctions; negotiation channels generate diplomacy states, social relations, and progress metrics.
- Sanctions generate trade embargoes, bottlenecks, and sanction-pressure metrics.
- Espionage cells generate covert operations, intelligence sensor grids, and sabotage targets; covert operations generate sabotage targets, failure modes, and risk metrics.
- Disaster responses generate emergency orders, relief supply chains, relief resource flows, and readiness levels; emergency orders generate policy rules plus mobilization or rationing based on severity.
- Scene materialization forwards conflict, objective, war-plan, battlefront, escalation, treaty, ceasefire, alliance, claim, demand, negotiation, sanction, espionage, covert, disaster, emergency, faction, front, term, target, operation, and severity controls into procedural shape controls.
- Procedural setpieces can emit conflict systems, strategic objectives, war plans, battlefronts, escalation ladders, treaties, ceasefires, alliances, rival claims, diplomatic demands, negotiation channels, sanctions, espionage cells, covert operations, disaster-response markers, and emergency-order markers.

## 2026-05-02 - Faction AI Decision Loop Scene Macros

- Added public `faction_ai`, `doctrine_model`, `goal_stack`, `threat_model`, `perception_feed`, `decision_rule`, `policy_selector`, `action_option`, `response_plan`, `escalation_choice`, `deescalation_choice`, `resource_strategy`, `logistics_priority`, `diplomatic_posture`, `contingency_plan`, and `adaptive_order` scene constructs.
- Faction AI systems define doctrine, goals, threats, perception signals, policy options, action options, response modes, risk tolerance, aggression, caution, utility weights, decision thresholds, memory horizons, adaptation rates, policy bias, and fallback policy.
- Faction AI systems generate doctrine models, goal stacks, threat models, perception feeds, policy selectors, response plans, resource strategies, logistics priorities, diplomatic postures, and contingency plans.
- Doctrine models generate decision rules, policy selectors, and diplomatic posture bias.
- Goal stacks generate strategic objectives and priority metrics.
- Threat models generate perception feeds, threat metrics, escalation choices, and deescalation choices.
- Perception feeds generate sensor grids, simulation probes, and signal-confidence metrics.
- Decision rules generate policy selectors, action options, and utility metrics.
- Policy selectors generate action options and response plans; action options generate adaptive orders and option-score metrics.
- Response plans generate escalation choices, deescalation choices, resource strategies, and logistics priorities.
- Escalation choices generate escalation ladders, mobilization orders, and optional war plans; deescalation choices generate negotiation channels, ceasefires, and optional treaties.
- Resource strategies generate production strategies, resource claims, strategic reserves, and optional rationing policies.
- Logistics priorities generate supply chains, supply routes, throughput rules, and bottleneck monitoring.
- Diplomatic postures generate diplomacy states, negotiation channels, and either sanctions or treaties based on aggression/caution.
- Contingency plans generate emergency orders, disaster-response systems, and adaptive orders; adaptive orders generate policy rules, scene-state changes, and adaptation metrics.
- Scene materialization forwards AI, doctrine, goal, threat, perception, decision, selector, option, response, escalation/deescalation, resource, logistics, diplomatic, contingency, adaptive, risk, aggression, caution, threshold, memory, and adaptation controls into procedural shape controls.
- Procedural setpieces can emit faction AI cores, doctrine markers, goal stacks, threat models, perception feeds, decision rules, selectors, action options, response plans, escalation/deescalation choices, resource strategies, logistics priorities, diplomatic postures, contingency plans, and adaptive-order markers.

## 2026-05-02 - Operational Execution Scene Macros

- Added public `operational_plan`, `order_queue`, `world_order`, `patrol_order`, `convoy_order`, `construction_order`, `repair_order`, `relief_order`, `mission_order`, `scheduled_action`, `task_assignment`, `crew_roster`, `convoy_route`, `construction_queue`, `repair_crew`, and `relief_team` scene constructs.
- Operational plans define orders, tasks, crews, teams, schedules, durations, deadlines, priorities, queue policy, completion, worksites, patrols, convoys, missions, required resources, and supplies.
- Operational plans generate order queues, crew rosters, scheduled actions, world orders, and mission orders.
- Order queues generate typed world orders, patrol orders, convoy orders, construction orders, repair orders, relief orders, mission orders, and queue-depth metrics.
- World orders generate scheduled actions, task assignments, scene-state changes, and execution metrics.
- Patrol orders generate patrol routes, schedules, and assignments.
- Convoy orders generate convoy routes, supply chains, and assignments; convoy routes generate supply routes, transport legs, and resource flows.
- Construction orders generate construction queues, crew rosters, and material flows; construction queues generate construction orders and throughput rules.
- Repair orders generate repair crews, maintenance plans, and repair schedules; repair crews generate repair schedules, maintenance plans, and assignments.
- Relief orders generate relief teams, relief supply chains, and relief flows; relief teams generate disaster-response links, relief orders, and supply chains.
- Mission orders generate mission nodes, task assignments, and scheduled actions.
- Scheduled actions generate timers, action nodes, and scene-state updates.
- Task assignments generate crew rosters and task-progress metrics; crew rosters generate population groups and labor systems.
- Scene materialization forwards operational, queue, order, patrol, convoy, construction, repair, relief, mission, schedule, assignment, crew, team, route, worksite, priority, deadline, duration, progress, completion, and supply controls into procedural shape controls.
- Procedural setpieces can emit operational plans, order queues, world orders, patrol orders, convoy orders, construction orders, repair orders, relief orders, mission orders, scheduled actions, task assignments, crew rosters, convoy routes, construction queues, repair crews, and relief teams.

## 2026-05-02 - Settlement Evolution and Construction Lifecycle Scene Macros

- Added public `settlement_evolution`, `growth_phase`, `expansion_zone`, `construction_stage`, `upgrade_plan`, `district_upgrade`, `building_upgrade`, `infrastructure_upgrade`, `material_delivery`, `staffing_plan`, `occupancy_plan`, `worksite`, `build_permit`, `damage_repair_plan`, `demolition_plan`, and `renovation_project` scene constructs.
- Settlement evolution systems define phases, growth phases, expansion zones, projects, upgrades, material requirements, staff roles, occupants, capacity, damage level, repair priority, permit state, inspection state, build progress, upgrade level, construction style, renovation theme, and demolition reason.
- Settlement evolution systems generate growth phases, expansion zones, upgrade plans, material delivery chains, staffing plans, occupancy plans, and optional damage repair plans.
- Growth phases generate construction stages, scheduled actions, and progress metrics.
- Expansion zones generate district scaffolds, district upgrades, construction orders, and resource flows.
- Construction stages generate worksites, material deliveries, task assignments, and scheduled actions.
- Upgrade plans generate district, building, and infrastructure upgrades.
- District upgrades generate construction queues, infrastructure upgrades, and upgrade metrics.
- Building upgrades generate construction orders, occupancy plans, and upgrade metrics.
- Infrastructure upgrades generate construction orders, resource flows, and service networks.
- Material deliveries generate convoy orders, resource flows, and stockpiles.
- Staffing plans generate crew rosters, labor systems, and task assignments.
- Occupancy plans generate population groups, room clusters, and capacity metrics.
- Worksites generate construction orders, crew rosters, and hazard fields.
- Build permits generate policy rules, inspection schedules, and permit-progress metrics.
- Damage repair plans generate repair orders, repair crews, and damage states.
- Demolition plans generate scheduled demolition actions, debris fields, and clearance queues.
- Renovation projects generate building upgrades, material deliveries, and occupancy plans.
- Scene materialization forwards evolution, growth, expansion, stage, upgrade, delivery, staffing, occupancy, permit, demolition, renovation, phase, zone, project, material, staff, occupant, capacity, damage, repair, inspection, progress, style, district, and building controls into procedural shape controls.
- Procedural setpieces can emit settlement evolution cores, growth phases, expansion zones, construction stages, upgrade plans, district upgrades, building upgrades, infrastructure upgrades, material deliveries, staffing plans, occupancy plans, worksites, build permits, damage repair plans, demolition plans, and renovation projects.

## 2026-05-02 - City Planning and Parcel Urbanism Scene Macros

- Added public `city_plan`, `zoning_rule`, `zoning_district`, `parcel_grid`, `land_parcel`, `parcel_subdivision`, `block_plan`, `street_hierarchy`, `transit_node`, `civic_service_plan`, `service_coverage`, `utility_corridor`, `public_space_plan`, `growth_boundary`, `district_dependency`, and `development_pressure` scene constructs.
- City plans define zoning districts, allowed uses, density, parcel counts, parcels, lots, subdivision pattern, blocks, street levels, road types, transit modes, civic services, coverage radius, coverage thresholds, utilities, corridors, public spaces, parks, growth limits, dependencies, pressure sources, and pressure levels.
- City plans generate zoning rules, zoning districts, parcel grids, street hierarchies, block plans, civic service plans, growth boundaries, development pressure maps, and district dependencies.
- Zoning rules generate policy rules, zoning districts, and density metrics.
- Zoning districts generate district scaffolds, zoning rules, and development-pressure systems.
- Parcel grids generate land parcels, parcel subdivisions, and street grids.
- Land parcels generate build permits, zoning rules, and development pressure markers.
- Parcel subdivisions generate land parcels, block plans, and street access hierarchy.
- Block plans generate parcel grids, street hierarchies, public-space plans, and service coverage.
- Street hierarchies generate street grids, road intersections, and transit nodes.
- Transit nodes generate service coverage and accessibility metrics.
- Civic service plans generate service coverage, utility corridors, staffing plans, and service metrics.
- Service coverage generates service networks, resource flows, and coverage metrics.
- Utility corridors generate service networks, resource flows, and street-access hierarchy.
- Public-space plans generate district reservations, service coverage, and open-space metrics.
- Growth boundaries generate zoning edge rules, settlement pressure, and growth-limit metrics.
- District dependencies generate service coverage, resource flows, and dependency-strength metrics.
- Development pressure generates settlement pressure, build-permit demand, and pressure metrics.
- Scene materialization forwards city-planning, zoning, parcel, subdivision, block, street, transit, civic-service, coverage, utility-corridor, public-space, boundary, dependency, pressure, allowed-use, density, service, park, growth-limit, and road-type controls into procedural shape controls.
- Procedural setpieces can emit city plans, zoning rules, zoning districts, parcel grids, land parcels, parcel subdivisions, block plans, street hierarchies, transit nodes, civic service plans, service coverage markers, utility corridors, public-space plans, growth boundaries, district dependencies, and development-pressure markers.

## 2026-05-02 - Climate Resilience and Biome-to-City Scene Macros

- Added public `climate_zone`, `climate_risk_map`, `flood_risk`, `fire_risk`, `heat_risk`, `resource_constraint`, `protected_land`, `green_infrastructure`, `stormwater_system`, `cooling_corridor`, `evacuation_route`, `emergency_shelter`, `resilience_plan`, `climate_adaptation`, `transit_oriented_growth`, and `risk_mitigation` scene constructs.
- Resilience systems define climate zones, hazards, risk types, flood level, fire level, heat level, stormwater capacity, canopy cover, resilience score, adaptation measures, evacuation routes, shelters, protected areas, resource limits, transit growth strategy, and mitigation actions.
- Resilience plans generate climate zones, climate risk maps, green infrastructure, climate adaptation systems, evacuation routes, emergency shelters, resource constraints, protected land, transit-oriented growth, and risk mitigation.
- Climate zones generate biome systems, weather systems, and climate-stress metrics.
- Climate risk maps generate flood, fire, and heat risks plus mitigation plans.
- Flood risks generate stormwater systems, evacuation routes, hazard fields, and flood-level metrics.
- Fire risks generate protected land/firebreaks, evacuation routes, hazard fields, and fire-level metrics.
- Heat risks generate cooling corridors, green infrastructure, hazard fields, and heat-level metrics.
- Resource constraints generate scarcity loops, resource claims, and resource-limit metrics.
- Protected land generates conservation zones, zoning rules, and protected-area metrics.
- Green infrastructure generates protected land, stormwater systems, and cooling corridors.
- Stormwater systems generate service networks, stormwater resource flows, and flood-risk reduction links.
- Cooling corridors generate street hierarchy, heat-risk reduction links, and public-space plans.
- Evacuation routes generate street hierarchy, transit nodes, and emergency shelters.
- Emergency shelters generate occupancy plans, service coverage, and supply chains.
- Climate adaptation generates green infrastructure, stormwater systems, cooling corridors, and risk mitigation.
- Transit-oriented growth generates transit nodes, zoning districts, development-pressure absorption, and compact growth boundaries.
- Risk mitigation generates policy rules, resilience metrics, and climate adaptation links.
- Scene materialization forwards climate-zone, risk-map, flood, fire, heat, resource-constraint, protected-land, green-infrastructure, stormwater, cooling-corridor, evacuation, shelter, resilience, adaptation, transit-growth, mitigation, hazard, risk, canopy, stormwater-capacity, resilience-score, protected-area, resource-limit, and mitigation-action controls into procedural shape controls.
- Procedural setpieces can emit resilience plans, climate zones, risk maps, flood/fire/heat risks, resource constraints, protected land, green infrastructure, stormwater systems, cooling corridors, evacuation routes, emergency shelters, climate adaptation plans, transit-oriented growth, and risk mitigation markers.

## 2026-05-02 - Infrastructure Network Scene Macros

- Added public `power_grid`, `substation`, `transformer_bank`, `power_line`, `water_network`, `pump_station`, `water_tower`, `sewer_network`, `treatment_plant`, `data_network`, `data_hub`, `fiber_line`, `transit_line`, `transit_station`, `service_connection`, and `maintenance_access` scene constructs.
- Infrastructure network systems define service types, network nodes, service nodes, route nodes, line segments, service taps, substations, transformers, voltage, redundancy, pressure, storage capacity, pump capacity, treatment capacity, station spacing, ridership, network type, utility type, and procedural component counts.
- Power grids generate service-network spines, substations, power lines, service taps, transformer banks, maintenance access, and capacity metrics.
- Water networks generate water service spines, pump stations, water towers, water resource flows, service taps, and maintenance access.
- Sewer networks generate sewer service spines, treatment plants, wastewater flows, service taps, manhole access, and maintenance access.
- Data networks generate data service spines, data hubs, fiber lines, data drops, cable access, and bandwidth metrics.
- Transit lines generate transit stations, transit nodes, service coverage, power/data service connections, track-access routes, and ridership-ready state.
- Service connections generate resource flows and service-capacity metrics; maintenance access generates traversable access geometry and reach metrics.
- Scene materialization forwards infrastructure-network, power-grid, substation, transformer-bank, power-line, water-network, pump-station, water-tower, sewer-network, treatment-plant, data-network, data-hub, fiber-line, transit-line, transit-station, service-connection, maintenance-access, network-node, line-segment, voltage, pressure, redundancy, capacity, station, stop, service-type, network-type, utility-type, pipe, conduit, cable-tray, junction-box, manhole, valve, hydrant, transformer, service-rail, and support controls into procedural shape controls.
- Procedural infrastructure can now visibly respond to these scene constructs by emitting pipes, conduits, cable trays, transformers, junction boxes, valves, hydrants, drains, manholes, service rails, supports, transit/service markers, and maintenance access markers.

## 2026-05-02 - Building Service Integration Scene Macros

- Added public `building_service_plan`, `service_core`, `utility_room`, `mechanical_room`, `electrical_panel`, `meter_bank`, `plumbing_stack`, `hvac_system`, `ventilation_duct`, `elevator_core`, `service_elevator`, `service_shaft`, `fire_suppression`, `sprinkler_zone`, `waste_chute`, and `loading_dock` scene constructs.
- Building-service systems define service types, service zones, served floors, rooms served, service load, circuits, risers, panels, meters, ducts, vents, shafts, elevator cars, dock bays, sprinkler density, fire rating, airflow, and waste capacity.
- Building service plans generate service cores, utility rooms, mechanical rooms, fire suppression systems, and loading docks.
- Service cores generate electrical panels, plumbing stacks, HVAC systems, elevator cores, and service shafts.
- Utility rooms generate meter banks, electrical panels, plumbing stacks, and utility service taps.
- Mechanical rooms generate HVAC systems, ventilation duct runs, control power, and condensate plumbing.
- Electrical panels generate metered power taps, circuit service connections, and load metrics.
- Meter banks generate metered utility taps and usage metrics.
- Plumbing stacks generate water/sewer service taps, waste chutes, sprinkler zones, and water flows.
- HVAC systems generate supply/return ventilation ducts and power service connections.
- Ventilation ducts generate air resource flows to service zones and shaft routing.
- Elevator cores generate service elevators, service shafts, and machine maintenance access.
- Service elevators generate power connections, loading-dock links, and maintenance access.
- Service shafts generate plumbing, air, and power risers.
- Fire suppression systems generate sprinkler zones, water supply links, and fire hazard mitigation.
- Sprinkler zones generate water service connections and fire coverage hazard fields.
- Waste chutes generate waste outlet connections, waste resource flows, and cleanout access.
- Loading docks generate dock service connections, dock access, and cargo resource flows.
- Scene materialization forwards building-service, service-core, utility-room, mechanical-room, electrical-panel, meter-bank, plumbing-stack, HVAC, ventilation-duct, elevator-core, service-elevator, service-shaft, fire-suppression, sprinkler-zone, waste-chute, loading-dock, floor, service-zone, circuit, riser, panel, meter, vent, shaft, car, dock-bay, sprinkler-density, fire-rating, waste-capacity, service-load, and airflow controls into procedural shape controls.
- Procedural infrastructure/access/setpieces can now respond with service cores, utility/mechanical rooms, panels, meter banks, plumbing risers, HVAC and ventilation ducts, elevator shafts, service lifts, fire/sprinkler markers, waste chutes, loading docks, service taps, pipes, conduits, ducts, cable trays, access walkways, gates, and metrics-ready state.

## 2026-05-02 - Functional Interior Scene Macros

- Added public `room_program`, `bathroom`, `kitchen`, `lab_room`, `med_bay`, `workshop_room`, `control_room`, `storage_room`, `office_room`, `bedroom`, `fixture_cluster`, `appliance_bank`, `workstation_cluster`, `cabinet_wall`, `counter_run`, `sanitary_fixture`, `lab_bench`, `medical_bed`, and `tool_rack` scene constructs.
- Room programs now generate actual room hierarchies plus a shared service core, so a single room-program block can arrange bathrooms, kitchens, labs, med bays, workshops, control rooms, storage rooms, offices, and bedrooms.
- Bathrooms generate sink, toilet, and shower sanitary fixtures plus plumbing and exhaust ventilation, so the word creates wet-room geometry and service intent.
- Kitchens generate counter runs, appliance banks, cabinet walls, and utility taps, so food-prep rooms materialize as furniture plus power/water/sewer service controls.
- Lab rooms generate lab benches, sterile cabinet storage, service taps, and sterility metrics, so laboratory authoring creates work surfaces and monitored clean-room state.
- Med bays generate medical beds, wash stations, cabinet storage, and patient-service taps, so medical interiors create treatment furniture and privacy/sterility controls.
- Workshop rooms generate workstation clusters, tool racks, assembly counters, and power/air service taps, so workshop language produces workbench geometry and tool organization.
- Control rooms generate operator stations, control panels, equipment cabinets, and power/data/air service taps, so operations spaces become interactive rooms with usable controls.
- Storage rooms generate cabinet walls, rack storage, and capacity metrics; office rooms generate desks, file storage, and office utility taps; bedrooms generate beds, side furnishings, and power taps.
- Fixture-family constructs generate service-aware furniture or fixture objects: appliance banks connect to counters and taps, workstation clusters expose terminals, sanitary fixtures carry water flow, lab benches expose sterility state, medical beds expose privacy state, and tool racks expose tool counts plus interaction prompts.
- Scene materialization forwards room-program, room-role, fixture, appliance, workstation, cabinet, counter, sink, toilet, shower, bed, tool, rack, cleanliness, sterility, privacy, work-surface, and every new functional-interior count into generated asset controls.
- Procedural setpieces can now visibly respond with room-program, bathroom, kitchen, lab, med-bay, workshop, control-room, storage-room, office, bedroom, fixture, appliance, workstation, cabinet-wall, counter-run, sanitary-fixture, lab-bench, medical-bed, and tool-rack markers connected to interior, furniture, service, metric, and interaction parts.

## 2026-05-02 - Interior Adjacency and Socket Composition

- Added public `room_adjacency`, `room_connection`, `door_opening`, `corridor_link`, `wall_run`, `room_socket`, and `fixture_socket` scene constructs.
- Room adjacencies turn room lists or adjacent-room pairs into room-connection children, so Lathe can arrange functional rooms as connected layouts instead of isolated room objects.
- Room connections create shared wall runs, door openings, corridor links, and endpoint sockets, so connecting two rooms prepares traversal geometry plus attachable endpoints.
- Door openings generate door-action behavior and interaction prompts, so the construct cuts a passage and prepares usable door state rather than only naming an opening.
- Corridor links generate room endpoint sockets and corridor-length metrics, so circulation routes carry placement and traversal controls into generated assets.
- Wall runs generate door openings and fixture sockets along a wall, so walls become editable placement surfaces for doors, cabinets, counters, appliances, signage, and other fixtures.
- Room sockets and fixture sockets publish composition sockets, anchors, socket targets, attach tags, and attach families, so future room/furniture placement can snap to intended locations.
- Scene materialization forwards adjacency, connection, room-pair, source/target room, connection type, wall side, opening width, threshold depth, doorway count, corridor width/length, wall length/thickness, socket role/target/tags, attach tags/family/count, and every new interior-composition count into generated asset controls.
- Procedural interiors now respond to room/fixture socket counts with visible attach socket components, while procedural setpieces can emit adjacency, room-connection, door-opening, corridor-link, wall-run, room-socket, and fixture-socket markers connected to interior, access, door, wall, and fixture parts.

## 2026-05-02 - Constraint-Aware Placement Constructs

- Added public `socket_binding`, `fixture_placement`, `furniture_placement`, `service_placement`, `wall_attachment`, `anchor_rule`, and `placement_constraint` scene constructs.
- Socket bindings generate room sockets, fixture sockets, snap-strength metrics, and explicit binding relationships, so authored objects can be attached to intended targets instead of merely co-located.
- Fixture placements choose concrete fixture families such as appliance banks, counter runs, cabinet walls, sanitary fixtures, lab benches, medical beds, tool racks, workstations, or generic fixture clusters, then create sockets and bindings for each placed instance.
- Furniture placements generate furniture clusters and socket bindings, so room authors can place desks, beds, seating, storage, or other furnishings onto prepared anchors.
- Service placements generate service sockets, service connections, and bindings, so power/water/data/air taps can be placed onto room or fixture anchors.
- Wall attachments generate wall runs, wall-side fixture sockets, and attached fixture objects, so cabinets, counters, appliances, tools, signage, and other wall-mounted objects can snap to a side of a room.
- Anchor rules generate paired room/fixture sockets plus anchor-priority metrics, so placement preferences become actionable state that later placement passes can consume.
- Placement constraints generate anchor rules and clearance metrics, so spacing, target sockets, orientation, offsets, snap strength, rotation allowance, and wall alignment survive as runtime controls.
- Scene materialization forwards placement mode/rule/target, target socket, source/placed object, placed family, fixture type, snap mode/strength, clearance, orientation, offsets, priority, wall alignment, rotation allowance, placement group, services, and every new placement count into generated asset controls.
- Procedural setpieces can now emit socket-binding, fixture-placement, furniture-placement, service-placement, wall-attachment, anchor-rule, and placement-constraint markers connected to sockets, fixtures, services, walls, anchors, and metrics.

## 2026-05-02 - Socket-Driven Auto-Layout Constructs

- Added public `auto_layout`, `room_layout_plan`, `fixture_layout`, `furniture_layout`, `service_layout`, and `wall_fixture_layout` scene constructs.
- Auto-layout now expands a room role into a room-layout plan, fixture layout, furniture layout, service layout, wall-fixture layout, and clearance constraints, so one construct arranges sockets, placements, service taps, wall mounts, and constraints instead of merely naming a style of room.
- Room-layout plans generate room sockets, fixture wall runs, adjacency chains, door openings, and corridor links, so room programs gain planned circulation and attachable placement surfaces.
- Fixture layouts choose role-aware fixture families such as counters, cabinets, appliances, sanitary fixtures, lab benches, medical beds, tool racks, and workstations, then create concrete fixture placements bound to target sockets.
- Furniture layouts create furniture placements on prepared anchors, so desks, beds, storage, workstations, and generic furnishings become arranged objects rather than unattached props.
- Service layouts place service taps for power, water, sewer, data, air, exhaust, oxygen, or other utilities, so fixtures and rooms carry actionable infrastructure placement.
- Wall-fixture layouts generate wall attachments against wall runs, so cabinets, counters, tools, terminals, lamps, signage, and other wall-mounted objects snap to room sides.
- Scene Graph state now carries layout strategy, density, zones, slots, auto-place switches, door/socket/anchor policies, fixture/furniture/wall-fixture/service type lists, placement rules, placement constraints, layout counts, socket counts, and auto-placed counts.
- Scene materialization forwards every auto-layout control and count into generated asset controls, including `auto_layout_count`, `room_layout_plan_count`, `fixture_layout_count`, `furniture_layout_count`, `service_layout_count`, `wall_fixture_layout_count`, `layout_zone_count`, `layout_socket_count`, and `auto_placed_count`.
- Procedural setpieces can now emit auto-layout, room-plan, fixture-plan, furniture-plan, service-plan, wall-fixture-plan, layout-zone, layout-socket, and auto-placed markers connected to room sockets, wall runs, placements, service connections, bindings, and constraints.

## 2026-05-02 - Room-Aware Layout Resolution

- Added public `layout_solver`, `room_bounds`, `wall_side_rule`, `socket_priority`, `clearance_zone`, and `layout_slot` scene constructs.
- Layout solvers now combine room dimensions, wall-side availability, socket priority, clearance targets, and slot spacing into resolved layout slots, then drive an `auto_layout` child with the slots that remain usable.
- Room bounds generate wall-run children and floor-area metrics, so room size modifies actual placement surfaces instead of living as a descriptive number.
- Wall-side rules score and expose usable wall runs, choose a wall side, and preserve blocked/preferred walls, so fixtures can target viable walls rather than generic room centers.
- Socket priorities generate ranked room sockets plus priority metrics, so placement can prefer service reach, avoid doors, and choose higher-value anchors.
- Clearance zones generate placement constraints and clearance metrics, so door swings, walk paths, and reserved buffers actively block or reduce available slots.
- Layout slots generate room sockets, fixture sockets, and either socket bindings or blocked-slot constraints, so every resolved slot is immediately placeable or explicitly unavailable.
- Scene Graph state now carries room width/depth/height, floor and usable area, wall sides, preferred/blocked walls, chosen wall side, wall weights, socket weights, priority rules, clearance policy/targets/zones, layout axis, slot spacing/capacity/index/kind, resolved slots, blocked slots, and resolution counts.
- Scene materialization forwards every room-resolution control and count into generated asset controls, including `layout_solver_count`, `room_bounds_count`, `wall_side_rule_count`, `socket_priority_count`, `clearance_zone_count`, `layout_slot_count`, `resolved_slot_count`, `blocked_slot_count`, `wall_side_count`, and `priority_socket_count`.
- Procedural setpieces can now emit layout-solver, room-bounds, wall-side-rule, socket-priority, clearance-zone, layout-slot, resolved-slot, blocked-slot, and priority-socket markers connected to auto layouts, wall runs, sockets, bindings, constraints, and metrics.

## 2026-05-02 - Footprint-Aware Packing Constructs

- Added public `footprint_packer`, `placement_footprint`, `occupancy_grid`, `fit_profile`, `collision_rule`, and `service_reach` scene constructs.
- Footprint packers now combine item dimensions, room grid cells, occupied cells, fit scores, collision rules, and service reach into placement footprints, layout slots, fit profiles, collision keepouts, and service links.
- Placement footprints reserve concrete width/depth/height areas, generate layout slots and clearance zones, and expose footprint-area metrics, so objects take space instead of only naming an item.
- Occupancy grids turn room dimensions and cell size into free layout slots plus occupied-cell keepouts, so packing can avoid already-used space.
- Fit profiles generate socket priorities, fit constraints, and fit-score metrics, so layouts can rank slots by whether the footprint actually fits.
- Collision rules generate overlap-blocking placement constraints and keepout clearance zones, so packed items avoid occupying the same cells or footprint pairs.
- Service reach generates service placements and socket priorities for required utilities, so packed fixtures prefer slots within power, water, data, air, or other service radius.
- Scene Graph state now carries footprint width/depth/height, area, shape, padding, rotation, grid rows/columns, cell size, occupied/free cells, packed items, fit policy/score, rotation/overlap permissions, collision policy/pairs, required services, service targets, service radius, max service distance, reach score, and packing counts.
- Scene materialization forwards every footprint-packing control and count into generated asset controls, including `footprint_packer_count`, `placement_footprint_count`, `occupancy_grid_count`, `fit_profile_count`, `collision_rule_count`, `service_reach_count`, `footprint_count`, `occupied_cell_count`, `free_cell_count`, `packed_item_count`, and `collision_pair_count`.
- Procedural setpieces can now emit footprint-packer, placement-footprint, occupancy-grid, fit-profile, collision-rule, service-reach, occupied-cell, free-cell, packed-item, and collision-pair markers connected to layout solvers, slots, sockets, bindings, constraints, clearance zones, and service placements.

## 2026-05-02 - Room Role Packing Presets

- Added public `room_pack_preset`, `footprint_size_preset`, `packing_policy_preset`, `clearance_preset`, `service_reach_preset`, and `role_item_set` scene constructs.
- Room pack presets expand roles such as kitchen, bathroom, lab room, med bay, workshop, control room, storage room, office, and bedroom into item sets, footprint sizes, packing policies, clearance profiles, service reach profiles, and a footprint packer, so a room role now prepares concrete placement work.
- Footprint size presets turn role items into placement footprints with role-aware width, depth, and height controls, so the named items reserve space before packing.
- Packing policy presets create occupancy grids, fit profiles, collision rules, and a packer, so policy words arrange slots and block overlaps instead of staying descriptive.
- Clearance presets generate clearance zones and collision keepouts for door swings, aisles, bed access, bench access, wet zones, and similar reserves, so role constraints become placement blockers.
- Service reach presets generate service-reach children and service-placement controls for power, water, sewer, exhaust, air, data, oxygen, or other required services, so packed fixtures can prefer reachable infrastructure.
- Role item sets generate placement footprints and feed a footprint packer, so interchangeable room contents become prepared geometry inputs.
- Scene Graph state now carries preset role, role preset, preset items, item footprints, default footprints, packing policy, packing density, clearance profile, service profile, role services, role clearances, role footprints, role packing rules, required clearance, preferred item order, and every role-preset count.
- Scene materialization forwards every role-preset control and count into generated asset controls, including `room_pack_preset_count`, `footprint_size_preset_count`, `packing_policy_preset_count`, `clearance_preset_count`, `service_reach_preset_count`, `role_item_set_count`, `preset_item_count`, `role_preset_count`, and `policy_rule_count`.
- Procedural setpieces can now emit room-pack-preset, footprint-size-preset, packing-policy-preset, clearance-preset, service-reach-preset, role-item-set, preset-item, role-preset, and policy-rule markers connected to packers, footprints, fit profiles, collision rules, service placements, and clearance zones.

## 2026-05-02 - Transform-Resolved Room Packing

- Added public `room_packing_solver`, `packing_slot`, `packed_transform`, `clearance_reservation`, and `service_anchor_map` scene constructs.
- Room packing solvers turn packed items, room dimensions, spacing, clearance reservations, and required services into concrete slot maps, packed transform maps, clearance reservations, and service anchor maps, so packing now produces positions instead of only footprint intent.
- Packing slots allocate item-ready sockets with resolved positions and slot IDs, so each packed object has an actionable target inside the room.
- Packed transforms bind an item to a slot, carry resolved position and rotation, assign a placement footprint, and create a socket binding, so generated room contents gain parent/child placement intent.
- Clearance reservations turn reserved paths, door swings, wet zones, bed access, bench access, or similar buffers into clearance zones plus placement constraints, so transforms are shaped by blocking space.
- Service anchor maps create service reach and service placement anchors for power, water, sewer, exhaust, data, air, oxygen, or other utilities, so resolved transforms can be arranged around usable infrastructure.
- Room pack presets and role item sets now emit room packing solvers after preparing item sets and footprints, so role-level room words can resolve into placed child-object transforms.
- Scene Graph state now carries packing axis, origin, spacing, slot maps, packed transform maps, resolved transform maps, clearance reservations, service anchors, parent object, child objects, packed item, slot IDs, resolved position, resolved rotation, and room-packing result counts in schema-valid form.
- Scene materialization forwards every transform-packing control and count into generated asset controls, including `room_packing_solver_count`, `packing_slot_count`, `packed_transform_count`, `clearance_reservation_count`, `service_anchor_map_count`, `resolved_transform_count`, `blocked_transform_count`, and `service_anchor_count`.
- Procedural setpieces can now emit room-packing-solver, packing-slot, packed-transform, clearance-reservation, service-anchor-map, and service-anchor markers connected to footprint packers, layout slots, placement footprints, clearance zones, service reach, and service placements.

## 2026-05-02 - Room Content Assetization

- Added public `room_content_plan`, `content_family_binding`, `furniture_asset`, `fixture_asset`, and `packed_child_asset` scene constructs.
- Room content plans consume packed items, solved room dimensions, spacing, required services, and clearance reservations, then generate content family bindings plus furniture or fixture child assets, so resolved room packing becomes generated room contents.
- Content family bindings map an item such as counter, cabinet, sink, lab bench, medical bed, workstation, tool rack, terminal, lamp, bed, or rack to a procedural source family and item controls, so item words prepare actual asset generation rather than labels.
- Furniture assets create packed transforms with furniture-specific controls and footprints, so counters, cabinets, workstations, beds, lamps, racks, and related content become generated child assets.
- Fixture assets create packed transforms plus service anchor maps, so sinks, appliances, lab benches, medical beds, showers, toilets, and terminals can carry service-aware placement state.
- Packed child assets bind an item to a packed transform, generated family, slot ID, resolved position, and resolved rotation, so materialization can build the child asset and assemble it into the parent room.
- Room pack presets now emit room content plans after resolving footprints and transforms, so high-level room roles can proceed from role intent to concrete child asset generation.
- Scene Graph state now carries content family, content asset type, generated child asset IDs, generated child asset lists, and content asset controls in schema-valid form.
- Scene materialization forwards every content-assetization control and count into generated asset controls, including `room_content_plan_count`, `content_family_binding_count`, `furniture_asset_count`, `fixture_asset_count`, `packed_child_asset_count`, `generated_child_asset_count`, and `content_family_count`.
- Procedural furniture generation now responds directly to packed item types: cabinets make cabinet bodies and drawers, counters and lab benches make work surfaces, sinks/toilets/showers/appliances make fixture bodies, medical beds make bed/cushion structures, workstations/terminals make table/lamp content, and tool racks make shelf/rack structures.
- Procedural setpieces can now emit room-content-plan, content-family-binding, furniture-asset, fixture-asset, and packed-child-asset markers connected to room packing solvers, packed transforms, placement footprints, service anchors, and generated furniture or fixture assets.

## 2026-05-02 - Builder Mode Construct Consequence Rule

- Carry forward the rule that Lathe Builder Mode words must make something, modify something, arrange something, or prepare information that soon makes, modifies, or arranges something.
- New constructs should not stop at parser vocabulary: they should lower into Scene Graph intent, preserve actionable state, forward controls through materialization, and trigger geometry, material, placement, hierarchy, or soon-used procedural state.

## 2026-05-02 - Content Surface Zoning

- Added public `content_surface_plan`, `content_material_zone`, `content_finish_preset`, `content_wear_profile`, and `content_marking_set` scene constructs.
- Content surface plans turn packed item types into item-specific material zones, finish layers, markings, and wear patterns, so room contents gain surface identity as part of generation rather than as detached descriptive labels.
- Content material zones create real `material_zone` children with zone/material bindings, so words like sink wet zone, service connection, cabinet kick plate, or workstation lamp become assignable surface regions.
- Content finish presets create `surface_layer` children, so packed contents carry layered finish stacks such as ceramic glaze, water spots, primer, paint, laminate, metal, fabric, or edge seals into the scene graph.
- Content wear profiles create `wear_pattern` children, so generated furniture and fixtures receive procedural scratch, stain, compression, edge-wear, or use-mark controls.
- Content marking sets create `decal` children, so item markings such as drain rings, labels, hazard tags, keyboard wear, bed numbers, tool outlines, and water streaks are materialized as surface authoring controls.
- Scene Graph state now carries `content_surface_profile`, `content_surface_zones`, `content_finish_layers`, `content_markings`, `content_wear`, and `content_material_profile`, plus counts for content surface plans, zones, decals, layers, material zones, and wear patterns.
- Scene materialization forwards content surface state into generated asset surface authoring, including materials, material layers, zones, story decals, decals, wear story, wear level, and procedural surface counts.
- Procedural furniture now responds to forwarded content surface controls by emitting visible surface-layer, material-zone, decal, and wear-pattern marker geometry on generated furniture or fixture assets.

## 2026-05-02 - Building Envelope Generation

- Added public `building_envelope`, `floor_stack`, `facade_grid`, `facade_bay`, `roof_profile`, `vertical_core`, and `entrance_plan` scene constructs.
- Building envelopes now turn floors, bays, roof style, facade style, floor roles, entries, and dimensions into a hierarchy of floor stacks, facade grids, roof profiles, vertical cores, and entrance plans, so a building word creates an actionable shell instead of naming a category.
- Floor stacks generate role-aware `room_pack_preset` children per floor, so building floors connect to the existing room-packing and generated-room-content pipeline.
- Facade grids generate facade bays plus facade material zones, and facade bays create opening sockets plus wall attachments for windows or doors, so facade layout becomes attachable geometry intent.
- Roof profiles create roof material zones and rooftop service anchor maps, so roof style and equipment counts feed both surface identity and service placement.
- Vertical cores create service cores, elevator cores, and service shafts, so circulation and utility routing become child systems inside the building.
- Entrance plans create door openings, entry sockets, and entry-clearance constraints, so entrances reserve space and expose usable attachment points.
- Scene Graph state now carries building dimensions, floor count, bay count, floor roles, floor plan maps, floor heights, facade sides, facade bay maps, roof pitch, vertical core types, entrance locations, and generated building control maps.
- Scene materialization forwards building envelope controls after transform-derived controls, so authored floor, bay, width, depth, roof, facade, core, and entrance choices reach generated assets.
- Procedural building generation now responds to these controls by emitting building-envelope frames, floor-stack plates, facade-grid controls, facade-bay geometry, roof-profile geometry, vertical-core geometry, and entrance-plan geometry.

## 2026-05-02 - Site Compound Layout

- Added public `site_compound`, `building_lot`, `courtyard_plan`, `pedestrian_path`, `service_alley`, `parking_zone`, `loading_zone`, and `exterior_utility` scene constructs.
- Site compounds now turn building lists, courtyards, access paths, service alleys, parking bays, loading zones, and utilities into child lots, public-space reserves, pedestrian routes, service routes, vehicle aprons, dock aprons, and utility spines, so a compound word arranges a multi-building site.
- Building lots reserve placement footprints and generate building envelopes, so each lot can become an actual building shell instead of a named parcel.
- Courtyard plans generate public-space plans and pedestrian loop paths, so open space becomes reserved circulation and surface intent.
- Pedestrian paths and service alleys generate maintenance access, entry sockets, and utility runs, so site circulation becomes usable placement and service state.
- Parking zones generate parking-bay footprints plus capacity metrics, while loading zones generate loading docks and truck-access service alleys, so vehicle support becomes actionable geometry and hierarchy.
- Exterior utilities generate utility corridors and per-utility service connections, so power, water, data, and other services become routed infrastructure feeding site buildings.
- Scene Graph state now carries site layout profile, site buildings, building lots, courtyard program, pedestrian paths, service alleys, parking zones, loading zones, exterior utilities, access points, utility maps, and site compound control maps.
- Scene materialization forwards site controls and nested site control maps into generated asset controls, including site/building/route counts, parking-bay counts, access lists, utility maps, and compound dimensions.
- Procedural setpieces now respond to these controls with visible site compound boundaries, lot pads, courtyard reserves, pedestrian strips, service lanes, parking aprons and stalls, loading aprons, and exterior utility spines.

## 2026-05-02 - District Exterior Control Layer

- Added public `district_site_plan`, `street_crossing`, `perimeter_plan`, `security_gate`, `landscape_zone`, `traffic_flow`, and `service_flow` scene constructs.
- District site plans now arrange block plans, site compounds, street spines, crossings, controlled perimeters, landscape zones, traffic routes, and service routes, so district-scale words compose multiple sites instead of naming an urban theme.
- Street crossings generate road intersections, pedestrian paths, traffic-flow controls, crosswalk counts, and crossing metrics, so pedestrian access modifies road and site circulation.
- Perimeter plans reserve perimeter footprints, place security gates, open patrol access, and expose perimeter segment counts, so district boundaries become actual arranged edge systems.
- Security gates generate traversal gates, maintenance access, control panels, and alarm grids, so access control becomes interactive and serviceable state.
- Landscape zones generate public-space plans, green infrastructure, stormwater systems, and material zones, so green/open-space words modify geometry, service drainage, and surface identity.
- Traffic flows generate street hierarchy links, road-intersection control points, and traffic-capacity metrics, while service flows generate utility corridors, service connections, maintenance access, and resource-flow state.
- Scene Graph state now carries district site profiles, compounds, blocks, crossings, perimeter segments, gates, landscape zones, traffic routes, service routes, and nested district site control maps.
- Scene materialization forwards district controls and nested district control maps into generated asset controls, including district, crossing, perimeter, gate, landscape, traffic-flow, and service-flow counts.
- Procedural setpieces now respond with visible district-site, street-crossing, perimeter, security-gate, landscape, traffic-flow, and service-flow markers connected to block, site, road, utility, access, and surface parts.

## 2026-05-02 - Interior Exterior Access Continuity

- Added public `access_sequence`, `public_entry`, `service_entry`, `threshold_transition`, `entry_lobby`, `access_checkpoint`, `loading_path`, and `wayfinding_node` scene constructs.
- Access sequences now arrange public entries, service entries, thresholds, lobby zones, checkpoints, loading paths, and wayfinding nodes, so exterior circulation can become an interior arrival chain instead of disconnected paths and rooms.
- Public entries generate entrance plans, door openings, threshold transitions, and entry wayfinding, so a named entry creates doors, surfaces, and user-facing navigation.
- Service entries generate loading paths, loading docks, service thresholds, and maintenance access, so back-of-house access becomes routable service geometry and hierarchy.
- Threshold transitions generate door openings, corridor links, material zones, and wear patterns, so moving from outside to inside modifies both route structure and surface identity.
- Entry lobbies generate room programs, room connections, wayfinding, and reception prompts, so arrivals become interior program and interaction state.
- Access checkpoints generate traversal gates, control panels, alarm grids, and credential locks, so security words create interactive gating and monitoring systems.
- Loading paths generate loading docks, service flows, maintenance access, and cargo resource flow, so cargo routes become structured service movement.
- Wayfinding nodes generate signage, map markers, and interaction prompts, so navigation language places visible guidance and inspectable map state.
- District site plans now emit an access sequence, so district-scale exterior planning can connect crossings, gates, routes, and compounds into entry/lobby/loading continuity.
- Scene Graph state now carries access transition profiles, entry points, service entry points, thresholds, lobby zones, checkpoint nodes, loading routes, wayfinding nodes, and nested access transition control maps.
- Scene materialization forwards access transition controls and nested maps into generated asset controls, including entry, service-entry, threshold, lobby, checkpoint, loading-path, wayfinding, door, corridor, gate, signage, map, material-zone, and wear counts.
- Procedural access generation now responds with visible access-sequence, public-entry, service-entry, threshold-transition, entry-lobby, access-checkpoint, loading-path, and wayfinding-node components connected to route, gate, lobby, platform, and signage parts.

## 2026-05-02 - Multi-Floor Circulation and Egress

- Added public `circulation_core`, `stair_run`, `elevator_bank`, `egress_route`, `emergency_exit`, `corridor_spine`, `floor_transition`, `public_circulation`, and `service_circulation` scene constructs.
- Circulation cores now arrange corridor spines, stair runs, elevator banks, egress routes, floor transitions, public circulation, and service circulation, so a building can author floor-to-floor movement as a single connected system.
- Stair runs generate floor transitions, landing maintenance access, and served-floor metrics, so stairs become vertical routing state instead of a generic access prop.
- Elevator banks generate elevator cores, service elevators, service shafts, and call panels, so vertical lift systems carry mechanical/service hierarchy and interaction controls.
- Egress routes generate corridor spines, emergency exits, exit wayfinding, and travel-distance metrics, so evacuation paths become routed scene structure with safety state.
- Emergency exits generate door openings, panic-bar door actions, exit prompts, and wayfinding markers, so exit words produce usable doors and visible guidance.
- Corridor spines generate per-floor corridor links, wayfinding, and width metrics, so horizontal circulation becomes route geometry and measurable clearance state.
- Floor transitions generate stair, elevator, and landing links between floors, so authored floor changes become navigable parent/child hierarchy.
- Public circulation generates access sequences, public corridors, public stairs, and wayfinding, while service circulation generates service entries, loading paths, service corridors, service lifts, and service cores.
- Scene Graph state now carries circulation profiles, floor labels, stair runs, elevator banks, egress routes, emergency exits, corridor spines, floor transitions, public routes, service routes, and nested circulation control maps.
- Scene materialization forwards circulation controls into generated assets, including circulation, stair, elevator, egress, exit, corridor, floor-transition, public-route, service-route, floor-count, platform, safety-gate, and wayfinding counts.
- Procedural access generation now responds with visible circulation-core, stair-run, elevator-bank, egress-route, emergency-exit, corridor-spine, floor-transition, public-circulation, and service-circulation components connected to route, platform, gate, stair, elevator, and signage parts.

## 2026-05-02 - Architectural Circulation Detailing

- Added public `stair_detail`, `tread_pattern`, `landing_platform`, `handrail_run`, `corridor_shell`, `door_rhythm`, `ceiling_service_grid`, `egress_surface_plan`, and `room_route_binding` scene constructs.
- Stair details now turn an authored stair route into tread/riser patterns, landing platforms, handrail runs, and egress surface markings, so a stair word creates the parts that make the route readable and buildable.
- Tread patterns create tread/riser metrics plus material and wear children, so stair proportions and foot-traffic surfaces flow into generated assets.
- Landing platforms create floor transitions, clearance reserves, wayfinding, and landing surface zones, so landings become navigable, measurable, and surfaced space.
- Handrail runs create serviceable rail access, rail material zones, and handrail count metrics, so safety rails are generated as physical route detail instead of style tags.
- Corridor shells create wall runs, door rhythms, ceiling service grids, finish material zones, and room-route bindings, so a corridor can become an enclosed route with doors, services, and room connections.
- Door rhythms cut repeated door openings and bind door bays to target rooms, while ceiling service grids route service connections and expose grid counts.
- Egress surface plans create material zones, wear patterns, decals, and wayfinding nodes, so exit paths carry visible floor/wall markings and use wear.
- Room-route bindings create room connections, route sockets, corridor links, and binding metrics, so corridor language prepares room placement and access relationships.
- Scene Graph state now carries circulation detail controls, tread/riser/landing/handrail counts, corridor wall/door/ceiling counts, egress surface zones, and room route targets.
- Scene materialization forwards nested circulation detail controls into generated access assets, and procedural access generation emits visible detail markers for stairs, treads, landings, handrails, corridor shells, door rhythms, ceiling grids, egress markings, and room bindings.
