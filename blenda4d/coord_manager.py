# SPDX-License-Identifier: GPL-3.0-or-later
"""The Coordinate Manager: a strip under the Attribute Manager, level with the timeline, with the selected object's
position, rotation and size (or scale) as three columns of X, Y and Z fields, a Reset button, and two dropdowns: Local
or World, and Size or Scale.

Numbers are shown as everywhere in Blenda (coords.py): Y up, centimetres, degrees. Local values are the object's own
(relative to its parent); World values are where it ends up in the scene. Typing a World value moves the object so it
lands there, whatever its parent. The strip is an area of its own (a role, see roles.py) that build.py splits off the
Attribute Manager while this module is loaded."""
import math

import bpy
from mathutils import Euler, Matrix, Vector

from . import coords, roles

ROLE = "COORDS"
FLAG = "show_properties_object"   # the one Properties tab flag no other role uses

SPACES = [("LOCAL", "Local", "Values relative to the object's parent (its own position, rotation and scale)"),
          ("WORLD", "World", "Values in the scene, wherever the object's parent is: typing one moves the object "
                             "so it ends up there")]
THIRDS = [("SIZE", "Size", "The third column is the object's size along each axis, in centimetres"),
          ("SCALE", "Scale", "The third column is how much the object is stretched along each axis")]

_EULER = {"XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"}


def _order(ob):
    return ob.rotation_mode if ob.rotation_mode in _EULER else "XYZ"


def _parts(ob):
    return ob.matrix_world.decompose()      # location, rotation (quaternion), scale


def _put(ob, loc, rot, scale):
    """Give the object this world placement; Blender works out its own values through the parent."""
    ob.matrix_world = Matrix.LocRotScale(loc, rot, scale)


# --- World values, shown the Blenda way (Y up, cm, degrees) ------------------------------------------------------
def _get_wpos(self):
    return coords.to_shown(self.matrix_world.translation)


def _set_wpos(self, value):
    _loc, rot, scale = _parts(self)
    _put(self, Vector(coords.from_shown(value)), rot, scale)


def _get_wrot(self):
    e = self.matrix_world.to_euler(_order(self))
    return (math.degrees(e.x), math.degrees(e.z), math.degrees(e.y))


def _set_wrot(self, value):
    loc, _rot, scale = _parts(self)
    e = Euler((math.radians(value[0]), math.radians(value[2]), math.radians(value[1])), _order(self))
    _put(self, loc, e.to_quaternion(), scale)


def _get_wscale(self):
    s = self.matrix_world.to_scale()
    return (s[0], s[2], s[1])


def _set_wscale(self, value):
    loc, rot, _scale = _parts(self)
    _put(self, loc, rot, Vector((value[0], value[2], value[1])))


def columns(ob, wm):
    """The property names of the three columns for these dropdown choices."""
    world = wm.b4d_cm_space == "WORLD"
    if wm.b4d_cm_third == "SIZE":
        third = "b4d_size"                               # size is the same seen from anywhere
    else:
        third = "b4d_wscale" if world else "b4d_scale"
    return ("b4d_wpos" if world else "b4d_pos", "b4d_wrot" if world else "b4d_rot", third)


class BLENDA4D_OT_cm_reset(bpy.types.Operator):
    bl_idname = "blenda4d.cm_reset"
    bl_label = "Reset"
    bl_description = ("Reset (Clear Location, Rotation and Scale in Blender): put the selected objects back at their "
                      "parent's origin, unturned and at their normal size")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.view_layer.objects.active is not None

    def execute(self, context):
        obs = set(context.selected_objects) | {context.view_layer.objects.active}
        for ob in obs:
            if ob is None:
                continue
            ob.location = (0.0, 0.0, 0.0)
            ob.rotation_euler = (0.0, 0.0, 0.0)
            ob.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            ob.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
            ob.scale = (1.0, 1.0, 1.0)
        return {"FINISHED"}


def draw(layout, context):
    wm = context.window_manager
    ob = context.view_layer.objects.active
    top = layout.row(align=False)
    top.label(text="", icon="COLLAPSEMENU")
    right = top.row(align=False)                         # Reset and the two dropdowns sit at the right end
    right.alignment = "RIGHT"
    right.operator("blenda4d.cm_reset", text="Reset")
    right.prop(wm, "b4d_cm_space", text="")
    right.prop(wm, "b4d_cm_third", text="")
    body = layout.column(align=False)
    body.active = ob is not None
    names = columns(ob, wm) if ob is not None else None
    size_locked = ob is not None and names[2] == "b4d_size" and ob.type != "MESH"
    for i, axis in enumerate("XYZ"):
        row = body.row(align=False)
        lab = row.row()
        lab.ui_units_x = 1
        lab.label(text=axis)
        if ob is None:
            for _c in range(3):
                row.label(text="")
            continue
        row.prop(ob, names[0], index=i, text="")
        row.prop(ob, names[1], index=i, text="")
        third = row.row()
        third.enabled = not size_locked                  # only meshes take a typed size (coords._set_size)
        third.prop(ob, names[2], index=i, text="")


class BLENDA4D_OT_cm_toggle(bpy.types.Operator):
    bl_idname = "blenda4d.cm_toggle"
    bl_label = "Coordinate Manager"
    bl_description = "Show or hide the Coordinate Manager under the Attribute Manager"

    def execute(self, context):
        from . import build
        on = not roles.areas(context.screen, ROLE)
        build.set_coords_shown(on)
        build.run_steps(build.coords_steps(context.window, on))
        return {"FINISHED"}


def toggle_button(layout, context):
    """The timeline's axes button: lit while the Coordinate Manager shows."""
    layout.operator("blenda4d.cm_toggle", text="", icon="EMPTY_ARROWS", depress=bool(roles.areas(context.screen, ROLE)))


class BLENDA4D_PT_coords(roles.RolePanel, bpy.types.Panel):
    bl_label = "Coordinate Manager"
    role = ROLE

    def draw(self, context):
        draw(self.layout, context)


CLASSES = (BLENDA4D_OT_cm_reset, BLENDA4D_OT_cm_toggle, BLENDA4D_PT_coords)
_PROPS = ("b4d_wpos", "b4d_wrot", "b4d_wscale")


def register():
    roles.ROLE_FLAGS[ROLE] = FLAG
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    O = bpy.types.Object
    O.b4d_wpos = bpy.props.FloatVectorProperty(name="Position (World)", description="Where the object is in the scene, wherever its parent is (Blenda shows Blender's Z as Y)", size=3, get=_get_wpos, set=_set_wpos, precision=2, subtype="XYZ")
    O.b4d_wrot = bpy.props.FloatVectorProperty(name="Rotation (World)", description="How the object is turned in the scene, in degrees (Blenda shows Blender's Z as Y)", size=3, get=_get_wrot, set=_set_wrot, precision=2, subtype="XYZ")
    O.b4d_wscale = bpy.props.FloatVectorProperty(name="Scale (World)", description="How much the object is stretched in the scene, its parents' stretch included (Blenda shows Blender's Z as Y)", size=3, get=_get_wscale, set=_set_wscale, precision=3, subtype="XYZ")
    W = bpy.types.WindowManager
    W.b4d_cm_space = bpy.props.EnumProperty(name="Values", description="Show and type values relative to the parent or in the scene", items=SPACES, default="LOCAL")
    W.b4d_cm_third = bpy.props.EnumProperty(name="Third Column", description="Show the object's size or its scale in the third column", items=THIRDS, default="SIZE")


def unregister():
    for T, names in ((bpy.types.WindowManager, ("b4d_cm_space", "b4d_cm_third")), (bpy.types.Object, _PROPS)):
        for n in names:
            if hasattr(T, n):
                delattr(T, n)
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    roles.ROLE_FLAGS.pop(ROLE, None)
