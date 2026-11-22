# UI run of the icon bar and tools column sizes: once the layout is built, the icon bar must be build.PALETTE_PX tall
# and the tools column build.MODES_PX wide; each one's drawing region and view are printed, and a screenshot of the
# window is saved to check by eye that every button is drawn whole; then the same again with the window full screen.
#   BLENDER_USER_CONFIG=<scratch> B4D_OUT=<scratch> Blender --factory-startup --window-geometry 100 60 1700 1000 \
#       --python tools/tests/tool_sizes_ui.py
# Prints "B4D TS ..." lines, "B4D TS FAIL ..." for every check that does not hold, and quits when done.
import os
import runpy

import bpy

os.environ["B4D_STEPS"] = "wait"
HERE = os.path.dirname(os.path.abspath(__file__))
ns = runpy.run_path(os.path.join(HERE, "..", "try_ui.py"))
PLAN, shot = ns["PLAN"], ns["shot"]
FAILS = []
SLACK = 6


def check(cond, what):
    print("B4D TS", "ok" if cond else "FAIL", what, flush=True)
    if not cond:
        FAILS.append(what)


def sizes(tag):
    def go():
        _sizes(tag)
    return go


def _sizes(tag):
    from blenda4d import build, roles
    w = bpy.context.window_manager.windows[0]
    print("B4D TS", tag, "window", w.width, w.height, "ui_scale", bpy.context.preferences.system.ui_scale, flush=True)
    for role, want, attr in (("PALETTE", build.px(build.PALETTE_PX), "height"), ("MODES", build.px(build.MODES_PX), "width")):
        areas = roles.areas(w.screen, role)
        check(len(areas) == 1, f"{tag} {role}: one area")
        if not areas:
            continue
        a = areas[0]
        have = getattr(a, attr)
        check(abs(have - want) <= SLACK, f"{tag} {role}: {attr} {have} px, planned {want}")
        region = next(r for r in a.regions if r.type == "WINDOW")
        v2d = region.view2d
        x0, y0 = v2d.region_to_view(0, 0)
        x1, y1 = v2d.region_to_view(region.width, region.height)
        print("B4D TS", tag, role, "region", region.width, region.height, "view", round(x0), round(y0), round(x1), round(y1), flush=True)


def show(tag):
    def go():
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
        shot("tool_sizes_" + tag)
    return go


def fullscreen():
    w = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=w, screen=w.screen):
        print("B4D TS fullscreen", bpy.ops.wm.window_fullscreen_toggle(), flush=True)


def finish():
    print("B4D TS RESULT", "FAIL" if FAILS else "PASS", len(FAILS), FAILS, flush=True)


W = [lambda: None] * 6
done = PLAN.pop()
PLAN += W + [sizes("window"), show("window"), fullscreen] + W * 2 + [sizes("fullscreen"), show("fullscreen"),
             finish, done, lambda: bpy.ops.wm.quit_blender()]
