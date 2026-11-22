# SPDX-License-Identifier: GPL-3.0-or-later
"""Add-on preferences: whether Blenda 4D's layout is on when Blender starts, and whether the Coordinate Manager shows."""
import bpy


class BLENDA4D_Prefs(bpy.types.AddonPreferences):
    bl_idname = __package__

    mode: bpy.props.BoolProperty(name="Start in Blenda 4D", default=True,
                                 description="Show Blenda 4D's layout when Blender starts")
    coords: bpy.props.BoolProperty(name="Coordinate Manager", default=True,
                                   description="Show the Coordinate Manager under the Attribute Manager")

    def draw(self, context):
        self.layout.prop(self, "mode")
        self.layout.prop(self, "coords")


def get():
    return bpy.context.preferences.addons[__package__].preferences


def register():
    bpy.utils.register_class(BLENDA4D_Prefs)


def unregister():
    bpy.utils.unregister_class(BLENDA4D_Prefs)
