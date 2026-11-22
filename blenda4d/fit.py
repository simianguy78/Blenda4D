# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep Blenda's fixed strips at their built sizes.

Blender stretches every area in proportion when a window changes size, so a strip built 30 px tall in a small window
grows with it (and a file saved in one window opens stretched in another). Blender only lets an edge be moved by hand
(its edge-move operator refuses to run from a timer), so once a Blenda window has kept a new size for a moment and a
strip has grown or shrunk with it, the layout is built again at its exact sizes, with the same steps that built it
first. Edges the user drags while the window keeps its size are left alone."""
import time

import bpy

from . import build, roles

INTERVAL = 0.5
TOLERANCE = 3                 # pixels a strip may be off before it is moved


def _timeline_height(window):
    view = next((a for a in window.screen.areas if a.type == "VIEW_3D"), None)
    hdr = 26
    if view is not None:
        r = next((r for r in view.regions if r.type == "HEADER"), None)
        if r is not None:
            hdr = r.height
    return build.px(build.TIMELINE_PX) + hdr


def plan(window):
    """(what, size in px, the strip's moving edge): strips that span the window first, then columns, then the rest."""
    p = build.px
    tl = _timeline_height(window)
    return [
        ("DOC_TABS", p(build.DOC_TABS_PX), "BOTTOM"),
        ("OBJECTS", p(build.MANAGERS_PX), "LEFT"),          # the managers column's width
        ("ASSETS", p(build.ASSETS_PX), "RIGHT"),
        ("MATERIALS", p(build.MATERIALS_PX), "LEFT"),
        ("PALETTE", p(build.PALETTE_PX), "BOTTOM"),
        ("MODES", p(build.MODES_PX), "RIGHT"),
        ("TIMELINE", tl, "TOP"),
        ("OM_HEAD", p(build.OM_HEAD_PX), "BOTTOM"),
        ("OM_BAR", p(build.MM_BAR_PX), "TOP"),
        ("MM_BAR", p(build.MM_BAR_PX), "TOP"),
        ("AB_BAR", p(build.MM_BAR_PX), "TOP"),
        ("COORDS", tl, "TOP"),
    ]


def _area(screen, what):
    if what == "TIMELINE":
        return next((a for a in screen.areas if a.type == "DOPESHEET_EDITOR"), None)
    found = roles.areas(screen, what) if what in roles.ROLE_FLAGS else []
    return found[0] if len(found) == 1 else None


def sizes(window):
    """{strip: its size in px along the axis it is fixed in} for the strips this layout has."""
    out = {}
    for what, _size, edge in plan(window):
        area = _area(window.screen, what)
        if area is not None:
            out[what] = area.height if edge in ("TOP", "BOTTOM") else area.width
    return out


def stretched(old, new):
    """Strips whose size changed by more than TOLERANCE."""
    return [k for k in old if k in new and abs(new[k] - old[k]) > TOLERANCE]


def fit(window):
    """Build the layout again at its exact sizes. Returns True when a build was started."""
    if build.busy() or not build.intact(window.screen):
        return False
    build.rebuild(window, force=True)
    return True


def _blenda_windows():
    from . import switch
    for w in bpy.context.window_manager.windows:
        ws = w.workspace
        if ws is not None and ws.name == switch.WORKSPACE:
            yield w


SETTLE = 1.0                  # seconds a window must keep its size before its strips are put back
_state = {}                   # window pointer -> {"size", "since", "base"}: size now, when it last changed, strip
#                               sizes measured while the window last kept its size


def _tick():
    """Dragging a window edge changes its size many times a second: nothing is moved until the size has been the same
    for SETTLE seconds, and then the layout is built again once, only if a strip is off the size it had before."""
    if build.busy():
        return INTERVAL
    try:
        now_t = time.monotonic()
        for w in _blenda_windows():
            key = w.as_pointer()
            size = (w.width, w.height)
            st = _state.setdefault(key, {"size": size, "since": now_t, "base": None})
            if not build.intact(w.screen):
                st.update(size=size, since=now_t, base=None)  # being built or changed: measure again once whole
                continue
            now = sizes(w)
            if st["size"] != size:
                st["size"], st["since"] = size, now_t         # still being resized (or just was)
                continue
            if now_t - st["since"] < SETTLE:
                continue
            if st["base"] is not None and stretched(st["base"], now):
                st["base"] = None                             # measured again after the build
                fit(w)
            else:
                st["base"] = now                              # settled and as before: follow edges the user dragged
    except (ReferenceError, RuntimeError, AttributeError) as ex:
        print("Blenda 4D: strip sizes", ex)
    return INTERVAL


def register():
    _state.clear()
    if not bpy.app.background and not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=INTERVAL, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    _state.clear()
