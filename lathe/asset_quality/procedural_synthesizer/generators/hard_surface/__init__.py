"""Hard-surface domain extension registration.

Imports trigger the registration of the hard-surface DomainExtension
against the module-level REGISTRY. New generators added to this
package must (1) export a GENERATOR symbol, (2) be added to
``HARD_SURFACE_GENERATORS`` below, and (3) have a corresponding
typed attribute schema in ``..attributes``.
"""

from __future__ import annotations

from ...attributes.decal_zone import DecalZoneAttributes
from ...attributes.fastener import FastenerAttributes
from ...attributes.frame import FrameAttributes
from ...attributes.handle import HandleAttributes
from ...attributes.inset import InsetAttributes
from ...attributes.material_zone import MaterialZoneAttributes
from ...attributes.panel import PanelAttributes
from ...attributes.primary_volume import PrimaryVolumeAttributes
from ...attributes.rail import RailAttributes
from ...attributes.socket import SocketAttributes
from ...attributes.trim import TrimAttributes
from ...attributes.wear_zone import WearZoneAttributes
from ...domain_extension import (
    DomainExtensionManifest,
    DomainExtensionRegistration,
)
from ...registry import REGISTRY
from . import (
    decal_zone,
    fastener,
    frame,
    handle,
    inset,
    material_zone,
    panel,
    primary_volume,
    rail,
    socket,
    trim,
    wear_zone,
)


HARD_SURFACE_DOMAIN_ID = "hard_surface"


HARD_SURFACE_NODE_SCHEMAS: dict[str, type] = {
    "primary_volume": PrimaryVolumeAttributes,
    "panel": PanelAttributes,
    "frame": FrameAttributes,
    "trim": TrimAttributes,
    "fastener": FastenerAttributes,
    "handle": HandleAttributes,
    "material_zone": MaterialZoneAttributes,
    "decal_zone": DecalZoneAttributes,
    "wear_zone": WearZoneAttributes,
    "inset": InsetAttributes,
    "rail": RailAttributes,
    "socket": SocketAttributes,
}


HARD_SURFACE_EDGE_SCHEMAS: dict[str, type] = {
    "attached_to": dict,  # raw dict — no typed edge schema yet
}


HARD_SURFACE_GENERATORS = (
    primary_volume.GENERATOR,
    panel.GENERATOR,
    frame.GENERATOR,
    trim.GENERATOR,
    fastener.GENERATOR,
    handle.GENERATOR,
    material_zone.GENERATOR,
    decal_zone.GENERATOR,
    wear_zone.GENERATOR,
    inset.GENERATOR,
    rail.GENERATOR,
    socket.GENERATOR,
)


# Decorators are imported by the decorators package so domain
# registration there can include them. We re-import the
# attached_to decorator here for the manifest's emitted-op-kinds
# inventory.
def _load_decorators():
    from ...decorators.hard_surface import attached_to as attached_to_module
    return (attached_to_module.DECORATOR,)


_MANIFEST = DomainExtensionManifest(
    domain_id=HARD_SURFACE_DOMAIN_ID,
    node_type_schemas=HARD_SURFACE_NODE_SCHEMAS,
    edge_type_schemas=HARD_SURFACE_EDGE_SCHEMAS,
    required_kernel_capabilities=(
        "solid.box",
        "solid.rounded_box",
        "solid.cylinder",
        "solid.sphere",
        "solid.panel",
        "op.union",
    ),
    emitted_shape_ir_ops=(
        "solid.box",
        "solid.rounded_box",
        "solid.cylinder",
        "solid.sphere",
        "solid.extruded_profile",
        "solid.revolved_profile",
        "solid.panel",
        "op.union",
    ),
    style_pack_compatibility=("*",),
    policy_pack_compatibility=("*",),
    description=(
        "Hard-surface domain extension: primary volumes (boxes, "
        "cylinders, spheres, profiles), panels with attachment edges. "
        "First procedural domain to register against the synthesizer's "
        "DomainExtensionManifest contract."
    ),
)


def register() -> None:
    """Idempotent registration of the hard-surface domain.

    Called automatically on import of this package. Safe to call
    multiple times — the registry replaces existing entries with
    identical content silently.
    """
    REGISTRY.register_domain_extension(
        DomainExtensionRegistration(
            manifest=_MANIFEST,
            generators=HARD_SURFACE_GENERATORS,
            decorators=_load_decorators(),
        )
    )


# Auto-register on import. Other modules that need the hard-surface
# domain just import this package; the side effect is registration.
register()
