"""Renders docs/banner.jpg with Blender: a cyberpunk street clinic where a result is on
the operating table. A holographic plot lies on the table, a robotic arm's laser
scalpel cuts into its one suspect data point, and a trace runs from that point to the
line of code that produced it. The title is drawn as neon tubes (own letterforms, no
font file), and a glitch, scanline and rain pass is added afterwards with Pillow.

    blender -b -P docs/make_banner_blender.py
    # or with the bpy module from PyPI (Python 3.11): pip install bpy==4.2.0 numpy pillow
    python docs/make_banner_blender.py

Cycles on the CPU; no GPU needed. Takes about a minute and a half (SAMPLES=24 env var for quick drafts).
"""
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
OUT_RAW, OUT = HERE / "banner_raw.png", HERE / "banner.jpg"
W, H, SAMPLES = 1600, 560, int(__import__("os").environ.get("SAMPLES", 96))
MAGENTA, CYAN, RED, WHITE = (1.0, 0.06, 0.45), (0.05, 0.85, 1.0), (1.0, 0.04, 0.03), (0.85, 0.95, 1.0)
MONO = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Medium.ttf"
JP = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
rng = np.random.default_rng(3)

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


def metal(colour=(0.02, 0.02, 0.025), rough=0.25):
    m = bpy.data.materials.new("m")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*colour, 1)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = rough
    return m


def link(obj, mat):
    scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def tube(points, radius, mat):
    """A 3-D polyline drawn as a round tube."""
    c = bpy.data.curves.new("t", "CURVE")
    c.dimensions, c.bevel_depth, c.bevel_resolution, c.use_fill_caps = "3D", radius, 4, True
    sp = c.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for p, xyz in zip(sp.points, points):
        p.co = (*xyz, 1)
    return link(bpy.data.objects.new("t", c), mat)


def cylinder(a, b, r, mat):
    a, b = Vector(a), Vector(b)
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=(b - a).length, location=(a + b) / 2, vertices=24)
    o = bpy.context.object
    o.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return o


def sphere(p, r, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=p, segments=24, ring_count=12)
    bpy.context.object.data.materials.append(mat)
    bpy.ops.object.shade_smooth()


def box(centre, size, mat):
    bpy.ops.mesh.primitive_cube_add(location=centre)
    o = bpy.context.object
    o.scale = [s / 2 for s in size]
    o.data.materials.append(mat)
    return o


def text(body, font, size, loc, mat, align="LEFT", spacing=1.0, rot=(90, 0, 0)):
    bpy.ops.object.text_add(location=loc, rotation=[math.radians(a) for a in rot])
    t = bpy.context.object
    t.data.body, t.data.font, t.data.size = body, bpy.data.fonts.load(font), size
    t.data.space_character, t.data.align_x, t.data.align_y = spacing, align, "CENTER"
    t.data.materials.append(mat)
    return t


NEON_M, NEON_M_DIM = emission(MAGENTA, 7.0), emission(MAGENTA, 2.0)
NEON_C, NEON_C_DIM = emission(CYAN, 8.0), emission(CYAN, 2.0)
NEON_R, NEON_W = emission(RED, 9.0), emission(WHITE, 4.0)
BLACK = emission((0, 0, 0), 0.0)
STEEL = metal()

# ---------------------------------------------------------------- title, neon tubes
LETTERS = {
    "R": [[(0, 0), (0, 4), (3.2, 4), (3.8, 3.4), (3.8, 2.6), (3.2, 2), (0, 2)], [(2.0, 2), (3.8, 0)]],
    "I": [[(0, 0), (0, 4)]],
    "P": [[(0, 0), (0, 4), (3.2, 4), (3.8, 3.4), (3.8, 2.6), (3.2, 2), (0, 2)]],
    "E": [[(3.8, 4), (0, 4), (0, 0), (3.8, 0)], [(0, 2), (3.0, 2)]],
    "D": [[(0, 0), (0, 4), (2.8, 4), (3.8, 3), (3.8, 1), (2.8, 0), (0, 0)]],
    "O": [[(1, 0), (0, 1), (0, 3), (1, 4), (2.8, 4), (3.8, 3), (3.8, 1), (2.8, 0), (1, 0)]],
    "C": [[(3.8, 4), (1, 4), (0, 3), (0, 1), (1, 0), (3.8, 0)]],
}
TY = -3.0                       # title plane, in front of the clinic
word, s = "RIPPERDOC", 0.4
x0, z0 = 0.9 - 8.1, 0.6
for ch in word:
    w = 0.0 if ch == "I" else 3.8
    for line in LETTERS[ch]:
        pts = [(x0 + x * s, TY, z0 + z * s) for x, z in line]
        tube(pts, 0.065, NEON_M)                                   # neon tube
        tube([(x, y - 0.06, z) for x, y, z in pts], 0.022, NEON_W)  # hot white core
        tube([(x + 0.07, y + 0.25, z - 0.07) for x, y, z in pts], 0.03, NEON_M_DIM)  # shadow copy
    x0 += (w + 1.25) * s
title_right = x0 - 1.25 * s
title_left = 0.9 - 8.1
tube([(title_left, TY, 0.3), (title_right, TY, 0.3)], 0.014, NEON_C)
text("// RESEARCH SUPERVISOR FOR CLAUDE CODE", MONO, 0.3, (title_left, TY, -0.05), NEON_C, spacing=1.1)
text("EVERY CLAIM TRACED TO ITS CODE //", MONO, 0.3, (title_right, TY, -0.05), NEON_M_DIM, align="RIGHT", spacing=1.1)
text("> verdict: REVISE_", MONO, 0.2, (title_left, TY, -0.5), NEON_R, spacing=1.05)

# ---------------------------------------------------------------- the clinic, dim and far behind the title
NEON_M, NEON_M_DIM = emission(MAGENTA, 2.5), emission(MAGENTA, 0.8)
NEON_C, NEON_C_DIM = emission(CYAN, 2.5), emission(CYAN, 0.7)
NEON_R, NEON_W = emission(RED, 5.0), emission(WHITE, 1.5)
CLINIC_DZ = 2.8
TX, TYb = 5.6, 7.5              # operating table centre (x, y)
before_clinic = set(bpy.data.objects)
box((TX, TYb, -0.55), (7.6, 2.2, 0.22), STEEL)
box((TX, TYb, -1.6), (0.9, 0.9, 2.0), STEEL)
tube([(TX - 3.8, TYb - 1.11, -0.44), (TX + 3.8, TYb - 1.11, -0.44)], 0.025, NEON_C)   # edge light
tube([(TX - 3.8, TYb - 1.11, -0.66), (TX + 3.8, TYb - 1.11, -0.66)], 0.015, NEON_M_DIM)

# holographic plot lying on the table, tilted towards the camera
PX0, PX1, PZ0 = TX - 3.4, TX + 1.5, -0.25
xs = np.linspace(0, 1, 160)
fit = 0.45 + 0.4 * np.sin(2 * np.pi * (1.3 * xs + 0.1)) * np.exp(-1.2 * xs)


def on_plot(u, v):
    return (PX0 + (PX1 - PX0) * u, TYb - 0.2 + 0.35 * v, PZ0 + 2.1 * v)


# hologram panel: a faint glowing sheet with a bright frame
bpy.ops.mesh.primitive_plane_add(size=1)
pl = bpy.context.object
a, b, c = Vector(on_plot(-0.04, -0.05)), Vector(on_plot(1.04, -0.05)), Vector(on_plot(-0.04, 1.08))
me = pl.data
for v, p_ in zip(me.vertices, [a, b, c + (b - a), c]):
    v.co = p_
me.vertices[2].co, me.vertices[3].co = c, c + (b - a)
pl.data.materials.append(emission(CYAN, 0.12))
fr = [tuple(a), tuple(b), tuple(c + (b - a)), tuple(c), tuple(a)]
tube(fr, 0.01, NEON_C_DIM)
for corner, d1, d2 in ((a, b - a, c - a), (b, a - b, c - a), (c, b - a, a - c), (c + (b - a), a - b, a - c)):
    tube([tuple(corner + d1.normalized() * 0.35), tuple(corner), tuple(corner + d2.normalized() * 0.35)], 0.025, NEON_C)
tube([on_plot(0, 0), on_plot(1, 0)], 0.012, NEON_C_DIM)            # axes
tube([on_plot(0, 0), on_plot(0, 1)], 0.012, NEON_C_DIM)
for g in (0.25, 0.5, 0.75):
    tube([on_plot(0, g), on_plot(1, g)], 0.004, NEON_C_DIM)
tube([on_plot(u, f) for u, f in zip(xs, fit)], 0.03, NEON_C)
SUSPECT = 7
for k, u in enumerate(xs[::12]):
    f = fit[k * 12] + rng.normal(0, 0.03)
    if k == SUSPECT:
        f += 0.34
        suspect = Vector(on_plot(u, f))
        ring = [(suspect.x + 0.16 * math.cos(t), suspect.y, suspect.z + 0.16 * math.sin(t))
                for t in np.linspace(0, 2 * np.pi, 33)]
        tube(ring, 0.03, NEON_R)
    sphere(on_plot(u, f), 0.065, NEON_R if k == SUSPECT else NEON_C)

# the trace: from the suspect point down the table to the offending line of code
CODE_X, CODE_Y = TX + 2.1, TYb + 0.2
lines = [0.9, 0.6, 1.1, 0.4, 0.8, 1.2, 0.7, 0.5, 1.0, 0.65, 0.85, 0.5]
BAD = 6
for i, L in enumerate(lines):
    z = 1.7 - i * 0.17
    ind = 0.15 if i in (2, 3, 6, 7) else 0.0
    mat = NEON_R if i == BAD else NEON_C_DIM
    tube([(CODE_X + ind, CODE_Y, z), (CODE_X + ind + L, CODE_Y, z)], 0.045 if i == BAD else 0.018, mat)
    if i == BAD:
        bad = Vector((CODE_X - 0.08, CODE_Y, z))
tube([(CODE_X - 0.18, CODE_Y, 1.85), (CODE_X - 0.18, CODE_Y, -0.3)], 0.006, NEON_C_DIM)   # gutter
mid = Vector((bad.x - 0.35, suspect.y - 0.05, suspect.z))
dash_a = [suspect + (mid - suspect) * t for t in np.linspace(0.12, 1, 9)]
for a, b in zip(dash_a[::2], dash_a[1::2]):
    tube([tuple(a), tuple(b)], 0.03, NEON_R)
    tube([tuple(a), tuple(b)], 0.01, NEON_W)
tube([tuple(mid), (mid.x, mid.y, bad.z), tuple(bad)], 0.025, NEON_R)
text("L42", MONO, 0.13, (CODE_X - 0.55, CODE_Y, bad.z), NEON_R, align="RIGHT")

# robotic arm with a laser scalpel, coming down from the ceiling
EMIT = Vector((suspect.x - 0.9, suspect.y - 0.2, suspect.z + 1.45))
joints = [Vector((TX - 3.6, TYb + 0.8, 6.5)), Vector((TX - 3.0, TYb + 0.4, 2.6)), Vector((EMIT.x - 0.6, EMIT.y, EMIT.z + 0.55)), EMIT]
for a, b in zip(joints, joints[1:]):
    cylinder(a, b, 0.16, STEEL)
    tube([tuple(a + Vector((0, -0.12, 0))), tuple(b + Vector((0, -0.12, 0)))], 0.008, NEON_M_DIM)
for j in joints[:-1]:
    sphere(j, 0.25, STEEL)
    ring = [(j.x + 0.2 * math.cos(t), j.y - 0.02, j.z + 0.2 * math.sin(t)) for t in np.linspace(0, 2 * np.pi, 33)]
    tube(ring, 0.012, NEON_C)
cylinder(EMIT, EMIT + (suspect - EMIT).normalized() * 0.25, 0.07, STEEL)
tip = EMIT + (suspect - EMIT).normalized() * 0.27
tube([tuple(tip), tuple(suspect)], 0.04, NEON_R)            # the beam
tube([tuple(tip), tuple(suspect)], 0.006, NEON_W)
for _ in range(28):                                         # sparks where it cuts
    d = Vector(rng.normal(0, 1, 3)).normalized() * rng.uniform(0.1, 0.5)
    tube([tuple(suspect), tuple(suspect + d)], 0.005, NEON_W)

# second arm holding a scanner over the plot
joints2 = [Vector((TX + 3.0, TYb + 1.0, 6.5)), Vector((TX + 2.2, TYb + 0.5, 2.9)), Vector((TX - 0.2, TYb, 2.3))]
for a, b in zip(joints2, joints2[1:]):
    cylinder(a, b, 0.11, STEEL)
for j in joints2:
    sphere(j, 0.17, STEEL)
scan = joints2[-1]
box(tuple(scan + Vector((0, 0, -0.12))), (0.9, 0.3, 0.1), STEEL)
tube([tuple(scan + Vector((-0.42, -0.16, -0.18))), tuple(scan + Vector((0.42, -0.16, -0.18)))], 0.014, NEON_C)

# surgical lamp ring overhead
bpy.ops.mesh.primitive_torus_add(location=(TX - 0.6, TYb + 0.3, 3.55), major_radius=0.8, minor_radius=0.05,
                                 rotation=(math.radians(76), 0, 0))
bpy.context.object.data.materials.append(emission(WHITE, 6.0))
bpy.ops.mesh.primitive_torus_add(location=(TX - 0.6, TYb + 0.35, 3.55), major_radius=0.92, minor_radius=0.08,
                                 rotation=(math.radians(76), 0, 0))
bpy.context.object.data.materials.append(STEEL)

# vertical neon sign at the right edge: "ripperdoc" in katakana
SIGN_X = TX + 4.6
box((SIGN_X, TYb + 0.5, 1.2), (0.62, 0.12, 3.6), STEEL)
for i, ch in enumerate("リッパードク"):
    text(ch, JP, 0.42 if ch not in "ッー" else 0.34, (SIGN_X, TYb + 0.42, 2.65 - i * 0.56), NEON_M,
         align="CENTER")
tube([(SIGN_X - 0.33, TYb + 0.43, -0.6), (SIGN_X - 0.33, TYb + 0.43, 3.0)], 0.01, NEON_C)

# lift the whole clinic so it sits above and behind the title
for o in set(bpy.data.objects) - before_clinic:
    o.location.z += CLINIC_DZ

# wet floor and back wall
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 8, -2.6))
floor = bpy.context.object
floor.data.materials.append(metal((0.01, 0.01, 0.015), 0.08))
GRID = emission(MAGENTA, 0.5)
for gx in np.arange(-24, 25, 1.6):
    tube([(gx, -6, -2.59), (gx * 1.0, 30, -2.59)], 0.006, GRID)
for gy in np.arange(-4, 30, 1.6):
    tube([(-30, gy, -2.59), (30, gy, -2.59)], 0.006, GRID)
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 14, 10), rotation=(math.radians(90), 0, 0))
bpy.context.object.data.materials.append(metal((0.012, 0.01, 0.02), 0.6))
for i in range(14):                                         # distant window lights on the wall
    x, z = rng.uniform(-20, 20), rng.uniform(-1.5, 8)
    col = [MAGENTA, CYAN, WHITE][rng.integers(3)]
    box((x, 13.95, z), (rng.uniform(0.2, 1.4), 0.02, rng.uniform(0.04, 0.12)), emission(col, rng.uniform(0.15, 0.5)))

# lights so the steel shows: magenta and cyan rims, a cold spot from the lamp
def light(kind, loc, rot, colour, energy, size=2.0):
    bpy.ops.object.light_add(type=kind, location=loc, rotation=[math.radians(a) for a in rot])
    lt = bpy.context.object.data
    lt.color, lt.energy = colour, energy
    if kind == "AREA":
        lt.size = size
    elif kind == "SPOT":
        lt.spot_size, lt.spot_blend = math.radians(40), 0.4


light("AREA", (TX - 6, TYb - 2, 4 + CLINIC_DZ), (60, 0, -70), MAGENTA, 900, 4)
light("AREA", (TX + 6, TYb - 2, 3 + CLINIC_DZ), (60, 0, 70), CYAN, 700, 4)
light("SPOT", (TX - 0.6, TYb + 0.3, 3.4 + CLINIC_DZ), (0, 0, 0), WHITE, 250)
light("AREA", (TX, TYb - 6, 0.5), (90, 0, 0), (0.6, 0.7, 1.0), 300, 8)

# ---------------------------------------------------------------- camera, render
bpy.ops.object.camera_add(location=(0.9, -22.0, 2.3))
cam = bpy.context.object
cam.rotation_euler = (math.radians(88.5), 0, 0)
cam.data.lens = 35
scene.camera = cam

world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.002, 0.001, 0.004, 1)
scene.world = world

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = W, H
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Punchy"

scene.use_nodes = True
nt = scene.node_tree
nt.nodes.clear()
rl, comp = nt.nodes.new("CompositorNodeRLayers"), nt.nodes.new("CompositorNodeComposite")
glare = nt.nodes.new("CompositorNodeGlare")
glare.glare_type, glare.quality, glare.size, glare.mix = "FOG_GLOW", "HIGH", 9, 0.0
nt.links.new(rl.outputs["Image"], glare.inputs["Image"])
nt.links.new(glare.outputs["Image"], comp.inputs["Image"])

scene.render.filepath = str(OUT_RAW)
bpy.ops.render.render(write_still=True)

# ---------------------------------------------------------------- glitch, scanlines, rain
from PIL import Image  # noqa: E402

img = np.asarray(Image.open(OUT_RAW).convert("RGB"), dtype=np.float32)
h, w, _ = img.shape
g = np.random.default_rng(11)
# chromatic aberration: red left, blue right
img[..., 0] = np.roll(img[..., 0], -2, axis=1)
img[..., 2] = np.roll(img[..., 2], 2, axis=1)
# a few horizontal glitch slices through the title
for _ in range(3):
    y0 = int(g.uniform(0.15, 0.55) * h)
    hh = int(g.integers(2, 9))
    img[y0:y0 + hh, : w // 2] = np.roll(img[y0:y0 + hh, : w // 2], int(g.integers(-14, 14)), axis=1)
# rain streaks
rain = np.zeros((h, w), np.float32)
for _ in range(900):
    x, y, L = int(g.integers(0, w)), int(g.integers(-40, h)), int(g.integers(12, 40))
    ys = np.arange(max(y, 0), min(y + L, h))
    xs_ = np.clip(x + (ys - y) * 0.12, 0, w - 1).astype(int)
    rain[ys, xs_] += g.uniform(6, 16)
img += rain[..., None] * np.array([0.7, 0.8, 1.0])
# scanlines, grain, vignette
img[::3] *= 0.86
img += g.normal(0, 3.0, (h, w))[..., None]
yy, xx = np.mgrid[0:h, 0:w]
vig = 1 - 0.35 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2 * 0.5)
img *= np.clip(vig, 0.55, 1)[..., None]
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(OUT, quality=92, optimize=True)
OUT_RAW.unlink()
print(OUT)
