"""Physics stage step body (collision proxy + mass).

Extracted from ``lathe/executor.py`` during Stage 2.IV.
"""

from __future__ import annotations

from typing import Any

from ...stages import collision as collision_mod
from ..common import dump_json, relpath
from ..geometry import estimate_mass_kg, part_groups_from_face_parts
from ..io import export_glb
from ..mesh import RuntimeMesh

_MAX_AUTHORED_PHYSICS_VALUES = 48
_DEFAULT_DENSITY_G_CM3 = 0.8


def _token(value: Any) -> str:
    return str(value).lower().replace("-", "_").replace(" ", "_").strip() if value is not None else ""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _iter_text_fragments(value: Any) -> list[str]:
    fragments: list[str] = []
    if value is None:
        return fragments
    if isinstance(value, dict):
        for item in value.values():
            fragments.extend(_iter_text_fragments(item))
        return fragments
    if isinstance(value, (list, tuple, set)):
        for item in value:
            fragments.extend(_iter_text_fragments(item))
        return fragments
    text = str(value).strip()
    return [text] if text else []


def _slug_fragment(value: str, fallback: str = "physics") -> str:
    lowered = value.lower()
    chars: list[str] = []
    previous_was_separator = False
    for char in lowered:
        if char.isalnum():
            chars.append(char)
            previous_was_separator = False
            continue
        if not previous_was_separator:
            chars.append("_")
            previous_was_separator = True
    slug = "".join(chars).strip("_")
    return slug[:48] if slug else fallback


def _authored_physics_texts(asset: dict[str, Any]) -> list[str]:
    """Collect existing source-visible words that imply physics semantics."""
    texts: list[str] = []
    source_values = [
        asset.get("name"),
        asset.get("kind"),
        asset.get("intent", {}).get("role"),
        asset.get("intent", {}).get("parts"),
        asset.get("intent", {}).get("interactions"),
        asset.get("assembly", {}).get("components"),
        asset.get("assembly", {}).get("traits"),
        asset.get("assembly", {}).get("mechanisms"),
        asset.get("features", {}).get("allow"),
        asset.get("publish", {}).get("tags"),
    ]
    seen: set[str] = set()
    for value in source_values:
        for fragment in _iter_text_fragments(value):
            slug = _slug_fragment(fragment)
            if slug in seen:
                continue
            seen.add(slug)
            texts.append(fragment)
            if len(texts) >= _MAX_AUTHORED_PHYSICS_VALUES:
                return texts
    return texts


def _contains_any(token: str, words: tuple[str, ...]) -> bool:
    normalized = f" {token.replace('_', ' ')} "
    return any(f" {word.replace('_', ' ')} " in normalized for word in words)


def _classify_physics_intent(asset: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    texts = _authored_physics_texts(asset)
    tokens = [_token(text) for text in texts]
    joined = " ".join(tokens)

    if _contains_any(joined, ("trigger", "sensor", "interaction_zone", "hitbox", "hurtbox", "pickup_zone")):
        body_type = "trigger"
    elif _contains_any(joined, ("cloth", "rope", "cable", "chain", "flag", "fabric")):
        body_type = "flexible"
    elif _contains_any(joined, ("projectile", "bullet", "missile", "rocket", "grenade", "arrow")):
        body_type = "projectile"
    elif _contains_any(joined, ("breakable", "destructible", "debris", "damage_state", "destroy")):
        body_type = "destructible"
    elif _contains_any(joined, ("vehicle", "car", "truck", "tank", "wheel", "suspension", "chassis")):
        body_type = "vehicle"
    elif _contains_any(joined, ("boat", "ship", "hull", "pontoon", "sail", "rudder", "propeller", "dock")):
        body_type = "watercraft"
    elif _contains_any(joined, ("weapon", "rifle", "pistol", "blade", "sword", "muzzle", "fire", "shoot")):
        body_type = "weapon"
    elif _contains_any(joined, ("door", "gate", "hinge", "lever", "button", "switch", "slider", "moving_part")):
        body_type = "kinematic"
    elif _contains_any(joined, ("pickup", "carry", "grab", "grip", "hold", "usable", "interactable")):
        body_type = "dynamic"
    else:
        body_type = "static"

    if _contains_any(joined, ("hinge", "door", "gate", "swing", "open", "close")):
        joint_policy = "hinge"
    elif _contains_any(joined, ("slide", "rail", "track", "drawer", "bolt")):
        joint_policy = "slider"
    elif _contains_any(joined, ("wheel", "axle", "roller", "spin", "turret", "rotate", "propeller")):
        joint_policy = "revolute"
    elif _contains_any(joined, ("rope", "cable", "chain", "cloth", "fabric")):
        joint_policy = "flexible_chain"
    elif _contains_any(joined, ("fixed", "weld", "mount", "attach", "dock", "socket")):
        joint_policy = "fixed"
    else:
        joint_policy = "none"

    if body_type in {"vehicle", "watercraft", "destructible", "flexible"} or joint_policy != "none":
        collision_policy = "per_part_hulls"
    elif body_type in {"weapon", "projectile", "dynamic", "kinematic"}:
        collision_policy = "convex_hull"
    else:
        collision_policy = "box"

    explicit_mass = cfg.get("mass")
    source = "authored_source_intent" if texts and (body_type != "static" or joint_policy != "none") else "build.physics"
    return {
        "body_type": body_type,
        "joint_policy": joint_policy,
        "collision_policy": collision_policy,
        "source": source,
        "source_values": texts,
        "mass_policy": str(explicit_mass) if explicit_mass is not None else "auto",
    }


def _resolve_collision_proxy_mode(
    physics_cfg: dict[str, Any],
    shape_cfg: dict[str, Any] | None = None,
    physics_intent: dict[str, Any] | None = None,
) -> str:
    shape_cfg = shape_cfg if isinstance(shape_cfg, dict) else {}
    authored = _token(shape_cfg.get("collision_proxy"))
    explicit_physics = _token(physics_cfg.get("collision"))
    inferred = _token((physics_intent or {}).get("collision_policy"))
    raw = authored if authored else explicit_physics
    if raw in {"", "none", "auto"} and inferred:
        raw = inferred
    aliases = {
        "": "box",
        "none": "box",
        "auto": "box",
        "bounds": "box",
        "aabb": "box",
        "bounding_box": "box",
        "box_proxy": "box",
        "convex": "convex_hull",
        "hull": "convex_hull",
        "convex_proxy": "convex_hull",
        "convex_decomp": "per_part_hulls",
        "decomp": "per_part_hulls",
        "parts": "per_part_hulls",
        "part_hulls": "per_part_hulls",
        "per_part": "per_part_hulls",
    }
    return aliases.get(raw, raw if raw in {"box", "convex_hull", "per_part_hulls"} else "box")


def _collision_proxy_source(
    physics_cfg: dict[str, Any],
    shape_cfg: dict[str, Any],
    physics_intent: dict[str, Any],
    resolved_collision_mode: str,
) -> str:
    if shape_cfg.get("collision_proxy"):
        return "shape.collision_proxy"
    explicit_physics = _token(physics_cfg.get("collision"))
    if explicit_physics not in {"", "none", "auto"}:
        return "build.physics.collision"
    if (
        physics_intent.get("source") == "authored_source_intent"
        and _token(physics_intent.get("collision_policy")) == resolved_collision_mode
    ):
        return "authored_source_intent"
    return "build.physics.collision"


def _collision_proxy_mesh(runtime_mesh: RuntimeMesh, mode: str) -> tuple[Any, str]:
    if mode == "convex_hull":
        proxy = collision_mod.single_hull(runtime_mesh.mesh)
        return proxy.mesh, "convex_hull"
    if mode == "per_part_hulls":
        proxies = collision_mod.per_part_hulls(runtime_mesh.mesh, list(runtime_mesh.face_parts))
        return collision_mod.combine_hulls(proxies), "per_part_hulls"
    return runtime_mesh.mesh.bounding_box.copy(), "box"


def _bounds_extents(group: dict[str, Any]) -> list[float]:
    mins = group.get("bounds_min") if isinstance(group.get("bounds_min"), list) else [0.0, 0.0, 0.0]
    maxs = group.get("bounds_max") if isinstance(group.get("bounds_max"), list) else [0.0, 0.0, 0.0]
    return [
        max(float(maxs[index]) - float(mins[index]), 1e-6)
        for index in range(3)
    ]


def _bounds_center(group: dict[str, Any]) -> list[float]:
    mins = group.get("bounds_min") if isinstance(group.get("bounds_min"), list) else [0.0, 0.0, 0.0]
    maxs = group.get("bounds_max") if isinstance(group.get("bounds_max"), list) else [0.0, 0.0, 0.0]
    return [round((float(mins[index]) + float(maxs[index])) * 0.5, 6) for index in range(3)]


def _bbox_volume_cm3(group: dict[str, Any]) -> float:
    x, y, z = _bounds_extents(group)
    return max(x * y * z, 1e-6)


def _inertia_box(mass_kg: float, extents_cm: list[float]) -> list[float]:
    x, y, z = extents_cm
    return [
        round(max((mass_kg * (y * y + z * z)) / 12.0, 1e-9), 9),
        round(max((mass_kg * (x * x + z * z)) / 12.0, 1e-9), 9),
        round(max((mass_kg * (x * x + y * y)) / 12.0, 1e-9), 9),
    ]


def _part_is_movable(part_name: str, physics_intent: dict[str, Any]) -> bool:
    token = _token(part_name)
    if _contains_any(token, ("door", "gate", "hinge", "wheel", "axle", "rotor", "propeller", "rudder")):
        return True
    if _contains_any(token, ("slider", "drawer", "lever", "button", "switch", "trigger", "blade")):
        return True
    if _contains_any(token, ("debris", "shard", "breakable", "projectile", "pickup", "grip")):
        return True
    return physics_intent.get("body_type") in {"dynamic", "vehicle", "watercraft", "projectile", "destructible"}


def _part_body_type(part_name: str, physics_intent: dict[str, Any]) -> str:
    token = _token(part_name)
    if _contains_any(token, ("trigger", "sensor", "zone", "hitbox", "hurtbox")):
        return "trigger"
    if _contains_any(token, ("wheel", "axle", "rotor", "propeller", "turret")):
        return "kinematic"
    if _contains_any(token, ("door", "gate", "hinge", "lever", "button", "switch", "slider", "drawer")):
        return "kinematic"
    if _contains_any(token, ("debris", "shard", "breakable", "projectile")):
        return "dynamic"
    return str(physics_intent.get("body_type") or "static")


def _physics_parts(runtime_mesh: RuntimeMesh, total_mass_kg: float, physics_intent: dict[str, Any]) -> list[dict[str, Any]]:
    groups = part_groups_from_face_parts(runtime_mesh.mesh, list(runtime_mesh.face_parts))
    if not groups:
        groups = [
            {
                "name": "mesh",
                "face_count": len(runtime_mesh.mesh.faces),
                "vertex_count": len(runtime_mesh.mesh.vertices),
                "bounds_min": [round(float(v), 6) for v in runtime_mesh.mesh.bounds[0]],
                "bounds_max": [round(float(v), 6) for v in runtime_mesh.mesh.bounds[1]],
            }
        ]
    volumes = [_bbox_volume_cm3(group) for group in groups]
    volume_total = max(sum(volumes), 1e-6)
    parts: list[dict[str, Any]] = []
    for group, volume in zip(groups, volumes):
        name = str(group.get("name") or "mesh")
        extents = _bounds_extents(group)
        mass = max(total_mass_kg * (volume / volume_total), 1e-6)
        movable = _part_is_movable(name, physics_intent)
        parts.append(
            {
                "id": name,
                "name": name,
                "body_type": _part_body_type(name, physics_intent),
                "movable": bool(movable),
                "mass": round(mass, 6),
                "mass_units": "kg",
                "length_units": "cm",
                "density_g_cm3": _DEFAULT_DENSITY_G_CM3,
                "inertia": _inertia_box(mass, extents),
                "center_of_mass": _bounds_center(group),
                "bounds_min": group.get("bounds_min"),
                "bounds_max": group.get("bounds_max"),
                "face_count": group.get("face_count"),
                "vertex_count": group.get("vertex_count"),
                "collision_proxy": "part_hull",
                "source": "topology.face_parts",
            }
        )
    return parts


def _joint_type_from_source(value: str, fallback: str) -> str:
    token = _token(value)
    if _contains_any(token, ("hinge", "door", "gate", "swing", "open", "close")):
        return "hinge"
    if _contains_any(token, ("slide", "rail", "track", "drawer", "bolt")):
        return "slider"
    if _contains_any(token, ("wheel", "axle", "roller", "spin", "rotate", "turret", "propeller")):
        return "revolute"
    if _contains_any(token, ("rope", "cable", "chain", "cloth", "fabric")):
        return "flexible"
    if _contains_any(token, ("attach", "mount", "dock", "socket", "connect", "fixed", "weld")):
        return "fixed"
    return fallback if fallback != "none" else "fixed"


def _joint_limits_for_type(joint_type: str) -> dict[str, float | list[float]]:
    if joint_type == "hinge":
        return {"axis": [0.0, 1.0, 0.0], "limit_lower": -90.0, "limit_upper": 90.0}
    if joint_type == "slider":
        return {"axis": [1.0, 0.0, 0.0], "limit_lower": -25.0, "limit_upper": 25.0}
    if joint_type == "revolute":
        return {"axis": [0.0, 0.0, 1.0], "limit_lower": -180.0, "limit_upper": 180.0}
    if joint_type == "flexible":
        return {"axis": [1.0, 0.0, 0.0], "limit_lower": -35.0, "limit_upper": 35.0}
    return {"axis": [0.0, 1.0, 0.0], "limit_lower": 0.0, "limit_upper": 0.0}


def _authored_physics_joints(
    asset: dict[str, Any],
    interfaces_bundle: dict[str, Any],
    physics_intent: dict[str, Any],
) -> list[dict[str, Any]]:
    joints: list[dict[str, Any]] = []
    seen: set[str] = set()
    fallback = str(physics_intent.get("joint_policy") or "none")
    sources = [
        *_as_list(asset.get("intent", {}).get("interactions")),
        *_as_list(asset.get("assembly", {}).get("mechanisms")),
        *_as_list(asset.get("build", {}).get("rig", {}).get("joints")),
    ]
    for raw in sources:
        text = str(raw).strip()
        if not text:
            continue
        joint_type = _joint_type_from_source(text, fallback)
        if joint_type == "fixed" and fallback == "none":
            continue
        jid = f"authored_{_slug_fragment(text, 'joint')}_{joint_type}"
        if jid in seen:
            continue
        seen.add(jid)
        joints.append(
            {
                "id": jid,
                "name": jid,
                "joint_type": joint_type,
                "parent_part_id": "root",
                "child_part_id": _slug_fragment(text, "moving_part"),
                **_joint_limits_for_type(joint_type),
                "source": "authored_source_intent",
                "source_value": text,
            }
        )
        if len(joints) >= _MAX_AUTHORED_PHYSICS_VALUES:
            return joints

    for socket in interfaces_bundle.get("sockets") or []:
        if not isinstance(socket, dict):
            continue
        socket_type = _token(socket.get("socket_type") or socket.get("kind"))
        if socket_type not in {"hinge", "door", "rail", "slot", "mount"}:
            continue
        metadata = socket.get("metadata") if isinstance(socket.get("metadata"), dict) else {}
        source_value = str(metadata.get("source_value") or socket.get("id") or "")
        joint_type = _joint_type_from_source(source_value or socket_type, "hinge" if socket_type in {"hinge", "door"} else "fixed")
        jid = f"interface_{_slug_fragment(str(socket.get('id') or socket_type), 'joint')}_{joint_type}"
        if jid in seen:
            continue
        seen.add(jid)
        joints.append(
            {
                "id": jid,
                "name": jid,
                "joint_type": joint_type,
                "parent_part_id": socket.get("parent_part_id") or "root",
                "child_part_id": socket.get("child_part_id") or _slug_fragment(source_value, "moving_part"),
                **_joint_limits_for_type(joint_type),
                "source": "interfaces.sockets",
                "source_value": source_value,
            }
        )
        if len(joints) >= _MAX_AUTHORED_PHYSICS_VALUES:
            break
    return joints


def _physics_constraints(physics_intent: dict[str, Any], joints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    body_type = str(physics_intent.get("body_type") or "static")
    if body_type in {"vehicle", "watercraft"}:
        constraints.append(
            {
                "id": f"{body_type}_stability",
                "constraint_type": "stability",
                "target": body_type,
                "source": "authored_source_intent",
            }
        )
    if body_type == "destructible":
        constraints.append(
            {
                "id": "destruction_release",
                "constraint_type": "break_threshold",
                "target": "movable_parts",
                "source": "authored_source_intent",
            }
        )
    for joint in joints:
        constraints.append(
            {
                "id": f"{joint['id']}_limits",
                "constraint_type": "joint_limits",
                "target": joint["id"],
                "limit_lower": joint.get("limit_lower"),
                "limit_upper": joint.get("limit_upper"),
                "axis": joint.get("axis"),
                "source": joint.get("source"),
            }
        )
    return constraints


def run(executor: Any, interfaces_bundle: dict[str, Any]) -> dict[str, Any]:
    """Run.

    Args:
        executor: executor argument.
        interfaces_bundle: interfaces_bundle argument.

    Returns:
        The result.
    """
    stage_dir = executor.stage_dirs["physics"]
    topology_runtime: RuntimeMesh = executor.runtime["topology"]["runtime_mesh"]
    cfg = executor.asset["build"]["physics"]
    shape_cfg = executor.asset.get("build", {}).get("shape", {})
    physics_intent = _classify_physics_intent(executor.asset, cfg)
    collision_mode = _resolve_collision_proxy_mode(cfg, shape_cfg, physics_intent)
    collision_mesh, resolved_collision_mode = _collision_proxy_mesh(topology_runtime, collision_mode)
    collision_path = stage_dir / "collision.glb"
    export_glb(collision_mesh, collision_path)
    mass_value = estimate_mass_kg(topology_runtime.mesh)
    parts = _physics_parts(topology_runtime, mass_value, physics_intent)
    joints = _authored_physics_joints(executor.asset, interfaces_bundle, physics_intent)
    constraints = _physics_constraints(physics_intent, joints)
    bundle = {
        "backend_id": "lathe.physics.proxy_v1",
        "collision": cfg.get("collision"),
        "collision_proxy_type": resolved_collision_mode,
        "collision_proxy_source": _collision_proxy_source(cfg, shape_cfg, physics_intent, resolved_collision_mode),
        "collision_proxy_uri": relpath(executor.out_dir, collision_path),
        "collision_uri": relpath(executor.out_dir, collision_path),
        "collision_proxy": True,
        "mass_kg": round(mass_value, 4),
        "center_of_mass": [round(float(v), 6) for v in topology_runtime.mesh.center_mass],
        "body_type": physics_intent["body_type"],
        "joint_policy": physics_intent["joint_policy"],
        "physics_intent": physics_intent,
        "parts": parts,
        "joints": joints,
        "constraints": constraints,
    }
    executor.runtime["physics"] = {"bundle": bundle, "collision_mesh": collision_mesh}
    dump_json(stage_dir / "bundle.json", bundle)
    return bundle
