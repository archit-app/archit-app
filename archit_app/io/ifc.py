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
from uuid import UUID, uuid4

from archit_app.building.building import Building
from archit_app.building.level import Level
from archit_app.elements.column import Column
from archit_app.elements.opening import Opening, OpeningKind
from archit_app.elements.room import Room
from archit_app.elements.slab import Slab, SlabType
from archit_app.elements.staircase import Staircase
from archit_app.elements.wall import Wall
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
    from archit_app.geometry.bbox import BoundingBox2D

    bb = stair.geometry.bounding_box()
    poly = Polygon2D.rectangle(
        bb.min_x, bb.min_y, bb.width, bb.height, crs=stair.geometry.crs
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
