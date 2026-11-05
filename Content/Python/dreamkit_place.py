"""Place a Dream Palette piece in front of the viewport camera, standing on the floor (Dreams panel, Place button)."""
import math

import unreal

import dreamkit_common as common

DISTANCE_CM = 300.0          # how far in front of the camera a piece lands
TRACE_UP_CM = 600.0
TRACE_DOWN_CM = 6000.0
STAGGER_CM = 70.0            # sideways step between pieces placed one after another from the same camera spot
_last_pose = None
_same_pose_count = 0


def floor_delta(floor_z, bounds_origin_z, bounds_extent_z):
    """How far to move an actor up so the bottom of its bounds rests on the floor. Pure arithmetic."""
    return floor_z - (bounds_origin_z - bounds_extent_z)


def viewport_camera():
    """(location, rotation) of the active level viewport camera, or a standing creator at the origin if there is none."""
    try:
        info = unreal.EditorLevelLibrary.get_level_viewport_camera_info()
    except Exception:
        info = None
    if info:
        return info[0], info[1]
    return unreal.Vector(0.0, 0.0, 170.0), unreal.Rotator(0.0, 0.0, 0.0)


def _editor_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _trace_objects(world, start, end, types):
    try:
        hit = unreal.SystemLibrary.line_trace_single_for_objects(
            world, start, end, types, False, [], unreal.DrawDebugTrace.NONE, True)
    except Exception as e:
        common.warn('floor trace failed: %s' % e)
        return None
    if hit is None:
        return None
    t = hit.to_tuple()      # (blocking_hit, initial_overlap, time, distance, location, impact_point, ...)
    return t[5].z if t[0] else None


def find_floor_z(world, x, y, around_z):
    """Z of the floor straight under (x, y), starting above around_z. None when nothing is there.

    The floor is level geometry first (WorldStatic objects), so pieces placed earlier do not become the floor for the
    next one. If the map has no static surface there (a floor built from a movable Blueprint), anything solid counts.
    """
    start = unreal.Vector(x, y, around_z + TRACE_UP_CM)
    end = unreal.Vector(x, y, around_z - TRACE_DOWN_CM)
    z = _trace_objects(world, start, end, [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1])
    if z is None:
        z = _trace_objects(world, start, end, [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2])
    return z


def actor_class_of(asset_path):
    """The Actor class of a palette Blueprint, or None when the asset is not a placeable actor."""
    cls = unreal.EditorAssetLibrary.load_blueprint_class(asset_path.split('.')[0])
    if cls is None:
        return None
    cdo = unreal.get_default_object(cls)
    return cls if isinstance(cdo, unreal.Actor) else None


def place(asset_path, camera=None, distance=DISTANCE_CM):
    """Spawn a palette Blueprint in front of the viewport camera on the floor and select it.

    Returns (actor, message). actor is None when nothing was placed; message always says what happened in plain words.
    camera: (location, rotation) override, used by the tests; the viewport's camera otherwise.
    """
    short = asset_path.split('/')[-1].split('.')[0]
    cls = actor_class_of(asset_path)
    if cls is None:
        return None, '%s cannot be placed in a map: it is not an actor.' % short
    world = _editor_world()
    if world is None:
        return None, 'Open a map first, then press Place.'
    loc, rot = camera if camera else viewport_camera()
    yaw = math.radians(rot.yaw)
    # Pressing Place again without moving the camera puts the next piece beside the last one, not inside it.
    global _last_pose, _same_pose_count
    pose = (round(loc.x), round(loc.y), round(loc.z), round(rot.yaw))
    _same_pose_count = _same_pose_count + 1 if pose == _last_pose else 0
    _last_pose = pose
    side = ((_same_pose_count + 1) // 2) * STAGGER_CM * (1 if _same_pose_count % 2 else -1)
    x = loc.x + math.cos(yaw) * distance - math.sin(yaw) * side
    y = loc.y + math.sin(yaw) * distance + math.cos(yaw) * side
    floor = find_floor_z(world, x, y, loc.z)
    if floor is None:
        floor = 0.0
        where = 'no floor under that spot, so it sits at height 0'
    else:
        where = 'on the floor'
    ea = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    # The piece faces the creator.
    with unreal.ScopedEditorTransaction('Place %s' % short):
        actor = ea.spawn_actor_from_class(cls, unreal.Vector(x, y, floor), unreal.Rotator(0.0, 0.0, rot.yaw + 180.0))
        if actor is None:
            return None, 'The editor could not create %s.' % short
        # Rest the bottom of the piece's bounds on the floor. Bounds can shift when the piece moves (components update
        # lazily), so measure again after each move; two or three passes settle every palette piece.
        for _ in range(4):
            origin, extent = actor.get_actor_bounds(False)
            dz = floor_delta(floor, origin.z, extent.z)
            if abs(dz) <= 0.25:
                break
            actor.set_actor_location(actor.get_actor_location() + unreal.Vector(0.0, 0.0, dz), False, False)
        ea.set_selected_level_actors([actor])
    origin, extent = actor.get_actor_bounds(False)
    common.log('placed %s as %s at (%.0f, %.0f, %.0f), bottom %.2f cm over the floor' % (
        short, actor.get_actor_label(), x, y, actor.get_actor_location().z, (origin.z - extent.z) - floor))
    return actor, 'Placed %s %s.' % (short, where)
