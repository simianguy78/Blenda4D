# SPDX-License-Identifier: GPL-3.0-or-later
"""The Blenda 4D | Blender switch.

On: Blenda's bars, managers and theme go in, and a "Blenda 4D" workspace with Blenda's layout is made and shown (the
workspace the person was in is remembered). Off: everything Blenda registered is taken back, the theme is restored,
the remembered workspace comes back and the Blenda workspace is removed, so the file is as it was."""
import os

import bpy

from . import bars, build, coords, kinds, layouts, managers, matman, menus, primitives, roles, theme

WORKSPACE = "Blenda 4D"
PREV_KEY = "b4d_prev_workspace"
MODE = (menus, primitives, bars, matman, managers, layouts, coords, roles, kinds)
_on = [False]


def is_on():
    return _on[0]


def _register_mode():
    for mod in MODE:
        try:
            mod.register()
        except Exception as ex:
            print("Blenda 4D: could not register", mod.__name__, ex)


def _unregister_mode():
    for mod in reversed(MODE):
        try:
            mod.unregister()
        except Exception as ex:
            print("Blenda 4D: could not unregister", mod.__name__, ex)


def _enter_workspace(window):
    ws = window.workspace
    if ws is not None and ws.name == WORKSPACE:
        build.rebuild(window, done=lambda: _finish(window))
        return
    prev = ws.name if ws else ""
    own = bpy.data.workspaces.get(WORKSPACE)
    if own is None:
        before = set(bpy.data.workspaces)
        with bpy.context.temp_override(window=window, screen=window.screen):
            bpy.ops.workspace.duplicate()
        own = next((w for w in bpy.data.workspaces if w not in before), None)
        if own is None:
            return
        own.name = WORKSPACE
    own[PREV_KEY] = prev
    window.workspace = own

    def when_shown(tries=[80]):
        tries[0] -= 1
        if window.screen.as_pointer() not in {s.as_pointer() for s in own.screens}:
            return 0.05 if tries[0] > 0 else None
        build.rebuild(window, done=lambda: _finish(window))
        return None
    bpy.app.timers.register(when_shown, first_interval=0.05)


def _finish(window):
    try:
        window.screen.show_statusbar = False
    except AttributeError:
        pass
    for area in window.screen.areas:
        area.tag_redraw()


def _leave_workspace(window, forget=False):
    """Back to the workspace used before. The Blenda 4D workspace stays (switching back shows it at once, nothing is
    rebuilt); it is removed only when the add-on is turned off (forget)."""
    ws = window.workspace
    if ws is None or ws.name != WORKSPACE:
        return
    prev = bpy.data.workspaces.get(ws.get(PREV_KEY, "")) or next((w for w in bpy.data.workspaces if w.name != WORKSPACE), None)
    if prev is None:
        return
    window.workspace = prev
    if not forget:
        return

    tries = [25]

    def later():
        w = bpy.data.workspaces.get(WORKSPACE)
        if w is None:
            return None
        if any(win.workspace == w for win in bpy.context.window_manager.windows):
            tries[0] -= 1
            return 0.2 if tries[0] > 0 else None              # the window changes workspace on its next event loop
        bpy.data.batch_remove(ids=[w])
        return None
    bpy.app.timers.register(later, first_interval=0.2)


_saved_prefs = {}
PREFS_OFF = {"show_regions_visibility_toggle": False, "show_corner_split": False}


def _screen_chrome(on):
    """Blender's hidden-region arrows and corner split zones are not part of Blenda's layout."""
    apps = bpy.context.preferences.apps
    if on:
        for k, v in PREFS_OFF.items():
            if hasattr(apps, k):
                _saved_prefs.setdefault(k, getattr(apps, k))
                setattr(apps, k, v)
    else:
        for k, v in _saved_prefs.items():
            setattr(apps, k, v)
        _saved_prefs.clear()


SPLASH = os.path.join(os.path.dirname(__file__), "splash.jpg")
_splash_saved = []


def splash(on):
    """Blenda 4D's picture on Blender's splash while Blenda mode is on. Blender reads the BLENDER_CUSTOM_SPLASH
    environment variable each time it draws the splash (wm_splash_screen.cc, wm_block_splash_image); a value the
    person set themselves is kept and put back."""
    key = "BLENDER_CUSTOM_SPLASH"
    if on and os.path.exists(SPLASH):
        if not _splash_saved:
            _splash_saved.append(os.environ.get(key))
        if _splash_saved[0] is None:                      # never over a splash the person chose
            os.environ[key] = SPLASH
    elif not on and _splash_saved:
        old = _splash_saved.pop()
        if old is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old


def _is_startup_cube(ob):
    """Blender's untouched startup cube: a plain 8-point mesh at the origin with no modifiers or parent."""
    me = ob.data
    return (ob.type == "MESH" and ob.name == "Cube" and me.name == "Cube" and len(me.vertices) == 8
            and not ob.modifiers and ob.parent is None and "b4d_type" not in ob
            and all(abs(v) < 1e-6 for v in ob.location) and all(abs(v) < 1e-6 for v in ob.rotation_euler)
            and all(abs(v - 1.0) < 1e-6 for v in ob.scale))


def swap_startup_cube(context=None):
    """In an unsaved file that still holds only Blender's startup scene (Cube, Light, Camera), Blenda's own Cube
    Object takes the place of the startup cube, so it has Size, Segments and Fillet settings from the start. Returns
    the new object, or None when the scene is not that untouched startup scene."""
    context = context or bpy.context
    if bpy.data.filepath or {o.name for o in bpy.data.objects} != {"Cube", "Light", "Camera"}:
        return None
    old = bpy.data.objects["Cube"]
    if not _is_startup_cube(old) or not old.users_collection:
        return None
    layer = context.view_layer
    was_active = layer.objects.active is old
    was_selected = old.select_get() if old.name in layer.objects else False
    collection = old.users_collection[0]
    mesh = old.data
    bpy.data.objects.remove(old)
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)
    ob = primitives.add_primitive(context, "cube", name="Cube", collection=collection)
    if was_selected:
        ob.select_set(True)
    if was_active:
        layer.objects.active = ob
    return ob


def set_mode(on, forget=False):
    splash(on)
    if on and not _on[0]:
        _register_mode()
        try:
            swap_startup_cube()
        except Exception as ex:
            print("Blenda 4D: could not swap the startup cube", ex)
        theme.apply()
        _screen_chrome(True)
        for scene in bpy.data.scenes:
            scene.unit_settings.system = "METRIC"
            scene.unit_settings.length_unit = "CENTIMETERS"
        _on[0] = True
        if not bpy.app.background:
            windows = list(bpy.context.window_manager.windows)
            if windows:
                _enter_workspace(windows[0])
    elif not on and _on[0]:
        if not bpy.app.background:
            for window in bpy.context.window_manager.windows:
                _leave_workspace(window, forget)
        theme.restore()
        _screen_chrome(False)
        _unregister_mode()
        _on[0] = False
    try:
        from . import settings
        settings.get().mode = on
    except Exception:
        pass
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


class BLENDA4D_OT_switch(bpy.types.Operator):
    bl_idname = "blenda4d.switch"
    bl_label = "Blenda 4D / Blender"
    bl_description = "Switch between Blenda 4D's layout and Blender's own"
    on: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        set_mode(self.on)
        return {"FINISHED"}


def _blender_header_button(self, context):
    """In Blender mode, the main menu bar keeps one way back."""
    if _on[0] or getattr(context.region, "alignment", "") != "RIGHT":
        return
    row = self.layout.row(align=True)
    row.operator("blenda4d.switch", text="Blenda 4D").on = True
    row.operator("blenda4d.switch", text="Blender", depress=True).on = False


def register():
    bpy.utils.register_class(BLENDA4D_OT_switch)
    bpy.types.TOPBAR_HT_upper_bar.append(_blender_header_button)


def unregister():
    if _on[0]:
        set_mode(False, forget=True)
    bpy.types.TOPBAR_HT_upper_bar.remove(_blender_header_button)
    bpy.utils.unregister_class(BLENDA4D_OT_switch)
