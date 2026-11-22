# Headless test of the startup cube swap (switch.swap_startup_cube): in Blender's untouched startup scene the plain
# cube becomes Blenda's own Cube Object (Size, Segments, Fillet), keeping its name, collection and selection; any
# other scene, a moved cube or a saved file is left alone.
#   BLENDER_USER_CONFIG=<scratch> Blender -b --factory-startup --python tools/tests/startup_cube_engine.py
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from blenda4d import managers, switch  # noqa: E402

FAIL = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what, flush=True)
    if not cond:
        FAIL.append(what)


try:
    switch._register_mode()
    old = bpy.data.objects["Cube"]
    check(old.type == "MESH" and not old.modifiers, "the startup cube is a plain mesh")
    old.select_set(True)
    bpy.context.view_layer.objects.active = old
    coll = old.users_collection[0]

    # a moved cube, then a renamed scene, are not touched
    old.location.x = 1.0
    check(switch.swap_startup_cube() is None and bpy.data.objects["Cube"] is old, "a moved cube is left alone")
    old.location.x = 0.0
    bpy.data.objects["Light"].name = "Lamp"
    check(switch.swap_startup_cube() is None and bpy.data.objects["Cube"] is old, "another scene is left alone")
    bpy.data.objects["Lamp"].name = "Light"

    new = switch.swap_startup_cube()
    check(new is not None and new.name == "Cube", "the startup cube is swapped for a Cube Object")
    check(managers.prim_kind(new) == "cube", "it is Blenda's parametric cube")
    check(len(new.modifiers) == 1 and new.modifiers[0].type == "NODES", "with its generator modifier")
    check(new.users_collection[0] is coll, "in the same collection")
    check(bpy.context.view_layer.objects.active is new and new.select_get(), "still active and selected")
    check({o.name for o in bpy.data.objects} == {"Cube", "Light", "Camera"}, "Light and Camera are as they were")
    check(not [m for m in bpy.data.meshes if m.users == 0 and m.name == "Cube" and m is not new.data], "no orphan mesh")
    check(switch.swap_startup_cube() is None, "a second call changes nothing")
    switch._unregister_mode()
except Exception:
    import traceback
    traceback.print_exc()
    FAIL.append("exception")
print("B4D SC RESULT", "FAIL" if FAIL else "PASS", len(FAIL), FAIL, flush=True)
sys.exit(1 if FAIL else 0)
