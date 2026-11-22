# UI run of the Coordinate Manager: the strip sits under the Attribute Manager, level with the timeline, shows the
# selected object, follows both dropdowns, changes the object when a field is edited, hides and comes back with the
# timeline's axes button, and goes away and comes back with the Blenda 4D | Blender switch.
#   BLENDER_USER_CONFIG=<scratch> B4D_OUT=<scratch> Blender --factory-startup --window-geometry 100 60 1700 1000 \
#       --python tools/tests/coord_manager_ui.py
# Prints "B4D CM ..." lines, "B4D CM FAIL ..." for every check that does not hold, and quits when done.
import os
import runpy

import bpy

os.environ["B4D_STEPS"] = "wait"
HERE = os.path.dirname(os.path.abspath(__file__))
ns = runpy.run_path(os.path.join(HERE, "..", "try_ui.py"))
PLAN, shot, select = ns["PLAN"], ns["shot"], ns["select"]
FAILS = []
COORDS_ROWS_PX = 102          # UI units the header row and the three rows need (measured at 2x: 201 px)


def win():
    return bpy.context.window_manager.windows[0]


def check(cond, what):
    print("B4D CM", "ok" if cond else "FAIL", what, flush=True)
    if not cond:
        FAILS.append(what)


def strip():
    from blenda4d import roles
    return roles.areas(win().screen, "COORDS")


def redraw():
    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)


def placed(tag):
    def go():
        from blenda4d import build, roles
        s = strip()
        check(len(s) == 1, f"{tag}: one Coordinate Manager ({len(s)})")
        if not s:
            return
        a = s[0]
        tl = [t for t in win().screen.areas if t.type == "DOPESHEET_EDITOR"]
        check(len(tl) == 1, f"{tag}: the timeline is still there")
        if tl:
            t = tl[0]
            check(abs(a.y - t.y) <= 3 and abs(a.height - t.height) <= 3, f"{tag}: level with the timeline "
                  f"(strip y{a.y} h{a.height}, timeline y{t.y} h{t.height})")
        from blenda4d import build
        need = build.px(COORDS_ROWS_PX)
        check(a.height >= need, f"{tag}: tall enough for the header row and X, Y, Z (h{a.height}, needs {need})")
        am = roles.areas(win().screen, "ATTRIBUTES")
        check(len(am) == 1, f"{tag}: one Attribute Manager")
        if am:
            m = am[0]
            check(abs(a.x - m.x) <= 2 and abs(a.width - m.width) <= 2 and m.y > a.y,
                  f"{tag}: right under the Attribute Manager, as wide (strip x{a.x} w{a.width}, attributes x{m.x} w{m.width} y{m.y})")
        check(build.intact(win().screen), f"{tag}: the layout counts as complete")
        for m in am:
            r = next(r for r in m.regions if r.type == "WINDOW")
            top = r.view2d.region_to_view(0, r.height)[1]
            check(top >= -2, f"{tag}: the Attribute Manager shows its top (view top {top:.1f})")
        print("B4D CM", tag, "areas", sorted((x.type, x.x, x.y, x.width, x.height) for x in win().screen.areas), flush=True)
    return go


def show(tag):
    def go():
        redraw()
        shot("cm_" + tag)
    return go


def dropdowns(space, third):
    def go():
        wm = bpy.context.window_manager
        wm.b4d_cm_space, wm.b4d_cm_third = space, third
        for a in win().screen.areas:
            a.tag_redraw()
    return go


def edit_through_ui():
    """Set a value as a field in the strip would (the panel's own property), and check the object moved."""
    from blenda4d import coord_manager
    ob = bpy.context.view_layer.objects.active
    wm = bpy.context.window_manager
    wm.b4d_cm_space, wm.b4d_cm_third = "WORLD", "SIZE"
    names = coord_manager.columns(ob, wm)
    before = ob.matrix_world.translation.copy()
    v = list(getattr(ob, names[0]))
    v[1] += 100.0
    setattr(ob, names[0], v)
    bpy.context.view_layer.update()
    moved = ob.matrix_world.translation - before
    check(abs(moved.z - 1.0) < 1e-3, f"World Position Y +100 cm raises the object 1 m ({tuple(moved)})")


def reset_from_strip():
    a = strip()[0]
    r = next(r for r in a.regions if r.type == "WINDOW")
    ob = bpy.context.view_layer.objects.active
    with bpy.context.temp_override(window=win(), screen=win().screen, area=a, region=r):
        res = bpy.ops.blenda4d.cm_reset()
    check(res == {"FINISHED"} and ob.location.length < 1e-6, f"Reset from the strip {res} {tuple(ob.location)}")


def press_toggle():
    w = win()
    with bpy.context.temp_override(window=w, screen=w.screen):
        print("B4D CM toggle", bpy.ops.blenda4d.cm_toggle(), flush=True)


def hidden():
    from blenda4d import build, roles
    check(not strip(), "axes button: the Coordinate Manager is hidden")
    am = roles.areas(win().screen, "ATTRIBUTES")
    tl = [t for t in win().screen.areas if t.type == "DOPESHEET_EDITOR"]
    if am and tl:
        check(abs(am[0].y - tl[0].y) <= 3, f"axes button: the Attribute Manager takes the room back (y{am[0].y}, timeline y{tl[0].y})")
    check(build.intact(win().screen), "hidden: the layout still counts as complete (no rebuild)")


def off():
    ns["blenda4d"].switch.set_mode(False)


def after_off():
    from blenda4d import roles
    check(not strip(), "off: no Coordinate Manager")
    check("COORDS" not in roles.ROLE_FLAGS, "off: its role is gone")
    check(not hasattr(bpy.types.Object, "b4d_wpos"), "off: its properties are gone")
    print("B4D CM off: workspaces", [w.name for w in bpy.data.workspaces], flush=True)


def finish():
    print("B4D CM RESULT", "FAIL" if FAILS else "PASS", len(FAILS), FAILS, flush=True)


W = [lambda: None] * 6
done = PLAN.pop()
PLAN += W + [placed("start"), lambda: select("Cube"), show("cube_local_size"),
             dropdowns("LOCAL", "SCALE"), lambda: None, show("cube_local_scale"),
             dropdowns("WORLD", "SIZE"), lambda: None, show("cube_world_size"),
             edit_through_ui, lambda: None, show("cube_moved"),
             reset_from_strip, lambda: None, show("cube_reset"),
             lambda: select("Camera"), dropdowns("LOCAL", "SIZE"), lambda: None, show("camera"),
             lambda: [o.select_set(False) for o in bpy.context.view_layer.objects],
             lambda: setattr(bpy.context.view_layer.objects, "active", None), lambda: None, show("nothing"),
             press_toggle] + W + [hidden, show("hidden"), press_toggle] + W + [placed("shown_again"), show("shown_again"),
             off] + W + [after_off, lambda: shot("cm_off"),
             lambda: ns["blenda4d"].switch.set_mode(True)] + W * 2 + [placed("on_again"), show("on_again"),
             finish, done, lambda: bpy.ops.wm.quit_blender()]
