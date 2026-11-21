"""Renders docs/banner.jpg with Blender: the name as neon-tube letters, each sealed in
its own glass cube on a dark plinth, glowing blue to magenta to red, over a wet
reflective floor. The letterforms are defined below as polylines with rounded bends
(no font file is used for them). A light scanline and chromatic-aberration pass is
added afterwards with Pillow.

    blender -b -P docs/make_banner_blender.py
    # or with the bpy module from PyPI (Python 3.11): pip install bpy==4.2.0 numpy pillow
    python docs/make_banner_blender.py

Cycles on the CPU; no GPU needed. Takes about two minutes (SAMPLES=24 env var for
quick drafts).
"""
import math
import os
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OUT_RAW, OUT = HERE / "banner_raw.png", HERE / "banner.jpg"
W, H, SAMPLES = 1600, 480, int(os.environ.get("SAMPLES", 160))
BLUE, MAGENTA, RED, CYAN = (0.15, 0.25, 1.0), (0.95, 0.1, 0.85), (1.0, 0.08, 0.25), (0.05, 0.85, 1.0)
MONO = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Medium.ttf"
rng = np.random.default_rng(5)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


# ---------------------------------------------------------------- materials
def emission(colour, strength):
    m = bpy.data.materials.new("e")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*colour, 1)
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    return m


def neon_gradient(strength, phase):
    """Emission whose colour runs blue -> magenta -> red across the letter (object space)."""
    m = bpy.data.materials.new("neon")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mix = nt.nodes.new("ShaderNodeMath")
    mix.operation = "MULTIPLY_ADD"
    mix.inputs[1].default_value, mix.inputs[2].default_value = 0.6, phase
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "SUBTRACT"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (*BLUE, 1)
    els[1].position, els[1].color = 1.0, (*RED, 1)
    mid = els.new(0.5)
    mid.color = (*MAGENTA, 1)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["X"], mix.inputs[0])            # x*0.6 + phase
    nt.links.new(mix.outputs[0], add.inputs[0])
    nt.links.new(sep.outputs["Z"], add.inputs[1])            # ... - z*1 (higher = bluer)
    add.inputs[1].default_value = 0
    zs = nt.nodes.new("ShaderNodeMath")
    zs.operation = "MULTIPLY"
    zs.inputs[1].default_value = 0.45
    nt.links.new(sep.outputs["Z"], zs.inputs[0])
    nt.links.new(zs.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], e.inputs["Color"])
    nt.links.new(e.outputs[0], out.inputs[0])
    return m


def principled(name, colour, metallic=0.0, rough=0.4, transmission=0.0, ior=1.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*colour, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = ior
    return m


GLASS = principled("glass", (0.92, 0.95, 1.0), rough=0.04, transmission=1.0, ior=1.3)
PLINTH = principled("plinth", (0.02, 0.02, 0.025), metallic=0.8, rough=0.35)
ELECTRODE = principled("electrode", (0.5, 0.5, 0.55), metallic=1.0, rough=0.25)
WIRE_R = principled("wire_r", (0.6, 0.02, 0.05), rough=0.5)
WIRE_K = principled("wire_k", (0.01, 0.01, 0.01), rough=0.5)
FLOOR = principled("floor", (0.008, 0.006, 0.012), metallic=0.6, rough=0.12)


def link(obj, mat):
    scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def tube(points, radius, mat, smooth=False):
    """A 3-D polyline (or a smooth NURBS through it) drawn as a round tube."""
    c = bpy.data.curves.new("t", "CURVE")
    c.dimensions, c.bevel_depth, c.bevel_resolution, c.use_fill_caps = "3D", radius, 6, True
    sp = c.splines.new("NURBS" if smooth else "POLY")
    sp.points.add(len(points) - 1)
    for p, xyz in zip(sp.points, points):
        p.co = (*xyz, 1)
    if smooth:
        sp.use_endpoint_u, sp.order_u = True, 3
    return link(bpy.data.objects.new("t", c), mat)


def rounded(pts, r=0.45, n=6):
    """Replace each interior corner of a 2-D polyline by a circular-ish fillet of radius r."""
    pts = [np.array(p, float) for p in pts]
    closed = np.allclose(pts[0], pts[-1])
    if closed:
        pts = pts[:-1]
        idx = range(len(pts))
    else:
        idx = range(1, len(pts) - 1)
    out = [] if closed else [pts[0]]
    for i in idx:
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
        u, v = (a - b), (c - b)
        lu, lv = np.linalg.norm(u), np.linalg.norm(v)
        rr = min(r, lu / 2.05, lv / 2.05)
        p0, p1 = b + u / lu * rr, b + v / lv * rr
        for t in np.linspace(0, 1, n):                      # quadratic Bezier p0 -> b -> p1
            out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t ** 2 * p1)
    out.append(out[0] if closed else pts[-1])
    return out


# ---------------------------------------------------------------- letters
LETTERS = {
    "R": [[(0, 0), (0, 4), (3.2, 4), (3.8, 3.4), (3.8, 2.6), (3.2, 2), (0, 2)], [(1.9, 2), (3.8, 0)]],
    "I": [[(1.9, 0), (1.9, 4)]],
    "P": [[(0, 0), (0, 4), (3.2, 4), (3.8, 3.4), (3.8, 2.6), (3.2, 2), (0, 2)]],
    "E": [[(3.8, 4), (0, 4), (0, 0), (3.8, 0)], [(0, 2), (3.0, 2)]],
    "D": [[(0, 0), (0, 4), (2.4, 4), (3.8, 2.6), (3.8, 1.4), (2.4, 0), (0, 0)]],
    "O": [[(1.2, 0), (0, 1.2), (0, 2.8), (1.2, 4), (2.6, 4), (3.8, 2.8), (3.8, 1.2), (2.6, 0), (1.2, 0)]],
    "C": [[(3.8, 3.6), (3.2, 4), (1.2, 4), (0, 2.8), (0, 1.2), (1.2, 0), (3.2, 0), (3.8, 0.4)]],
}
CUBE, GAP = 1.0, 0.14
word = "RIPPERDOC"
x_start = -(len(word) * CUBE + (len(word) - 1) * GAP) / 2 + CUBE / 2
Z0 = 0.62                                                   # cube centre height
LS = 0.125                                                  # letter scale inside the cube

for k, ch in enumerate(word):
    cx = x_start + k * (CUBE + GAP)
    tilt = rng.normal(0, 2.0)
    # plinth and glass cube
    bpy.ops.mesh.primitive_cube_add(size=CUBE, location=(cx, 0, Z0))
    cube = bpy.context.object
    cube.data.materials.append(GLASS)
    bev = cube.modifiers.new("bev", "BEVEL")
    bev.width, bev.segments = 0.05, 4
    bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, 0, Z0 - CUBE / 2 - 0.06))
    pl = bpy.context.object
    pl.scale = (CUBE * 1.04, CUBE * 1.04, 0.12)
    pl.data.materials.append(PLINTH)
    b2 = pl.modifiers.new("bev", "BEVEL")
    b2.width, b2.segments = 0.03, 3
    # the neon tube, on a plane slightly behind the cube centre
    mat = neon_gradient(2.6, -0.15 + 1.0 * k / (len(word) - 1))
    ends = []
    for line in LETTERS[ch]:
        pts = rounded(line, r=0.55)
        xyz = [(cx + (x - 1.9) * LS, 0.05, Z0 + (z - 2.0) * LS) for x, z in pts]
        tube(xyz, 0.03, mat)
        tube([(x, y - 0.02, z) for x, y, z in xyz], 0.012, emission((1, 0.8, 1), 0.9))   # hot core
        ends += [xyz[0], xyz[-1]]
    # electrodes at the open ends and wires down to the plinth
    for (x, y, z) in ends[:2]:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=0.08, location=(x, y + 0.06, z))
        bpy.context.object.data.materials.append(ELECTRODE)
        base = (x + rng.uniform(-0.1, 0.1), 0.25, Z0 - CUBE / 2 + 0.04)
        mid = ((x + base[0]) / 2 + rng.uniform(-0.15, 0.15), 0.3, (z + base[2]) / 2)
        tube([(x, y + 0.08, z), mid, base], 0.008, WIRE_R if rng.random() < 0.5 else WIRE_K, smooth=True)
    # power cable out of the back of the plinth
    tube([(cx + 0.3, 0.4, Z0 - CUBE / 2 - 0.08), (cx + 0.35, 0.9, Z0 - CUBE / 2 - 0.16),
          (cx + 0.2 + rng.uniform(-0.3, 0.3), 1.6, -0.12)], 0.02, WIRE_K, smooth=True)

title_l, title_r = x_start - CUBE / 2, x_start + (len(word) - 1) * (CUBE + GAP) + CUBE / 2


# ---------------------------------------------------------------- taglines
def text(body, size, loc, mat, align):
    bpy.ops.object.text_add(location=loc, rotation=(math.radians(90), 0, 0))
    t = bpy.context.object
    t.data.body, t.data.font, t.data.size = body, bpy.data.fonts.load(MONO), size
    t.data.space_character, t.data.align_x, t.data.align_y = 1.12, align, "CENTER"
    t.data.materials.append(mat)


TZ = Z0 + CUBE / 2 + 0.3
text("// RESEARCH SUPERVISOR FOR CLAUDE CODE", 0.2, (title_l, 0, TZ), emission(CYAN, 3.0), "LEFT")
text("EVERY CLAIM TRACED TO ITS CODE //", 0.2, (title_r, 0, TZ), emission(MAGENTA, 2.2), "RIGHT")

# ---------------------------------------------------------------- floor, back wall, lights
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 10, 0))
bpy.context.object.data.materials.append(FLOOR)
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 6, 10), rotation=(math.radians(90), 0, 0))
bpy.context.object.data.materials.append(principled("wall", (0.006, 0.004, 0.01), rough=0.8))


def light(kind, loc, rot, colour, energy, size=2.0):
    bpy.ops.object.light_add(type=kind, location=loc, rotation=[math.radians(a) for a in rot])
    lt = bpy.context.object.data
    lt.color, lt.energy = colour, energy
    if kind == "AREA":
        lt.size = size


light("AREA", (-7, -3, 4), (55, 0, -60), BLUE, 1400, 5)
light("AREA", (7, -3, 4), (55, 0, 60), RED, 1400, 5)
light("AREA", (0, -4, 6), (35, 0, 0), (0.9, 0.85, 1.0), 300, 10)

# ---------------------------------------------------------------- camera, render
bpy.ops.object.camera_add(location=(0, -12.0, 3.1))
cam = bpy.context.object
cam.rotation_euler = (math.radians(79), 0, 0)
cam.data.lens = 37
scene.camera = cam

world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.003, 0.002, 0.006, 1)
scene.world = world

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.cycles.max_bounces, scene.cycles.transmission_bounces = 12, 12
scene.render.resolution_x, scene.render.resolution_y = W, H
scene.view_settings.view_transform = "Standard"

scene.use_nodes = True
nt = scene.node_tree
nt.nodes.clear()
rl, comp = nt.nodes.new("CompositorNodeRLayers"), nt.nodes.new("CompositorNodeComposite")
glare = nt.nodes.new("CompositorNodeGlare")
glare.glare_type, glare.quality, glare.size, glare.mix = "FOG_GLOW", "HIGH", 8, -0.2
nt.links.new(rl.outputs["Image"], glare.inputs["Image"])
nt.links.new(glare.outputs["Image"], comp.inputs["Image"])

scene.render.filepath = str(OUT_RAW)
bpy.ops.render.render(write_still=True)

# ---------------------------------------------------------------- light post-processing
from PIL import Image  # noqa: E402

img = np.asarray(Image.open(OUT_RAW).convert("RGB"), dtype=np.float32)
h, w, _ = img.shape
g = np.random.default_rng(11)
img[..., 0] = np.roll(img[..., 0], -1, axis=1)             # slight chromatic aberration
img[..., 2] = np.roll(img[..., 2], 1, axis=1)
img[::3] *= 0.93                                            # faint scanlines
img += g.normal(0, 2.5, (h, w))[..., None]                  # grain
yy, xx = np.mgrid[0:h, 0:w]
vig = 1 - 0.3 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2 * 0.5)
img *= np.clip(vig, 0.6, 1)[..., None]
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(OUT, quality=92, optimize=True)
OUT_RAW.unlink()
print(OUT)
