# UI run for material tags: the try_ui sample scene, the floor gets an image material, a click on its swatch in the
# Object Manager shows the tag (Tag page, Seamless rows, Coordinates page), a click on the name goes back to the object.
#   BLENDER_USER_CONFIG=<scratch> B4D_OUT=<folder> Blender --factory-startup --enable-event-simulate \
#       --window-geometry 100 60 1700 1000 --python tools/tests/material_tag_ui.py
import importlib.util
import os

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["B4D_STEPS"] = ""
spec = importlib.util.spec_from_file_location("try_ui", os.path.join(ROOT, "tools", "try_ui.py"))
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)
done = ui.PLAN.pop()
W = lambda: bpy.context.window_manager.windows[0]          # noqa: E731


def redraw():
    for a in W().screen.areas:
        a.tag_redraw()


def floor_material():
    img = bpy.data.images.new("ground_grid", 256, 256)
    img.generated_type = "COLOR_GRID"
    mat = bpy.data.materials.new("aerial_rocks")
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bpy.data.objects["Floor"].data.materials.append(mat)
    for a in W().screen.areas:
        if a.type == "VIEW_3D":
            a.spaces.active.shading.type = "MATERIAL"
    redraw()


def click_swatch():
    r = ui.om_region()
    from blenda4d import managers                       # the tags sit just right of the separator after the check
    share, _w = managers._name_column(bpy.context, r, managers.visible_rows(bpy.context))
    x, y = r.x + int(share * r.width + 1.2 * managers.row_height()), ui.row_y(ui.row_index("Floor"))
    ui.ev("MOUSEMOVE", "NOTHING", x, y)
    ui.ev("LEFTMOUSE", "PRESS", x, y)
    ui.ev("LEFTMOUSE", "RELEASE", x, y)


def report(what):
    wm = bpy.context.window_manager
    print("B4D", what, "subject", repr(wm.b4d_am_subject), "active", bpy.context.view_layer.objects.active.name,
          "tags", len(bpy.data.objects["Floor"].b4d_mat_tags), flush=True)


def set_tag(**kw):
    t = bpy.data.objects["Floor"].b4d_mat_tags[0]
    for k, v in kw.items():
        setattr(t, k, v)
    redraw()


def tab(t):
    bpy.context.window_manager.b4d_tag_tab = t
    redraw()


def click_name():
    r = ui.om_region()
    x, y = r.x + 90, ui.row_y(ui.row_index("Floor"))
    ui.ev("MOUSEMOVE", "NOTHING", x, y)
    ui.ev("LEFTMOUSE", "PRESS", x, y)
    ui.ev("LEFTMOUSE", "RELEASE", x, y)


N = lambda k=2: [lambda: None] * k                      # noqa: E731
steps = [floor_material, *N(), lambda: ui.select("Cube"), *N(), click_swatch, *N(), lambda: report("after swatch click"),
         lambda: ui.shot("tag_page"),
         lambda: set_tag(length_u=6.0, length_v=6.0, seamless=True), *N(3), lambda: ui.shot("tag_seamless"),
         lambda: tab("COORD"), *N(), lambda: ui.shot("tag_coord"),
         lambda: tab("BASIC"), *N(), lambda: ui.shot("tag_basic"),
         lambda: tab("TAG"), click_name, *N(), lambda: report("after name click"), lambda: ui.shot("object_again")]
ui.PLAN += steps + [done, lambda: bpy.ops.wm.quit_blender()]
