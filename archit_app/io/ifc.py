"""
IFC 4.x write-only export for floorplan buildings and levels.

Requires the optional dependency:
    pip install archit-app[ifc]   # installs ifcopenshell

Exported IFC entities
---------------------
Spatial hierarchy
    IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey (one per Level)

Per level
    IfcWall        — walls (Polygon2D footprint extruded by wall.height)
    IfcSpace       — rooms (boundary polygon extruded by level.floor_height)
    IfcDoor        — door openings (placed at sill, extruded by height)
    IfcWindow      — window openings (placed at sill, extruded by height)
    IfcColumn      — columns (footprint polygon extruded by column.height)
    IfcSlab        — slabs (boundary extruded downward by thickness from elevation)
    IfcStair       — staircases (bounding-box polygon extruded by total_rise)

Note: opening void-cutting (IfcRelVoidsElement) is not set; doors and windows
are represented as standalone elements placed inside the storey.  Full IFC
parametric linkage can be added in a future iteration.

Usage::

    from archit_app.io.ifc import building_to_ifc, save_building_ifc

    model = building_to_ifc(my_building)
    model.write("output.ifc")          # ifcopenshell native write

    save_building_ifc(my_building, "output.ifc")   # convenience wrapper
"""

from __future__ import annotations

import time
from uuid import UUID

from archit_app.building.building import Building, BuildingMetadata
from archit_app.building.level import Level
from archit_app.elements.beam import Beam
from archit_app.elements.column import Column
from archit_app.elements.elevator import Elevator
from archit_app.elements.furniture import Furniture
from archit_app.elements.opening import Opening, OpeningKind
from archit_app.elements.ramp import Ramp
from archit_app.elements.room import Room
from archit_app.elements.slab import Slab, SlabType
from archit_app.elements.staircase import Staircase
from archit_app.elements.wall import Wall
from archit_app.geometry.crs import WORLD
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D

# ---------------------------------------------------------------------------
# Dependency guard
# ---------------------------------------------------------------------------


def _require_ifcopenshell():
    try:
        import ifcopenshell
        import ifcopenshell.guid  # noqa: F401 — ensure sub-module is available
        return ifcopenshell
    except ImportError:
        raise ImportError(
            "ifcopenshell is required for IFC export. "
            "Install it with: pip install archit-app[ifc]\n"
            "  or: pip install ifcopenshell"
        ) from None


# ---------------------------------------------------------------------------
# GUID helpers
# ---------------------------------------------------------------------------


def _new_guid() -> str:
    """Generate a fresh IFC GUID (22-char custom base64)."""
    ifc = _require_ifcopenshell()
    return ifc.guid.new()


def _guid_from_uuid(uid: UUID) -> str:
    """
    Convert a Python UUID to an IFC GUID.

    Produces a stable 22-char IFC GUID so that re-exporting the same model
    always yields the same GUIDs.
    """
    ifc = _require_ifcopenshell()
    return ifc.guid.compress(uid.hex)


# ---------------------------------------------------------------------------
# Low-level IFC factory helpers
# ---------------------------------------------------------------------------


def _pt3(f, x: float, y: float, z: float):
    return f.create_entity("IfcCartesianPoint", Coordinates=(x, y, z))


def _pt2(f, x: float, y: float):
    return f.create_entity("IfcCartesianPoint", Coordinates=(x, y))


def _dir3(f, x: float, y: float, z: float):
    return f.create_entity("IfcDirection", DirectionRatios=(x, y, z))


def _dir2(f, x: float, y: float):
    return f.create_entity("IfcDirection", DirectionRatios=(x, y))


def _axis2_3d(f, x: float = 0.0, y: float = 0.0, z: float = 0.0):
    """Identity IfcAxis2Placement3D at position (x, y, z)."""
    return f.create_entity(
        "IfcAxis2Placement3D",
        Location=_pt3(f, x, y, z),
        Axis=_dir3(f, 0.0, 0.0, 1.0),
        RefDirection=_dir3(f, 1.0, 0.0, 0.0),
    )


def _local_placement(f, x: float = 0.0, y: float = 0.0, z: float = 0.0,
                     relative_to=None):
    return f.create_entity(
        "IfcLocalPlacement",
        PlacementRelTo=relative_to,
        RelativePlacement=_axis2_3d(f, x, y, z),
    )


def _polygon_to_2d_profile(f, polygon: Polygon2D, profile_name: str = ""):
    """
    Convert a Polygon2D exterior ring to an IfcArbitraryClosedProfileDef.
    The ring is closed by repeating the first vertex.
    """
    pts_2d = [_pt2(f, p.x, p.y) for p in polygon.exterior]
    # Close the polyline explicitly
    pts_2d.append(pts_2d[0])
    polyline = f.create_entity("IfcPolyline", Points=pts_2d)
    return f.create_entity(
        "IfcArbitraryClosedProfileDef",
        ProfileType="AREA",
        ProfileName=profile_name or None,
        OuterCurve=polyline,
    )


def _extruded_solid(f, profile, depth: float, z_offset: float = 0.0):
    """
    Create an IfcExtrudedAreaSolid extruded in the +Z direction.

    Args:
        profile:   IfcArbitraryClosedProfileDef (or any IfcProfileDef)
        depth:     extrusion depth in meters (must be > 0)
        z_offset:  placement of the profile along Z before extrusion
    """
    return f.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=_axis2_3d(f, 0.0, 0.0, z_offset),
        ExtrudedDirection=_dir3(f, 0.0, 0.0, 1.0),
        Depth=max(depth, 1e-3),  # IFC requires positive depth
    )


def _shape_representation(f, context, body_item):
    """Wrap a solid into IfcProductDefinitionShape."""
    rep = f.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[body_item],
    )
    return f.create_entity(
        "IfcProductDefinitionShape",
        Representations=[rep],
    )


# ---------------------------------------------------------------------------
# Boilerplate: owner history, units, geometric context
# ---------------------------------------------------------------------------


def _create_owner_history(f, architect_name: str = ""):
    person = f.create_entity(
        "IfcPerson",
        Identification="ARCH",
        FamilyName=architect_name or None,
    )
    org = f.create_entity(
        "IfcOrganization",
        Name="archit-app",
    )
    pno = f.create_entity(
        "IfcPersonAndOrganization",
        ThePerson=person,
        TheOrganization=org,
    )
    app = f.create_entity(
        "IfcApplication",
        ApplicationDeveloper=org,
        Version="0.1.0",
        ApplicationFullName="archit-app",
        ApplicationIdentifier="archit-app",
    )
    return f.create_entity(
        "IfcOwnerHistory",
        OwningUser=pno,
        OwningApplication=app,
        ChangeAction="NOTDEFINED",
        LastModifiedDate=None,
        LastModifyingUser=None,
        LastModifyingApplication=None,
        CreationDate=int(time.time()),
    )


def _create_units(f):
    length = f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix=None, Name="METRE")
    area = f.create_entity("IfcSIUnit", UnitType="AREAUNIT", Prefix=None, Name="SQUARE_METRE")
    volume = f.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Prefix=None, Name="CUBIC_METRE")
    angle = f.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Prefix=None, Name="RADIAN")
    return f.create_entity("IfcUnitAssignment", Units=[length, area, volume, angle])


def _create_geometric_context(f):
    world_cs = _axis2_3d(f, 0.0, 0.0, 0.0)
    true_north = _dir2(f, 0.0, 1.0)
    return f.create_entity(
        "IfcGeometricRepresentationContext",
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-4,
        WorldCoordinateSystem=world_cs,
        TrueNorth=true_north,
    )


# ---------------------------------------------------------------------------
# Spatial hierarchy entities
# ---------------------------------------------------------------------------


def _create_project(f, building: Building, units, context, owner_history):
    return f.create_entity(
        "IfcProject",
        GlobalId=_new_guid(),
        OwnerHistory=owner_history,
        Name=building.metadata.name or "Unnamed Project",
        Description=None,
        ObjectType=None,
        LongName=None,
        Phase=None,
        RepresentationContexts=[context],
        UnitsInContext=units,
    )


def _create_site(f, owner_history):
    placement = _local_placement(f, 0.0, 0.0, 0.0)
    return f.create_entity(
        "IfcSite",
        GlobalId=_new_guid(),
        OwnerHistory=owner_history,
        Name="Site",
        Description=None,
        ObjectType=None,
        ObjectPlacement=placement,
        Representation=None,
        LongName=None,
        CompositionType="ELEMENT",
        RefLatitude=None,
        RefLongitude=None,
        RefElevation=0.0,
        LandTitleNumber=None,
        SiteAddress=None,
    )


def _create_building_entity(f, building: Building, owner_history, site_placement):
    placement = _local_placement(f, 0.0, 0.0, 0.0, relative_to=site_placement)
    return f.create_entity(
        "IfcBuilding",
        GlobalId=_new_guid(),
        OwnerHistory=owner_history,
        Name=building.metadata.name or "Building",
        Description=None,
        ObjectType=None,
        ObjectPlacement=placement,
        Representation=None,
        LongName=None,
        CompositionType="ELEMENT",
        ElevationOfRefHeight=0.0,
        ElevationOfTerrain=None,
        BuildingAddress=None,
    )


def _create_storey(f, level: Level, owner_history, building_placement):
    placement = _local_placement(f, 0.0, 0.0, level.elevation, relative_to=building_placement)
    return f.create_entity(
        "IfcBuildingStorey",
        GlobalId=_new_guid(),
        OwnerHistory=owner_history,
        Name=level.name or f"Level {level.index}",
        Description=None,
        ObjectType=None,
        ObjectPlacement=placement,
        Representation=None,
        LongName=None,
        CompositionType="ELEMENT",
        Elevation=level.elevation,
    )


# ---------------------------------------------------------------------------
# Relationship helpers
# ---------------------------------------------------------------------------


def _aggregate(f, owner_history, parent, children: list):
    """IfcRelAggregates: parent decomposes into children."""
    if not children:
        return
    f.create_entity(
        "IfcRelAggregates",
        GlobalId=_new_guid(),
        OwnerHistory=owner_history,
        Name=None,
        Description=None,
        RelatingObject=parent,
        RelatedObjects=children,
    )


def _contain_in_storey(f, owner_history, storey, elements: list):
    """IfcRelContainedInSpatialStructure: elements belong to the storey."""
    if not elements:
        return
    f.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=_new_guid(),
        OwnerHistory=owner_history,
        Name=None,
        Description=None,
        RelatedElements=elements,
        RelatingStructure=storey,
    )


# ---------------------------------------------------------------------------
# Element exporters
# ---------------------------------------------------------------------------


def _export_wall(f, wall: Wall, context, owner_history, storey_placement, elevation: float):
    """Export a Wall as IfcWall with extruded polygon geometry."""
    if isinstance(wall.geometry, Polygon2D):
        poly = wall.geometry
    else:
        pts = wall.geometry.to_polyline(resolution=32)
        from archit_app.geometry.polygon import Polygon2D as _P
        poly = _P(exterior=tuple(pts), crs=wall.geometry.crs if hasattr(wall.geometry, "crs") else None)

    profile = _polygon_to_2d_profile(f, poly, "WallProfile")
    solid = _extruded_solid(f, profile, depth=wall.height, z_offset=0.0)
    shape = _shape_representation(f, context, solid)
    placement = _local_placement(f, 0.0, 0.0, elevation, relative_to=storey_placement)

    ifc_wall = f.create_entity(
        "IfcWall",
        GlobalId=_guid_from_uuid(wall.id),
        OwnerHistory=owner_history,
        Name=f"Wall [{wall.wall_type.value}]",
        Description=None,
        ObjectType=wall.wall_type.value,
        ObjectPlacement=placement,
        Representation=shape,
        Tag=str(wall.id),
        PredefinedType=_wall_predefined_type(wall.wall_type.value),
    )
    return ifc_wall


def _wall_predefined_type(wall_type_value: str) -> str:
    mapping = {
        "exterior": "STANDARD",
        "interior": "STANDARD",
        "curtain": "CURTAIN_WALL",
        "shear": "SHEAR",
        "party": "STANDARD",
        "retaining": "RETAINING",
    }
    return mapping.get(wall_type_value, "NOTDEFINED")


def _export_room(f, room: Room, context, owner_history, storey_placement,
                 elevation: float, floor_height: float):
    """Export a Room as IfcSpace with extruded boundary polygon."""
    profile = _polygon_to_2d_profile(f, room.boundary, "SpaceProfile")
    solid = _extruded_solid(f, profile, depth=floor_height, z_offset=0.0)
    shape = _shape_representation(f, context, solid)
    placement = _local_placement(f, 0.0, 0.0, elevation, relative_to=storey_placement)

    return f.create_entity(
        "IfcSpace",
        GlobalId=_guid_from_uuid(room.id),
        OwnerHistory=owner_history,
        Name=room.name or "Space",
        Description=room.program or None,
        ObjectType=room.program or None,
        ObjectPlacement=placement,
        Representation=shape,
        LongName=room.name or None,
        CompositionType="ELEMENT",
        PredefinedType="SPACE",
        ElevationWithFlooring=elevation,
    )


def _export_opening(f, opening: Opening, context, owner_history,
                    storey_placement, elevation: float):
    """Export a Door or Window as an IfcDoor / IfcWindow."""
    z = elevation + opening.sill_height
    profile = _polygon_to_2d_profile(f, opening.geometry, "OpeningProfile")
    solid = _extruded_solid(f, profile, depth=opening.height, z_offset=0.0)
    shape = _shape_representation(f, context, solid)
    placement = _local_placement(f, 0.0, 0.0, z, relative_to=storey_placement)

    if opening.kind.value == "door":
        return f.create_entity(
            "IfcDoor",
            GlobalId=_guid_from_uuid(opening.id),
            OwnerHistory=owner_history,
            Name="Door",
            Description=None,
            ObjectType="DOOR",
            ObjectPlacement=placement,
            Representation=shape,
            Tag=str(opening.id),
            OverallHeight=opening.height,
            OverallWidth=opening.width,
            PredefinedType="DOOR",
            OperationType="SINGLE_SWING_LEFT",
        )
    else:  # window / archway / pass_through → IfcWindow
        return f.create_entity(
            "IfcWindow",
            GlobalId=_guid_from_uuid(opening.id),
            OwnerHistory=owner_history,
            Name="Window" if opening.kind.value == "window" else opening.kind.value.title(),
            Description=None,
            ObjectType="WINDOW",
            ObjectPlacement=placement,
            Representation=shape,
            Tag=str(opening.id),
            OverallHeight=opening.height,
            OverallWidth=opening.width,
            PredefinedType="WINDOW",
            PartitioningType="SINGLE_PANEL",
        )


def _export_column(f, column: Column, context, owner_history,
                   storey_placement, elevation: float):
    """Export a Column as IfcColumn with extruded footprint polygon."""
    profile = _polygon_to_2d_profile(f, column.geometry, "ColumnProfile")
    solid = _extruded_solid(f, profile, depth=column.height, z_offset=0.0)
    shape = _shape_representation(f, context, solid)
    placement = _local_placement(f, 0.0, 0.0, elevation, relative_to=storey_placement)

    return f.create_entity(
        "IfcColumn",
        GlobalId=_guid_from_uuid(column.id),
        OwnerHistory=owner_history,
        Name=f"Column [{column.shape.value}]",
        Description=None,
        ObjectType=column.shape.value,
        ObjectPlacement=placement,
        Representation=shape,
        Tag=str(column.id),
        PredefinedType="COLUMN",
    )


def _export_slab(f, slab: Slab, context, owner_history, storey_placement):
    """
    Export a Slab as IfcSlab.

    The slab is placed with its bottom face at (elevation - thickness) and
    extruded upward by thickness so the top surface sits at slab.elevation.
    """
    profile = _polygon_to_2d_profile(f, slab.boundary, "SlabProfile")
    solid = _extruded_solid(f, profile, depth=slab.thickness, z_offset=0.0)
    shape = _shape_representation(f, context, solid)

    z_bottom = slab.elevation - slab.thickness
    placement = _local_placement(f, 0.0, 0.0, z_bottom, relative_to=storey_placement)

    predefined = {
        "floor": "FLOOR",
        "ceiling": "ROOF",
        "roof": "ROOF",
    }.get(slab.slab_type.value, "NOTDEFINED")

    return f.create_entity(
        "IfcSlab",
        GlobalId=_guid_from_uuid(slab.id),
        OwnerHistory=owner_history,
        Name=f"Slab [{slab.slab_type.value}]",
        Description=None,
        ObjectType=slab.slab_type.value,
        ObjectPlacement=placement,
        Representation=shape,
        Tag=str(slab.id),
        PredefinedType=predefined,
    )


def _export_staircase(f, stair: Staircase, context, owner_history,
                      storey_placement, elevation: float):
    """
    Export a Staircase as IfcStair.

    Geometry is a bounding-box polygon of the staircase footprint extruded
    by the total rise — a simplified but legally valid IFC representation.
    """

    bb = stair.bounding_box()
    poly = Polygon2D.rectangle(
        bb.min_corner.x, bb.min_corner.y, bb.width, bb.height, crs=stair.boundary.crs
    )

    profile = _polygon_to_2d_profile(f, poly, "StairProfile")
    solid = _extruded_solid(f, profile, depth=max(stair.total_rise, 0.1), z_offset=0.0)
    shape = _shape_representation(f, context, solid)
    placement = _local_placement(f, 0.0, 0.0, elevation, relative_to=storey_placement)

    return f.create_entity(
        "IfcStair",
        GlobalId=_guid_from_uuid(stair.id),
        OwnerHistory=owner_history,
        Name="Stair",
        Description=None,
        ObjectType=None,
        ObjectPlacement=placement,
        Representation=shape,
        Tag=str(stair.id),
        PredefinedType="STRAIGHT_RUN_STAIR",
    )


def _export_ramp(f, ramp: Ramp, context, owner_history,
                 storey_placement, elevation: float):
    """Export a Ramp as IfcRamp with extruded footprint polygon."""
    profile = _polygon_to_2d_profile(f, ramp.boundary, "RampProfile")
    rise = ramp.total_rise
    solid = _extruded_solid(f, profile, depth=max(rise, 0.05), z_offset=0.0)
    shape = _shape_representation(f, context, solid)
    placement = _local_placement(f, 0.0, 0.0, elevation, relative_to=storey_placement)

    return f.create_entity(
        "IfcRamp",
        GlobalId=_guid_from_uuid(ramp.id),
        OwnerHistory=owner_history,
        Name=f"Ramp [{ramp.ramp_type.value}]",
        Description=None,
        ObjectType=ramp.ramp_type.value,
        ObjectPlacement=placement,
        Representation=shape,
        Tag=str(ramp.id),
        PredefinedType="STRAIGHT_RUN_RAMP",
    )


def _export_beam(f, beam: Beam, context, owner_history,
                 storey_placement):
    """Export a Beam as IfcBeam with extruded footprint polygon."""
    profile = _polygon_to_2d_profile(f, beam.geometry, "BeamProfile")
    solid = _extruded_solid(f, profile, depth=beam.depth, z_offset=0.0)
    shape = _shape_representation(f, context, solid)
    z = beam.elevation - beam.depth
    placement = _local_placement(f, 0.0, 0.0, z, relative_to=storey_placement)

    return f.create_entity(
        "IfcBeam",
        GlobalId=_guid_from_uuid(beam.id),
        OwnerHistory=owner_history,
        Name=f"Beam [{beam.section.value}]",
        Description=None,
        ObjectType=beam.section.value,
        ObjectPlacement=placement,
        Representation=shape,
        Tag=str(beam.id),
        PredefinedType="BEAM",
    )


def _export_furniture(f, furn: Furniture, context, owner_history,
                      storey_placement, elevation: float):
    """Export a Furniture item as IfcFurnishingElement."""
    profile = _polygon_to_2d_profile(f, furn.footprint, "FurnProfile")
    height = max(furn.height, 0.05)
    solid = _extruded_solid(f, profile, depth=height, z_offset=0.0)
    shape = _shape_representation(f, context, solid)
    placement = _local_placement(f, 0.0, 0.0, elevation, relative_to=storey_placement)

    label = furn.label or furn.category.value.replace("_", " ").title()
    return f.create_entity(
        "IfcFurnishingElement",
        GlobalId=_guid_from_uuid(furn.id),
        OwnerHistory=owner_history,
        Name=label,
        Description=furn.category.value,
        ObjectType=furn.category.value,
        ObjectPlacement=placement,
        Representation=shape,
        Tag=str(furn.id),
    )


def _export_elevator(f, elevator: Elevator, context, owner_history,
                     storey_placement, elevation: float):
    """Export an Elevator shaft as IfcTransportElement."""
    profile = _polygon_to_2d_profile(f, elevator.shaft, "ElevatorProfile")
    # Approximate cab height — Elevator no longer carries pit_depth as a field;
    # 2.5 m is a sensible IFC stand-in.
    height = 2.5
    solid = _extruded_solid(f, profile, depth=height, z_offset=0.0)
    shape = _shape_representation(f, context, solid)
    placement = _local_placement(f, 0.0, 0.0, elevation, relative_to=storey_placement)

    return f.create_entity(
        "IfcTransportElement",
        GlobalId=_guid_from_uuid(elevator.id),
        OwnerHistory=owner_history,
        Name="Elevator",
        Description=None,
        ObjectType="ELEVATOR",
        ObjectPlacement=placement,
        Representation=shape,
        Tag=str(elevator.id),
        PredefinedType="ELEVATOR",
    )


def _export_level(f, level: Level, context, owner_history,
                  storey_placement) -> list:
    """Export all elements in a level; return list of IFC product entities."""
    ifc_elements = []
    elev = level.elevation

    for wall in level.walls:
        ifc_elements.append(
            _export_wall(f, wall, context, owner_history, storey_placement, elev)
        )
        # Collect openings from wall
        for opening in wall.openings:
            ifc_elements.append(
                _export_opening(f, opening, context, owner_history, storey_placement, elev)
            )

    for opening in level.openings:
        ifc_elements.append(
            _export_opening(f, opening, context, owner_history, storey_placement, elev)
        )

    for room in level.rooms:
        ifc_elements.append(
            _export_room(f, room, context, owner_history, storey_placement,
                         elev, level.floor_height)
        )

    for col in level.columns:
        ifc_elements.append(
            _export_column(f, col, context, owner_history, storey_placement, elev)
        )

    for slab in level.slabs:
        ifc_elements.append(
            _export_slab(f, slab, context, owner_history, storey_placement)
        )

    for stair in level.staircases:
        ifc_elements.append(
            _export_staircase(f, stair, context, owner_history, storey_placement, elev)
        )

    for ramp in level.ramps:
        ifc_elements.append(
            _export_ramp(f, ramp, context, owner_history, storey_placement, elev)
        )

    for beam in level.beams:
        ifc_elements.append(
            _export_beam(f, beam, context, owner_history, storey_placement)
        )

    for furn in level.furniture:
        ifc_elements.append(
            _export_furniture(f, furn, context, owner_history, storey_placement, elev)
        )

    return ifc_elements


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def building_to_ifc(building: Building):
    """
    Export a :class:`~archit_app.building.building.Building` to an IFC 4
    model object.

    Args:
        building: The building to export.

    Returns:
        ``ifcopenshell.file`` — call ``.write(path)`` to save to disk.

    Raises:
        ImportError: If *ifcopenshell* is not installed.
    """
    ifc = _require_ifcopenshell()
    f = ifc.file(schema="IFC4")

    # --- Boilerplate -------------------------------------------------------
    owner_history = _create_owner_history(f, building.metadata.architect)
    context = _create_geometric_context(f)
    units = _create_units(f)

    # --- Spatial hierarchy -------------------------------------------------
    project = _create_project(f, building, units, context, owner_history)
    site = _create_site(f, owner_history)
    bldg_entity = _create_building_entity(f, building, owner_history,
                                          site.ObjectPlacement)

    _aggregate(f, owner_history, project, [site])
    _aggregate(f, owner_history, site, [bldg_entity])

    # --- Levels ------------------------------------------------------------
    storeys = []
    for level in building.levels:
        storey = _create_storey(f, level, owner_history,
                                bldg_entity.ObjectPlacement)
        elements = _export_level(f, level, context, owner_history,
                                 storey.ObjectPlacement)
        _contain_in_storey(f, owner_history, storey, elements)
        storeys.append(storey)

    _aggregate(f, owner_history, bldg_entity, storeys)

    # --- Elevators (building-level vertical elements) ----------------------
    if building.elevators:
        # Place at ground (lowest storey) elevation
        base_elev = building.levels[0].elevation if building.levels else 0.0
        base_placement = (
            storeys[0].ObjectPlacement if storeys
            else _local_placement(f, 0.0, 0.0, base_elev)
        )
        elev_elements = []
        for elevator in building.elevators:
            elev_elements.append(
                _export_elevator(f, elevator, context, owner_history,
                                 base_placement, base_elev)
            )
        if elev_elements and storeys:
            _contain_in_storey(f, owner_history, storeys[0], elev_elements)

    return f


def save_building_ifc(building: Building, path: str) -> None:
    """
    Export a building to an IFC 4 file.

    Args:
        building: The building to export.
        path:     Destination file path (e.g. ``"my_building.ifc"``).

    Raises:
        ImportError: If *ifcopenshell* is not installed.
    """
    model = building_to_ifc(building)
    model.write(path)


# ---------------------------------------------------------------------------
# IFC import — geometry helpers
# ---------------------------------------------------------------------------


def _extract_polygon_from_product(ifc_product) -> "Polygon2D | None":
    """
    Extract a 2-D footprint polygon from an IFC product's body representation.

    Looks for the first ``IfcExtrudedAreaSolid`` whose swept area is an
    ``IfcArbitraryClosedProfileDef`` with an ``IfcPolyline`` outer curve.
    Returns ``None`` if no suitable geometry is found.
    """
    try:
        rep = ifc_product.Representation
        if rep is None:
            return None
        for shape_rep in rep.Representations:
            for item in shape_rep.Items:
                if not item.is_a("IfcExtrudedAreaSolid"):
                    continue
                profile = item.SweptArea
                if not profile.is_a("IfcArbitraryClosedProfileDef"):
                    continue
                outer = profile.OuterCurve
                if not outer.is_a("IfcPolyline"):
                    continue
                pts = []
                for ifc_pt in outer.Points:
                    coords = ifc_pt.Coordinates
                    pts.append(Point2D(x=float(coords[0]), y=float(coords[1]), crs=WORLD))
                # GeoJSON / IFC polylines may close themselves (first == last)
                if len(pts) > 1 and pts[0].x == pts[-1].x and pts[0].y == pts[-1].y:
                    pts = pts[:-1]
                if len(pts) >= 3:
                    return Polygon2D(exterior=tuple(pts), crs=WORLD)
    except Exception:
        pass
    return None


def _extract_extrusion_depth(ifc_product) -> float:
    """Return the extrusion depth from the first IfcExtrudedAreaSolid found."""
    try:
        rep = ifc_product.Representation
        if rep is None:
            return 3.0
        for shape_rep in rep.Representations:
            for item in shape_rep.Items:
                if item.is_a("IfcExtrudedAreaSolid"):
                    return float(item.Depth)
    except Exception:
        pass
    return 3.0


def _extract_local_z(ifc_product) -> float:
    """Return the Z component of the product's local placement."""
    try:
        pl = ifc_product.ObjectPlacement
        if pl is None:
            return 0.0
        if pl.is_a("IfcLocalPlacement"):
            rel = pl.RelativePlacement
            if rel and rel.is_a("IfcAxis2Placement3D"):
                return float(rel.Location.Coordinates[2])
    except Exception:
        pass
    return 0.0


# ---------------------------------------------------------------------------
# IFC entity → archit_app element converters
# ---------------------------------------------------------------------------


def _ifc_wall_to_wall(ifc_wall) -> "Wall | None":
    poly = _extract_polygon_from_product(ifc_wall)
    if poly is None:
        return None
    height = _extract_extrusion_depth(ifc_wall)
    obj_type = (getattr(ifc_wall, "ObjectType", None) or "interior").lower()
    from archit_app.elements.wall import WallType as _WT
    _wt_map = {
        "exterior": _WT.EXTERIOR,
        "interior": _WT.INTERIOR,
        "curtain_wall": _WT.CURTAIN,
        "curtain": _WT.CURTAIN,
        "shear": _WT.SHEAR,
        "retaining": _WT.RETAINING,
        "party": _WT.PARTY,
    }
    wall_type = _wt_map.get(obj_type, _WT.INTERIOR)
    return Wall(geometry=poly, thickness=0.2, height=height, wall_type=wall_type)


def _ifc_space_to_room(ifc_space) -> "Room | None":
    poly = _extract_polygon_from_product(ifc_space)
    if poly is None:
        return None
    name = ifc_space.Name or ""
    program = ifc_space.ObjectType or ifc_space.Description or ""
    return Room(boundary=poly, name=name, program=program)


def _ifc_door_to_opening(ifc_door) -> "Opening | None":
    poly = _extract_polygon_from_product(ifc_door)
    if poly is None:
        return None
    width = float(getattr(ifc_door, "OverallWidth", None) or 0.9)
    height = float(getattr(ifc_door, "OverallHeight", None) or 2.1)
    sill_z = _extract_local_z(ifc_door)
    return Opening(
        geometry=poly,
        kind=OpeningKind.DOOR,
        width=width,
        height=height,
        sill_height=max(sill_z, 0.0),
    )


def _ifc_window_to_opening(ifc_window) -> "Opening | None":
    poly = _extract_polygon_from_product(ifc_window)
    if poly is None:
        return None
    width = float(getattr(ifc_window, "OverallWidth", None) or 1.2)
    height = float(getattr(ifc_window, "OverallHeight", None) or 1.2)
    sill_z = _extract_local_z(ifc_window)
    return Opening(
        geometry=poly,
        kind=OpeningKind.WINDOW,
        width=width,
        height=height,
        sill_height=max(sill_z, 0.0),
    )


def _ifc_column_to_column(ifc_col) -> "Column | None":
    poly = _extract_polygon_from_product(ifc_col)
    if poly is None:
        return None
    height = _extract_extrusion_depth(ifc_col)
    from archit_app.elements.column import ColumnShape
    return Column(geometry=poly, height=height, shape=ColumnShape.RECTANGULAR)


def _ifc_slab_to_slab(ifc_slab, storey_elev: float = 0.0) -> "Slab | None":
    poly = _extract_polygon_from_product(ifc_slab)
    if poly is None:
        return None
    thickness = _extract_extrusion_depth(ifc_slab)
    z_bottom = _extract_local_z(ifc_slab)
    elevation = storey_elev + z_bottom + thickness

    predefined = (getattr(ifc_slab, "PredefinedType", None) or "FLOOR").upper()
    slab_type_map = {"FLOOR": SlabType.FLOOR, "ROOF": SlabType.ROOF, "CEILING": SlabType.CEILING}
    slab_type = slab_type_map.get(predefined, SlabType.FLOOR)

    return Slab(
        boundary=poly,
        thickness=thickness,
        elevation=elevation,
        slab_type=slab_type,
    )


def _ifc_stair_to_staircase(ifc_stair) -> "Staircase | None":
    poly = _extract_polygon_from_product(ifc_stair)
    if poly is None:
        return None
    total_rise = _extract_extrusion_depth(ifc_stair)
    rise_count = 10
    rise_height = total_rise / rise_count
    bb = poly.bounding_box()
    width = min(bb.width, bb.height)
    return Staircase(
        boundary=poly,
        rise_count=rise_count,
        rise_height=rise_height,
        run_depth=0.28,
        width=width,
    )


def _ifc_ramp_to_ramp(ifc_ramp) -> "Ramp | None":
    poly = _extract_polygon_from_product(ifc_ramp)
    if poly is None:
        return None
    import math as _math
    rise = _extract_extrusion_depth(ifc_ramp)
    bb = poly.bounding_box()
    length = max(bb.width, bb.height)
    slope_angle = _math.atan2(rise, length) if length > 0 else 0.0
    width = min(bb.width, bb.height)
    return Ramp(
        boundary=poly,
        width=width,
        slope_angle=slope_angle,
    )


def _ifc_beam_to_beam(ifc_beam) -> "Beam | None":
    poly = _extract_polygon_from_product(ifc_beam)
    if poly is None:
        return None
    depth = _extract_extrusion_depth(ifc_beam)
    z = _extract_local_z(ifc_beam)
    elevation = z + depth
    bb = poly.bounding_box()
    width = min(bb.width, bb.height)
    from archit_app.elements.beam import BeamSection
    return Beam(geometry=poly, width=width, depth=depth, elevation=elevation,
                section=BeamSection.RECTANGULAR)


def _ifc_furnishing_to_furniture(ifc_furn) -> "Furniture | None":
    poly = _extract_polygon_from_product(ifc_furn)
    if poly is None:
        return None
    height = _extract_extrusion_depth(ifc_furn)
    label = ifc_furn.Name or ""
    bb = poly.bounding_box()
    from archit_app.elements.furniture import FurnitureCategory
    return Furniture(
        footprint=poly,
        label=label,
        category=FurnitureCategory.CUSTOM,
        width=bb.width,
        depth=bb.height,
        height=height,
    )


def _ifc_transport_to_elevator(ifc_te) -> "Elevator | None":
    poly = _extract_polygon_from_product(ifc_te)
    if poly is None:
        return None
    bb = poly.bounding_box()
    return Elevator(
        shaft=poly,
        cab_width=bb.width * 0.8,
        cab_depth=bb.height * 0.8,
        bottom_level_index=0,
        top_level_index=1,
    )


# ---------------------------------------------------------------------------
# IFC import — public API
# ---------------------------------------------------------------------------


def building_from_ifc(path: str) -> Building:
    """
    Import a :class:`~archit_app.building.building.Building` from an IFC 4 file.

    Reads the ``IfcBuildingStorey`` hierarchy and converts contained elements
    back to their corresponding archit_app types via the
    ``IfcRelContainedInSpatialStructure`` relationships.

    Supported element types
    -----------------------
    * ``IfcWall``              → :class:`~archit_app.elements.wall.Wall`
    * ``IfcSpace``             → :class:`~archit_app.elements.room.Room`
    * ``IfcDoor``              → :class:`~archit_app.elements.opening.Opening` (DOOR)
    * ``IfcWindow``            → :class:`~archit_app.elements.opening.Opening` (WINDOW)
    * ``IfcColumn``            → :class:`~archit_app.elements.column.Column`
    * ``IfcSlab``              → :class:`~archit_app.elements.slab.Slab`
    * ``IfcStair``             → :class:`~archit_app.elements.staircase.Staircase`
    * ``IfcRamp``              → :class:`~archit_app.elements.ramp.Ramp`
    * ``IfcBeam``              → :class:`~archit_app.elements.beam.Beam`
    * ``IfcFurnishingElement`` → :class:`~archit_app.elements.furniture.Furniture`
    * ``IfcTransportElement``  → :class:`~archit_app.elements.elevator.Elevator`
      (building-level, not storey-level)

    Geometry is reconstructed from ``IfcExtrudedAreaSolid`` profiles.
    Elements whose geometry cannot be read are silently skipped.

    Parameters
    ----------
    path:
        Path to the IFC file.

    Returns
    -------
    Building
        A :class:`~archit_app.building.building.Building` populated with
        levels and elements extracted from the IFC file.

    Raises
    ------
    ImportError
        If *ifcopenshell* is not installed.
    """
    ifc = _require_ifcopenshell()
    f = ifc.open(path)

    # --- Building metadata ---------------------------------------------------
    projects = f.by_type("IfcProject")
    project_name = projects[0].Name if projects else ""
    buildings_ifc = f.by_type("IfcBuilding")
    building_name = (buildings_ifc[0].Name if buildings_ifc else project_name) or ""

    # --- Storeys → Levels ----------------------------------------------------
    storeys = sorted(
        f.by_type("IfcBuildingStorey"),
        key=lambda s: float(s.Elevation or 0.0),
    )

    # Build a map: storey IFC ID → set of contained element IDs
    storey_elements: dict[int, list] = {s.id(): [] for s in storeys}
    for rel in f.by_type("IfcRelContainedInSpatialStructure"):
        storey = rel.RelatingStructure
        if storey.is_a("IfcBuildingStorey") and storey.id() in storey_elements:
            storey_elements[storey.id()].extend(rel.RelatedElements)

    levels: list[Level] = []
    for idx, storey in enumerate(storeys):
        elev = float(storey.Elevation or 0.0)
        level = Level(
            index=idx,
            elevation=elev,
            floor_height=3.0,
            name=storey.Name or f"Level {idx}",
        )
        for el in storey_elements.get(storey.id(), []):
            try:
                if el.is_a("IfcWall"):
                    obj = _ifc_wall_to_wall(el)
                    if obj:
                        level = level.add_wall(obj)
                elif el.is_a("IfcSpace"):
                    obj = _ifc_space_to_room(el)
                    if obj:
                        level = level.add_room(obj)
                elif el.is_a("IfcDoor"):
                    obj = _ifc_door_to_opening(el)
                    if obj:
                        level = level.add_opening(obj)
                elif el.is_a("IfcWindow"):
                    obj = _ifc_window_to_opening(el)
                    if obj:
                        level = level.add_opening(obj)
                elif el.is_a("IfcColumn"):
                    obj = _ifc_column_to_column(el)
                    if obj:
                        level = level.add_column(obj)
                elif el.is_a("IfcSlab"):
                    obj = _ifc_slab_to_slab(el, storey_elev=elev)
                    if obj:
                        level = level.add_slab(obj)
                elif el.is_a("IfcStair"):
                    obj = _ifc_stair_to_staircase(el)
                    if obj:
                        level = level.add_staircase(obj)
                elif el.is_a("IfcRamp"):
                    obj = _ifc_ramp_to_ramp(el)
                    if obj:
                        level = level.add_ramp(obj)
                elif el.is_a("IfcBeam"):
                    obj = _ifc_beam_to_beam(el)
                    if obj:
                        level = level.add_beam(obj)
                elif el.is_a("IfcFurnishingElement"):
                    obj = _ifc_furnishing_to_furniture(el)
                    if obj:
                        level = level.add_furniture(obj)
            except Exception:
                pass
        levels.append(level)

    # --- Elevators (IfcTransportElement, building-level) ---------------------
    elevators: list[Elevator] = []
    for te in f.by_type("IfcTransportElement"):
        try:
            predefined = (getattr(te, "PredefinedType", None) or "").upper()
            if predefined == "ELEVATOR":
                obj = _ifc_transport_to_elevator(te)
                if obj:
                    elevators.append(obj)
        except Exception:
            pass

    return Building(
        metadata=BuildingMetadata(name=building_name),
        levels=tuple(levels),
        elevators=tuple(elevators),
    )


def level_from_ifc(path: str, *, storey_index: int = 0) -> Level:
    """
    Import a single :class:`~archit_app.building.level.Level` from an IFC file.

    Parameters
    ----------
    path:
        Path to the IFC file.
    storey_index:
        Which ``IfcBuildingStorey`` to import (0 = lowest, by elevation).

    Returns
    -------
    Level

    Raises
    ------
    ImportError
        If *ifcopenshell* is not installed.
    IndexError
        If the file has fewer storeys than *storey_index*.
    """
    building = building_from_ifc(path)
    if not building.levels:
        return Level(index=0, elevation=0.0, floor_height=3.0)
    return building.levels[min(storey_index, len(building.levels) - 1)]
