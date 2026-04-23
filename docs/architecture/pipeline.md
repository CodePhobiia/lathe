# Compiler pipeline

Lathe's compiler runs source through a fixed sequence of stages — `STAGE_ORDER`. Shape is the one probabilistic stage; everything else is deterministic so that two runs from the same inputs produce byte-stable outputs (modulo the shape handoff).

```mermaid
flowchart LR
    refs["refs"] --> intent["intent"]
    intent --> shape["shape<br/>(probabilistic)"]
    shape --> topology["topology"]
    topology --> uv["uv"]
    uv --> surface["surface"]
    surface --> execution["execution"]
    execution --> rig["rig"]
    rig --> interfaces["interfaces"]
    interfaces --> physics["physics"]
    physics --> optimize["optimize"]
    optimize --> validate["validate"]
    validate --> package["package"]
    package --> publish["publish"]

    classDef probabilistic fill:#fce4a6,stroke:#c69221,color:#000
    classDef deterministic fill:#d6eaff,stroke:#3a78c2,color:#000
    class shape probabilistic
    class refs,intent,topology,uv,surface,execution,rig,interfaces,physics,optimize,validate,package,publish deterministic
```

## Stage-by-stage

- **refs** — resolve reference sources declared by the asset (`reference_set`, image refs, scan refs).
- **intent** — freeze the author's declarative intent (families, components, profiles, contracts) into a canonical form.
- **shape** — produce an authoritative mesh from intent under the stable `lathe.shape.intent_mesh_handoff_v1` contract; the only probabilistic stage.
- **topology** — apply deterministic topology rules (hard-surface cleanup, merge, symmetry) via the Blender adapter or a fallback path.
- **uv** — lay out UVs with xatlas or a deterministic box-atlas fallback.
- **surface** — evaluate surface programs, bake textures, and emit governed texture packs.
- **execution** — run any external executor steps (Blender bridge, bake/render intent, retained `.blend` artifacts).
- **rig** — apply rig templates and bone/joint definitions.
- **interfaces** — emit interface bindings (attachment points, sockets, component contracts).
- **physics** — derive collision, mass, and interaction properties from intent.
- **optimize** — LOD, decimation, and mobile adapts per variant policy.
- **validate** — run certification validators (semantic, visual, flow, surface, silhouette).
- **package** — emit the bundle (usd / glb / gltf / obj) under the stable package contract.
- **publish** — ship bundle + manifest to the configured target (scaffold in v0.1).

See [Shape stage](shape_stage.md) for the internals of the shape stage and [Backends](backends.md) for the stack bindings and fallback semantics.
