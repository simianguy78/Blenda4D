# SPDX-License-Identifier: GPL-3.0-or-later
"""Coordinates as Blenda shows them: Y up, centimetres, rotations X, Y, Z in degrees.

Blender stays Z-up in metres underneath: shown (x, y, z) = Blender (x, z, y), 1 cm = 0.01 m. The properties convert
on read and write, so the numbers people see and type are the Y-up ones."""
import math

import bpy

SCALE = 0.01


def to_shown(v):
    return (v[0] / SCALE, v[2] / SCALE, v[1] / SCALE)


def from_shown(v):
    return (v[0] * SCALE, v[2] * SCALE, v[1] * SCALE)


def _get_pos(self):
    return to_shown(self.location)


def _set_pos(self, value):
    self.location = from_shown(value)


def _get_rot(self):
    e = self.rotation_euler
    return (math.degrees(e.x), math.degrees(e.z), math.degrees(e.y))


def _set_rot(self, value):
    self.rotation_euler = (math.radians(value[0]), math.radians(value[2]), math.radians(value[1]))


def _get_scale(self):
    s = self.scale
    return (s[0], s[2], s[1])


def _set_scale(self, value):
    self.scale = (value[0], value[2], value[1])


def _get_size(self):
    return to_shown(self.dimensions)


def _set_size(self, value):
    """Stretch the object until it is this size. Blender reads an object's size with its parents' scale included but
    sets it as if they had none, so scale by the ratio of the size wanted to the size it has: right under any parent."""
    if self.type != "MESH":
        return
    want, have = from_shown(value), self.dimensions
    s = list(self.scale)
    for i in range(3):
        if have[i] > 1e-9:
            s[i] *= want[i] / have[i]
    self.scale = s


def register():
    O = bpy.types.Object
    O.b4d_pos = bpy.props.FloatVectorProperty(description="Where the object is (Blenda shows Blender's Z as Y)", name="Position", size=3, get=_get_pos, set=_set_pos, precision=2, subtype="XYZ")
    O.b4d_rot = bpy.props.FloatVectorProperty(description="How the object is turned, in degrees (Blenda shows Blender's Z as Y)", name="Rotation", size=3, get=_get_rot, set=_set_rot, precision=2, subtype="XYZ")
    O.b4d_scale = bpy.props.FloatVectorProperty(description="How much the object is stretched along each axis (Blenda shows Blender's Z as Y)", name="Scale", size=3, get=_get_scale, set=_set_scale, precision=3, subtype="XYZ")
    O.b4d_size = bpy.props.FloatVectorProperty(description="The object's size along each axis (Blenda shows Blender's Z as Y)", name="Size", size=3, get=_get_size, set=_set_size, precision=2, subtype="XYZ")


def unregister():
    for n in ("b4d_pos", "b4d_rot", "b4d_scale", "b4d_size"):
        delattr(bpy.types.Object, n)
