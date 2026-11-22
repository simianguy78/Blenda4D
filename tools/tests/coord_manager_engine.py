# Headless test of the Coordinate Manager (blenda4d/coord_manager.py): every field of every column, in Local and World,
# moves, turns or sizes the object as shown; both dropdowns change which values the columns edit; Reset puts the
# selected objects back; and switching the module off takes its role and properties away again.
#   BLENDER_USER_CONFIG=<scratch> Blender -b --factory-startup --python tools/tests/coord_manager_engine.py
import math
import os
import sys
import traceback

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from blenda4d import coord_manager, coords, kinds, roles, switch  # noqa: E402

FAIL = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what, flush=True)
    if not cond:
        FAIL.append(what)


def near(a, b, eps=1e-3):
    return all(abs(x - y) <= eps for x, y in zip(a, b))


def update():
    bpy.context.view_layer.update()


def scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    col = bpy.context.scene.collection
    parent = bpy.data.objects.new("Parent", None)
    col.objects.link(parent)
    parent.location = (1.0, 2.0, 3.0)
    parent.rotation_euler = (0.0, 0.0, math.radians(90))
    parent.scale = (2.0, 2.0, 2.0)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    cube = bpy.context.object
    cube.name = "Cube"
    cube.parent = parent
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    cube.select_set(True)
    bpy.context.view_layer.objects.active = cube
    update()
    return parent, cube


def test_registered():
    check(roles.ROLE_FLAGS.get(coord_manager.ROLE) == coord_manager.FLAG, "role registered on its own tab flag")
    others = [f for n, f in roles.ROLE_FLAGS.items() if n != coord_manager.ROLE]
    check(coord_manager.FLAG not in others, "no other role uses the flag")
    check("coord_manager" in kinds.FEATURES, "listed in kinds.FEATURES")
    for n in ("b4d_wpos", "b4d_wrot", "b4d_wscale"):
        check(hasattr(bpy.types.Object, n), f"Object.{n} registered")


def test_columns():
    wm = bpy.context.window_manager
    _p, cube = scene()
    seen = {}
    for space in ("LOCAL", "WORLD"):
        for third in ("SIZE", "SCALE"):
            wm.b4d_cm_space, wm.b4d_cm_third = space, third
            seen[(space, third)] = coord_manager.columns(cube, wm)
    check(seen[("LOCAL", "SIZE")] == ("b4d_pos", "b4d_rot", "b4d_size"), f"Local + Size columns {seen[('LOCAL', 'SIZE')]}")
    check(seen[("LOCAL", "SCALE")] == ("b4d_pos", "b4d_rot", "b4d_scale"), f"Local + Scale columns {seen[('LOCAL', 'SCALE')]}")
    check(seen[("WORLD", "SIZE")] == ("b4d_wpos", "b4d_wrot", "b4d_size"), f"World + Size columns {seen[('WORLD', 'SIZE')]}")
    check(seen[("WORLD", "SCALE")] == ("b4d_wpos", "b4d_wrot", "b4d_wscale"), f"World + Scale columns {seen[('WORLD', 'SCALE')]}")
    wm.b4d_cm_space, wm.b4d_cm_third = "LOCAL", "SIZE"


def test_local():
    _p, cube = scene()
    for i, axis in enumerate("XYZ"):
        _p, cube = scene()
        v = list(cube.b4d_pos)
        v[i] = 50.0
        cube.b4d_pos = v
        update()
        want = [0.0, 0.0, 0.0]
        want[{0: 0, 1: 2, 2: 1}[i]] = 0.5                 # shown Y is Blender's Z, cm to m
        check(near(cube.location, want), f"Local Position {axis} = 50 cm moves the object {tuple(cube.location)}")

        r = list(cube.b4d_rot)
        r[i] = 30.0
        cube.b4d_rot = r
        update()
        want = [0.0, 0.0, 0.0]
        want[{0: 0, 1: 2, 2: 1}[i]] = math.radians(30)
        check(near(cube.rotation_euler, want), f"Local Rotation {axis} = 30 turns the object {tuple(cube.rotation_euler)}")

        s = list(cube.b4d_scale)
        s[i] = 3.0
        cube.b4d_scale = s
        update()
        want = [1.0, 1.0, 1.0]
        want[{0: 0, 1: 2, 2: 1}[i]] = 3.0
        check(near(cube.scale, want), f"Local Scale {axis} = 3 stretches the object {tuple(cube.scale)}")

        _p, cube = scene()
        d = list(cube.b4d_size)
        d[i] = 250.0
        cube.b4d_size = d
        update()
        got = coords.to_shown(cube.dimensions)
        check(abs(got[i] - 250.0) < 1e-2, f"Size {axis} = 250 cm sizes the object {tuple(round(x, 2) for x in got)}")


def test_world():
    for i, axis in enumerate("XYZ"):
        parent, cube = scene()
        local_before = cube.location.copy()
        v = list(cube.b4d_wpos)
        v[i] = 70.0
        cube.b4d_wpos = v
        update()
        got = coords.to_shown(cube.matrix_world.translation)
        check(abs(got[i] - 70.0) < 1e-2, f"World Position {axis} = 70 cm puts the object there {tuple(round(x, 2) for x in got)}")
        check((cube.location - local_before).length > 1e-4, f"World Position {axis}: the local position changed with it")
        check(cube.parent is parent, f"World Position {axis}: the object keeps its parent")

        parent, cube = scene()
        r = list(cube.b4d_wrot)
        r[i] = 40.0
        cube.b4d_wrot = r
        update()
        got = cube.b4d_wrot
        check(abs(got[i] - 40.0) < 1e-2, f"World Rotation {axis} = 40 turns the object to it {tuple(round(x, 2) for x in got)}")

        parent, cube = scene()
        s = list(cube.b4d_wscale)
        s[i] = 5.0
        cube.b4d_wscale = s
        update()
        got = cube.b4d_wscale
        check(abs(got[i] - 5.0) < 1e-3, f"World Scale {axis} = 5 stretches the object to it {tuple(round(x, 3) for x in got)}")
        check(abs(cube.scale[{0: 0, 1: 2, 2: 1}[i]] - 2.5) < 1e-3,
              f"World Scale {axis}: the local scale is half of it under the parent's 2x ({tuple(cube.scale)})")

    parent, cube = scene()
    check(near(cube.b4d_wpos, coords.to_shown(cube.matrix_world.translation)), "World Position reads the scene position")
    check(not near(cube.b4d_wpos, cube.b4d_pos), "World and Local Position differ under a moved parent")


def test_reset():
    parent, cube = scene()
    other = bpy.data.objects.new("Other", None)
    bpy.context.scene.collection.objects.link(other)
    other.location, other.rotation_euler, other.scale = (3, 4, 5), (0.3, 0.2, 0.1), (2, 2, 2)
    cube.location, cube.rotation_euler, cube.scale = (1, 1, 1), (0.5, 0.5, 0.5), (3, 1, 2)
    parent.select_set(False)
    other.select_set(True)
    cube.select_set(True)
    bpy.context.view_layer.objects.active = cube
    with bpy.context.temp_override(selected_objects=[cube, other], active_object=cube):
        res = bpy.ops.blenda4d.cm_reset()
    check(res == {"FINISHED"}, f"Reset runs {res}")
    for ob in (cube, other):
        check(near(ob.location, (0, 0, 0)) and near(ob.rotation_euler, (0, 0, 0)) and near(ob.scale, (1, 1, 1)),
              f"Reset puts {ob.name} back")
    check(near(parent.location, (1, 2, 3)), "Reset leaves unselected objects alone")


def test_unregister():
    coord_manager.unregister()
    check(coord_manager.ROLE not in roles.ROLE_FLAGS, "off: role gone")
    check(not any(hasattr(bpy.types.Object, n) for n in ("b4d_wpos", "b4d_wrot", "b4d_wscale")), "off: object properties gone")
    check(not hasattr(bpy.types.WindowManager, "b4d_cm_space"), "off: dropdowns gone")
    check(not hasattr(bpy.ops.blenda4d, "cm_reset") or "cm_reset" not in dir(bpy.ops.blenda4d), "off: Reset gone")
    coord_manager.register()
    check(roles.ROLE_FLAGS.get(coord_manager.ROLE) == coord_manager.FLAG, "on again: role back")


try:
    switch._register_mode()
    test_registered()
    test_columns()
    test_local()
    test_world()
    test_reset()
    test_unregister()
    switch._unregister_mode()
    check(coord_manager.ROLE not in roles.ROLE_FLAGS, "Blenda off: role gone")
    check(not hasattr(bpy.types.Object, "b4d_wpos"), "Blenda off: world properties gone")
except Exception:
    traceback.print_exc()
    FAIL.append("exception")
print("B4D CM RESULT", "FAIL" if FAIL else "PASS", len(FAIL), FAIL, flush=True)
sys.exit(1 if FAIL else 0)
