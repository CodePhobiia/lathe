# Wonder Readiness Glossary

## Dream Brief

A structured JSON summary of the user's desired scene. It captures intent,
style, required elements, constraints, and export targets before any scene graph
or Lathe source is generated.

## Scene Graph

The persistent JSON truth model for a Wonder scene. It gives scenes, regions,
objects, materials, lights, cameras, curiosity anchors, hidden state, exports,
and memory events stable IDs.

## Scene Object

An instance inside a Scene Graph with a stable `object_id`, transform, semantic
role, material bindings, state, affordances, and source links to Lathe assets,
families, or kits.

## Asset

A single Lathe build target or generated output that can become part of a
larger scene. In Wonder, an asset can be used by one or more scene objects.

## Family

A reusable Lathe source grouping that can produce related assets or variants
with shared structure, style, and constraints.

## Kit

A reusable collection of compatible assets or modules intended to be assembled
together, such as a room shell, prop set, or platform-specific asset group.

## Region

A named spatial area inside a scene, such as a chamber, courtyard, shop zone, or
street corner. Scene objects reference regions so layout and validation can stay
scene-aware.

## World Memory

Structured memory attached to a scene or package. It records durable facts,
events, hidden state, continuity constraints, and branch history that should
survive patches and rebuilds.

## Scene Package

The durable folder/package form of a Wonder scene. It is expected to contain
source contracts, normalized graph data, build outputs, renders, reports,
exports, and metadata once the package phase exists.

## Branch

A named continuation of a scene state. Branches let Wonder explore changes or
curiosity expansions while preserving the original scene state and stable IDs.

## Scene Patch

A structured edit request that targets a scene, region, object, camera, light,
curiosity anchor, hidden state, or asset while declaring what must be preserved.

## Render Inspection

A structured report over a render or render pass. It records quality scores,
grounded problems, and recommended scene patches for repair or refinement.

## Wonder Report

A machine-readable and human-readable summary of a Wonder scene operation. It
should describe inputs, outputs, diagnostics, artifacts, scores, and remaining
limits once the reporting contract is implemented.
