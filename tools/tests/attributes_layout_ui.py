# UI run of the Attribute Manager's layout: shows the cube's pages (Fillet on and off), a sphere, the camera, the light
# and the floor through the tab buttons, takes a screenshot of each, and reports any error raised while drawing.
#   BLENDER_USER_CONFIG=<scratch> B4D_OUT=<scratch> Blender --factory-startup --window-geometry 100 60 1700 1000 \
#       --python tools/tests/attributes_layout_ui.py
# Prints "B4D AM ..." lines, "B4D AM FAIL ..." for every check that does not hold, and quits when done.
import os
import runpy
import traceback

import bpy

os.environ["B4D_STEPS"] = "wait"
HERE = os.path.dirname(os.path.abspath(__file__))
ns = runpy.run_path(os.path.join(HERE, "..", "try_ui.py"))
PLAN, shot, select = ns["PLAN"], ns["shot"], ns["select"]
FAILS = []
ERRORS = []


def check(cond, what):
    print("B4D AM", "ok" if cond else "FAIL", what, flush=True)
    if not cond:
        FAILS.append(what)


def watch_draw():
    from blenda4d import managers
    cls = managers.BLENDA4D_PT_attributes
    orig = cls.draw

    def draw(self, context):
        try:
            orig(self, context)
        except Exception:
            ERRORS.append(traceback.format_exc())
            raise
    cls.draw = draw


def tab(key):
    def go():
        from blenda4d import managers
        w = bpy.context.window_manager.windows[0]
        keys = [t[0] for t in managers._page_tabs(bpy.context.view_layer.objects.active)]
        k = key if key in keys else keys[min(2, len(keys) - 1)]      # a kind without that page: its third page
        with bpy.context.temp_override(window=w, screen=w.screen):
            res = bpy.ops.blenda4d.am_tab(key=k, label=k.title())
        check(res == {"FINISHED"} and bpy.context.window_manager.b4d_am_tab == k, f"tab {k} shows its page")
        for a in w.screen.areas:
            a.tag_redraw()
    return go


def fillet(on):
    def go():
        from blenda4d import managers, primitives
        ob = bpy.data.objects["Cube"]
        mod = managers._generator(ob)
        owner, attr = primitives.input_slot(mod, mod.node_group.interface.items_tree["Fillet"].identifier)
        setattr(owner, attr, on)
        for a in bpy.context.window_manager.windows[0].screen.areas:
            a.tag_redraw()
    return go


def show(name):
    def go():
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
        shot("am_" + name)
        check(not ERRORS, f"{name}: drawn without errors")
        for e in ERRORS:
            print(e, flush=True)
        ERRORS.clear()
    return go


def finish():
    print("B4D AM RESULT", "FAIL" if FAILS else "PASS", len(FAILS), FAILS, flush=True)


N = lambda: None  # noqa: E731
done = PLAN.pop()
PLAN += [watch_draw, N, N,
         lambda: select("Cube"), tab("OBJECT"), N, show("cube_object"),
         fillet(False), N, show("cube_fillet_off"), fillet(True),
         tab("BASIC"), N, show("cube_basic"),
         tab("COORD"), N, show("cube_coord"),
         lambda: select("Sphere"), tab("OBJECT"), N, show("sphere_object"),
         lambda: select("Camera"), tab("OBJECT"), N, show("camera_object"),
         tab("PHYSICAL"), N, show("camera_physical"),
         lambda: select("Area"), tab("OBJECT"), N, show("light_object"),
         lambda: select("Floor"), tab("OBJECT"), N, show("floor_object"),
         finish, done, lambda: bpy.ops.wm.quit_blender()]
