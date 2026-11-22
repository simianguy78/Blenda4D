# UI run of the strip sizes (blenda4d/fit.py): the fixed strips (file tabs, icon bar, tools column, timeline,
# managers column, Object Manager header and size bar) must be their planned size once the layout is built, after the
# window goes full screen (Blender alone would stretch them about 2.3x there) and again after it comes back.
#   BLENDER_USER_CONFIG=<scratch> B4D_OUT=<scratch> Blender --factory-startup --window-geometry 100 60 1700 1000 \
#       --python tools/tests/fit_ui.py
# Prints "B4D FIT ..." lines, "B4D FIT FAIL ..." for every check that does not hold, and quits when done.
import os
import runpy

import bpy

os.environ["B4D_STEPS"] = "wait"
HERE = os.path.dirname(os.path.abspath(__file__))
ns = runpy.run_path(os.path.join(HERE, "..", "try_ui.py"))
PLAN, shot = ns["PLAN"], ns["shot"]
FAILS = []
SLACK = 12                    # px a strip may differ from its plan (area edges and rounding at 2x scale)


def win():
    return bpy.context.window_manager.windows[0]


def check(cond, what):
    print("B4D FIT", "ok" if cond else "FAIL", what, flush=True)
    if not cond:
        FAILS.append(what)


def report(tag):
    from blenda4d import build, fit
    w = win()
    print("B4D FIT", tag, "window", w.width, w.height, "intact", build.intact(w.screen), "busy", build.busy(),
          "ui_scale", bpy.context.preferences.system.ui_scale, flush=True)
    now = fit.sizes(w)
    for what, size, _edge in fit.plan(w):
        print("B4D FIT", tag, what, now.get(what, "not in this layout"), "planned", size, flush=True)
    return now


def compare(tag):
    def go():
        from blenda4d import build, fit
        now = report(tag)
        check(build.intact(win().screen) and not build.busy(), f"{tag}: layout whole and settled")
        check(len(now) >= 5, f"{tag}: {len(now)} strips measured")
        for what, size, _edge in fit.plan(win()):
            if what in now:
                check(abs(now[what] - size) <= SLACK, f"{tag}: {what} is {now[what]} px, planned {size}")
    return go


def fullscreen():
    w = win()
    with bpy.context.temp_override(window=w, screen=w.screen):
        print("B4D FIT fullscreen", bpy.ops.wm.window_fullscreen_toggle(), flush=True)


def show(tag):
    def go():
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
        shot("fit_" + tag)
    return go


def finish():
    print("B4D FIT RESULT", "FAIL" if FAILS else "PASS", len(FAILS), FAILS, flush=True)


W = [lambda: None] * 6
done = PLAN.pop()
PLAN += W + [compare("built"), show("built"),
             fullscreen] + W * 4 + [compare("fullscreen"), show("fullscreen"),
             fullscreen] + W * 4 + [compare("back"), show("back"),
             finish, done, lambda: bpy.ops.wm.quit_blender()]
