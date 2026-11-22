# SPDX-License-Identifier: GPL-3.0-or-later
"""The managers: Object Manager, Attribute Manager (follows the selection), Material Manager, Asset Browser,
Variations. Each is a panel drawn with Blender's UI elements in its own role area."""
import math
import time

import bpy

from . import matman, menus, roles

TYPE_ICON = {"MESH": "MESH_DATA", "CURVE": "CURVE_BEZCURVE", "SURFACE": "OUTLINER_OB_SURFACE", "META": "OUTLINER_OB_META",
             "FONT": "OUTLINER_OB_FONT", "EMPTY": "OUTLINER_OB_EMPTY", "LIGHT": "LIGHT_AREA", "CAMERA": "OUTLINER_OB_CAMERA",
             "ARMATURE": "OUTLINER_OB_ARMATURE", "LATTICE": "OUTLINER_OB_LATTICE", "VOLUME": "OUTLINER_OB_VOLUME",
             "POINTCLOUD": "OUTLINER_OB_POINTCLOUD", "CURVES": "OUTLINER_OB_CURVES", "GREASEPENCIL": "OUTLINER_OB_GREASEPENCIL"}
TYPE_LABEL = {"MESH": "Polygon Object", "CURVE": "Spline", "FONT": "Text Spline Object", "EMPTY": "Null", "LIGHT": "Light Object",
              "CAMERA": "Camera Object", "ARMATURE": "Joint", "LATTICE": "FFD", "VOLUME": "Volume", "SURFACE": "Surface",
              "META": "Metaball", "POINTCLOUD": "Point Cloud", "CURVES": "Hair", "GREASEPENCIL": "Sketch"}


PRIM_ICON = {"cube": "MESH_CUBE", "sphere": "MESH_UVSPHERE", "cylinder": "MESH_CYLINDER", "plane": "MESH_PLANE", "disc": "MESH_CIRCLE",
             "cone": "MESH_CONE", "torus": "MESH_TORUS", "pyramid": "MESH_CONE", "tube": "MESH_CYLINDER", "oiltank": "MESH_CAPSULE",
             "capsule": "MESH_CAPSULE", "platonic": "MESH_ICOSPHERE", "relief": "IMAGE_DATA", "landscape": "RNDCURVE",
             "figure": "ARMATURE_DATA", "bezier": "SURFACE_NSURFACE", "cyc": "MESH_GRID"}


def type_icon(ob):
    from . import kinds
    if kinds.kind_of(ob):
        return kinds.KINDS[kinds.kind_of(ob)]["icon"]
    k = ob.get("b4d_type")
    if k in PRIM_ICON:
        return PRIM_ICON[k]
    if ob.type == "LIGHT":
        return {"POINT": "LIGHT_POINT", "SUN": "LIGHT_SUN", "SPOT": "LIGHT_SPOT", "AREA": "LIGHT_AREA"}.get(ob.data.type, "LIGHT")
    return TYPE_ICON.get(ob.type, "OBJECT_DATA")


def type_icon_kw(ob):
    """Layout keywords for an object's row icon: its type icon tinted by the create-column group (icons.py), or
    Blender's plain icon."""
    from . import icons
    return icons.object_icon(ob, type_icon(ob))


# --- manager menus ------------------------------------------------------------------------------------------------
I = menus.item
OM_MENUS = [menus.simple_menu("File", [I("Merge Objects...", "wm.append", "APPEND_BLEND"), I("Save Selected Objects As...")], "om"),
            menus.simple_menu("Edit", [I("Undo", "ed.undo"), I("Redo", "ed.redo"), menus.SEP, I("Rename...", "blenda4d.om_rename"), I("Copy", "view3d.copybuffer"),
                                        I("Paste", "view3d.pastebuffer"), I("Delete", "object.delete"), menus.SEP,
                                        I("Select All", "object.select_all", action="SELECT"), I("Deselect All", "object.select_all", action="DESELECT")], "om"),
            menus.simple_menu("View", [I("Expand All", "blenda4d.om_expand", open=True), I("Collapse All", "blenda4d.om_expand", open=False)], "om"),
            menus.simple_menu("Object", [I("Group Objects", "blenda4d.group", "OUTLINER_OB_EMPTY"),
                                          I("Make Editable", "blenda4d.make_editable", "MESH_DATA"),
                                          I("Duplicate", "object.duplicate_move", "DUPLICATE")], "om"),
            menus.simple_menu("Tags", [I("Material", "blenda4d.mat_tag", "MATERIAL"), I("Smoothing", "object.shade_auto_smooth", "SHADING_SMOOTH")], "om"),
            menus.simple_menu("Bookmarks", [I("Add Bookmark")], "om")]
AM_MENUS = [menus.simple_menu("Mode", [I("Object"), I("Tag"), I("Material")], "am"),
            menus.simple_menu("Edit", [I("Copy"), I("Paste")], "am"),
            menus.simple_menu("User Data", [I("Add User Data...")], "am")]
MM_MENUS = [menus.simple_menu(n, [I("New Material", "blenda4d.new_material", "ADD")] if n == "Create" else [I("…")], "mm")
            for n in ("Create", "Edit", "View", "Select", "Material")]


MANAGER_TIPS = {"Objects": "Object Manager: every object in the scene, how they are grouped, and their tags",
                "Attributes": "Attribute Manager: the settings of what is selected",
                "Materials": "Material Manager: the scene's materials",
                "Asset Browser": "Asset Browser: models, materials and more to add to the scene"}


def manager_title(layout, title, right_tabs=None):
    """The manager's own tab strip: its name (and the other managers grouped with it)."""
    row = layout.row(align=True)
    row.alignment = "LEFT"
    if right_tabs:
        wm = bpy.context.window_manager
        row.prop(wm, right_tabs, expand=True)
    else:
        row.operator("blenda4d.title", text=title, depress=True).what = MANAGER_TIPS.get(title, title)


# --- Object Manager -------------------------------------------------------------------------------------------------
CAMERA_PAGES = {}            # tab -> fn(col, ob): the camera's own pages (cameras.py)
FONT_PAGE = []               # [fn(col, ob)]: the text object's Object page (texts.py)
CAMERA_TABS = []             # its extra tabs after Basic, Coord., Object
CAMERA_TITLES = {}
AM_SUBJECTS = {}             # "TAG" -> fn(layout, context, ob) -> True when it drew the page (wm.b4d_am_subject "TAG:...")
OM_TAG_BUTTON = []           # [fn(layout, ob, slot_index, material)]: draws a material swatch as a clickable tag
_clicks = ["", 0.0]          # last Object Manager click: row name, time (two on one row = rename)
_renamed = [0.0]


class BLENDA4D_OT_om_select(bpy.types.Operator):
    bl_idname = "blenda4d.om_select"
    bl_label = "Select"
    bl_description = "Select the object (Shift adds to the selection); a click below the list deselects all"
    bl_options = {"UNDO"}
    name: bpy.props.StringProperty(options={"SKIP_SAVE"})
    extend: bpy.props.BoolProperty(options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return roles.role(context.area) == "OBJECTS"

    def invoke(self, context, event):
        self.extend = event.shift or event.ctrl or event.oskey
        if not self.name:
            ob = object_at(context, event)
            now = time.monotonic()
            last, _clicks[:] = list(_clicks), [ob.name if ob else "", now]
            if (ob is not None and not self.extend and last[0] == ob.name
                    and now - last[1] < context.preferences.inputs.mouse_double_click_time / 1000
                    and now - _renamed[0] > 0.6):
                _clicks[0] = ""
                return bpy.ops.blenda4d.om_rename("INVOKE_DEFAULT", name=ob.name)
            if ob is None:
                if self.extend:
                    return {"CANCELLED"}
                context.window_manager.b4d_am_subject = ""
                for o in context.view_layer.objects:
                    o.select_set(False)
                return {"FINISHED"}
            self.name = ob.name
        return self.execute(context)

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is None:
            return {"CANCELLED"}
        context.window_manager.b4d_am_subject = ""         # a click on the object shows the object again, not its tag
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if not self.extend:
            for o in context.view_layer.objects:
                o.select_set(False)
        try:
            ob.select_set(not (self.extend and ob.select_get()))
        except RuntimeError:
            return {"CANCELLED"}
        context.view_layer.objects.active = ob
        return {"FINISHED"}


class BLENDA4D_OT_om_delete(bpy.types.Operator):
    bl_idname = "blenda4d.om_delete"
    bl_label = "Delete"
    bl_description = "Delete the selected objects"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return roles.role(context.area) == "OBJECTS" and any(o.select_get() for o in context.view_layer.objects)

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        context.window_manager.b4d_am_subject = ""
        return bpy.ops.object.delete(confirm=False)


class BLENDA4D_OT_om_fold(bpy.types.Operator):
    bl_idname = "blenda4d.om_fold"
    bl_label = "Fold"
    bl_description = "Show or hide the objects under this one"
    name: bpy.props.StringProperty()

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob:
            ob.b4d_om_closed = not ob.b4d_om_closed
        return {"FINISHED"}


class BLENDA4D_OT_om_expand(bpy.types.Operator):
    bl_idname = "blenda4d.om_expand"
    bl_label = "Expand"
    bl_description = "Open or close every object that has objects under it"
    open: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        for ob in context.scene.objects:
            ob.b4d_om_closed = not self.open
        return {"FINISHED"}


class BLENDA4D_OT_group(bpy.types.Operator):
    bl_idname = "blenda4d.group"
    bl_label = "Group Objects"
    bl_description = "Put the selected objects under a new Null"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sel = list(context.selected_objects)
        if not sel:
            return {"CANCELLED"}
        null = bpy.data.objects.new("Null", None)
        context.collection.objects.link(null)
        for ob in sel:
            mw = ob.matrix_world.copy()
            ob.parent = null
            ob.matrix_parent_inverse.identity()
            ob.matrix_world = mw
        return {"FINISHED"}


TOP_LEVEL = "\x00top"
ROWS_TOP_APART = 0.35        # kept for layouts that still have a separate head strip
ROWS_TOP_UNITS = 2.88        # where the first object row starts, in row heights below the top of the panel area (measured
#                               on Blender 5.2, Windows, 2x, Size 0/50/100, one panel with the tab and menu row: icon centres sit at 2.88 + i + 0.5)
STRIPE = (0.02, 0.02, 0.02, 1.0)      # added to every other Object Manager row: +5 grey levels, as in the original (Joseph, Nov 19)


def visible_rows(context):
    """The Object Manager's rows in drawing order: (object, depth). Folded objects hide their children; the search
    keeps an object when it or anything under it matches."""
    needle = context.window_manager.b4d_om_search.lower()
    out = []

    def walk(ob, depth):
        if needle and needle not in ob.name.lower() and not any(needle in c.name.lower() for c in ob.children_recursive):
            return
        out.append((ob, depth))
        if ob.children and not ob.b4d_om_closed:
            for c in sorted(ob.children, key=lambda c: c.name):
                walk(c, depth + 1)
    for ob in context.scene.objects:
        if ob.parent is None:
            walk(ob, 0)
    return out


def head_apart(screen):
    """The Object Manager's title, menus and tools are drawn at the top of its own panel (one panel, not two)."""
    return False


def rows_top(screen=None):
    """Where the first object row starts, in row heights below the top of the Object Manager's panel area."""
    screen = screen or bpy.context.window.screen
    return ROWS_TOP_APART if head_apart(screen) else ROWS_TOP_UNITS


def row_height():
    s = bpy.context.preferences.system
    # Blender's own row height (U.widget_unit): C rounding, half away from zero. Python's round() rounds halves to even,
    # so at scales where 18 * scale ends in .5 (e.g. 125% on Windows) the rows came out a pixel short and drifted (#4).
    return int(math.floor(18 * s.ui_scale + 0.5) + 2 * s.pixel_size)


def row_at(context, region, mouse_y):
    """Index of the Object Manager row under a window y (len(rows) or more = below the last row, -1 = above)."""
    y = region.view2d.region_to_view(0, mouse_y - region.y)[1]
    h = row_height()
    return int((-y - rows_top() * h) // h)


def object_at(context, event):
    """The object on the Object Manager row under the mouse, or None."""
    if roles.role(context.area) != "OBJECTS" or context.region is None or context.region.type != "WINDOW":
        return None
    rows = visible_rows(context)
    i = row_at(context, context.region, event.mouse_y)
    return rows[i][0] if 0 <= i < len(rows) else None


def _is_under(ob, other):
    p = other
    while p is not None:
        if p == ob:
            return True
        p = p.parent
    return False


def reparent(objs, target):
    """Put objs under target (None = top level), keeping where they are in the world."""
    done = 0
    for ob in objs:
        if target is not None and (ob == target or _is_under(ob, target)):
            continue
        mw = ob.matrix_world.copy()
        ob.parent = target
        ob.matrix_parent_inverse.identity()        # no hidden parent inverse: the local values are the real ones
        ob.matrix_world = mw
        done += 1
    return done


class BLENDA4D_OT_om_drag(bpy.types.Operator):
    bl_idname = "blenda4d.om_drag"
    bl_label = "Drag in the Object Manager"
    bl_description = "Drag objects onto another object to put them under it; drop below the list for the top level"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return roles.role(context.area) == "OBJECTS"

    def _target(self, context, event):
        i = row_at(context, self.region, event.mouse_y)
        if i >= len(self.rows):
            return TOP_LEVEL
        if i < 0:
            return ""
        ob = self.rows[i][0]
        return "" if ob in self.objs or any(_is_under(o, ob) for o in self.objs) else ob.name

    def invoke(self, context, event):
        self.region = context.region
        self.rows = visible_rows(context)
        i = row_at(context, self.region, event.mouse_prev_press_y)
        if not 0 <= i < len(self.rows):
            return {"PASS_THROUGH"}
        src = self.rows[i][0]
        self.objs = [src] + ([o for o in context.selected_objects if o != src] if src.select_get() else [])
        context.window_manager.b4d_om_drop = ""
        context.window.cursor_modal_set("HAND")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        context.window_manager.b4d_om_drop = ""
        context.window.cursor_modal_restore()
        self.region.tag_redraw()

    def modal(self, context, event):
        wm = context.window_manager
        if event.type in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            t = self._target(context, event)
            if t != wm.b4d_om_drop:
                wm.b4d_om_drop = t
                self.region.tag_redraw()
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            t = self._target(context, event)
            self._end(context)
            if not t:
                return {"CANCELLED"}
            n = reparent(self.objs, None if t == TOP_LEVEL else bpy.data.objects.get(t))
            return {"FINISHED"} if n else {"CANCELLED"}
        if event.type in {"ESC", "RIGHTMOUSE"}:
            self._end(context)
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}


class BLENDA4D_OT_om_rename(bpy.types.Operator):
    bl_idname = "blenda4d.om_rename"
    bl_label = "Rename"
    bl_description = "Rename the active object"
    bl_options = {"UNDO"}
    name: bpy.props.StringProperty(options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return roles.role(context.area) == "OBJECTS"

    def invoke(self, context, event):
        _renamed[0] = time.monotonic()
        ob = bpy.data.objects.get(self.name) or object_at(context, event) or context.active_object
        if ob is None:
            return {"CANCELLED"}
        self.name = ob.name
        return context.window_manager.invoke_popup(self, width=220)

    def draw(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is not None:
            self.layout.activate_init = True
            self.layout.prop(ob, "name", text="", **type_icon_kw(ob))

    def execute(self, context):
        return {"FINISHED"}


def _tags(ob):
    """The icons after an object's row: one per material, plus smoothing and modifiers."""
    out = []
    for i, slot in enumerate(getattr(ob, "material_slots", [])):
        if slot.material:
            out.append(("MATERIAL", slot.material, i))
    if ob.type == "MESH" and any(m.type == "SMOOTH_BY_ANGLE" or m.name.startswith("Smooth") for m in ob.modifiers):
        out.append(("SHADING_SMOOTH", None, -1))
    return out


def _main_view(context):
    """The largest 3D view in the window, with its drawing region."""
    views = [a for a in context.window.screen.areas if a.type == "VIEW_3D" and len(a.spaces)]
    if not views:
        return None, None
    area = max(views, key=lambda a: a.width * a.height)
    return area, next((r for r in area.regions if r.type == "WINDOW"), None)


def _in_solo(context):
    from . import solo
    return solo.is_on(context.scene)


class BLENDA4D_OT_om_solo(bpy.types.Operator):
    bl_idname = "blenda4d.om_solo"
    bl_label = "Solo"
    bl_description = ("Show only the selected objects and what is under them; the camera does not move. Press again "
                      "to show everything")

    def execute(self, context):
        from . import solo
        if not solo.run(context, "TOGGLE"):
            self.report({"INFO"}, "Select the objects to solo first")
            return {"CANCELLED"}
        solo.redraw(context)
        return {"FINISHED"}


class BLENDA4D_OT_om_scroll_active(bpy.types.Operator):
    bl_idname = "blenda4d.om_scroll_active"
    bl_label = "Scroll to First Active"
    bl_description = "Open the folders above the active object and scroll the Object Manager to it"

    def execute(self, context):
        ob = context.view_layer.objects.active
        if ob is None:
            return {"CANCELLED"}
        p = ob.parent
        while p is not None:
            p.b4d_om_closed = False
            p = p.parent
        area = next((a for a in context.window.screen.areas if roles.role(a) == "OBJECTS"), None)
        region = next((r for r in area.regions if r.type == "WINDOW"), None) if area else None
        if region is None:
            return {"CANCELLED"}
        rows = [r[0] for r in visible_rows(context)]
        if ob not in rows:
            return {"CANCELLED"}
        h = row_height()
        row_top = -(rows_top() + rows.index(ob)) * h
        v2d = region.view2d
        top = v2d.region_to_view(0, region.height)[1]
        bottom = v2d.region_to_view(0, 0)[1]
        if bottom + h <= row_top <= top:
            return {"FINISHED"}                          # already in sight
        with context.temp_override(area=area, region=region):
            for _ in range(400):                         # Blender moves a little per scroll: step until the row shows
                top = v2d.region_to_view(0, region.height)[1]
                bottom = v2d.region_to_view(0, 0)[1]
                if bottom + 2 * h <= row_top <= top - h:
                    break
                before = top
                if row_top > top - h:
                    bpy.ops.view2d.scroll_up(deltay=40)
                else:
                    bpy.ops.view2d.scroll_down(deltay=40)
                if v2d.region_to_view(0, region.height)[1] == before:
                    break                                # at the end of the list
        area.tag_redraw()
        return {"FINISHED"}


ZOOM_LIMIT = 2.0             # Blender's own largest zoom for this kind of area


def _om_fit_zoom(context, region):
    """The largest zoom at which the widest row (indent, icons, its name and the status columns) still fits the
    Object Manager's width, so a larger Size never pushes anything out of the panel."""
    import blf
    rows = visible_rows(context)
    h = row_height()
    style = context.preferences.ui_styles[0].widget
    blf.size(0, style.points * context.preferences.system.ui_scale)
    widest = 0.0
    for ob, depth in rows:
        widest = max(widest, h * (2.4 + 0.8 * depth) + blf.dimensions(0, ob.name)[0])
    tags = max((len(_tags(ob)) for ob, _d in rows), default=0)
    content = widest + (3 + tags) * h + 1.2 * h
    return max(1.0, min(ZOOM_LIMIT, region.width / max(content, 1.0)))


def _om_zoom(self, context):
    """The size slider: Blender's own area zoom (as Ctrl+scroll), so names, icons and rows grow together, smoothly
    from the normal size up to the largest size at which every row still fits the panel."""
    area = next((a for a in context.window.screen.areas if roles.role(a) == "OBJECTS"), None)
    region = next((r for r in area.regions if r.type == "WINDOW"), None) if area else None
    if region is None:
        return
    target = 1.0 + (_om_fit_zoom(context, region) - 1.0) * self.b4d_om_zoom / 100.0
    fac = (1.0 - 1.0 / target) / 2.0                     # Blender's zoom_in: new scale = 1 / (1 - 2 * fac)
    with context.temp_override(area=area, region=region):
        try:
            bpy.ops.view2d.reset()
            if fac > 0.0005:
                bpy.ops.view2d.zoom_in(zoomfacx=fac, zoomfacy=fac)
        except RuntimeError as ex:
            print("Blenda 4D: Object Manager size", ex)
    area.tag_redraw()


class BLENDA4D_OT_size_step(bpy.types.Operator):
    bl_idname = "blenda4d.size_step"
    bl_label = "Size"
    bl_description = "Make the names and icons smaller or larger"
    prop: bpy.props.StringProperty(options={"SKIP_SAVE"})
    step: bpy.props.FloatProperty(default=1.0, options={"SKIP_SAVE"})

    def execute(self, context):
        wm = context.window_manager
        rna = wm.bl_rna.properties[self.prop]
        v = max(rna.hard_min, min(rna.hard_max, getattr(wm, self.prop) + self.step))
        setattr(wm, self.prop, int(round(v)) if rna.type == "INT" else v)
        return {"FINISHED"}


def size_bar(row, prop, step=1):
    """A manager's size bar: zoom out button, the slider, zoom in button (the buttons step it, the slider drags)."""
    o = row.operator("blenda4d.size_step", text="", icon="ZOOM_OUT", emboss=False)
    o.prop, o.step = prop, -step
    row.prop(bpy.context.window_manager, prop, text="Size", slider=True)
    o = row.operator("blenda4d.size_step", text="", icon="ZOOM_IN", emboss=False)
    o.prop, o.step = prop, step


class BLENDA4D_PT_om_bar(roles.RolePanel, bpy.types.Panel):
    """The Object Manager's bottom strip: an area of its own so the Size slider stays at the bottom."""
    bl_label = "Object Manager Size"
    role = "OM_BAR"

    def draw(self, context):
        sp = self.layout.split(factor=0.35)              # a short slider on the right, as in the Material Manager
        sp.label(text="")
        row = sp.row(align=True)                         # zoom out / Size / zoom in: says what it does at a glance
        size_bar(row, "b4d_om_zoom", step=10)


def _name_column(context, region, rows):
    """(share, layout width): the share of an Object Manager row taken by the name and the dots and check next to it.
    The tags go to its right, behind a separator."""
    import blf
    try:
        v2d = region.view2d
        zoom = (v2d.view_to_region(0, 0, clip=False)[1] - v2d.view_to_region(0, -1000, clip=False)[1]) / 1000
    except (AttributeError, ZeroDivisionError):
        zoom = 1.0
    width = region.width / max(zoom, 0.01)
    h = row_height()
    style = context.preferences.ui_styles[0].widget
    blf.size(0, style.points * context.preferences.system.ui_scale)
    widest = max((h * (2.4 + 0.8 * d) + blf.dimensions(0, ob.name)[0] for ob, d in rows), default=h * 3)
    left = widest + STATUS_ICONS * h + 1.8 * h          # a little room so the widest name is not cut short
    return max(0.2, min(0.8, left / max(width, 1))), width


ACTIVE_CAMERA_ICON = "SNAP_FACE_CENTER"      # a square with a dot in the middle: the scene's active camera
STATUS_ICONS = 3            # the two dots and the check
DIVIDER_GREY = (0.12, 0.12, 0.12, 1.0)
DIVIDER_MARGIN = -4         # UI px (times the UI scale): puts the separator midway between the check column and the tags


def _status_split(context, buttons):
    """The split factor that leaves exactly `buttons` icon widths (plus a little room) for the status side of a row,
    whatever the panel width and the Size (zoom)."""
    region = context.region
    try:
        v2d = region.view2d
        zoom = (v2d.view_to_region(0, 0, clip=False)[1] - v2d.view_to_region(0, -1000, clip=False)[1]) / 1000
    except (AttributeError, ZeroDivisionError):
        zoom = 1.0
    width = region.width / max(zoom, 0.01)               # the panel's width in layout units
    need = buttons * row_height() + row_height() * 0.6
    return max(0.25, min(0.9, 1 - need / max(width, 1)))


OM_MENU_SHARE = 0.915


def _icon_px():
    """An icon-only label's width: one unit."""
    return 20 * bpy.context.preferences.system.ui_scale


OM_SEARCH_MIN_PX = 120                                    # the search box always shows as a field, never only its icon


def _om_menu_share():
    """The menus' share of the Object Manager's title line. The search box keeps at least OM_SEARCH_MIN_PX; menus that
    no longer fit go into the » menu."""
    w = menus.panel_width()
    if not w:
        return OM_MENU_SHARE
    need = OM_SEARCH_MIN_PX * bpy.context.preferences.system.ui_scale + 3 * _icon_px()
    return max(0.35, min(OM_MENU_SHARE, 1 - need / max(w, 1)))


def draw_om_head(layout, context):
    """The top of the Object Manager's panel, above the rows: the tab, then one row with the menus, the tools and the
    search box."""
    manager_title(layout, "Objects", right_tabs="b4d_om_tab")
    share = _om_menu_share()
    sp = layout.split(factor=share, align=True)           # menus on the left, tools and the search box at the right
    bar = sp.row(align=True)
    bar.label(text="", icon="COLLAPSEMENU")
    menus.menu_bar(bar, OM_MENUS, avail=menus.panel_width(share, _icon_px()))
    right = sp.row(align=True)
    right.operator("blenda4d.om_scroll_active", text="", icon="ZOOM_SELECTED", emboss=False)
    right.operator("blenda4d.om_solo", text="", icon="SELECT_INTERSECT", emboss=False, depress=_in_solo(context))
    right.operator("blenda4d.solo", text="", icon="HIDE_OFF", emboss=False).mode = "OFF"   # Solo Off
    right.prop(context.window_manager, "b4d_om_search", text="", icon="VIEWZOOM", placeholder="Search")


class BLENDA4D_PT_objects(roles.RolePanel, bpy.types.Panel):
    bl_label = "Objects"
    role = "OBJECTS"

    def draw(self, context):
        layout = self.layout
        draw_om_head(layout, context)
        col = layout.column(align=True)
        drop = context.window_manager.b4d_om_drop
        rows = visible_rows(context)
        tags = max((len(_tags(ob)) + (ob.type == "CAMERA") for ob, _d in rows), default=0)
        share, width = _name_column(context, context.region, rows)
        for ob, depth in rows:
            self._row(col, ob, depth, tags, share, width)

        if drop == TOP_LEVEL:
            col.label(text="Move to top level", icon="TRIA_UP")

    def _row(self, col, ob, depth, tag_room=0, share=0.5, width=300.0):
        sp = col.split(factor=share, align=True)          # name, dots and check | the tags, behind a separator
        left = sp.row(align=True)
        status_share = max(0.05, min(0.6, (STATUS_ICONS * row_height() + 0.8 * row_height()) / max(width * share, 1)))
        ns = left.split(factor=1 - status_share, align=True)
        row = ns.row(align=True)
        if depth:
            row.separator(factor=1.6 * depth)
        if ob.children:
            row.operator("blenda4d.om_fold", text="", icon="DISCLOSURE_TRI_RIGHT" if ob.b4d_om_closed else "DISCLOSURE_TRI_DOWN",
                         emboss=False).name = ob.name
        else:
            row.label(text="", icon="BLANK1")
        name = row.row(align=True)
        name.alignment = "LEFT"
        name.label(text=ob.name, **type_icon_kw(ob))     # a label, so a press here can start a drag (see om_drag)
        status = ns.row(align=True)                       # next to the name, left-aligned, in a column of their own
        status.alignment = "LEFT"
        status.prop(ob, "hide_viewport", text="", emboss=False, icon="LAYER_ACTIVE" if not ob.hide_viewport else "LAYER_USED")
        status.prop(ob, "hide_render", text="", emboss=False, icon="LAYER_ACTIVE" if not ob.hide_render else "LAYER_USED")
        status.prop(ob, "b4d_enabled", text="", emboss=False, icon="CHECKMARK" if ob.b4d_enabled else "X")
        right = sp.row(align=True)
        right.alignment = "LEFT"
        right.separator(factor=0.5)
        if ob.type == "CAMERA":                            # the camera's view switch: filled while looking through it
            right.operator("blenda4d.om_look_through", text="", emboss=False,
                           icon=ACTIVE_CAMERA_ICON if bpy.context.scene.camera == ob else "VIEW_CAMERA_UNSELECTED").name = ob.name
        for icon, mat, slot in _tags(ob):
            if mat is not None and OM_TAG_BUTTON:
                OM_TAG_BUTTON[0](right, ob, slot, mat)
            elif mat is not None:
                right.label(text="", icon_value=right.icon(mat))
            else:
                right.label(text="", icon=icon)


def _big_view(context):
    views = [a for a in context.screen.areas if a.type == "VIEW_3D" and len(a.spaces)]
    return max(views, key=lambda a: a.width * a.height) if views else None


def _region_3d(area):
    """The 3D view's view data, or None while the area is being changed (it can have no editor then)."""
    if area is None or not len(area.spaces):
        return None
    space = area.spaces.active
    return getattr(space, "region_3d", None) if space is not None and space.type == "VIEW_3D" else None


def looking_through(context, ob):
    """True while the viewport looks through this camera."""
    if context.scene.camera != ob:
        return False
    r3 = _region_3d(_big_view(context))
    return r3 is not None and r3.view_perspective == "CAMERA"


class BLENDA4D_OT_om_look_through(bpy.types.Operator):
    bl_idname = "blenda4d.om_look_through"
    bl_label = "Look Through Camera"
    bl_description = "Look through this camera in the viewport; click again to go back to the free view"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        ob = context.scene.objects.get(self.name)
        area = _big_view(context)
        if ob is None or ob.type != "CAMERA" or area is None:
            return {"CANCELLED"}
        r3 = _region_3d(area)
        if r3 is None:
            return {"CANCELLED"}
        from . import viewmenus
        if looking_through(context, ob):
            viewmenus.back_to_editor(area, area.spaces.active)    # back where the editor camera was left
        else:
            viewmenus.look_through(area, area.spaces.active, ob)  # orbit / pan / zoom now move this camera
        for a in context.screen.areas:
            a.tag_redraw()
        return {"FINISHED"}


# --- Attribute Manager ------------------------------------------------------------------------------------------
TABS_COMMON = [("BASIC", "Basic", ""), ("COORD", "Coord.", ""), ("OBJECT", "Object", "")]


def _page_tabs(ob):
    from . import kinds
    k = kinds.kind_of(ob)
    if k:
        own = [(t[0], t[1], "") for t in kinds.KINDS[k]["tabs"]]
        if own and kinds.KINDS[k].get("own_tabs_only"):
            return own
        return TABS_COMMON[:2] + own if own else list(TABS_COMMON)
    tabs = list(TABS_COMMON)
    if ob.type == "MESH":
        tabs.append(("PHONG", "Phong", ""))
    if ob.type == "CAMERA" and CAMERA_PAGES:
        tabs += CAMERA_TABS
    if ob.type == "LIGHT":
        tabs[2] = ("OBJECT", "General", "")
        tabs += [("DETAILS", "Details", ""), ("SHADOW", "Shadow", "")]
    return tabs


def _tab_items(self, context):
    ob = context.view_layer.objects.active if context else None
    return _page_tabs(ob) if ob is not None else TABS_COMMON


# --- Attribute Manager rows ------------------------------------------------------------------------------------------
# Every setting on a page is one row: its keyframe marker, its name on the left, then a short number field. A number
# with a small range is a slider across the rest of the row; switches, lists and text fill the row.
LABEL_SHARE = 0.42           # the name's share of the row (long names such as "Fillet Subdivision" fit)
FIELD_UNITS = 6              # a number field's width, in Blender's widget units
SLIDER_SPAN = 1000           # a number whose soft range is no wider than this becomes a slider
_RAW_KW = ("expand", "icon_only", "toggle")


def _raw(kw):
    """Buttons that carry their own text (expanded lists, icon buttons, toggles) keep Blender's own drawing."""
    return any(kw.get(k) for k in _RAW_KW) or kw.get("emboss") is False


def _rna_prop(owner, attr):
    try:
        return owner.bl_rna.properties[attr]
    except (AttributeError, KeyError, TypeError):
        return None


def _bounded(p):
    if p is None or p.type not in ("INT", "FLOAT"):
        return False
    lo, hi = p.soft_min, p.soft_max
    return abs(lo) < 1e9 and abs(hi) < 1e9 and 0 < hi - lo <= SLIDER_SPAN


def attr_row(layout, owner, attr, label=None, index=-1, active=True, slider=None, **kw):
    """One Attribute Manager row: keyframe marker | name | field (and slider). Returns the row."""
    p = _rna_prop(owner, attr)
    if label is None:
        label = p.name if p is not None else attr
    while isinstance(layout, (AttrColumn, AttrRow)):    # draw straight into Blender's layout
        layout = layout._lay if isinstance(layout, AttrColumn) else layout._parent
    row = layout.row(align=False)
    row.use_property_split = False
    row.use_property_decorate = False
    if not active:
        row.active = False
    try:
        row.prop_decorator(owner, attr, index=index)
    except (TypeError, RuntimeError):
        row.label(text="", icon="BLANK1")
    sp = row.split(factor=LABEL_SHARE, align=True)
    sp.label(text=label)
    rest = sp.row(align=True)
    if _raw(kw):                                         # buttons that carry their own text
        rest.prop(owner, attr, index=index, **kw)
        return row
    kw.pop("toggle", None)
    number = p is not None and p.type in ("INT", "FLOAT") and p.subtype not in ("COLOR", "COLOR_GAMMA")
    if slider is None:
        slider = _bounded(p)
    if number and not slider:
        rest.alignment = "LEFT"                        # a short field, as wide as any number needs
        f = rest.row(align=True)
        f.ui_units_x = FIELD_UNITS
        f.prop(owner, attr, index=index, text="", **kw)
    else:
        rest.prop(owner, attr, index=index, text="", slider=bool(slider and number), **kw)
    return row


class AttrColumn:
    """A page's column: settings drawn with prop() become Attribute Manager rows (attr_row), everything else is the
    plain Blender layout. Pages written for a plain column work unchanged; a sub-column is one of these again."""

    def __init__(self, layout):
        object.__setattr__(self, "_lay", layout)

    def prop(self, data, property, text=None, index=-1, **kw):
        p = _rna_prop(data, property)
        vector = (p is not None and index == -1 and getattr(p, "is_array", False) and p.array_length in (2, 3, 4)
                  and p.subtype not in ("COLOR", "COLOR_GAMMA") and p.type in ("INT", "FLOAT", "BOOLEAN")
                  and not _raw(kw))
        if vector:                                     # one row per axis, as the Coord. page shows them
            name = text if text is not None else p.name
            sub = self._lay.column(align=True)
            for i in range(p.array_length):
                attr_row(sub, data, property, label=f"{name} . {'XYZW'[i]}", index=i, **kw)
            return None
        label = text if text is not None else None
        if label == "" and p is not None and p.type == "BOOLEAN":
            label = None
        return attr_row(self._lay, data, property, label=label, index=index, **kw)

    def column(self, **kw):
        return AttrColumn(self._lay.column(**kw))

    def row(self, **kw):
        return AttrRow(self._lay, kw)

    def __getattr__(self, name):
        return getattr(self._lay, name)

    def __setattr__(self, name, value):
        setattr(self._lay, name, value)


class AttrRow:
    """A page's row: a setting drawn into it becomes an Attribute Manager row (with the row's greying); buttons and
    labels drawn into it share one plain Blender row, as the page laid them out."""

    def __init__(self, parent, kw):
        d = self.__dict__
        d["_parent"], d["_kw"], d["_set"], d["_col"], d["_row"] = parent, kw, {}, None, None

    def _apply(self, lay):
        for k, v in self._set.items():
            if k != "alignment" or lay is self._row:
                setattr(lay, k, v)
        return lay

    def prop(self, data, property, text=None, index=-1, **kw):
        if self._col is None:
            self.__dict__["_col"] = self._apply(self._parent.column(align=True))
        return AttrColumn(self._col).prop(data, property, text=text, index=index, **kw)

    def __getattr__(self, name):
        if name in self._set:
            return self._set[name]
        if self._row is None:
            self.__dict__["_row"] = self._apply(self._parent.row(**self._kw))
        return getattr(self._row, name)

    def __setattr__(self, name, value):
        self._set[name] = value
        for lay in (self._col, self._row):
            if lay is not None:
                setattr(lay, name, value)


class BLENDA4D_OT_am_tab(bpy.types.Operator):
    bl_idname = "blenda4d.am_tab"
    bl_label = "Page"
    bl_options = {"INTERNAL"}
    key: bpy.props.StringProperty()
    label: bpy.props.StringProperty()

    @classmethod
    def description(cls, context, props):
        return f"Show the {props.label} page"

    def execute(self, context):
        context.window_manager.b4d_am_tab = self.key
        return {"FINISHED"}


def page_tabs(layout, ob, current):
    """The page tabs: short buttons from the left, the shown page filled; more than five wrap onto rows of four."""
    tabs = _page_tabs(ob)
    per = 4 if len(tabs) > 5 else len(tabs)
    col = layout.column(align=False)
    for start in range(0, len(tabs), max(per, 1)):
        row = col.row(align=False)
        row.alignment = "LEFT"
        for key, label, _d in tabs[start:start + per]:
            o = row.operator("blenda4d.am_tab", text=label, depress=key == current)
            o.key, o.label = key, label


def _vec(col, data, prop, label, axes="XYZ"):
    sub = col.column(align=True)
    for i, a in enumerate(axes):
        sub.prop(data, prop, index=i, text=f"{label} . {a}")


def page_basic(col, ob):
    col.prop(ob, "name", text="Name")
    col.prop(ob, "b4d_vis_editor", text="Visible in Editor")
    col.prop(ob, "b4d_vis_render", text="Visible in Renderer")
    col.separator()
    col.prop(ob, "color", text="Display Color")
    col.prop(ob, "show_in_front", text="X-Ray")


def page_coord(col, ob):
    _vec(col, ob, "b4d_pos", "P")
    col.separator()
    _vec(col, ob, "b4d_scale", "S")
    col.separator()
    _vec(col, ob, "b4d_rot", "R")
    col.separator()
    col.prop(ob, "rotation_mode", text="Rotation Order")


def prim_kind(ob):
    from . import primitives
    k = ob.get("b4d_type")
    return k if k in primitives.PRIMS else None


def _generator(ob):
    return next((m for m in ob.modifiers if m.type == "NODES" and m.node_group and m.node_group.name.startswith("Blenda ")), None)


# rows a page greys out until the switch they belong to is on
_NEEDS = {"Fillet Radius": "Fillet", "Fillet Segments": "Fillet", "Fillet Subdivision": "Fillet", "From": "Slice", "To": "Slice",
          "Regular Grid": "Slice", "Width": None, "Radius Y": None}


def page_primitive(col, ob, kind):
    """A primitive's Object page: its generator's settings, in order, with Blender's own fields."""
    from . import primitives
    mod = _generator(ob)
    if mod is None or mod.node_group is None:
        col.label(text="This object's generator is missing")
        return
    items = mod.node_group.interface.items_tree
    values = {}
    for sname, stype, _default, _key in primitives.PRIMS[kind][2]:
        if sname not in items:
            continue
        try:
            owner, attr = primitives.input_slot(mod, items[sname].identifier)
        except KeyError:
            continue
        values[sname] = (owner, attr)
    for sname, stype, _default, _key in primitives.PRIMS[kind][2]:
        if sname not in values:
            continue
        owner, attr = values[sname]
        row = col.column(align=True)
        switch = _NEEDS.get(sname)
        if switch and switch in values:
            o2, a2 = values[switch]
            try:
                row.active = bool(getattr(o2, a2))
            except (AttributeError, TypeError):
                pass
        if stype == "VECTOR":
            sub = row.column(align=True)
            for i, axis in enumerate("XYZ"):
                sub.prop(owner, attr, index=i, text=f"{sname} . {axis}")
        else:
            row.prop(owner, attr, text=sname)


VOLUME_LOOK = (("Density", "Density"), ("Color", "Color"), ("Anisotropy", "Light Scattering"),
               ("Absorption Color", "Absorption Color"), ("Emission Strength", "Emission"),
               ("Emission Color", "Emission Color"), ("Blackbody Intensity", "Glow"), ("Temperature", "Glow Temperature"))


def _volume_shader(ob):
    """The volume shader the object renders with: the first Principled Volume (or Volume Scatter) on its material's
    Volume input, else anywhere in the material."""
    mat = ob.active_material
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return mat, None
    nodes = mat.node_tree.nodes
    for kind in ("PRINCIPLED_VOLUME", "VOLUME_SCATTER"):
        node = next((n for n in nodes if n.type == kind), None)
        if node is not None:
            return mat, node
    return mat, None


def _volume_look(col, ob):
    """Top-level controls for how the volume looks, plus its render detail."""
    mat, node = _volume_shader(ob)
    col.label(text="Look")
    if node is None:
        col.label(text="Add a volume material to set density and colour" if mat is None
                  else f"{mat.name} has no volume shader")
    else:
        for name, label in VOLUME_LOOK:
            sock = node.inputs.get(name)
            if sock is None or not hasattr(sock, "default_value"):
                continue
            if sock.is_linked:
                row = col.row()
                row.active = False
                row.label(text=f"{label}: set by the material's nodes")
            else:
                col.prop(sock, "default_value", text=label)
    col.prop(ob.data.render, "step_size", text="Detail (Step Size)")


def page_volume(col, ob):
    """A volume (OpenVDB) object: its file, sequence, viewport display and render quality, and the grids it holds.
    The Look rows are the volume material's own shader inputs, so changing them here changes the material."""
    d = ob.data
    _volume_look(col, ob)
    col.separator()
    col.prop(d, "filepath", text="File")
    col.prop(d, "is_sequence", text="Sequence")
    if d.is_sequence:
        col.prop(d, "frame_start", text="Start Frame")
        col.prop(d, "frame_offset", text="Offset")
        col.prop(d, "sequence_mode", text="Mode")
    col.separator()
    col.label(text="Viewport")
    col.prop(d.display, "density", text="Density")
    col.prop(d.display, "wireframe_type", text="Wireframe")
    if d.display.wireframe_type in ("BOXES", "POINTS"):
        col.prop(d.display, "wireframe_detail", text="Detail")
    col.prop(d.display, "interpolation_method", text="Interpolation")
    col.separator()
    col.label(text="Render")
    col.prop(d.render, "space", text="Space")
    col.prop(d.render, "precision", text="Precision")
    col.prop(d.render, "clipping", text="Clipping")
    col.separator()
    try:                                                  # reading the file's grid list is cheap: names and types only
        if d.filepath and not d.grids.is_loaded:
            d.grids.load()
        grids = [(g.name, g.data_type) for g in d.grids]
    except (AttributeError, RuntimeError, ReferenceError):
        grids = []
    if grids:
        col.label(text="Grids")
        for name, kind in grids:
            col.label(text=f"{name}    {kind.replace('_', ' ').title()}", icon="DOT")
    elif d.filepath:
        col.label(text="Grids: none loaded (check the file path)")


def page_object(col, ob):
    from . import kinds
    d = ob.data
    kind = prim_kind(ob)
    if kind:
        return page_primitive(col, ob, kind)
    if ob.type == "MESH":
        col.label(text=f"Points: {len(d.vertices)}    Polygons: {len(d.polygons)}")
        _vec(col, ob, "b4d_size", "Size")
    elif ob.type == "LIGHT":
        col.prop(d, "color", text="Color")
        col.prop(d, "energy", text="Intensity")
        col.prop(d, "type", text="Type")
        col.prop(d, "use_shadow", text="Shadow")
        if d.type == "AREA":
            col.prop(d, "shape", text="Area Shape")
            col.prop(d, "size", text="Size")
    elif ob.type == "CAMERA":
        col.prop(d, "type", text="Projection")
        col.prop(d, "lens", text="Focal Length")
        col.prop(d, "sensor_width", text="Sensor Size")
        col.prop(d, "clip_start", text="Near Clipping")
        col.prop(d, "clip_end", text="Far Clipping")
    elif ob.type == "EMPTY":
        col.prop(ob, "empty_display_type", text="Display")
        col.prop(ob, "empty_display_size", text="Radius")
    elif ob.type == "CURVE" and "spline" in kinds.KINDS:          # the splines module draws any curve's page
        kinds.KINDS["spline"]["pages"]["OBJECT"](col, ob)
    elif ob.type == "CURVE":
        col.prop(d, "resolution_u", text="Intermediate Points")
        col.prop(d, "dimensions", text="Type")
        col.prop(d, "extrude", text="Extrude")
        col.prop(d, "bevel_depth", text="Thickness")
    elif ob.type == "FONT" and FONT_PAGE:
        FONT_PAGE[0](col, ob)
    elif ob.type == "FONT":
        col.prop(d, "body", text="Text")
        col.prop(d, "size", text="Height")
        col.prop(d, "extrude", text="Depth")
        col.prop(d, "align_x", text="Align")
    elif ob.type == "VOLUME":
        page_volume(col, ob)
    else:
        col.label(text="No settings for this object type yet")


def page_phong(col, ob):
    col.operator("object.shade_smooth", text="Smooth")
    col.operator("object.shade_flat", text="Flat")
    col.operator("object.shade_auto_smooth", text="Smooth by Angle")


def page_light_details(col, ob):
    d = ob.data
    col.prop(d, "diffuse_factor", text="Diffuse")
    col.prop(d, "specular_factor", text="Specular")
    col.prop(d, "volume_factor", text="Volume")
    if d.type == "SPOT":
        col.prop(d, "spot_size", text="Outer Angle")
        col.prop(d, "spot_blend", text="Falloff")


def page_light_shadow(col, ob):
    d = ob.data
    col.prop(d, "use_shadow", text="Cast Shadows")
    col.prop(d, "shadow_soft_size", text="Shadow Radius")


PAGES = {"BASIC": page_basic, "COORD": page_coord, "OBJECT": page_object, "PHONG": page_phong,
         "DETAILS": page_light_details, "SHADOW": page_light_shadow}


class BLENDA4D_PT_attributes(roles.RolePanel, bpy.types.Panel):
    bl_label = "Attributes"
    role = "ATTRIBUTES"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        manager_title(layout, "Attributes", right_tabs="b4d_right_tab")
        if wm.b4d_right_tab == "LAYERS":
            return draw_layers(layout, context)
        if wm.b4d_right_tab == "VARIATIONS":
            return draw_variations(layout, context)
        bar = layout.row(align=True)
        bar.label(text="", icon="COLLAPSEMENU")
        menus.menu_bar(bar, AM_MENUS, avail=menus.panel_width(1.0, _icon_px()))
        ob = context.view_layer.objects.active
        layout.separator(factor=0.3)
        from . import phong
        if phong.draw_page(layout, context):              # the Phong Break Selection tool's options
            return
        fn = AM_SUBJECTS.get(wm.b4d_am_subject.partition(":")[0])
        if fn is not None and wm.b4d_am_subject.startswith("MAT:") and fn(layout, context, ob):
            return                                         # a material picked in the Material Manager
        if ob is None:
            layout.label(text="Nothing selected")
            return
        if fn is not None and fn(layout, context, ob):
            return
        head = layout.row(align=True)
        kind = prim_kind(ob)
        from . import primitives
        from . import kinds
        own = kinds.kind_of(ob)
        label = (kinds.KINDS[own]["label"] if own else
                 (primitives.PRIMS[kind][1] + " Object") if kind else TYPE_LABEL.get(ob.type, "Object"))
        head.label(text=f"{label} [{ob.name}]", **type_icon_kw(ob))
        tab = wm.b4d_am_tab
        tabs = [t[0] for t in _page_tabs(ob)]
        if tab not in tabs:
            tab = "OBJECT" if "OBJECT" in tabs else tabs[min(2, len(tabs) - 1)]
        page_tabs(layout, ob, tab)
        layout.separator(factor=0.5)
        page = kinds.KINDS[own]["pages"].get(tab) if own else None
        if page is None and ob.type == "CAMERA" and tab in CAMERA_PAGES:
            page = CAMERA_PAGES[tab]
        title = (kinds.KINDS[own]["titles"].get(tab) if own else None) or (
            CAMERA_TITLES.get(tab) if ob.type == "CAMERA" else None) or {
            "BASIC": "Basic Properties", "COORD": "Coordinates", "OBJECT": "Object Properties", "PHONG": "Phong",
            "DETAILS": "Details", "SHADOW": "Shadow"}.get(tab, dict((t[0], t[1]) for t in _page_tabs(ob)).get(tab, tab))
        layout.label(text=title)
        col = AttrColumn(layout.column())
        (page or PAGES.get(tab, lambda c, o: None))(col, ob)


# --- Layers: the scene's collections, one row each ----------------------------------------------------------------
def layer_rows(layer_collection, depth=0):
    """(layer collection, depth) of every layer under the scene's own collection, in order."""
    for child in layer_collection.children:
        yield child, depth
        yield from layer_rows(child, depth + 1)


def _move_objects(collection, objects):
    for ob in objects:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        collection.objects.link(ob)


class BLENDA4D_OT_layer_new(bpy.types.Operator):
    bl_idname = "blenda4d.layer_new"
    bl_label = "New Layer"
    bl_description = "Add a layer to the scene (Blender: a new collection); the selected objects move into it"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        col = bpy.data.collections.new("Layer")
        context.scene.collection.children.link(col)
        _move_objects(col, list(context.selected_objects))
        return {"FINISHED"}


class BLENDA4D_OT_layer_assign(bpy.types.Operator):
    bl_idname = "blenda4d.layer_assign"
    bl_label = "Move Selected Here"
    bl_description = "Move the selected objects into this layer"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        col = bpy.data.collections.get(self.name)
        if col is None:
            return {"CANCELLED"}
        _move_objects(col, list(context.selected_objects))
        return {"FINISHED"}


class BLENDA4D_OT_layer_select(bpy.types.Operator):
    bl_idname = "blenda4d.layer_select"
    bl_label = "Select Layer's Objects"
    bl_description = "Select the objects in this layer"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        col = bpy.data.collections.get(self.name)
        if col is None:
            return {"CANCELLED"}
        for ob in context.view_layer.objects:
            ob.select_set(False)
        for ob in col.all_objects:
            if ob.name in context.view_layer.objects:
                ob.select_set(True)
        return {"FINISHED"}


def draw_layers(layout, context):
    top = layout.row(align=True)
    top.alignment = "LEFT"
    top.operator("blenda4d.layer_new", text="New Layer", icon="ADD")
    layout.separator(factor=0.4)
    rows = list(layer_rows(context.view_layer.layer_collection))
    if not rows:
        layout.label(text="No layers yet: New Layer groups the selected objects.")
        return
    col = layout.column(align=True)
    for lc, depth in rows:
        row = col.row(align=True)
        if depth:
            row.separator(factor=2.0 * depth)
        row.prop(lc.collection, "name", text="", emboss=False, icon="OUTLINER_COLLECTION")
        row.prop(lc, "hide_viewport", text="", icon_only=True, emboss=False)
        row.prop(lc.collection, "hide_render", text="", icon_only=True, emboss=False)
        o = row.operator("blenda4d.layer_select", text="", icon="RESTRICT_SELECT_OFF", emboss=False)
        o.name = lc.collection.name
        o = row.operator("blenda4d.layer_assign", text="", icon="IMPORT", emboss=False)
        o.name = lc.collection.name


def draw_variations(layout, context):
    layout.label(text="Variations of this scene appear here.")
    layout.operator("blenda4d.noop", text="New Variation", icon="ADD")


# --- Material Manager --------------------------------------------------------------------------------------------
class BLENDA4D_OT_new_material(bpy.types.Operator):
    bl_idname = "blenda4d.new_material"
    bl_label = "New Material"
    bl_description = "Make a new material"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        mat = bpy.data.materials.new("Mat")
        mat.use_nodes = True
        context.window_manager.b4d_material = mat.name
        return {"FINISHED"}


class BLENDA4D_OT_mat_pick(bpy.types.Operator):
    bl_idname = "blenda4d.mat_pick"
    bl_label = "Material"
    bl_description = "Select this material; Shift-click puts it on the selected objects"
    name: bpy.props.StringProperty()

    def invoke(self, context, event):
        mat = bpy.data.materials.get(self.name)
        if mat is None:
            return {"CANCELLED"}
        context.window_manager.b4d_material = mat.name
        from . import matpage
        matpage.show(context, mat)                         # the Attribute Manager shows the material
        if event.shift:
            for ob in context.selected_objects:
                if hasattr(ob.data, "materials"):
                    if ob.data.materials:
                        ob.data.materials[0] = mat
                    else:
                        ob.data.materials.append(mat)
        return {"FINISHED"}


class BLENDA4D_OT_mat_tag(bpy.types.Operator):
    bl_idname = "blenda4d.mat_tag"
    bl_label = "Material Tag"
    bl_description = "Give the selected objects the current material"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        mat = bpy.data.materials.get(context.window_manager.b4d_material) or bpy.data.materials.new("Mat")
        for ob in context.selected_objects:
            if hasattr(ob.data, "materials"):
                ob.data.materials.append(mat)
        return {"FINISHED"}


class BLENDA4D_PT_materials(roles.RolePanel, bpy.types.Panel):
    bl_label = "Materials"
    role = "MATERIALS"

    def draw(self, context):
        layout = self.layout
        manager_title(layout, "Materials")
        bar = layout.row(align=True)
        bar.label(text="", icon="COLLAPSEMENU")
        menus.menu_bar(bar, MM_MENUS, avail=menus.panel_width(1.0, _icon_px()))
        matman.draw_tools(layout, context)
        layout.separator(factor=0.4)
        matman.draw_materials(layout, context)


# --- Asset Browser (layout per the approved mock-up; Blender's asset libraries underneath) ------------------------
AB_TIPS = {"AUTO": "Assets that suit what is selected", "ALL": "Every asset", "MODELS": "Objects to add to the scene",
           "MATERIALS": "Materials", "MEDIA": "Images, movies and sounds", "NODES": "Node groups",
           "OPERATORS": "Saved commands", "SCENES": "Whole scenes and templates", "PRESETS": "Saved settings",
           "HDRIS": "Environment images that light the scene", "POSES": "Character poses", "BRUSHES": "Sculpt and paint brushes"}
AB_TABS = (("AUTO", "Auto"), ("ALL", "All"), ("MODELS", "Models"), ("MATERIALS", "Materials"), ("MEDIA", "Media"), ("NODES", "Nodes"),
           ("OPERATORS", "Operators"), ("SCENES", "Scenes"), ("PRESETS", "Presets"), ("HDRIS", "HDRIs"), ("POSES", "Poses"), ("BRUSHES", "Brushes"))
AB_GREY = {"MEDIA", "OPERATORS", "PRESETS"}
AB_SMART = (("FUND", "Favorites", True), ("VIEWZOOM", "Featured Content", False), ("BOOKMARKS", "Keywords", True),
            ("NEWFOLDER", "New Assets", False), ("FILE_FOLDER", "Other", False), ("TIME", "Recently Created", True), ("TIME", "Recently Used", True))
AB_MENUS = [menus.simple_menu(n, [I("…")], "ab") for n in ("Create", "Edit", "View", "Libraries")]


class BLENDA4D_PT_assets(roles.RolePanel, bpy.types.Panel):
    bl_label = "Asset Browser"
    role = "ASSETS"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        from . import kinds
        if "ASSETS" in kinds.PANELS:
            return kinds.PANELS["ASSETS"](layout, context)
        manager_title(layout, "Asset Browser")
        bar = layout.row(align=True)
        menus.menu_bar(bar, AB_MENUS)
        grid = layout.grid_flow(row_major=True, columns=6, even_columns=True, align=True)
        for key, label in AB_TABS:
            cell = grid.row(align=True)
            cell.enabled = key not in AB_GREY
            cell.prop_enum(wm, "b4d_ab_tab", key, text=label)
        nav = layout.row(align=True)
        nav.operator("blenda4d.noop", text="", icon="BACK")
        nav.operator("blenda4d.noop", text="", icon="FORWARD")
        nav.operator("blenda4d.noop", text="", icon="HOME")
        nav.operator("blenda4d.noop", text="", icon="SOLO_OFF")
        nav.prop(wm, "b4d_ab_search", text="", icon="VIEWZOOM")
        split = layout.split(factor=0.48)
        tree = split.column(align=True)
        tree.label(text="Smart Searches", icon="DISCLOSURE_TRI_DOWN")
        for icon, label, ok in AB_SMART:
            r = tree.row(align=True)
            r.enabled = ok
            r.separator(factor=2.0)
            r.label(text=label, icon=icon)
        tree.separator()
        for lib in context.preferences.filepaths.asset_libraries:
            r = tree.row(align=True)
            r.label(text=lib.name, icon="FILE_FOLDER")
        right = split.column()
        right.label(text="Home")
        homes = (("MATERIAL", "Materials", "MATERIALS"), ("MESH_CUBE", "Models", "MODELS"), ("WORLD", "HDRIs", "HDRIS"),
                 ("FILE_BLEND", "Templates", "SCENES"), ("ARMATURE_DATA", "Motion Capture", "POSES"), ("NODETREE", "Nodes", "NODES"),
                 ("BRUSH_DATA", "Brushes", "BRUSHES"), ("ASSET_MANAGER", "All Assets", "ALL"))
        hg = right.grid_flow(row_major=True, columns=2, even_columns=True)
        for icon, label, tab in homes:
            b = hg.column(align=True)
            b.scale_y = 2.2
            b.prop_enum(wm, "b4d_ab_tab", tab, text=label, icon=icon)


classes = (BLENDA4D_OT_am_tab, BLENDA4D_OT_layer_new, BLENDA4D_OT_layer_assign, BLENDA4D_OT_layer_select, BLENDA4D_OT_om_look_through, BLENDA4D_OT_size_step, BLENDA4D_OT_om_delete, BLENDA4D_OT_om_solo, BLENDA4D_OT_om_scroll_active, BLENDA4D_OT_om_select, BLENDA4D_OT_om_drag, BLENDA4D_OT_om_rename, BLENDA4D_OT_om_fold, BLENDA4D_OT_om_expand, BLENDA4D_OT_group, BLENDA4D_OT_new_material,
           BLENDA4D_OT_mat_pick, BLENDA4D_OT_mat_tag, *OM_MENUS, *AM_MENUS, *MM_MENUS, *AB_MENUS,
           *(menus.make_more(m) for m in (OM_MENUS, AM_MENUS, MM_MENUS)),
           BLENDA4D_PT_objects, BLENDA4D_PT_om_bar, BLENDA4D_PT_attributes, BLENDA4D_PT_materials, BLENDA4D_PT_assets)


def _vis_get(attr):
    def get(self):
        return 2 if getattr(self, attr) else 0
    return get


def _vis_set(attr):
    def put(self, v):
        setattr(self, attr, v == 2)
    return put


def _enabled_set(self, v):
    self["_b4d_enabled"] = bool(v)
    self.hide_viewport = not v
    self.hide_render = not v


_last_active = [None]


@bpy.app.handlers.persistent
def _object_page_on_select(*_args):
    """Selecting another object puts the Attribute Manager on its Object page (the page stays as the user left it
    while the same object stays selected)."""
    try:
        ob = bpy.context.view_layer.objects.active
        name = ob.name_full if ob is not None else None
        if name == _last_active[0]:
            return
        _last_active[0] = name
        wm = bpy.context.window_manager
        if ob is not None and wm.b4d_am_tab != "OBJECT":
            wm.b4d_am_tab = "OBJECT"
    except (AttributeError, RuntimeError, ReferenceError):
        pass


def register():
    for c in classes:
        bpy.utils.register_class(c)
    _last_active[0] = None
    if _object_page_on_select not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_object_page_on_select)
    O, W = bpy.types.Object, bpy.types.WindowManager
    vis = [("DEFAULT", "Default", "Shown as usual"), ("ON", "On", "Shown"), ("OFF", "Off", "Hidden")]
    O.b4d_om_closed = bpy.props.BoolProperty(description='Whether the objects under this one are folded away in the Object Manager', default=False)
    O.b4d_enabled = bpy.props.BoolProperty(description='Switch the object on or off in the viewport and in renders', name="Enabled", get=lambda self: self.get("_b4d_enabled", True), set=_enabled_set)
    O.b4d_vis_editor = bpy.props.EnumProperty(description='Show or hide the object in the viewport (Blender: Hide in Viewport)', items=vis, get=_vis_get("hide_viewport"), set=_vis_set("hide_viewport"))
    O.b4d_vis_render = bpy.props.EnumProperty(description='Show or hide the object in renders (Blender: Disable in Renders)', items=vis, get=_vis_get("hide_render"), set=_vis_set("hide_render"))
    W.b4d_om_search = bpy.props.StringProperty(description='Show only objects whose name contains this', name="Search", options={"TEXTEDIT_UPDATE"})
    W.b4d_om_drop = bpy.props.StringProperty(description='Where a dragged object will be dropped', )
    W.b4d_om_zoom = bpy.props.FloatProperty(name="Size", description="Size of the Object Manager's names and icons, "
                                            "up to the largest that still fits the panel",
                                            default=0.0, min=0.0, max=100.0, subtype="PERCENTAGE", precision=0,
                                            update=_om_zoom)
    W.b4d_am_tab = bpy.props.EnumProperty(description='The page of settings the Attribute Manager shows', items=_tab_items, name="Page")
    W.b4d_om_tab = bpy.props.EnumProperty(description='The Object Manager', items=[("OBJECTS", "Objects", MANAGER_TIPS["Objects"])])
    W.b4d_right_tab = bpy.props.EnumProperty(description='Show the Attribute Manager, the Layers or the Variations', items=[("ATTRIBUTES", "Attributes", "The selected object's, tag's or material's settings"),
                                                ("LAYERS", "Layers", "The scene's layers: show, hide and select the objects in each"),
                                                ("VARIATIONS", "Variations", "Versions of the scene to switch between")])
    W.b4d_material = bpy.props.StringProperty(description='The material selected in the Material Manager', )
    W.b4d_am_subject = bpy.props.StringProperty(description='What the Attribute Manager shows besides the object: a tag or a material', )      # what the Attribute Manager shows besides the object (a tag)
    W.b4d_ab_tab = bpy.props.EnumProperty(description='Which kind of asset the Asset Browser lists', items=[(k, l, AB_TIPS.get(k, f"Show {l.lower()}")) for k, l in AB_TABS], default="ALL")
    W.b4d_ab_search = bpy.props.StringProperty(description='Show only assets whose name contains this', name="Search")
    _add_keymap()
    _draw.append(bpy.types.SpaceProperties.draw_handler_add(_draw_rows, (), "WINDOW", "POST_PIXEL"))


_keymaps = []
_draw = []


def _draw_rows():
    """Row highlights in the Object Manager (selected, active, drop target), like Blender's own lists."""
    context = bpy.context
    if roles.role(context.area) != "OBJECTS":
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    region = context.region
    c = context.preferences.themes[0].user_interface.wcol_regular.inner_sel     # the theme's pressed-button colour
    drop = context.window_manager.b4d_om_drop
    h = row_height()
    rects = []
    active = context.view_layer.objects.active
    rows = visible_rows(context)
    i = 0
    while True:
        top = region.view2d.view_to_region(0, -(rows_top() + i) * h, clip=False)[1]
        bottom = region.view2d.view_to_region(0, -(rows_top() + i + 1) * h, clip=False)[1]   # zoomed rows are taller
        if bottom > region.height:           # above the visible part: skip on
            i += 1
            continue
        if top < 0:
            break
        ob = rows[i][0] if i < len(rows) else None
        if ob is not None and ob.name == drop:
            k = 0.95
        elif ob is not None and ob == active and ob.select_get():
            k = 0.6
        elif ob is not None and ob.select_get():
            k = 0.35
        else:
            k = None
        if k is not None:
            rects.append((bottom, top, (c[0] * k, c[1] * k, c[2] * k, 1.0)))
        elif i % 2:                          # alternating dark and mid grey, to the bottom of the list
            rects.append((bottom, top, STRIPE))
        i += 1
    if not rects:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ADDITIVE")        # lightens the row behind the text instead of covering it
    for y0, y1, col in rects:
        batch = batch_for_shader(shader, "TRIS", {"pos": [(0, y0), (region.width, y0), (region.width, y1), (0, y1)]},
                                 indices=[(0, 1, 2), (0, 2, 3)])
        shader.uniform_float("color", col)
        batch.draw(shader)
    share, _w = _name_column(context, region, rows)       # the separator between the names and the tags
    x = share * region.width + DIVIDER_MARGIN * context.preferences.system.ui_scale
    top = region.view2d.view_to_region(0, -rows_top() * h, clip=False)[1]
    batch = batch_for_shader(shader, "TRIS", {"pos": [(x, 0), (x + 2, 0), (x + 2, top), (x, top)]}, indices=[(0, 1, 2), (0, 2, 3)])
    gpu.state.blend_set("NONE")
    shader.uniform_float("color", DIVIDER_GREY)
    batch.draw(shader)


def _add_keymap():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return
    km = kc.keymaps.new(name="Property Editor", space_type="PROPERTIES")
    _keymaps.append((km, km.keymap_items.new("blenda4d.om_drag", "LEFTMOUSE", "CLICK_DRAG")))
    _keymaps.append((km, km.keymap_items.new("blenda4d.om_select", "LEFTMOUSE", "CLICK")))
    _keymaps.append((km, km.keymap_items.new("blenda4d.om_select", "LEFTMOUSE", "CLICK", shift=True)))
    _keymaps.append((km, km.keymap_items.new("blenda4d.om_rename", "LEFTMOUSE", "DOUBLE_CLICK")))
    _keymaps.append((km, km.keymap_items.new("blenda4d.om_rename", "F2", "PRESS")))
    for key in ("DEL", "BACK_SPACE"):                      # Delete and Backspace delete the selection (issue #2)
        _keymaps.append((km, km.keymap_items.new("blenda4d.om_delete", key, "PRESS")))


def unregister():
    if _object_page_on_select in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_object_page_on_select)
    for h in _draw:
        bpy.types.SpaceProperties.draw_handler_remove(h, "WINDOW")
    _draw.clear()
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _keymaps.clear()
    O, W = bpy.types.Object, bpy.types.WindowManager
    for n in ("b4d_om_closed", "b4d_enabled", "b4d_vis_editor", "b4d_vis_render"):
        delattr(O, n)
    for n in ("b4d_om_search", "b4d_om_drop", "b4d_om_zoom", "b4d_am_tab", "b4d_om_tab", "b4d_right_tab", "b4d_material", "b4d_ab_tab", "b4d_ab_search", "b4d_am_subject"):
        delattr(W, n)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
