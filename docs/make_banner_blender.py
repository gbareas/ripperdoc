"""Renders docs/banner.jpg with Blender: the name in hand-drawn, extruded double-stroke
letters, glowing ice blue on black, over a measured curve whose one suspect data point
is caught in a reticle and traced back to its source. Same style as the braindance
banner. The letterforms are defined below as polylines (no font file is used for them).

    blender -b -P docs/make_banner_blender.py
    # or with the bpy module from PyPI (Python 3.11): pip install bpy==4.2.0 numpy pillow
    python docs/make_banner_blender.py

Cycles on the CPU; no GPU needed. Takes about half a minute.
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
OUT_RAW, OUT = HERE / "banner_raw.png", HERE / "banner.jpg"
W, H, SAMPLES = 1600, 420, 64
ICE = (0.45, 0.75, 1.0)
SUB_FONT = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
rng = np.random.default_rng(7)

# letters on a 3.8 x 4 cell; each is a list of polylines
LETTERS = {
    "B": [[(0, 0), (0, 4), (3.1, 4), (3.6, 3.5), (3.6, 2.5), (3.1, 2), (0, 2)],
          [(3.1, 2), (3.8, 1.5), (3.8, 0.5), (3.3, 0), (0, 0)]],
    "R": [[(0, 0), (0, 4), (3.2, 4), (3.8, 3.4), (3.8, 2.6), (3.2, 2), (0, 2)], [(2.0, 2), (3.8, 0)]],
    "A": [[(0, 0), (0, 3), (1, 4), (2.8, 4), (3.8, 3), (3.8, 0)], [(0, 1.7), (3.8, 1.7)]],
    "I": [[(0, 0), (0, 4)]],
    "N": [[(0, 0), (0, 4), (3.8, 0), (3.8, 4)]],
    "P": [[(0, 0), (0, 4), (3.2, 4), (3.8, 3.4), (3.8, 2.6), (3.2, 2), (0, 2)]],
    "O": [[(1, 0), (0, 1), (0, 3), (1, 4), (2.8, 4), (3.8, 3), (3.8, 1), (2.8, 0), (1, 0)]],
    "D": [[(0, 0), (0, 4), (2.8, 4), (3.8, 3), (3.8, 1), (2.8, 0), (0, 0)]],
    "C": [[(3.8, 4), (1, 4), (0, 3), (0, 1), (1, 0), (3.8, 0)]],
    "E": [[(3.8, 4), (0, 4), (0, 0), (3.8, 0)], [(0, 2), (3.0, 2)]],
}
ADVANCE = {"I": 0.0}
GAP = 1.3

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def emission(name, colour, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*colour, 1)
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    return m


GLOW, BLACK = emission("glow", ICE, 6.0), emission("black", (0, 0, 0), 0.0)


def tube(points, radius, mat, y):
    """A polyline in the x-z plane at depth y, drawn as a round tube."""
    c = bpy.data.curves.new("stroke", "CURVE")
    c.dimensions = "3D"
    c.bevel_depth = radius
    c.bevel_resolution = 4
    c.use_fill_caps = True
    sp = c.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for p, (x, z) in zip(sp.points, points):
        p.co = (x, y, z, 1)
    o = bpy.data.objects.new("stroke", c)
    scene.collection.objects.link(o)
    c.materials.append(mat)
    return o


def outlined(points, r_out, r_in, mat=None, y=0.0):
    """Double stroke: a glowing tube with a black one in front, so only its two edges show."""
    tube(points, r_out, mat or GLOW, y)
    tube(points, r_in, BLACK, y - r_out - 0.01)


DEPTH = (0.34, 0.8, -0.27)   # extrusion of the letters: x, depth, z
GLOW_BACK, GLOW_EDGE = emission("glow_back", ICE, 2.5), emission("glow_edge", ICE, 2.0)


def extruded(points, r_out, r_in):
    """A letter stroke with depth: the front double stroke, a thin dimmer copy pushed back
    and down-right, and thin edges joining their corners."""
    dx, dy, dz = DEPTH
    outlined(points, r_out, r_in)
    tube([(x + dx, z + dz) for x, z in points], r_out * 0.3, GLOW_BACK, dy)
    for x, z in points:
        c = bpy.data.curves.new("edge", "CURVE")
        c.dimensions, c.bevel_depth = "3D", r_out * 0.3
        sp = c.splines.new("POLY")
        sp.points.add(1)
        sp.points[0].co, sp.points[1].co = (x, 0.0, z, 1), (x + dx, dy, z + dz, 1)
        o = bpy.data.objects.new("edge", c)
        scene.collection.objects.link(o)
        c.materials.append(GLOW_EDGE)


# title
word, scale, r_out, r_in = "RIPPERDOC", 0.62, 0.15, 0.075
widths = [ADVANCE.get(ch, 3.8) for ch in word]
total = (sum(widths) + GAP * (len(word) - 1)) * scale
x0, z0 = -total / 2, 0.55
for ch, w in zip(word, widths):
    for line in LETTERS[ch]:
        extruded([(x0 + x * scale, z0 + z * scale) for x, z in line], r_out, r_in)
    x0 += (w + GAP) * scale

# a measured curve with its fit and data points, under the title; one point is off,
# caught in a reticle and traced back to its source (the dashed drop line)
x = np.linspace(0, 1, 200)
fit = 0.5 + 0.45 * np.sin(2 * np.pi * (1.5 * x + 0.05)) * np.exp(-1.6 * x)
X, Z = -total / 2 + total * x, -1.6 + 1.5 * fit
tube(list(zip(X, Z)), 0.025, emission("fit", ICE, 4.0), 0.0)
DOTS = emission("dots", ICE, 6.0)
ALERT = emission("alert", ICE, 9.0)
SUSPECT = 13
for k, (xi, fi) in enumerate(zip(X[::10], fit[::10])):
    zi = -1.6 + 1.5 * (fi + rng.normal(0, 0.04))
    if k == SUSPECT:
        zi = -1.6 + 1.5 * (fi + 0.2)
        # reticle: circle with four ticks
        R = 0.32
        ring = [(xi + R * math.cos(t), zi + R * math.sin(t)) for t in np.linspace(0, 2 * np.pi, 49)]
        tube(ring, 0.02, ALERT, 0.0)
        for a in (0, 90, 180, 270):
            c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
            tube([(xi + c * (R - 0.1), zi + s * (R - 0.1)), (xi + c * (R + 0.14), zi + s * (R + 0.14))], 0.02, ALERT, 0.0)
        # dashed trace down to the axis rule
        zz = zi - R - 0.14
        while zz > -1.75:
            tube([(xi, zz), (xi, max(zz - 0.07, -1.8))], 0.008, DOTS, 0.0)
            zz -= 0.14
    ring = [(xi + 0.09 * math.cos(t), zi + 0.09 * math.sin(t)) for t in np.linspace(0, 2 * np.pi, 25)]
    tube(ring, 0.018, ALERT if k == SUSPECT else DOTS, 0.0)
RULE = emission("rule", ICE, 2.0)
for zz in (-1.8, 0.05):
    tube([(-total / 2, zz), (total / 2, zz)], 0.008, RULE, 0.0)

# subtitle in wide-tracked capitals
bpy.ops.object.text_add(location=(0, 0, -2.35), rotation=(math.radians(90), 0, 0))
t = bpy.context.object
t.data.body = "A RESEARCH SUPERVISOR FOR CLAUDE CODE   ·   EVERY CLAIM TRACED TO ITS CODE"
t.data.font = bpy.data.fonts.load(SUB_FONT)
t.data.size = 0.38
t.data.space_character = 1.35
t.data.align_x, t.data.align_y = "CENTER", "CENTER"
SUB = emission("sub", ICE, 3.0)
t.data.materials.append(SUB)

# camera: orthographic, straight on
bpy.ops.object.camera_add(location=(0, -20, 0.2), rotation=(math.radians(90), 0, 0))
cam = bpy.context.object
cam.data.type = "ORTHO"
cam.data.ortho_scale = total * 1.18
scene.camera = cam

world = bpy.data.worlds.new("world")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.004, 0.006, 1)
scene.world = world

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = W, H
scene.view_settings.view_transform = "AgX"

# compositor: soft bloom
scene.use_nodes = True
nt = scene.node_tree
nt.nodes.clear()
rl = nt.nodes.new("CompositorNodeRLayers")
glare = nt.nodes.new("CompositorNodeGlare")
glare.glare_type, glare.quality, glare.size, glare.mix = "FOG_GLOW", "HIGH", 9, -0.1
comp = nt.nodes.new("CompositorNodeComposite")
nt.links.new(rl.outputs["Image"], glare.inputs["Image"])
nt.links.new(glare.outputs["Image"], comp.inputs["Image"])

from PIL import Image  # noqa: E402


def grain(path):
    """Add a little film grain."""
    img = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    img += np.random.default_rng(1).normal(0, 3.0, img.shape[:2])[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


scene.render.filepath = str(OUT_RAW)
bpy.ops.render.render(write_still=True)
grain(OUT_RAW).save(OUT, quality=92, optimize=True)
OUT_RAW.unlink()
print(OUT)
