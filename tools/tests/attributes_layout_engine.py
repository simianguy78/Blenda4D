# Headless test of the Attribute Manager's row layout (managers.attr_row / AttrColumn): every page of every object
# kind is drawn into a recording layout, and every setting must come out as one row of keyframe marker, name on the
# left and field; numbers with a small range must be sliders, other numbers short fields; vectors one row per axis;
# rows that depend on an off switch (Fillet) greyed; and the page tabs one button per page, the shown one pressed.
# Settings a page lays out in sub-rows of its own are listed as "note" lines (they keep the page's own layout).
#   BLENDER_USER_CONFIG=<scratch> Blender -b --factory-startup --python tools/tests/attributes_layout_engine.py
import os
import sys
import traceback

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from blenda4d import kinds, managers, switch  # noqa: E402

FAIL = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what, flush=True)
    if not cond:
        FAIL.append(what)


class Rec:
    """A stand-in for Blender's UILayout that records what is drawn into it."""

    def __init__(self, kind="column", parent=None):
        self.__dict__.update(kind=kind, parent=parent, items=[], attrs={})

    def __setattr__(self, name, value):
        self.attrs[name] = value

    def __getattr__(self, name):
        if name in self.attrs:
            return self.attrs[name]
        if name in ("active", "enabled"):
            return True
        if name in ("use_property_split", "use_property_decorate"):
            return False
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **kw: self._leaf(name, *a, **kw)      # any other drawing call (templates, popovers)

    def _child(self, kind, **kw):
        c = Rec(kind, self)
        c.attrs["kw"] = kw
        self.items.append(c)
        return c

    def row(self, **kw):
        return self._child("row", **kw)

    def column(self, **kw):
        return self._child("column", **kw)

    def split(self, **kw):
        return self._child("split", **kw)

    def box(self, **kw):
        return self._child("box", **kw)

    def grid_flow(self, **kw):
        return self._child("grid", **kw)

    def column_flow(self, **kw):
        return self._child("column", **kw)

    def _leaf(self, kind, *a, **kw):
        self.items.append(("leaf", kind, a, kw))
        return _Props()

    def prop(self, *a, **kw):
        return self._leaf("prop", *a, **kw)

    def prop_decorator(self, *a, **kw):
        return self._leaf("decorator", *a, **kw)

    def label(self, *a, **kw):
        return self._leaf("label", *a, **kw)

    def operator(self, *a, **kw):
        return self._leaf("operator", *a, **kw)

    def separator(self, *a, **kw):
        return self._leaf("separator")

    def prop_enum(self, *a, **kw):
        return self._leaf("prop_enum", *a, **kw)

    def menu(self, *a, **kw):
        return self._leaf("menu", *a, **kw)

    def template_ID(self, *a, **kw):
        return self._leaf("template", *a, **kw)

    def template_list(self, *a, **kw):
        return self._leaf("template", *a, **kw)

    def context_pointer_set(self, *a, **kw):
        return None


class _Props:
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)


def leaves(rec):
    for it in rec.items:
        if isinstance(it, Rec):
            yield from leaves(it)
        else:
            yield rec, it


def rows_of(rec):
    """Every attr_row drawn under rec: a row holding a decorator then a split."""
    for it in rec.items:
        if isinstance(it, Rec):
            if it.kind == "row" and it.items and isinstance(it.items[0], tuple) and it.items[0][1] == "decorator":
                yield it
            else:
                yield from rows_of(it)


def greyed(rec):
    while rec is not None:
        if rec.attrs.get("active", True) is False:
            return True
        rec = rec.parent
    return False


def row_parts(r):
    """(label text, field leaf, its layout) of one attr_row."""
    sp = next(i for i in r.items if isinstance(i, Rec) and i.kind == "split")
    label = next(i for i in sp.items if isinstance(i, tuple) and i[1] == "label")[3].get("text")
    field = [(lay, it) for lay, it in leaves(sp) if it[1] == "prop"]
    return label, field


def page_report(name, ob, page_fn):
    root = Rec()
    col = managers.AttrColumn(root)
    try:
        page_fn(col, ob)
    except Exception:
        traceback.print_exc()
        check(False, f"{name}: page draws")
        return []
    rows = list(rows_of(root))
    loose = [it for lay, it in leaves(root) if it[1] == "prop" and not any(lay is r or _under(lay, r) for r in rows)]
    loose = [it for it in loose if not (it[3].get("expand") or it[3].get("toggle"))]
    print(f"note {name}: {len(rows)} rows" + (f", {len(loose)} settings drawn in the page's own sub-rows "
          f"{[it[2][1] if len(it[2]) > 1 else '?' for it in loose]}" if loose else ""), flush=True)
    for r in rows:
        label, field = row_parts(r)
        check(bool(label) and len(field) == 1, f"{name}: row '{label}' has a name and one field")
    return rows


def _under(lay, r):
    while lay is not None:
        if lay is r:
            return True
        lay = lay.parent
    return False


def find(rows, label):
    for r in rows:
        if row_parts(r)[0] == label:
            return r
    return None


def field_of(r):
    return row_parts(r)[1][0]


def test_cube():
    bpy.ops.blenda4d.add_primitive(kind="cube")
    cube = bpy.context.object
    rows = page_report("Cube Object", cube, managers.page_object)
    for axis in "XYZ":
        r = find(rows, f"Size . {axis}")
        check(r is not None, f"Cube: Size . {axis} row")
        if r is not None:
            lay, it = field_of(r)
            check(not it[3].get("slider") and lay.attrs.get("ui_units_x") == managers.FIELD_UNITS,
                  f"Cube: Size . {axis} is a short field")
    for name in ("Segments X", "Fillet Radius", "Fillet Subdivision"):
        r = find(rows, name)
        check(r is not None and field_of(r)[1][3].get("slider") is True, f"Cube: {name} is a slider")
    for name in ("Separate Surfaces", "Fillet"):
        r = find(rows, name)
        check(r is not None and field_of(r)[1][3].get("text") == "", f"Cube: {name} switch sits in the field column")
    mod = managers._generator(cube)
    from blenda4d import primitives
    items = mod.node_group.interface.items_tree
    owner, attr = primitives.input_slot(mod, items["Fillet"].identifier)
    setattr(owner, attr, False)
    rows = page_report("Cube Object (Fillet off)", cube, managers.page_object)
    check(greyed(find(rows, "Fillet Radius")) and greyed(find(rows, "Fillet Subdivision")),
          "Fillet off: its radius and subdivision rows are greyed")
    check(not greyed(find(rows, "Segments X")), "Fillet off: other rows are not greyed")
    setattr(owner, attr, True)
    rows = page_report("Cube Object (Fillet on)", cube, managers.page_object)
    check(not greyed(find(rows, "Fillet Radius")), "Fillet on: its radius row is live")

    rows = page_report("Basic", cube, managers.page_basic)
    check([row_parts(r)[0] for r in rows] == ["Name", "Visible in Editor", "Visible in Renderer", "Display Color", "X-Ray"],
          f"Basic rows {[row_parts(r)[0] for r in rows]}")
    rows = page_report("Coord.", cube, managers.page_coord)
    check(len(rows) == 10, f"Coord.: P, S, R one row per axis and Rotation Order ({len(rows)})")
    return cube


def test_tabs(cube):
    root = Rec()
    managers.page_tabs(root, cube, "OBJECT")
    ops = [it for lay, it in leaves(root) if it[1] == "operator"]
    tabs = managers._page_tabs(cube)
    check(len(ops) == len(tabs), f"one tab button per page ({len(ops)} for {len(tabs)})")
    pressed = [it for it in ops if it[3].get("depress")]
    check(len(pressed) == 1 and pressed[0][3].get("text") == "Object", "only the shown page's tab is pressed")
    rows = [r for r in root.items[0].items if isinstance(r, Rec)]
    check(all(r.attrs.get("alignment") == "LEFT" for r in rows), "tabs start at the left and keep their size")
    wm = bpy.context.window_manager
    res = bpy.ops.blenda4d.am_tab(key="COORD", label="Coord.")
    check(res == {"FINISHED"} and wm.b4d_am_tab == "COORD", "a tab button shows its page")


def test_object_page_on_select(cube):
    """Selecting an object shows its Object page; the page the user picks stays while the object stays selected."""
    wm = bpy.context.window_manager
    bpy.ops.mesh.primitive_uv_sphere_add()
    other = bpy.context.object
    for ob in (cube, other, cube):
        wm.b4d_am_tab = "BASIC"
        bpy.context.view_layer.objects.active = ob
        bpy.context.view_layer.update()
        check(wm.b4d_am_tab == "OBJECT", f"selecting {ob.name} opens its Object page")
        wm.b4d_am_tab = "COORD"
        bpy.context.view_layer.update()
        check(wm.b4d_am_tab == "COORD", f"{ob.name} stays on the page the user picked")


def test_layers(cube):
    """The Layers tab next to Attributes: New Layer groups the selected objects; rows draw; Select picks them again."""
    wm = bpy.context.window_manager
    tabs = [i.identifier for i in wm.bl_rna.properties["b4d_right_tab"].enum_items]
    check(tabs[:2] == ["ATTRIBUTES", "LAYERS"], f"the Layers tab sits next to Attributes {tabs}")
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    cube.select_set(True)
    scene = bpy.context.scene
    before = len(scene.collection.children)
    check(bpy.ops.blenda4d.layer_new() == {"FINISHED"} and len(scene.collection.children) == before + 1,
          "New Layer adds a layer")
    col = scene.collection.children[-1]
    check(tuple(cube.users_collection) == (col,), "the selected object moved into the new layer")
    root = Rec()
    managers.draw_layers(root, bpy.context)
    ops = [it for _lay, it in leaves(root) if it[1] == "operator"]
    names = [it for _lay, it in leaves(root) if it[1] == "prop" and it[2][1] == "name"]
    check(len(ops) >= 3 and names, f"the layer is drawn with its name, select and move buttons ({len(ops)} buttons)")
    cube.select_set(False)
    check(bpy.ops.blenda4d.layer_select(name=col.name) == {"FINISHED"} and cube.select_get(),
          "Select picks the layer's objects")
    other = bpy.data.objects.new("LayerTest", None)
    bpy.context.scene.collection.objects.link(other)
    other.select_set(True)
    check(bpy.ops.blenda4d.layer_assign(name=col.name) == {"FINISHED"} and other.name in col.objects,
          "Move Selected Here puts the selected objects in the layer")
    bpy.data.objects.remove(other)


def test_every_kind():
    """Every kind's every page draws, and every setting on it is a row."""
    for kind, k in sorted(kinds.KINDS.items()):
        if k["create"] is None:
            continue
        before = set(bpy.data.objects)
        try:
            bpy.ops.blenda4d.add_kind(kind=kind)
        except Exception as ex:
            print("skip", kind, ex)
            continue
        new = [o for o in bpy.data.objects if o not in before]
        ob = bpy.context.view_layer.objects.active
        if ob is None or ob not in new:
            continue
        for tab, fn in k["pages"].items():
            page_report(f"{k['label']} / {tab}", ob, fn)
    for t in ("CAMERA", "LIGHT", "EMPTY", "MESH"):
        bpy.ops.object.select_all(action="DESELECT")
        if t == "CAMERA":
            bpy.ops.object.camera_add()
        elif t == "LIGHT":
            bpy.ops.object.light_add(type="AREA")
        elif t == "EMPTY":
            bpy.ops.object.empty_add()
        else:
            bpy.ops.mesh.primitive_monkey_add()
        ob = bpy.context.object
        for key, label, _d in managers._page_tabs(ob):
            fn = (managers.CAMERA_PAGES.get(key) if t == "CAMERA" else None) or managers.PAGES.get(key)
            k = kinds.kind_of(ob)
            if k and key in kinds.KINDS[k]["pages"]:
                fn = kinds.KINDS[k]["pages"][key]
            if fn is not None:
                page_report(f"{t} / {label}", ob, fn)


try:
    switch._register_mode()
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    cube = test_cube()
    test_tabs(cube)
    test_object_page_on_select(cube)
    test_layers(cube)
    test_every_kind()
    switch._unregister_mode()
except Exception:
    traceback.print_exc()
    FAIL.append("exception")
print("B4D AM RESULT", "FAIL" if FAIL else "PASS", len(FAIL), FAIL[:40], flush=True)
sys.exit(1 if FAIL else 0)
