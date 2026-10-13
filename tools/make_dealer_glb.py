#!/usr/bin/env python3
"""Generate the 3D dealer (GLB / glTF 2.0 binary) for the card games.

A stylised, low-poly upper-body model of the dealer from the BlackJack /
Casino sprites: grey swept-back hair, moustache, slate-navy suit over an
olive waistcoat, white wing collar, black bow tie, and the tall wooden
chair back behind him. Built from code so it can be tweaked and rebuilt.

Conventions: metres, Y up, the dealer faces +Z (towards the players),
origin on the floor under the dealer. The table top is assumed at about
y = 0.95; everything below the waist is left out.

Rig: rigid parts on a node hierarchy (no skinning), so it loads anywhere.
Animations, named after the sprite frames they replace:
  Idle      4.0 s loop  breathing, small head drift      (dl_idle)
  Prepare   2.0 s       hands meet in front, shuffle tap (dl_prepare)
  Deal      1.6 s       right hand slides a card out      (dl_arrival/mid/return)
  Look      2.4 s       turns his head to the side        (dl_aim/profile)
  Nod       1.6 s       eyes-down nod when a hand ends    (dl_complete)
The card in the right hand ("HeldCard") is scaled to 0 except while
dealing.

Usage: python3 tools/make_dealer_glb.py [output.glb]
Requires: numpy, Pillow
"""
import io
import json
import math
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "..", "assets", "source")

# Palette sampled from the dealer sprites (lifted slightly for PBR lighting).
C = {
    "jacket": (47, 58, 70), "jacket_dark": (30, 37, 46), "lapel": (38, 47, 58),
    "vest": (72, 66, 48), "vest_dark": (52, 47, 34), "shirt": (232, 226, 212),
    "tie": (30, 30, 32), "skin": (205, 160, 128), "skin_shadow": (176, 128, 100),
    "hair": (104, 100, 92), "hair_light": (146, 142, 132), "hair_dark": (74, 70, 64),
    "mustache": (88, 80, 72), "wood": (101, 70, 44), "wood_light": (146, 108, 66),
    "wood_dark": (66, 44, 26), "brass": (201, 162, 90),
}
srgb = lambda c: [round((v / 255) ** 2.2, 4) for v in c] + [1.0]


# ===================================================================== mesh

class Mesh:
    """Positions, normals, optional UVs and triangle indices."""

    def __init__(self, pos, idx, uv=None, nrm=None):
        self.pos = np.asarray(pos, np.float32)
        self.idx = np.asarray(idx, np.uint32).reshape(-1, 3)
        self.uv = None if uv is None else np.asarray(uv, np.float32)
        self.nrm = smooth_normals(self.pos, self.idx) if nrm is None else np.asarray(nrm, np.float32)

    def transformed(self, m):
        p = self.pos @ m[:3, :3].T + m[:3, 3]
        n = self.nrm @ np.linalg.inv(m[:3, :3])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        return Mesh(p, self.idx, self.uv, n)


def merge(*meshes):
    pos, idx, nrm, uv, off = [], [], [], [], 0
    for m in meshes:
        pos.append(m.pos); nrm.append(m.nrm); idx.append(m.idx + off); off += len(m.pos)
        uv.append(m.uv if m.uv is not None else np.zeros((len(m.pos), 2), np.float32))
    has_uv = any(m.uv is not None for m in meshes)
    return Mesh(np.vstack(pos), np.vstack(idx), np.vstack(uv) if has_uv else None, np.vstack(nrm))


def smooth_normals(pos, idx):
    """Area-weighted vertex normals, shared across vertices at the same
    position (sphere poles and seams) so there are no degenerate ones."""
    a, b, c = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
    fn = np.cross(b - a, c - a)
    _, group = np.unique(np.round(pos, 6), axis=0, return_inverse=True)
    group = group.reshape(-1)
    n = np.zeros((group.max() + 1, 3))
    for k in range(3):
        np.add.at(n, group[idx[:, k]], fn)
    n = n[group]
    length = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.where(length > 1e-10, n / np.maximum(length, 1e-12), [0.0, 1.0, 0.0])
    return n.astype(np.float32)


def compact(m):
    """Drop vertices no triangle uses."""
    used = np.unique(m.idx)
    remap = np.full(len(m.pos), -1)
    remap[used] = np.arange(len(used))
    return Mesh(m.pos[used], remap[m.idx], None if m.uv is None else m.uv[used], m.nrm[used])


def mat(t=(0, 0, 0), r=(0, 0, 0), s=(1, 1, 1)):
    """4x4 from translation, XYZ euler (degrees) and scale."""
    rx, ry, rz = np.radians(r)
    Rx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
    Ry = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
    Rz = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
    m = np.eye(4)
    m[:3, :3] = Rz @ Ry @ Rx @ np.diag(s)
    m[:3, 3] = t
    return m


def grid_indices(rows, cols, wrap=False):
    """Quads over a (rows+1) x (cols+1) vertex grid, CCW seen from outside."""
    idx = []
    w = cols + 1
    for i in range(rows):
        for j in range(cols):
            a, b = i * w + j, i * w + j + 1
            c, d = a + w, b + w
            idx += [(a, c, b), (b, c, d)]
    return idx


def sphere(rx=1, ry=1, rz=1, seg=24, rings=16, center=(0, 0, 0)):
    """UV sphere; theta=0 faces +Z so the seam is at the back."""
    pos, uv = [], []
    for i in range(rings + 1):
        phi = math.pi * i / rings                    # 0 top .. pi bottom
        for j in range(seg + 1):
            th = 2 * math.pi * j / seg - math.pi     # -pi..pi, 0 at front
            x, y, z = math.sin(phi) * math.sin(th), math.cos(phi), math.sin(phi) * math.cos(th)
            pos.append((center[0] + rx * x, center[1] + ry * y, center[2] + rz * z))
            uv.append((j / seg, i / rings))
    return Mesh(pos, grid_indices(rings, seg), uv)


def loft(sections, seg=32, power=2.0, cap_top=True, cap_bottom=True):
    """Superelliptic cross-sections [(y, half_width, half_depth, z_offset)],
    listed top to bottom. UVs are cylindrical: u=0.5 at the front."""
    pos, uv = [], []
    ys = [s[0] for s in sections]
    y0, y1 = max(ys), min(ys)
    for (y, a, b, zo) in sections:
        for j in range(seg + 1):
            th = 2 * math.pi * j / seg - math.pi
            s, c = math.sin(th), math.cos(th)
            x = a * np.sign(s) * abs(s) ** (2 / power)
            z = b * np.sign(c) * abs(c) ** (2 / power) + zo
            pos.append((x, y, z))
            uv.append((j / seg, (y0 - y) / (y0 - y1)))
    idx = grid_indices(len(sections) - 1, seg)
    w = seg + 1
    if cap_top:
        y, a, b, zo = sections[0]
        pos.append((0, y, zo)); uv.append((0.5, 0.0)); ci = len(pos) - 1
        idx += [(ci, j, j + 1) for j in range(seg)]
    if cap_bottom:
        y, a, b, zo = sections[-1]
        base = (len(sections) - 1) * w
        pos.append((0, y, zo)); uv.append((0.5, 1.0)); ci = len(pos) - 1
        idx += [(ci, base + j + 1, base + j) for j in range(seg)]
    return Mesh(pos, idx, uv)


def tube(length, r0, r1, seg=16, rings=6, power=2.0, squash=1.0):
    """Tapered limb from the origin down -Y, capped both ends."""
    secs = [(-length * i / rings, (r0 + (r1 - r0) * i / rings), (r0 + (r1 - r0) * i / rings) * squash, 0)
            for i in range(rings + 1)]
    return loft(secs, seg, power)


def rounded_slab(w, h, t, r, seg=8):
    """Rounded rectangle in XY, thickness t along Z, with planar UVs on both faces."""
    hw, hh = w / 2, h / 2
    pts = []
    for cx, cy, a0 in [(hw - r, -hh + r, -90), (hw - r, hh - r, 0), (-hw + r, hh - r, 90), (-hw + r, -hh + r, 180)]:
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts = np.array(pts)
    n = len(pts)
    u, v = pts[:, 0] / w + 0.5, 0.5 - pts[:, 1] / h
    hz = t / 2
    parts = []
    for side in (1, -1):
        p = np.vstack([[0, 0, side * hz], np.column_stack([pts, np.full(n, side * hz)])])
        uvs = np.vstack([[0.5, 0.5], np.column_stack([u if side > 0 else 1 - u, v])])
        idx = [(0, 1 + i, 1 + (i + 1) % n) if side > 0 else (0, 1 + (i + 1) % n, 1 + i) for i in range(n)]
        parts.append(Mesh(p, idx, uvs, np.tile([0, 0, side], (n + 1, 1))))
    tang = np.roll(pts, -1, 0) - np.roll(pts, 1, 0)
    out = np.column_stack([tang[:, 1], -tang[:, 0], np.zeros(n)])
    out /= np.linalg.norm(out, axis=1, keepdims=True)
    p = np.vstack([np.column_stack([pts, np.full(n, hz)]), np.column_stack([pts, np.full(n, -hz)])])
    idx = []
    for i in range(n):
        j = (i + 1) % n
        idx += [(i, n + i, n + j), (i, n + j, j)]
    edge = Mesh(p, idx, np.full((2 * n, 2), 0.02), np.vstack([out, out]))
    return parts[0], parts[1], edge


# ================================================================ textures

def tex_torso():
    """Cylindrical wrap for the torso loft: u=0.5 is the chest centre,
    v=0 the top of the shoulders, v=1 the waist."""
    W, H = 1024, 512
    img = Image.new("RGB", (W, H), C["jacket"])
    d = ImageDraw.Draw(img)
    cx = W // 2
    X = lambda f: cx + int(f * W)          # f = fraction of the full wrap
    Y = lambda f: int(f * H)
    # Fabric texture: faint vertical weave.
    rng = np.random.default_rng(3)
    arr = np.asarray(img).astype(np.int16)
    arr += (rng.normal(0, 3, (H, W, 1))).astype(np.int16)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    # Shirt front and waistcoat inside the jacket's V.
    d.polygon([(X(-.075), Y(.0)), (X(.075), Y(.0)), (X(.03), Y(.62)), (X(-.03), Y(.62))], fill=C["vest"])
    d.polygon([(X(-.05), Y(.0)), (X(.05), Y(.0)), (X(.018), Y(.30)), (X(-.018), Y(.30))], fill=C["shirt"])
    # Waistcoat V and buttons.
    d.line([(X(-.05), Y(.0)), (X(0), Y(.31))], fill=C["vest_dark"], width=5)
    d.line([(X(.05), Y(.0)), (X(0), Y(.31))], fill=C["vest_dark"], width=5)
    d.line([(X(0), Y(.31)), (X(0), Y(.66))], fill=C["vest_dark"], width=3)
    for f in (.38, .47, .56):
        d.ellipse([X(-.004), Y(f) - 5, X(.004), Y(f) + 5], fill=(40, 36, 26), outline=(110, 98, 70))
    # Shirt placket.
    d.line([(X(0), Y(.06)), (X(0), Y(.29))], fill=(205, 198, 182), width=3)
    # Lapels: a darker satin-edged band either side of the V.
    for sgn in (-1, 1):
        d.polygon([(X(sgn * .075), Y(.0)), (X(sgn * .13), Y(.02)), (X(sgn * .10), Y(.20)),
                   (X(sgn * .035), Y(.62)), (X(sgn * .028), Y(.62))], fill=C["lapel"])
        d.line([(X(sgn * .075), Y(.0)), (X(sgn * .03), Y(.62))], fill=(70, 84, 98), width=3)
        d.line([(X(sgn * .13), Y(.02)), (X(sgn * .10), Y(.20)), (X(sgn * .035), Y(.62))],
               fill=C["jacket_dark"], width=3)
        d.line([(X(sgn * .10), Y(.20)), (X(sgn * .12), Y(.17))], fill=C["jacket_dark"], width=3)  # notch
    # Jacket closes below the V: front edge and one button.
    d.line([(X(.03), Y(.62)), (X(.035), Y(1))], fill=C["jacket_dark"], width=3)
    d.ellipse([X(-.006), Y(.72) - 7, X(.006), Y(.72) + 7], fill=(24, 28, 34), outline=(80, 90, 100))
    # Breast pocket with a white pocket square on his left (viewer's right).
    d.line([(X(.10), Y(.33)), (X(.16), Y(.31))], fill=C["jacket_dark"], width=4)
    d.polygon([(X(.11), Y(.325)), (X(.125), Y(.27)), (X(.14), Y(.30)), (X(.15), Y(.315))], fill=C["shirt"])
    # Side seams and back seam for some structure.
    for f in (-.25, .25):
        d.line([(X(f), Y(.15)), (X(f * 0.95), Y(1))], fill=C["jacket_dark"], width=2)
    d.line([(0, Y(.1)), (0, Y(1))], fill=C["jacket_dark"], width=4)
    d.line([(W - 1, Y(.1)), (W - 1, Y(1))], fill=C["jacket_dark"], width=4)
    return img.filter(ImageFilter.SMOOTH)


def tex_face():
    """Front projection of the head: x in [-0.1, 0.1] m -> u, y relative to
    the head centre in [0.13, -0.13] m -> v. Painted in the sprites' style."""
    W = H = 512
    img = Image.new("RGB", (W, H), C["skin"])
    d = ImageDraw.Draw(img)
    P = lambda x, y: (W / 2 + x / 0.2 * W, H / 2 - y / 0.26 * H)
    # Soft cheek/jaw shading.
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    for sgn in (-1, 1):
        sd.ellipse([*P(sgn * 0.075 - 0.02, 0.02), *P(sgn * 0.075 + 0.02, -0.07)], fill=90)
    sd.ellipse([*P(-0.03, -0.075), *P(0.03, -0.1)], fill=50)
    shade = shade.filter(ImageFilter.GaussianBlur(18))
    img = Image.composite(Image.new("RGB", (W, H), C["skin_shadow"]), img, shade)
    d = ImageDraw.Draw(img)
    line = (92, 66, 54)
    # Eyes: almond whites, grey-green irises, heavy upper lids.
    for sgn in (-1, 1):
        ex, ey = sgn * 0.032, 0.022
        eye = [P(ex - 0.016, ey), P(ex - 0.006, ey + 0.007), P(ex + 0.008, ey + 0.007),
               P(ex + 0.017, ey + 0.001), P(ex + 0.006, ey - 0.006), P(ex - 0.008, ey - 0.006)]
        d.polygon(eye, fill=(236, 230, 218))
        ix, iy = P(ex + sgn * -0.001, ey + 0.0005)
        r = 0.0062 / 0.2 * W
        d.ellipse([ix - r, iy - r, ix + r, iy + r], fill=(96, 110, 98))
        r2 = r * 0.45
        d.ellipse([ix - r2, iy - r2, ix + r2, iy + r2], fill=(28, 26, 24))
        d.ellipse([ix - r2 * .2 + 3, iy - r2 - 1, ix + r2 * .5 + 3, iy - r2 * .2], fill=(250, 250, 245))
        d.line(eye[:4], fill=line, width=4)                                    # upper lid
        d.line([P(ex - 0.014, ey + 0.012), P(ex + 0.012, ey + 0.013)], fill=(180, 135, 108), width=3)  # crease
        d.line(eye[3:] + [eye[0]], fill=(150, 110, 90), width=2)               # lower lid
        # Brows: thick, grey-brown, slightly arched, lower towards the nose.
        brow = [P(ex - sgn * 0.02, ey + 0.021), P(ex, ey + 0.028), P(ex + sgn * 0.02, ey + 0.024)]
        brow = sorted(brow)
        d.line(brow, fill=(96, 88, 80), width=9, joint="curve")
        # Nasolabial fold and crow's feet.
        d.line([P(sgn * 0.016, -0.012), P(sgn * 0.03, -0.045), P(sgn * 0.034, -0.06)], fill=(170, 124, 98), width=3)
        d.line([P(sgn * 0.052, ey), P(sgn * 0.058, ey + 0.004)], fill=(175, 130, 104), width=2)
    # Forehead lines, nose shadow, mouth.
    for k in range(2):
        d.arc([*P(-0.035, 0.075 + k * 0.01), *P(0.035, 0.05 + k * 0.01)], 200, 340, fill=(184, 140, 112), width=2)
    d.line([P(-0.008, -0.005), P(-0.006, -0.022)], fill=(170, 124, 98), width=3)
    d.ellipse([*P(-0.011, -0.025), *P(-0.005, -0.029)], fill=(150, 104, 84))
    d.ellipse([*P(0.005, -0.025), *P(0.011, -0.029)], fill=(150, 104, 84))
    d.line([P(-0.02, -0.05), P(0, -0.052), P(0.02, -0.05)], fill=(130, 80, 70), width=4, joint="curve")
    d.line([P(-0.015, -0.058), P(0.015, -0.058)], fill=(186, 126, 108), width=3)   # lower lip
    d.line([P(-0.012, -0.082), P(0.012, -0.082)], fill=(176, 130, 104), width=3)   # chin dimple
    return img.filter(ImageFilter.SMOOTH)


def tex_hair():
    """Streaks along u (around the head) so they read as combed-back hair."""
    W, H = 256, 256
    rng = np.random.default_rng(7)
    base = np.array(C["hair"], np.float32)
    rows = np.linspace(-1, 1, H)[:, None]
    streak = np.sin(np.linspace(0, 90 * math.pi, W) + rng.normal(0, .4, W))[None, :] * 5
    noise = rng.normal(0, 4, (H, W))
    light = (np.array(C["hair_light"], np.float32) - base) * np.clip(1 - abs(rows) * 1.3, 0, 1)[..., None] * .55
    arr = base + light + (streak + noise)[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.8))


def tex_chair():
    """The tall wooden chair back seen behind him in the sprites."""
    W, H = 512, 512
    rng = np.random.default_rng(11)
    y = np.arange(H)[:, None]; x = np.arange(W)[None, :]
    grain = np.sin(x / 7.0 + np.sin(y / 60.0) * 3 + rng.normal(0, .2, (1, W))) * 9 + rng.normal(0, 4, (H, W))
    arr = np.array(C["wood"], np.float32) + grain[..., None]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([26, 26, W - 27, H - 27], radius=40, outline=C["wood_light"], width=10)
    d.rounded_rectangle([46, 46, W - 47, H - 47], radius=30, outline=C["wood_dark"], width=6)
    d.rounded_rectangle([70, 70, W - 71, H - 71], radius=22, outline=C["wood_light"], width=4)
    d.rounded_rectangle([82, 82, W - 83, H - 83], radius=18, outline=C["wood_dark"], width=3)
    return img.filter(ImageFilter.SMOOTH)


def tex_card_back():
    """The card back used in the games, if the source art is present."""
    path = os.path.join(SOURCE, "cardback.webp")
    if os.path.exists(path):
        return Image.open(path).convert("RGB").resize((256, 512), Image.LANCZOS)
    img = Image.new("RGB", (256, 512), (240, 236, 224))
    ImageDraw.Draw(img).rounded_rectangle([14, 18, 241, 493], 16, fill=(150, 34, 34))
    return img


def tex_card_front():
    img = Image.new("RGB", (256, 512), (250, 248, 240))
    d = ImageDraw.Draw(img)
    d.text((22, 14), "A", fill=(20, 20, 24), font_size=56)
    cx, cy, s = 128, 256, 70
    d.ellipse([cx - s * .55, cy - s * .1, cx, cy + s * .45], fill=(20, 20, 24))
    d.ellipse([cx, cy - s * .1, cx + s * .55, cy + s * .45], fill=(20, 20, 24))
    d.polygon([(cx - s * .53, cy + s * .12), (cx + s * .53, cy + s * .12), (cx, cy - s * .6)], fill=(20, 20, 24))
    d.polygon([(cx, cy + s * .2), (cx - s * .25, cy + s * .62), (cx + s * .25, cy + s * .62)], fill=(20, 20, 24))
    return img


# ================================================================== model

def build_model():
    """Returns (nodes, meshes) where each mesh is a list of (Mesh, material)."""
    meshes, nodes = [], []

    def add_mesh(name, prims):
        meshes.append({"name": name, "prims": prims})
        return len(meshes) - 1

    def add_node(name, t=(0, 0, 0), r=None, mesh=None, children=(), s=None):
        n = {"name": name, "translation": list(map(float, t))}
        if r is not None:
            n["rotation"] = list(map(float, r))
        if s is not None:
            n["scale"] = list(map(float, s))
        if mesh is not None:
            n["mesh"] = mesh
        if children:
            n["children"] = list(children)
        nodes.append(n)
        return len(nodes) - 1

    # ---- torso (node at the waist, y = 1.0)
    torso = loft([
        (0.545, 0.050, 0.050, 0.0),
        (0.520, 0.120, 0.085, 0.0),
        (0.500, 0.185, 0.105, 0.0),
        (0.465, 0.222, 0.118, 0.0),
        (0.420, 0.228, 0.128, 0.005),
        (0.340, 0.212, 0.138, 0.012),
        (0.240, 0.198, 0.136, 0.012),
        (0.120, 0.186, 0.128, 0.008),
        (0.000, 0.180, 0.124, 0.004),
        (-0.150, 0.184, 0.124, 0.0),
    ], seg=40, power=2.4)
    collar = merge(
        tube(0.045, 0.061, 0.066, seg=24, rings=2).transformed(mat((0, 0.56, -0.002))),
        # Wing tips of the collar.
        sphere(0.018, 0.010, 0.006, 8, 6).transformed(mat((-0.022, 0.52, 0.064), (0, 0, 25))),
        sphere(0.018, 0.010, 0.006, 8, 6).transformed(mat((0.022, 0.52, 0.064), (0, 0, -25))),
    )
    bowtie = merge(
        sphere(0.030, 0.017, 0.010, 12, 8).transformed(mat((-0.026, 0.522, 0.074), (0, 0, -8))),
        sphere(0.030, 0.017, 0.010, 12, 8).transformed(mat((0.026, 0.522, 0.074), (0, 0, 8))),
        sphere(0.011, 0.012, 0.010, 10, 8).transformed(mat((0, 0.522, 0.080))),
    )
    neck = tube(0.14, 0.056, 0.060, seg=20, rings=3).transformed(mat((0, 0.635, -0.006)))
    m_torso = add_mesh("Torso", [(torso, "Jacket"), (collar, "Shirt"), (bowtie, "BowTie"), (neck, "Skin")])

    # ---- head (node at the top of the neck)
    head = sphere(0.090, 0.114, 0.100, seg=40, rings=28, center=(0, 0.085, 0.012))
    p = head.pos.copy()
    rel_y = (p[:, 1] - 0.085) / 0.114
    front = np.clip(p[:, 2] / 0.1, 0, 1)
    jaw = np.clip(-rel_y, 0, 1)
    p[:, 0] *= 1 - 0.22 * jaw ** 1.5                     # narrower jaw and chin
    p[:, 2] += 0.010 * jaw * front                       # chin forward a touch
    p[:, 0] *= 1 + 0.04 * np.clip(rel_y, 0, 1)           # broader cranium
    def bump(cx, cy, sx, sy, h):                         # raise the surface along +Z
        g = np.exp(-(((p[:, 0] - cx) / sx) ** 2 + ((p[:, 1] - cy) / sy) ** 2)) * front ** 3
        p[:, 2] += h * g
    bump(0, 0.085 + 0.004, 0.009, 0.026, 0.020)         # nose bridge
    bump(0, 0.085 - 0.016, 0.012, 0.011, 0.010)         # nose tip
    for sgn in (-1, 1):
        bump(sgn * 0.032, 0.085 + 0.022, 0.014, 0.008, -0.008)   # eye sockets
        bump(sgn * 0.032, 0.085 + 0.040, 0.020, 0.006, 0.004)    # brow ridge
        bump(sgn * 0.045, 0.085 - 0.015, 0.018, 0.016, 0.004)    # cheekbones
    bump(0, 0.085 - 0.088, 0.022, 0.012, 0.006)          # chin
    face_uv = np.column_stack([0.5 + p[:, 0] / 0.2, 0.5 - (p[:, 1] - 0.085) / 0.26])
    head = Mesh(p, head.idx, face_uv)
    ears = merge(*[sphere(0.012, 0.028, 0.019, 10, 8).transformed(mat((sgn * 0.089, 0.085 + 0.006, -0.004), (0, sgn * 15, 0)))
                   for sgn in (-1, 1)])
    # Hair: a slightly larger shell over the cranium, combed back with volume on top.
    hair = sphere(0.096, 0.121, 0.107, seg=96, rings=64, center=(0, 0.088, 0.006))
    hp = hair.pos.copy()
    ry = (hp[:, 1] - 0.088) / 0.121
    rz = (hp[:, 2] - 0.006) / 0.107
    rx = hp[:, 0] / 0.096
    hp[:, 1] += 0.020 * np.clip(ry, 0, 1) ** 2 * np.clip(rz + 0.6, 0, 1)   # volume on top
    hp[:, 2] += 0.010 * np.clip(ry, 0, 1) * np.clip(rz, 0, 1)
    front_top = np.clip((rz - 0.2) / 0.8, 0, 1) * np.clip((ry - 0.25) / 0.5, 0, 1)
    hp[:, 1] += 0.016 * front_top                                       # swept-up front
    hp[:, 2] += 0.010 * front_top
    hp[:, 0] *= 1 + 0.05 * np.clip(ry, 0, 1) * np.clip(-rz + 0.3, 0, 1)  # fuller at the back
    # Hairline: high on the forehead, receding at the temples, down to the
    # ear tops at the sides and to the nape at the back.
    thresh = 0.08 + 0.36 * np.clip(rz, 0, 1) ** 0.8 + 0.12 * np.clip(rz, 0, 1) * np.abs(rx) - 0.62 * np.clip(-rz, 0, 1)
    keep = ry > thresh
    tri_keep = keep[hair.idx].all(axis=1)
    hair = compact(Mesh(hp, hair.idx[tri_keep], hair.uv))
    # Moustache: a tapered, drooping bar across the upper lip.
    pts, n = [], 14
    for i in range(n + 1):
        t = i / n * 2 - 1
        x = t * 0.034
        x = t * 0.040
        y = 0.085 - 0.036 - 0.016 * abs(t) ** 1.5
        z = 0.118 - 0.034 * t * t
        r = 0.0105 * (1 - abs(t) ** 2.2) + 0.0018
        pts.append((x, y, z, r))
    mpos, midx = [], []
    for i, (x, y, z, r) in enumerate(pts):
        for k in range(8):
            a = 2 * math.pi * k / 8
            mpos.append((x, y + r * math.cos(a), z + r * 0.7 * math.sin(a)))
    for i in range(n):
        for k in range(8):
            a, b = i * 8 + k, i * 8 + (k + 1) % 8
            midx += [(a, b, a + 8), (b, b + 8, a + 8)]
    mustache = Mesh(mpos, midx)
    m_head = add_mesh("Head", [(head, "Face"), (ears, "Skin"), (hair, "Hair"), (mustache, "Mustache")])

    # ---- arms: shoulder -> upper arm -> elbow -> forearm -> hand
    upper = merge(sphere(0.060, 0.060, 0.060, 16, 12), tube(0.30, 0.056, 0.047, seg=18, rings=4))
    fore = merge(sphere(0.048, 0.048, 0.048, 14, 10), tube(0.27, 0.046, 0.038, seg=18, rings=4))
    cuff = tube(0.022, 0.039, 0.039, seg=18, rings=1).transformed(mat((0, -0.258, 0)))
    m_upper = add_mesh("UpperArm", [(upper, "Sleeve")])
    m_fore = add_mesh("Forearm", [(fore, "Sleeve"), (cuff, "Shirt")])
    hand_parts, nails = [sphere(0.036, 0.048, 0.016, 14, 10, center=(0, -0.045, 0))], []
    for k, fx in enumerate((-0.021, -0.007, 0.007, 0.021)):           # fingers
        L = (0.040, 0.046, 0.044, 0.036)[k]
        # Fingers curl slightly towards the palm (-Z) so the hand reads palm-down.
        hand_parts.append(tube(L, 0.0085, 0.0075, seg=8, rings=2).transformed(mat((fx, -0.080, 0.0), (22, 0, 0))))
        a = math.radians(22)                                            # nail on the back of the fingertip
        tip = np.array([fx, -0.080 - (L - 0.007) * math.cos(a), -(L - 0.007) * math.sin(a)])
        nails.append(sphere(0.0055, 0.0065, 0.0022, 8, 6).transformed(
            mat(tip + 0.0068 * np.array([0, math.sin(a), math.cos(a)]), (22, 0, 0))))
    hand_parts.append(sphere(0.034, 0.012, 0.010, 12, 6, center=(0, -0.078, 0.008)))  # knuckles
    m_hand = {}
    for side, sgn in (("L", 1), ("R", -1)):
        thumb = tube(0.045, 0.010, 0.008, seg=8, rings=2).transformed(mat((-sgn * 0.034, -0.03, -0.004), (0, 0, -sgn * 40)))
        m_hand[side] = add_mesh("Hand" + side, [(merge(*hand_parts, thumb), "Skin"), (merge(*nails), "Nail")])

    # ---- card held in the right hand
    cf, cb, ce = rounded_slab(0.0635, 0.0889, 0.0004, 0.003)
    m_card = add_mesh("Card", [(cf, "CardFront"), (cb, "CardBack"), (ce, "CardEdge")])

    # ---- chair back
    chf, chb, che = rounded_slab(0.62, 0.78, 0.05, 0.07)
    finial = merge(*[sphere(0.03, 0.03, 0.03, 12, 8).transformed(mat((sgn * 0.27, 0.40, 0))) for sgn in (-1, 1)])
    m_chair = add_mesh("Chair", [(chf, "Wood"), (chb, "Wood"), (che, "WoodDark"), (finial, "Brass")])

    # ---- hierarchy
    q = euler_quat
    card = add_node("HeldCard", (0.0, -0.10, -0.02), q(0, 180, 0), m_card, s=(0, 0, 0))
    hand_r = add_node("HandR", (0, -0.27, 0), q(*REST["HandR"]), m_hand["R"], [card])
    hand_l = add_node("HandL", (0, -0.27, 0), q(*REST["HandL"]), m_hand["L"])
    fore_r = add_node("ForearmR", (0, -0.30, 0), q(*REST["ForearmR"]), m_fore, [hand_r])
    fore_l = add_node("ForearmL", (0, -0.30, 0), q(*REST["ForearmL"]), m_fore, [hand_l])
    arm_r = add_node("UpperArmR", (-0.19, 0.41, 0.0), q(*REST["UpperArmR"]), m_upper, [fore_r])
    arm_l = add_node("UpperArmL", (0.19, 0.41, 0.0), q(*REST["UpperArmL"]), m_upper, [fore_l])
    head_n = add_node("Head", (0, 0.585, -0.004), q(*REST["Head"]), m_head, s=None)
    torso_n = add_node("Torso", (0, 1.0, 0), q(*REST["Torso"]), m_torso, [head_n, arm_r, arm_l])
    chair_n = add_node("Chair", (0, 1.52, -0.21), None, m_chair)
    root = add_node("Dealer", (0, 0, 0), None, None, [torso_n, chair_n])
    return nodes, meshes, root


def euler_quat(x, y, z):
    """XYZ euler (degrees, applied X then Y then Z) -> glTF quaternion [x, y, z, w]."""
    hx, hy, hz = (math.radians(a) / 2 for a in (x, y, z))
    qx = np.array([math.sin(hx), 0, 0, math.cos(hx)])
    qy = np.array([0, math.sin(hy), 0, math.cos(hy)])
    qz = np.array([0, 0, math.sin(hz), math.cos(hz)])
    return qmul(qz, qmul(qy, qx))


def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw,
                     aw * bw - ax * bx - ay * by - az * bz])


# Rest pose: hands resting on the table edge in front of him. Poses were
# solved with forward kinematics against target hand positions (table top
# at y ~ 0.95). Rotation signs: for a limb hanging down -Y, negative X
# swings it forward; for the torso and head, positive X leans/nods forward
# and negative Y turns towards his right (-X).
REST = {
    "Torso": (0, 0, 0), "Head": (0, 0, 0),
    "UpperArmR": (-34.2, 4.9, -1.5), "ForearmR": (-19.0, 12.0, 0), "HandR": (-27.2, 0, 10.9),
    "UpperArmL": (-34.3, -4.7, 1.2), "ForearmL": (-18.6, -11.8, 0), "HandL": (-27.5, 0, -11.9),
}
PREP = {
    "UpperArmR": (-19.6, -11.5, 0), "ForearmR": (-61.0, 43.8, 0), "HandR": (-25.7, 0, 5.5),
    "UpperArmL": (-19.6, 11.5, 0), "ForearmL": (-61.0, -43.8, 0), "HandL": (-25.7, 0, -5.5),
}
tap = lambda e, dx: (e[0] + dx, e[1], e[2])


def around(node, pose, t_in=0.45, t_out=1.55, end=2.0, taps=()):
    """Rest -> pose (with optional taps) -> rest."""
    keys = [(0, REST[node]), (t_in, pose)]
    keys += [(t, tap(pose, dx)) for t, dx in taps]
    return keys + [(t_out, pose), (end, REST[node])]


ANIMS = {
    "Idle": {
        "rot": {
            "Torso": [(0, (0, 0, 0)), (2, (1.0, 0, 0)), (4, (0, 0, 0))],
            "Head": [(0, (0, 0, 0)), (1.3, (-2, 4, 0)), (2.8, (1, -3, 0)), (4, (0, 0, 0))],
        },
        "scale": {"Torso": [(0, (1, 1, 1)), (2, (1.012, 1.006, 1.02)), (4, (1, 1, 1))]},
    },
    "Prepare": {   # hands meet in front of him and square the deck (two taps)
        "rot": dict(
            {n: around(n, PREP[n], taps=((0.75, 6), (0.95, 0), (1.15, 6), (1.35, 0)) if n.startswith("Fore") else ())
             for n in PREP},
            Head=[(0, (0, 0, 0)), (0.45, (16, 0, 0)), (1.55, (16, 0, 0)), (2, (0, 0, 0))],
        ),
    },
    "Deal": {      # leans in and slides a card out towards the seat on his right
        "rot": {
            "UpperArmR": [(0, REST["UpperArmR"]), (0.35, (-58.8, -10.9, 16.9)), (0.75, (-65.4, -4.6, 12.5)),
                          (1.05, (-62.0, -6.0, 13.0)), (1.6, REST["UpperArmR"])],
            "ForearmR": [(0, REST["ForearmR"]), (0.35, (0, 14.7, 0)), (0.75, (0, 12.2, 0)),
                         (1.05, (-6, 12, 0)), (1.6, REST["ForearmR"])],
            "HandR": [(0, REST["HandR"]), (0.35, (-20.5, 0, -7.2)), (0.75, (-8.7, 0, -1.9)),
                      (1.05, (-24, 0, -2)), (1.6, REST["HandR"])],
            "Torso": [(0, (0, 0, 0)), (0.35, (4, -6, 0)), (0.75, (10, -12, 0)), (1.05, (9, -11, 0)), (1.6, (0, 0, 0))],
            "Head": [(0, (0, 0, 0)), (0.75, (6, -14, 0)), (1.6, (0, 0, 0))],
            # The left hand stays on the felt while he leans in.
            "ForearmL": [(0, REST["ForearmL"]), (0.75, (-30, -11.8, 0)), (1.05, (-29, -11.8, 0)), (1.6, REST["ForearmL"])],
        },
        "scale": {"HeldCard": [(0, (0, 0, 0)), (0.05, (1, 1, 1)), (0.95, (1, 1, 1)), (1.0, (0, 0, 0)), (1.6, (0, 0, 0))]},
    },
    "Look": {      # glances to his left, like the dl_aim / dl_profile frames
        "rot": {"Head": [(0, (0, 0, 0)), (0.4, (-2, 38, 0)), (1.6, (-2, 40, 0)), (2.0, (0, 0, 0)), (2.4, (0, 0, 0))],
                "Torso": [(0, (0, 0, 0)), (0.5, (0, 6, 0)), (1.6, (0, 6, 0)), (2.2, (0, 0, 0)), (2.4, (0, 0, 0))]},
    },
    "Nod": {       # eyes-down nod when a hand is settled (dl_complete)
        "rot": {"Head": [(0, (0, 0, 0)), (0.35, (18, 0, 2)), (0.9, (16, 0, 2)), (1.3, (-2, 0, 0)), (1.6, (0, 0, 0))]},
    },
}


# ================================================================== glTF

class Builder:
    def __init__(self):
        self.bin = bytearray()
        self.views, self.accessors = [], []

    def view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        v = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            v["target"] = target
        self.bin += data
        self.views.append(v)
        return len(self.views) - 1

    def accessor(self, arr, ctype, typ, target=None, minmax=False):
        a = {"bufferView": self.view(arr.tobytes(), target), "componentType": ctype,
             "count": len(arr), "type": typ}
        if minmax:
            a["min"] = arr.min(axis=0).reshape(-1).tolist()
            a["max"] = arr.max(axis=0).reshape(-1).tolist()
        self.accessors.append(a)
        return len(self.accessors) - 1


def png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def build_gltf():
    nodes, meshes, root = build_model()
    b = Builder()
    FLOAT, U16, U32 = 5126, 5123, 5125
    ARRAY, ELEMENT = 34962, 34963

    textures = {
        "Jacket": tex_torso(), "Face": tex_face(), "Hair": tex_hair(), "Wood": tex_chair(),
        "CardBack": tex_card_back(), "CardFront": tex_card_front(),
    }
    tex_index = {name: i for i, name in enumerate(textures)}
    plain = {
        "Shirt": (C["shirt"], 0.6), "Sleeve": (C["jacket"], 0.85), "BowTie": (C["tie"], 0.35), "Skin": (C["skin"], 0.6),
        "Mustache": (C["mustache"], 0.85), "Nail": ((226, 190, 172), 0.3), "WoodDark": (C["wood_dark"], 0.6),
        "Brass": (C["brass"], 0.35), "CardEdge": ((236, 232, 220), 0.7),
    }
    materials, mat_index = [], {}
    for name in ["Jacket", "Sleeve", "Shirt", "BowTie", "Skin", "Nail", "Face", "Hair", "Mustache",
                 "Wood", "WoodDark", "Brass", "CardFront", "CardBack", "CardEdge"]:
        if name in textures:
            pbr = {"baseColorTexture": {"index": tex_index[name]}, "metallicFactor": 0.0,
                   "roughnessFactor": {"Jacket": 0.85, "Hair": 0.8, "Face": 0.6, "Wood": 0.55}.get(name, 0.6)}
        else:
            col, rough = plain[name]
            pbr = {"baseColorFactor": srgb(col), "metallicFactor": 0.9 if name == "Brass" else 0.0,
                   "roughnessFactor": rough}
        mat_index[name] = len(materials)
        materials.append({"name": name, "pbrMetallicRoughness": pbr})

    gl_meshes = []
    for m in meshes:
        prims = []
        for mesh, mname in m["prims"]:
            attrs = {
                "POSITION": b.accessor(mesh.pos.astype(np.float32), FLOAT, "VEC3", ARRAY, True),
                "NORMAL": b.accessor(mesh.nrm.astype(np.float32), FLOAT, "VEC3", ARRAY),
            }
            if mname in textures:
                attrs["TEXCOORD_0"] = b.accessor(mesh.uv.astype(np.float32), FLOAT, "VEC2", ARRAY)
            ind = mesh.idx.reshape(-1)
            ind = ind.astype(np.uint16) if len(mesh.pos) < 65536 else ind.astype(np.uint32)
            prims.append({"attributes": attrs, "material": mat_index[mname],
                          "indices": b.accessor(ind, U16 if ind.dtype == np.uint16 else U32, "SCALAR", ELEMENT)})
        gl_meshes.append({"name": m["name"], "primitives": prims})

    images = []
    for name, img in textures.items():
        images.append({"name": name, "bufferView": b.view(png(img)), "mimeType": "image/png"})

    node_index = {n["name"]: i for i, n in enumerate(nodes)}
    animations = []
    for aname, spec in ANIMS.items():
        samplers, channels = [], []
        for path, tracks in (("rotation", spec.get("rot", {})), ("scale", spec.get("scale", {}))):
            for nname, keys in tracks.items():
                times = np.array([k[0] for k in keys], np.float32)
                if path == "rotation":
                    vals = np.array([euler_quat(*k[1]) for k in keys], np.float32)
                    for i in range(1, len(vals)):          # keep quaternions in one hemisphere
                        if np.dot(vals[i], vals[i - 1]) < 0:
                            vals[i] = -vals[i]
                    typ = "VEC4"
                else:
                    vals = np.array([k[1] for k in keys], np.float32)
                    typ = "VEC3"
                samplers.append({"input": b.accessor(times, FLOAT, "SCALAR", minmax=True),
                                 "output": b.accessor(vals, FLOAT, typ), "interpolation": "LINEAR"})
                channels.append({"sampler": len(samplers) - 1, "target": {"node": node_index[nname], "path": path}})
        animations.append({"name": aname, "samplers": samplers, "channels": channels})

    while len(b.bin) % 4:
        b.bin.append(0)
    gltf = {
        "asset": {"version": "2.0", "generator": "make_dealer_glb.py"},
        "scene": 0,
        "scenes": [{"name": "Dealer", "nodes": [root]}],
        "nodes": nodes,
        "meshes": gl_meshes,
        "materials": materials,
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 33071}],
        "images": images,
        "textures": [{"sampler": 0, "source": i} for i in range(len(images))],
        "animations": animations,
        "accessors": b.accessors,
        "bufferViews": b.views,
        "buffers": [{"byteLength": len(b.bin)}],
    }
    return gltf, bytes(b.bin)


def write_glb(path):
    gltf, binary = build_gltf()
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(binary), 0x004E4942) + binary)
    return total


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "assets", "dealer.glb")
    print(f"wrote {out} ({write_glb(out)} bytes)")
