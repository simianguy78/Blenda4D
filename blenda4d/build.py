# SPDX-License-Identifier: GPL-3.0-or-later
"""Build Blenda's Standard layout on the live screen at exact pixel sizes.

Areas are made with area_split / area_close (which work without window focus), one step per redraw, because an
area's size only updates on the next event loop:
  document tabs (full width, top) | managers column (right, full height: Objects over Attributes)
  command palette (top, left of the managers) | modes column (left) | create column (left of the managers)
  timeline (bottom, under the viewport) | Coordinate Manager (under Attributes, level with the timeline) | optional Material Manager column (between viewport and create column)
  | optional Asset Browser column (left of the viewport)."""
import bpy

from . import roles

DOC_TABS_PX = 30
PALETTE_PX = 40               # one row of icon buttons (bars.PALETTE_SCALE) and the panel's margins
TIMELINE_PX = 82                # with the header: tall enough for the Coordinate Manager beside it (header row + X, Y, Z rows)
TOOL_ZOOM = {"CREATE": 8}     # zoom steps (as Ctrl+scroll): larger icons, boxes stay square
MODES_PX = 55                 # one column of square buttons (bars.MODES_SCALE) and the panel's margins: wide enough
                              # that the tool icons, which Blender draws about 5 px right of centre, stay inside
CREATE_PX = 70
STRIP_ZOOM = 0               # the create column is drawn at its own size (strip.py): the strip needs no zoom
MANAGERS_PX = 330
MATERIALS_PX = 230
MM_BAR_PX = 30
ASSETS_PX = 420
EDGE = 3

_active = [0]


def busy():
    return _active[0] > 0


def run_steps(gen, done=None):
    """Run a generator one step per redraw; a step that fails while the window is not ready is retried."""
    state = {"retries": 20}
    _active[0] += 1

    def tick():
        try:
            next(gen)
            return 0.0                                   # the next step as soon as Blender has laid out the last
        except StopIteration:
            _active[0] -= 1
            if done:
                done()
            return None
        except RuntimeError as ex:
            state["retries"] -= 1
            if state["retries"] > 0:
                return 0.25
            _active[0] -= 1
            print("Blenda 4D: layout step gave up:", ex)
            return None
        except Exception:
            _active[0] -= 1
            raise
    bpy.app.timers.register(tick)


def _scale():
    return bpy.context.preferences.system.ui_scale


def px(v):
    return int(round(v * _scale()))


def _region(area, kind):
    return next((r for r in area.regions if r.type == kind), None)


def _ov(window, area, region="WINDOW"):
    return bpy.context.temp_override(window=window, screen=window.screen, area=area, region=_region(area, region))


def biggest_view(screen):
    views = [a for a in screen.areas if a.type == "VIEW_3D"]
    if not views:
        big = max(screen.areas, key=lambda a: a.width * a.height)
        big.type = "VIEW_3D"
        views = [big]
    return max(views, key=lambda a: a.width * a.height)


def split(window, area, direction, size_px, side):
    size = area.height if direction == "HORIZONTAL" else area.width
    frac = size_px / max(size, 1)
    factor = {"TOP": 1 - frac, "BOTTOM": frac, "LEFT": frac, "RIGHT": 1 - frac}[side]
    before = {a.as_pointer() for a in window.screen.areas}
    with _ov(window, area):
        bpy.ops.screen.area_split(direction=direction, factor=factor)
    new = next(a for a in window.screen.areas if a.as_pointer() not in before)
    yield
    pair = (new, area)
    if direction == "HORIZONTAL":
        top, bottom = sorted(pair, key=lambda a: -a.y)
        return top if side == "TOP" else bottom
    left, right = sorted(pair, key=lambda a: a.x)
    return left if side == "LEFT" else right


def make_role(window, area, name):
    area.type = "PROPERTIES"
    yield
    for _ in range(20):
        if roles.set_role(area, name):
            break
        area.tag_redraw()
        yield
    roles.hide_nav(area)
    yield
    if name in TOOL_ZOOM:
        _zoom(window, area, TOOL_ZOOM[name])
        yield


def _zoom(window, area, n):
    """Blender's own area zoom (as Ctrl+scroll does): buttons and icons grow together."""
    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    if region is None:
        return
    try:
        with bpy.context.temp_override(window=window, screen=window.screen, area=area, region=region):
            for _ in range(n):
                bpy.ops.view2d.zoom_in()
    except RuntimeError as ex:
        print("Blenda 4D: could not zoom", area.type, ex)


def split_now(window, area, direction, size_px, side, size=None):
    """Split off a strip and return it at once: Blender makes the smaller part the new area, which is the strip.
    `size` stands in for the area's size when Blender has not laid the area out yet."""
    size = size or (area.height if direction == "HORIZONTAL" else area.width)
    frac = size_px / max(size, 1)
    factor = {"TOP": 1 - frac, "BOTTOM": frac, "LEFT": frac, "RIGHT": 1 - frac}[side]
    before = {a.as_pointer() for a in window.screen.areas}
    with _ov(window, area):
        bpy.ops.screen.area_split(direction=direction, factor=factor)
    return next(a for a in window.screen.areas if a.as_pointer() not in before)


def role_now(area, name):
    """The area becomes its role's editor in the same step it appears (no frame shows a stray editor)."""
    area.type = "PROPERTIES"
    roles.set_role(area, name)
    try:
        roles.hide_nav(area)
    except RuntimeError:
        pass


def settle(window, *pairs):
    """After the frame: make sure each area has its role and no tab column (set at once where Blender allowed)."""
    for area, name in pairs:
        for _ in range(20):
            if roles.set_role(area, name):
                break
            yield
        roles.hide_nav(area, window)


def _add_column(window, width_px, side, main, bar):
    """A column beside the viewport with its bottom strip, each one its final editor from the frame it appears in."""
    view = biggest_view(window.screen)
    col = split_now(window, view, "VERTICAL", px(width_px) + EDGE, side)
    role_now(col, main)
    yield                                                  # Blender lays the column out before it can be split
    strip = split_now(window, col, "HORIZONTAL", px(MM_BAR_PX) + EDGE, "BOTTOM")
    role_now(strip, bar)
    yield
    yield from settle(window, (col, main), (strip, bar))


def add_assets(window):
    """The Asset Browser column, left of the viewport, with its bottom strip."""
    yield from _add_column(window, ASSETS_PX, "LEFT", "ASSETS", "AB_BAR")


def add_materials(window):
    """The Material Manager column, right of the viewport, with its bottom strip."""
    yield from _add_column(window, MATERIALS_PX, "RIGHT", "MATERIALS", "MM_BAR")


COLUMNS = {"MATERIALS": (add_materials, "MM_BAR"), "ASSETS": (add_assets, "AB_BAR")}
CORE = ("DOC_TABS", "PALETTE", "MODES", "OBJECTS", "ATTRIBUTES", "OM_BAR")


_coords_shown = [True]       # used when the add-on's preferences cannot be read (run from a checkout in tests)


def coords_shown():
    try:
        from . import settings
        return settings.get().coords
    except (KeyError, AttributeError):
        return _coords_shown[0]


def set_coords_shown(on):
    _coords_shown[0] = on
    try:
        from . import settings
        settings.get().coords = on
    except (KeyError, AttributeError):
        pass


def coords_strip():
    """The Coordinate Manager strip is part of the layout while its module (coord_manager.py) is loaded and the
    timeline's axes button has not hidden it."""
    return "COORDS" in roles.ROLE_FLAGS and coords_shown()


def to_top(window, area):
    """Scroll an area's panel back to its top (a split that made it shorter leaves it scrolled part way down)."""
    try:
        with _ov(window, area):
            bpy.ops.view2d.scroll_up(deltay=100000)
    except RuntimeError:
        pass


def coords_steps(window, on):
    """Show or hide the Coordinate Manager under the Attribute Manager, leaving every other area where it is."""
    screen = window.screen
    if on:
        attrs = roles.areas(screen, "ATTRIBUTES")
        if attrs and not roles.areas(screen, "COORDS"):
            tl = next((a for a in screen.areas if a.type == "DOPESHEET_EDITOR"), None)
            height = tl.height if tl is not None else px(TIMELINE_PX) + 26
            cm = yield from split(window, attrs[0], "HORIZONTAL", height + EDGE, "BOTTOM")
            yield from make_role(window, cm, "COORDS")
            for a in roles.areas(screen, "ATTRIBUTES"):
                to_top(window, a)
    else:
        for a in roles.areas(screen, "COORDS"):           # its room goes back to the Attribute Manager above it
            with _ov(window, a):
                bpy.ops.screen.area_close()
        yield
    for a in screen.areas:
        a.tag_redraw()


_coords_shown = [True]       # used when the add-on's preferences cannot be read (run from a checkout in tests)


def coords_shown():
    try:
        from . import settings
        return settings.get().coords
    except (KeyError, AttributeError):
        return _coords_shown[0]


def set_coords_shown(on):
    _coords_shown[0] = on
    try:
        from . import settings
        settings.get().coords = on
    except (KeyError, AttributeError):
        pass


def coords_strip():
    """The Coordinate Manager strip is part of the layout while its module (coord_manager.py) is loaded and the
    timeline's axes button has not hidden it."""
    return "COORDS" in roles.ROLE_FLAGS and coords_shown()


def to_top(window, area):
    """Scroll an area's panel back to its top (a split that made it shorter leaves it scrolled part way down)."""
    try:
        with _ov(window, area):
            bpy.ops.view2d.scroll_up(deltay=100000)
    except RuntimeError:
        pass


def coords_steps(window, on):
    """Show or hide the Coordinate Manager under the Attribute Manager, leaving every other area where it is."""
    screen = window.screen
    if on:
        attrs = roles.areas(screen, "ATTRIBUTES")
        if attrs and not roles.areas(screen, "COORDS"):
            tl = next((a for a in screen.areas if a.type == "DOPESHEET_EDITOR"), None)
            height = tl.height if tl is not None else px(TIMELINE_PX) + 26
            cm = yield from split(window, attrs[0], "HORIZONTAL", height + EDGE, "BOTTOM")
            yield from make_role(window, cm, "COORDS")
            for a in roles.areas(screen, "ATTRIBUTES"):
                to_top(window, a)
    else:
        for a in roles.areas(screen, "COORDS"):           # its room goes back to the Attribute Manager above it
            with _ov(window, a):
                bpy.ops.screen.area_close()
        yield
    for a in screen.areas:
        a.tag_redraw()


def intact(screen):
    """The Standard layout is all there (each strip once, a viewport and the timeline): nothing to rebuild."""
    if any(len(roles.areas(screen, r)) != 1 for r in CORE):
        return False
    if "COORDS" in roles.ROLE_FLAGS and len(roles.areas(screen, "COORDS")) != (1 if coords_strip() else 0):
        return False
    if not any(a.type == "VIEW_3D" for a in screen.areas) or not any(a.type == "DOPESHEET_EDITOR" for a in screen.areas):
        return False
    for main, (_add, bar) in COLUMNS.items():
        if len(roles.areas(screen, main)) != len(roles.areas(screen, bar)) or len(roles.areas(screen, main)) > 1:
            return False
    return True


def column_steps(window, name, on):
    """Show or hide one optional column, leaving every other area where it is."""
    screen = window.screen
    add, bar = COLUMNS[name]
    if on:
        yield from add(window)
    else:
        for role in (bar, name):                           # the strip into its column, the column into the viewport,
            for a in roles.areas(screen, role):            # in one step: no frame shows the column without its strip
                with _ov(window, a):
                    bpy.ops.screen.area_close()
        yield
    if not intact(screen):                                 # the change did not land as planned: build it all
        yield from steps(window, materials=bool(roles.areas(screen, "MATERIALS")) if name != "MATERIALS" else on,
                         assets=bool(roles.areas(screen, "ASSETS")) if name != "ASSETS" else on)
    for a in screen.areas:
        a.tag_redraw()


def steps(window, materials=False, assets=False):
    screen = window.screen
    from . import render_settings
    render_settings.show_view(screen)                     # Render Settings in the viewport's place: viewport back first
    # 1. everything back into one viewport
    for _ in range(60):
        extra = [a for a in screen.areas if a.type != "VIEW_3D"] + \
                [a for a in screen.areas if a.type == "VIEW_3D" and a != biggest_view(screen)]
        if not extra:
            break
        # a window that shrank leaves the tools column very narrow, and Blender then refuses to close a strip that
        # runs across it ("A narrow vertical area interferes"): close the narrow areas first, and when one close is
        # refused, try the next area instead of the same one again
        extra.sort(key=lambda a: a.width >= px(MODES_PX))
        count = len(screen.areas)
        for a in extra:
            try:
                with _ov(window, a):
                    bpy.ops.screen.area_close()
            except RuntimeError:
                continue
            if len(screen.areas) < count:
                break
        else:
            raise RuntimeError("no area could be closed")
        yield
    view = biggest_view(screen)
    hdr = _region(view, "HEADER").height if _region(view, "HEADER") else 26
    # 2. strips at exact sizes, full-width ones first
    tabs = yield from split(window, view, "HORIZONTAL", px(DOC_TABS_PX) + EDGE, "TOP")
    yield from make_role(window, tabs, "DOC_TABS")
    managers = yield from split(window, biggest_view(screen), "VERTICAL", px(MANAGERS_PX) + EDGE, "RIGHT")
    yield from make_role(window, managers, "OBJECTS")
    palette = yield from split(window, biggest_view(screen), "HORIZONTAL", px(PALETTE_PX) + EDGE, "TOP")
    yield from make_role(window, palette, "PALETTE")
    modes = yield from split(window, biggest_view(screen), "VERTICAL", px(MODES_PX) + EDGE, "LEFT")
    yield from make_role(window, modes, "MODES")
    # the create column is drawn in the viewport's own toolbar strip (bars.BLENDA4D_PT_view_tools), moved to the
    # viewport's right edge: the strip keeps its width when the window is resized; a separate area would stretch
    timeline = yield from split(window, biggest_view(screen), "HORIZONTAL", px(TIMELINE_PX) + hdr + EDGE, "BOTTOM")
    timeline.type = "DOPESHEET_EDITOR"
    timeline.ui_type = "TIMELINE"
    yield
    if assets:
        yield from add_assets(window)
    if materials:
        yield from add_materials(window)
    attributes = yield from split(window, managers, "HORIZONTAL", round(managers.height * 0.56), "BOTTOM")
    yield from make_role(window, attributes, "ATTRIBUTES")
    objs = sorted(roles.areas(screen, "OBJECTS"), key=lambda a: a.y)
    if len(objs) > 1:                                      # the split can hand back the other half
        yield from make_role(window, objs[0], "ATTRIBUTES")
    attrs = roles.areas(screen, "ATTRIBUTES")
    if coords_strip() and attrs:                           # the Coordinate Manager: under the Attribute Manager, as
        cm = yield from split(window, attrs[0], "HORIZONTAL", px(TIMELINE_PX) + hdr + EDGE, "BOTTOM")   # tall as
        yield from make_role(window, cm, "COORDS")         # the timeline, so the two line up along the bottom
        for a in roles.areas(screen, "ATTRIBUTES"):
            to_top(window, a)
    objs = sorted(roles.areas(screen, "OBJECTS"), key=lambda a: a.y)
    if objs:                                               # the Object Manager's bottom strip: its Size slider
        om_bar = yield from split(window, objs[-1], "HORIZONTAL", px(MM_BAR_PX) + EDGE, "BOTTOM")
        yield from make_role(window, om_bar, "OM_BAR")
        objs = sorted(roles.areas(screen, "OBJECTS") + roles.areas(screen, "OM_BAR"), key=lambda a: a.y)
        if len(roles.areas(screen, "OBJECTS")) == 2:       # the split handed back the other half
            yield from make_role(window, min(roles.areas(screen, "OBJECTS"), key=lambda a: a.y), "OM_BAR")
    # 3. the viewport and timeline lose Blender's own chrome; the toolbar strip moves to the viewport's right edge
    for a in screen.areas:
        if a.type == "VIEW_3D":
            dress_view(a)
            tools = _region(a, "TOOLS")
            if tools is not None and tools.alignment != "RIGHT":
                try:
                    with _ov(window, a, "TOOLS"):
                        bpy.ops.screen.region_flip()
                except RuntimeError as ex:
                    print("Blenda 4D: could not move the toolbar strip", ex)
                yield
            if tools is not None:                          # start the strip's view fresh after the move, then zoom
                try:                                       # it so its buttons are as big as the tools column's
                    with _ov(window, a, "TOOLS"):
                        bpy.ops.view2d.reset()
                        for _ in range(STRIP_ZOOM):
                            bpy.ops.view2d.zoom_in()
                except RuntimeError:
                    pass
                yield
        elif a.type == "DOPESHEET_EDITOR":
            st = a.spaces.active
            st.show_region_channels = False
            st.show_region_ui = False
    for a in screen.areas:
        a.tag_redraw()


def dress_view(area):
    v3d = area.spaces.active
    # four views: the create column is one separate column beside them (quadview), not a strip in every view
    quad = sum(a.type == "VIEW_3D" for a in area.id_data.areas) > 1
    for attr, want in (("show_region_ui", False), ("show_region_toolbar", not quad), ("show_region_header", True),
                       ("show_region_tool_header", True), ("show_region_hud", False)):
        if getattr(v3d, attr) != want:
            setattr(v3d, attr, want)
    v3d.show_gizmo_navigate = False
    v3d.lock_camera = True          # looking through a camera, orbit / pan / zoom move the camera itself
    v3d.overlay.show_text = False
    v3d.overlay.show_stats = False


def toggle(window, name, on):
    """Show or hide an optional column (Material Manager, Asset Browser): only that column changes."""
    run_steps(column_steps(window, name, on))


def rebuild(window, done=None, force=False):
    """Build the Standard layout; a layout that is already all there is only tidied (no area moves)."""
    if not force and intact(window.screen):
        for a in window.screen.areas:
            if a.type == "VIEW_3D":
                dress_view(a)
        if done:
            done()
        return
    run_steps(steps(window, materials=bool(roles.areas(window.screen, "MATERIALS")),
                    assets=bool(roles.areas(window.screen, "ASSETS"))), done)
