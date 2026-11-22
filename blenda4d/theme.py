# SPDX-License-Identifier: GPL-3.0-or-later
"""Blenda 4D's colours on Blender's theme while Blenda mode is on; every value changed is snapshotted and put back
when the switch goes to Blender. Panels #2b2b2b, viewport #363636, status #1c1c1c, fields #1c1c1c, selection
#4b4b6d / #aba8c7, text #d0d0d0, selected names #e8923a."""
import bpy

PANEL = (0.169, 0.169, 0.169, 1.0)      # 2b2b2b
PANEL_DARK = (0.11, 0.11, 0.11, 1.0)    # 1c1c1c
MENU_BACK = (0.102, 0.102, 0.102, 1.0)  # 1a1a1a
MENU_HOVER = (0.302, 0.302, 0.302, 1.0) # 4d4d4d
VIEW = (0.212, 0.212, 0.212)            # 363636
FIELD = (0.235, 0.235, 0.235, 1.0)
FIELD_HI = (0.30, 0.30, 0.30, 1.0)
SEL = (0.294, 0.294, 0.427, 1.0)        # 4b4b6d
SEL_TEXT = (0.95, 0.95, 0.95)
TEXT = (0.82, 0.82, 0.82)
TEXT_DIM = (0.60, 0.60, 0.60)
OUTLINE = (0.13, 0.13, 0.13, 1.0)
ACCENT = (0.67, 0.66, 0.78, 1.0)        # aba8c7

OM_BACK = (0.1686, 0.1686, 0.1686)   # 2b2b2b: manager background
OM_SEL = (0.91, 0.57, 0.23)        # e8923a
OM_ACTIVE = (0.96, 0.78, 0.30)     # f5c74d
_snap = []


def _set(owner, attr, value):
    try:
        old = getattr(owner, attr)
    except AttributeError:
        return
    try:
        old = tuple(old)
    except TypeError:
        pass
    _snap.append((owner, attr, old))
    try:
        setattr(owner, attr, value)
    except (TypeError, ValueError):
        _snap.pop()


def apply():
    th = bpy.context.preferences.themes[0]
    ui = th.user_interface
    # the tools column lives in the viewport's toolbar strip: solid beside the view, not floating over it
    _set(bpy.context.preferences.system, "use_region_overlap", False)
    for name in ("wcol_regular", "wcol_tool", "wcol_toolbar_item", "wcol_text", "wcol_num", "wcol_numslider",
                 "wcol_option", "wcol_toggle", "wcol_box", "wcol_menu", "wcol_pulldown", "wcol_menu_back",
                 "wcol_menu_item", "wcol_tab", "wcol_list_item", "wcol_scroll", "wcol_progress", "wcol_tooltip",
                 "wcol_radio", "wcol_pie_menu"):
        w = getattr(ui, name, None)
        if w is None:
            continue
        _set(w, "inner", FIELD)
        _set(w, "inner_sel", SEL)
        _set(w, "outline", OUTLINE)
        _set(w, "text", TEXT)
        _set(w, "text_sel", SEL_TEXT)
        _set(w, "item", ACCENT)
        _set(w, "show_shaded", False)
        _set(w, "roundness", 0.15)
    _set(th.view_3d, "camera", (0.89, 0.843, 0.796))
    # Object Manager names: selected = orange, active = bright
    _set(ui.wcol_list_item, "outline", (0, 0, 0, 0))          # trees are plain rows, no boxes
    _set(ui.wcol_list_item, "inner", (0, 0, 0, 0))
    _set(ui.wcol_option, "outline", (0.45, 0.45, 0.45))       # an unchecked box must be seen on the panel
    _set(ui.wcol_regular, "text_sel", OM_SEL)
    _set(ui.wcol_regular, "text", (0.651, 0.651, 0.651))      # manager menus are a6a6a6
    _set(ui.wcol_radio, "text_sel", OM_ACTIVE)
    _set(ui.wcol_radio, "inner", PANEL_DARK)                  # tabs and segmented choices: the others darker,
    _set(ui.wcol_radio, "inner_sel", FIELD)                   # the chosen one lighter (and its text yellow)
    _set(ui.wcol_radio, "outline", PANEL_DARK)
    _set(ui.wcol_menu_back, "inner", MENU_BACK)
    _set(ui.wcol_menu_back, "outline", (0.212, 0.212, 0.212, 1.0))
    # menus: flat rows on the menu background, a grey band on the hovered row
    _set(ui.wcol_menu_item, "inner", (0, 0, 0, 0))
    _set(ui.wcol_menu_item, "outline", (0, 0, 0, 0))
    _set(ui.wcol_menu_item, "inner_sel", MENU_HOVER)
    _set(ui.wcol_tooltip, "inner", PANEL)
    _set(ui.wcol_pulldown, "inner", (0, 0, 0, 0))
    _set(ui.wcol_tab, "inner", PANEL)
    _set(ui.wcol_tab, "inner_sel", (0.24, 0.24, 0.24, 1.0))
    # Attribute Manager value fields: #1c1c1c boxes with centred #cccccc text; sliders keep the blue fill
    for name in ("wcol_num", "wcol_text"):
        w = getattr(ui, name)
        _set(w, "inner", (0.11, 0.11, 0.11, 1.0))
        _set(w, "text", (0.80, 0.80, 0.80, 1.0))
        _set(w, "roundness", 0.1)
    _set(ui.wcol_numslider, "inner", (0.11, 0.11, 0.11, 1.0))
    _set(ui.wcol_numslider, "item", (0.329, 0.353, 0.60, 1.0))
    _set(ui, "widget_emboss", (0, 0, 0, 0))
    _set(ui, "editor_border", (0.09, 0.09, 0.09))
    _set(ui, "editor_outline", (0.09, 0.09, 0.09))
    _set(ui, "editor_outline_active", (0.09, 0.09, 0.09))
    for sp_name in ("view_3d", "properties", "dopesheet_editor", "outliner", "image_editor", "node_editor",
                    "text_editor", "spreadsheet", "preferences", "info", "file_browser"):
        sp = getattr(th, sp_name, None)
        if sp is None:
            continue
        s = sp.space
        _set(s, "header", PANEL)
        _set(s, "header_text", TEXT)
        _set(s, "header_text_hi", SEL_TEXT)
        _set(s, "text", TEXT)
        _set(s, "text_hi", SEL_TEXT)
        _set(s, "title", TEXT)
        _set(s, "back", PANEL)
        _set(s, "button", PANEL)
        _set(s, "button_text", TEXT)
        _set(s, "button_title", TEXT)
        _set(s, "navigation_bar", PANEL)
        _set(s, "execution_buts", PANEL)
        _set(s, "tab_active", (0.24, 0.24, 0.24))
        _set(s, "tab_inactive", PANEL[:3])
        _set(s, "tab_back", PANEL)
        _set(s, "tab_outline", (0.09, 0.09, 0.09))
        sp2 = getattr(sp, "space_list", None)
    v3 = th.view_3d
    _set(v3.space.gradients, "high_gradient", VIEW)
    _set(v3.space.gradients, "background_type", "SINGLE_COLOR")
    _set(v3, "grid", (0.30, 0.30, 0.30, 0.5))
    _set(v3, "wire", (0.0, 0.0, 0.0))
    # selection outline #af5710
    _set(v3, "object_selected", (0.686, 0.341, 0.063))
    _set(v3, "object_active", (0.686, 0.341, 0.063))
    _set(v3, "empty", (0.6, 0.6, 0.6))
    _set(th.topbar.space, "header", PANEL)
    _set(th.topbar.space, "back", PANEL)
    _set(th.statusbar.space, "header", PANEL_DARK)
    _set(th.statusbar.space, "header_text", TEXT_DIM)
    _set(th.properties.space, "back", OM_BACK)      # managers: 2b2b2b
    _set(th.properties, "match", ACCENT[:3])
    _set(th.properties, "active_modifier", ACCENT)
    _set(th.dopesheet_editor.space, "back", PANEL)
    _set(th.dopesheet_editor, "time_scrub_background", PANEL_DARK)
    _set(th.dopesheet_editor, "frame_current", ACCENT[:3])
    _set(th.dopesheet_editor, "grid", (0.22, 0.22, 0.22))
    _set(th.dopesheet_editor, "preview_range", (0.3, 0.3, 0.3, 0.3))
    _set(th.dopesheet_editor, "view_sliders", PANEL)
    clear = (0.0, 0.0, 0.0, 0.0)
    for sp_name in ("view_3d", "properties", "dopesheet_editor", "outliner", "image_editor", "node_editor",
                    "text_editor", "spreadsheet", "preferences", "info", "file_browser", "topbar", "statusbar"):
        sp = getattr(th, sp_name, None)
        pc = getattr(getattr(sp, "space", None), "panelcolors", None)
        if pc is not None:
            _set(pc, "header", clear)
            _set(pc, "back", clear)
            _set(pc, "sub_back", clear)
    _set(ui, "panel_roundness", 0.0)
    _set(ui, "icon_alpha", 1.0)
    # icons: full colour so the colour hierarchy shows (tinted copies in icons.py, tool accents); Blender's own icon
    # categories are set to the plain icon grey, so only the hierarchy's colours stand out
    _set(ui, "icon_saturation", 1.0)
    for cat in ("icon_object", "icon_object_data", "icon_modifier", "icon_shading", "icon_folder", "icon_scene",
                "icon_collection"):
        _set(ui, cat, TEXT + (1.0,))
    _set(ui, "widget_text_cursor", ACCENT[:3])
    _set(ui, "menu_shadow_fac", 0.0)
    # Blenda shows Y up: Blender's Z is shown as Y, so it is green, and Blender's Y is shown as Z, so it is blue.
    # Gizmos, the floor's axis lines and the view axis all take these
    _set(ui, "axis_y", (0.157, 0.565, 1.0))
    _set(ui, "axis_z", (0.545, 0.863, 0.0))


def restore():
    while _snap:
        owner, attr, old = _snap.pop()
        try:
            setattr(owner, attr, old)
        except (TypeError, ValueError, ReferenceError):
            pass


# type colours: an object's viewport frame is drawn in its type's colour; selected frames are lifted toward white.
TYPE_GENERATOR = (0.55, 0.91, 0.38, 1.0)
TYPE_DEFORMER = (0.67, 0.56, 0.99, 1.0)
TYPE_FIELD = (0.97, 0.60, 0.80, 1.0)


def lifted(color, amount=0.45):
    """The selected state of a type colour: the same hue, lighter."""
    return tuple(c + (1.0 - c) * amount for c in color[:3]) + (color[3] if len(color) > 3 else 1.0,)


def dimmed(color, amount=0.72):
    return tuple(c * amount for c in color[:3]) + (color[3] if len(color) > 3 else 1.0,)
