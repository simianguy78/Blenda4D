# SPDX-License-Identifier: GPL-3.0-or-later
"""How a feature module plugs into Blenda 4D without editing the shared files.

A module (lights.py, deformers.py, ...) calls these from its register():
  add(kind, label, icon, create=fn, tabs=[("OBJECT", "Object")], pages={"OBJECT": fn}, titles={...})
      an object kind (stored as ob["b4d_type"]): its Attribute Manager tabs and pages, its Object Manager icon and the
      function that makes one (create(context) -> object). Basic and Coord. tabs are always there; list the rest.
  create_button(group, label, kind)   put the kind behind a create-column button (group as in bars.CREATE_GROUPS);
      a button with the same label is replaced, otherwise it is added to the group.
  menu_item(menu, label, kind, icon)  add the kind to a main menu (e.g. "Create").
  panel(role, fn)                     draw a whole manager (role "ASSETS") with fn(layout, context).
  view_page(name, fn)                 a viewport tab page ("RENDER": Render Settings) drawn with fn(layout, context).
  resolver(fn)                        fn(ob) -> kind for objects without a b4d_type of ours (plain Blender lights).
Modules listed in FEATURES are imported and registered by the switch when Blenda mode goes on."""
import bpy

FEATURES = ("render_settings", "assets", "splines", "generators", "deformers", "lights", "sky", "keymap", "quadview", "topbar", "addons_ui", "material_tag", "matpage", "cameras", "texts", "updates", "phong", "node_arrange", "solo", "coord_manager")

KINDS = {}
PANELS = {}
VIEW_PAGES = {}
_MENU = {}


def add(kind, label, icon, create=None, tabs=(), pages=None, titles=None, describe=None, own_tabs_only=False):
    """own_tabs_only: the kind shows only its own tabs (no Basic / Coord.), as the Sky does: it has no place or size."""
    KINDS[kind] = {"label": label, "icon": icon, "create": create, "tabs": list(tabs), "pages": dict(pages or {}),
                   "titles": dict(titles or {}), "describe": describe, "own_tabs_only": own_tabs_only}


RESOLVERS = []     # fn(ob) -> kind or None: gives objects no module made (plain Blender lights...) a module's kind


def resolver(fn):
    if fn not in RESOLVERS:
        RESOLVERS.append(fn)


def kind_of(ob):
    if ob is None:
        return None
    k = ob.get("b4d_type")
    if k in KINDS:
        return k
    for fn in RESOLVERS:
        k = fn(ob)
        if k in KINDS:
            return k
    return None


def create_button(group, label, kind):
    from . import bars
    members = bars.GROUPS.get(group)
    if members is None:
        return
    icon = KINDS[kind]["icon"] if kind in KINDS else "NONE"
    entry = (label, icon, "blenda4d.add_kind", {"kind": kind})
    for i, m in enumerate(members):
        if m[0] == label:
            members[i] = entry
            return
    members.append(entry)


def menu_item(menu, label, kind, icon=None):
    _MENU.setdefault(menu, [])
    if all(e[1] != kind for e in _MENU[menu]):
        _MENU[menu].append((label, kind, icon or (KINDS[kind]["icon"] if kind in KINDS else "NONE")))


def menu_items(menu):
    return _MENU.get(menu, [])


def panel(role, fn):
    PANELS[role] = fn


def view_page(name, fn):
    VIEW_PAGES[name] = fn


class BLENDA4D_OT_add_kind(bpy.types.Operator):
    bl_idname = "blenda4d.add_kind"
    bl_label = "Create"
    bl_options = {"REGISTER", "UNDO"}
    kind: bpy.props.StringProperty()

    @classmethod
    def description(cls, context, props):
        k = KINDS.get(props.kind)
        return (k["describe"] or ("Create a " + k["label"])) if k else ""

    def execute(self, context):
        k = KINDS.get(self.kind)
        if k is None or k["create"] is None:
            return {"CANCELLED"}
        ob = k["create"](context)
        if isinstance(ob, bpy.types.Object):
            for o in context.view_layer.objects.selected:
                o.select_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob
        return {"FINISHED"}


def _features():
    import importlib
    out = []
    for name in FEATURES:
        try:
            out.append(importlib.import_module(f"{__package__}.{name}"))
        except ModuleNotFoundError as ex:
            if ex.name != f"{__package__}.{name}":
                print("Blenda 4D:", name, ex)
        except Exception as ex:
            print("Blenda 4D: could not load", name, ex)
    return out


def register():
    bpy.utils.register_class(BLENDA4D_OT_add_kind)
    for mod in _features():
        try:
            mod.register()
        except Exception as ex:
            import traceback
            traceback.print_exc()
            print("Blenda 4D: could not register", mod.__name__, ex)


def unregister():
    for mod in reversed(_features()):
        try:
            mod.unregister()
        except Exception as ex:
            print("Blenda 4D: could not unregister", mod.__name__, ex)
    bpy.utils.unregister_class(BLENDA4D_OT_add_kind)
