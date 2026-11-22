# SPDX-License-Identifier: GPL-3.0-or-later
"""The camera's Attribute Manager pages: Object (lens, field of view, film offset, focus), Physical (depth of field and
aperture), Details (clipping) and Composition (framing guides). Every row is one of Blender's own camera settings;
settings Blender has no equivalent for are left out rather than shown greyed."""

import bpy

from . import managers

TABS = [("PHYSICAL", "Physical", ""), ("DETAILS", "Details", ""), ("COMPOSITION", "Composition", "")]
TITLES = {"OBJECT": "Object Properties", "PHYSICAL": "Physical", "DETAILS": "Details", "COMPOSITION": "Composition Helpers"}

# guide toggle -> Blender's camera flag (two columns, as laid out on the page)
GUIDES = (("Grid", "show_composition_thirds"), ("Diagonal", "show_composition_center_diagonal"),
          ("Triangles", "show_composition_harmony_tri_a"), ("Golden Section", "show_composition_golden"),
          ("Crosshair", "show_composition_center"))


LABEL_SPLIT = 0.5            # label half / field half, so long names such as Field of View (Horizontal) fit


def _row(col, owner, attr, label, active=True, **kw):
    """One page row, drawn as every Attribute Manager row is (managers.attr_row)."""
    return managers.attr_row(col, owner, attr, label=label, active=bool(active), **kw)


def page_object(col, ob):
    cam = ob.data
    persp = cam.type == "PERSP"
    _row(col, cam, "type", "Projection")
    col.separator()
    _row(col, cam, "lens", "Focal Length", persp)
    _row(col, cam, "sensor_width", "Sensor Size")
    eq = cam.lens * 36.0 / max(cam.sensor_width, 0.001)
    r = col.row()
    r.active = persp
    r.label(text=f"35 mm equivalent focal length: {eq:.0f} mm")
    _row(col, cam, "angle_x", "Field of View (Horizontal)", persp)
    _row(col, cam, "angle_y", "Field of View (Vertical)", persp)
    _row(col, cam, "ortho_scale", "Zoom", cam.type == "ORTHO")
    col.separator()
    _row(col, cam, "b4d_offset_x", "Film Offset X (%)")
    _row(col, cam, "b4d_offset_y", "Film Offset Y (%)")
    col.separator()
    r = _row(col, cam.dof, "focus_distance", "Focus Distance")
    r.operator("ui.eyedropper_depth", text="", icon="EYEDROPPER")
    _row(col, cam.dof, "focus_object", "Focus Object")


def page_physical(col, ob):
    dof = ob.data.dof
    _row(col, dof, "use_dof", "Depth of Field")
    col.separator()
    _row(col, dof, "aperture_fstop", "F-Stop (f/#)", dof.use_dof)
    col.separator()
    _row(col, dof, "aperture_blades", "Aperture Blades", dof.use_dof)
    _row(col, dof, "aperture_rotation", "Aperture Rotation", dof.use_dof)
    _row(col, dof, "aperture_ratio", "Aperture Ratio", dof.use_dof)


def page_details(col, ob):
    cam = ob.data
    _row(col, cam, "clip_start", "Near Clipping")
    _row(col, cam, "clip_end", "Far Clipping")
    col.separator()
    _row(col, cam, "show_limits", "Show Clipping Range")


def page_composition(col, ob):
    cam = ob.data
    _row(col, cam, "b4d_guides", "Enable")
    col.separator()
    grid = col.grid_flow(row_major=True, columns=2, even_columns=True)
    grid.use_property_split = False                   # checkbox with its name beside it, no keyframe dots
    grid.use_property_decorate = False
    grid.active = cam.b4d_guides
    for label, flag in GUIDES:
        grid.prop(cam, flag, text=label)


PAGES = {"OBJECT": page_object, "PHYSICAL": page_physical, "DETAILS": page_details, "COMPOSITION": page_composition}


# --- settings shown in Blenda's own units ----------------------------------------------------------------------------
def _offset(axis):
    attr = "shift_" + axis

    def get(self):
        return getattr(self, attr) * 100.0

    def set(self, v):
        setattr(self, attr, v / 100.0)
    return get, set


def _guides_get(self):
    return bool(self.get("b4d_guides_off") is None)


def _guides_set(self, on):
    """Turning the guides off remembers which were on; turning them back on restores them."""
    if not on and self.get("b4d_guides_off") is None:
        self["b4d_guides_off"] = [f for _l, f in GUIDES if getattr(self, f)]
        for _l, f in GUIDES:
            setattr(self, f, False)
    elif on and self.get("b4d_guides_off") is not None:
        for f in self["b4d_guides_off"]:
            setattr(self, f, True)
        del self["b4d_guides_off"]


def _view_for(context):
    """The 3D view a new camera copies: the one the command came from, else the largest in the window."""
    if context.area is not None and context.area.type == "VIEW_3D":
        return context.area.spaces.active
    views = [a for a in context.screen.areas if a.type == "VIEW_3D" and len(a.spaces)] if context.screen else []
    return max(views, key=lambda a: a.width * a.height).spaces.active if views else None


class BLENDA4D_OT_add_camera(bpy.types.Operator):
    bl_idname = "blenda4d.add_camera"
    bl_label = "Camera"
    bl_description = ("Create a camera where the view is looking from: same position, angle and framing, so it "
                      "shows exactly what the view shows")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        sp = _view_for(context)
        if context.mode != "OBJECT" and context.object is not None:
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.camera_add()
        ob = context.active_object
        if sp is None or ob is None or ob.type != "CAMERA":
            return {"FINISHED"}
        rv = sp.region_3d
        ob.matrix_world = rv.view_matrix.inverted()
        src = context.scene.camera
        if rv.view_perspective == "CAMERA" and src is not None and src.type == "CAMERA":
            d, s = ob.data, src.data                             # looking through a camera: the same lens
            d.type, d.lens, d.ortho_scale = s.type, s.lens, s.ortho_scale
            d.sensor_width, d.sensor_height, d.sensor_fit = s.sensor_width, s.sensor_height, s.sensor_fit
        elif rv.view_perspective == "ORTHO":
            ob.data.type = "ORTHO"
            ob.data.sensor_fit = "AUTO"
            ob.data.ortho_scale = 2.0 / min(rv.window_matrix[0][0], rv.window_matrix[1][1])   # the view's wider side
        else:
            # the view's focal length is measured against a sensor twice as wide as a camera's 36 mm one
            # (measured: the same number gives a camera half the view's width), so half of it frames the same
            ob.data.sensor_width, ob.data.sensor_fit = 36.0, "AUTO"
            ob.data.lens = sp.lens / 2.0
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDA4D_OT_add_camera)
    from . import bars
    for g in bars.CREATE_GROUPS:                               # the camera button makes it where the view is
        if g and g[0] == "camera":
            g[1][0] = ("Camera", "OUTLINER_OB_CAMERA", "blenda4d.add_camera", {})
    C = bpy.types.Camera
    for axis in ("x", "y"):
        g, s = _offset(axis)
        setattr(C, "b4d_offset_" + axis, bpy.props.FloatProperty(
            name="Film Offset " + axis.upper(), get=g, set=s, step=10, precision=1,
            description=f"Shift the image {('sideways' if axis == 'x' else 'up and down')} without turning the camera "
                        f"(Blender: Shift {axis.upper()})"))
    C.b4d_guides = bpy.props.BoolProperty(name="Composition Helpers", get=_guides_get, set=_guides_set,
                                          description="Show the framing guides chosen below in the camera view")
    managers.CAMERA_PAGES.update(PAGES)
    managers.CAMERA_TABS[:] = TABS
    managers.CAMERA_TITLES.update(TITLES)


def unregister():
    from . import bars
    for g in bars.CREATE_GROUPS:
        if g and g[0] == "camera":
            g[1][0] = ("Camera", "OUTLINER_OB_CAMERA", "object.camera_add", {})
    bpy.utils.unregister_class(BLENDA4D_OT_add_camera)
    managers.CAMERA_PAGES.clear()
    managers.CAMERA_TABS.clear()
    managers.CAMERA_TITLES.clear()
    for n in ("b4d_offset_x", "b4d_offset_y", "b4d_guides"):
        if hasattr(bpy.types.Camera, n):
            delattr(bpy.types.Camera, n)
