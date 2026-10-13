#!/usr/bin/env python3
"""Generate a playing-card GLB (glTF 2.0 binary) for the cards chat.

The card is a thin rounded-rectangle slab in standard poker size
(63.5 x 88.9 mm, 0.3 mm thick), modelled in metres, standing in the XY
plane with the face pointing +Z. It has three primitives/materials:
front (ace of spades texture), back (patterned texture) and edge.

Usage: python3 tools/make_card_glb.py [output.glb]
Requires: numpy, Pillow
"""
import io
import json
import math
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH = 0.0635
HEIGHT = 0.0889
THICKNESS = 0.0003
CORNER_RADIUS = 0.003
CORNER_SEGMENTS = 8
TEX_W, TEX_H = 512, 717  # drawing size: same aspect ratio as the card
TEX_OUT = (512, 1024)  # power-of-two size stored in the GLB


# ---------------------------------------------------------------- textures

def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 has no scalable default font
        return ImageFont.load_default()


def _spade(draw, cx, cy, s, fill):
    """Draw a spade centred at (cx, cy) with overall height ~s."""
    r = s * 0.26
    # Two lobes plus an inverted heart point.
    draw.ellipse([cx - 2 * r, cy - r * 0.4, cx, cy + 1.6 * r], fill=fill)
    draw.ellipse([cx, cy - r * 0.4, cx + 2 * r, cy + 1.6 * r], fill=fill)
    draw.polygon([(cx - 1.95 * r, cy + 0.45 * r), (cx + 1.95 * r, cy + 0.45 * r),
                  (cx, cy - s * 0.5)], fill=fill)
    # Stem.
    draw.polygon([(cx, cy + 0.6 * r), (cx - r * 1.1, cy + s * 0.5),
                  (cx + r * 1.1, cy + s * 0.5)], fill=fill)


def front_texture():
    img = Image.new("RGB", (TEX_W, TEX_H), (250, 250, 247))
    d = ImageDraw.Draw(img)
    black = (20, 20, 24)
    d.rounded_rectangle([14, 14, TEX_W - 15, TEX_H - 15], radius=18,
                        outline=(205, 205, 200), width=3)
    _spade(d, TEX_W / 2, TEX_H / 2, 230, black)
    font = _font(72)
    for flip in (False, True):
        corner = Image.new("RGBA", (110, 170), (0, 0, 0, 0))
        cd = ImageDraw.Draw(corner)
        cd.text((55, 48), "A", font=font, fill=black, anchor="mm")
        _spade(cd, 55, 122, 56, black)
        if flip:
            corner = corner.rotate(180)
            img.paste(corner, (TEX_W - 30 - 110, TEX_H - 24 - 170), corner)
        else:
            img.paste(corner, (30, 24), corner)
    return img


def back_texture():
    img = Image.new("RGB", (TEX_W, TEX_H), (250, 250, 247))
    d = ImageDraw.Draw(img)
    navy, gold = (28, 46, 110), (214, 178, 92)
    m = 28
    d.rounded_rectangle([m, m, TEX_W - m - 1, TEX_H - m - 1], radius=16, fill=navy)
    step = 32
    for y in range(m + 12, TEX_H - m - 12, step):
        for x in range(m + 12, TEX_W - m - 12, step):
            cx, cy = x + step / 2, y + step / 2
            if cx > TEX_W - m - 12 or cy > TEX_H - m - 12:
                continue
            h = step * 0.32
            d.polygon([(cx, cy - h), (cx + h, cy), (cx, cy + h), (cx - h, cy)],
                      outline=gold)
    d.rounded_rectangle([m + 8, m + 8, TEX_W - m - 9, TEX_H - m - 9], radius=12,
                        outline=gold, width=3)
    # Central medallion.
    cx, cy, r = TEX_W / 2, TEX_H / 2, 70
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=navy, outline=gold, width=4)
    _spade(d, cx, cy, 80, gold)
    return img


def png_bytes(img):
    buf = io.BytesIO()
    img.resize(TEX_OUT, Image.LANCZOS).save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# -------------------------------------------------------------- geometry

def outline():
    """Counter-clockwise rounded-rectangle outline in XY (viewed from +Z)."""
    hw, hh, r = WIDTH / 2, HEIGHT / 2, CORNER_RADIUS
    centres = [(hw - r, -hh + r, -90), (hw - r, hh - r, 0),
               (-hw + r, hh - r, 90), (-hw + r, -hh + r, 180)]
    pts = []
    for cx, cy, start in centres:
        for i in range(CORNER_SEGMENTS + 1):
            a = math.radians(start + 90 * i / CORNER_SEGMENTS)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return np.array(pts, dtype=np.float32)


def build_primitives():
    pts = outline()
    n = len(pts)
    hz = THICKNESS / 2
    u = pts[:, 0] / WIDTH + 0.5
    v = 0.5 - pts[:, 1] / HEIGHT  # glTF UV origin is top-left

    prims = []
    # Front (+Z): centre fan, CCW.
    pos = np.vstack([[0, 0, hz], np.column_stack([pts, np.full(n, hz)])])
    nrm = np.tile([0, 0, 1], (n + 1, 1))
    uv = np.vstack([[0.5, 0.5], np.column_stack([u, v])])
    idx = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
    prims.append((pos, nrm, uv, idx))

    # Back (-Z): reversed winding, U mirrored so the texture reads correctly.
    pos = np.vstack([[0, 0, -hz], np.column_stack([pts, np.full(n, -hz)])])
    nrm = np.tile([0, 0, -1], (n + 1, 1))
    uv = np.vstack([[0.5, 0.5], np.column_stack([1 - u, v])])
    idx = [(0, 1 + (i + 1) % n, 1 + i) for i in range(n)]
    prims.append((pos, nrm, uv, idx))

    # Edge: a quad per outline segment, normals smoothed per vertex from
    # the neighbouring segment directions. Untextured, so no UVs.
    tang = np.roll(pts, -1, axis=0) - np.roll(pts, 1, axis=0)
    out = np.column_stack([tang[:, 1], -tang[:, 0]])
    out /= np.linalg.norm(out, axis=1, keepdims=True)
    pos = np.vstack([np.column_stack([pts, np.full(n, hz)]),
                     np.column_stack([pts, np.full(n, -hz)])])
    nrm = np.vstack([np.column_stack([out, np.zeros(n)])] * 2)
    idx = []
    for i in range(n):
        j = (i + 1) % n
        idx += [(i, n + i, n + j), (i, n + j, j)]
    prims.append((pos, nrm, None, idx))
    return prims


# ------------------------------------------------------------------ glTF

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

    def accessor(self, arr, ctype, typ, target, minmax=False):
        a = {"bufferView": self.view(arr.tobytes(), target), "componentType": ctype,
             "count": len(arr), "type": typ}
        if minmax:
            a["min"] = arr.min(axis=0).tolist()
            a["max"] = arr.max(axis=0).tolist()
        self.accessors.append(a)
        return len(self.accessors) - 1


def build_gltf():
    b = Builder()
    ARRAY, ELEMENT = 34962, 34963
    FLOAT, UINT16 = 5126, 5123

    gl_prims = []
    for mat, (pos, nrm, uv, idx) in enumerate(build_primitives()):
        attrs = {
            "POSITION": b.accessor(pos.astype(np.float32), FLOAT, "VEC3", ARRAY, True),
            "NORMAL": b.accessor(nrm.astype(np.float32), FLOAT, "VEC3", ARRAY),
        }
        if uv is not None:
            attrs["TEXCOORD_0"] = b.accessor(uv.astype(np.float32), FLOAT, "VEC2", ARRAY)
        ind = np.array(idx, dtype=np.uint16).reshape(-1)
        gl_prims.append({"attributes": attrs, "material": mat,
                         "indices": b.accessor(ind, UINT16, "SCALAR", ELEMENT)})

    front_img = b.view(png_bytes(front_texture()))
    back_img = b.view(png_bytes(back_texture()))
    while len(b.bin) % 4:
        b.bin.append(0)

    def textured(name, tex):
        return {"name": name, "pbrMetallicRoughness": {
            "baseColorTexture": {"index": tex}, "metallicFactor": 0.0,
            "roughnessFactor": 0.55}}

    gltf = {
        "asset": {"version": "2.0", "generator": "cards-chat make_card_glb.py"},
        "scene": 0,
        "scenes": [{"name": "Card", "nodes": [0]}],
        "nodes": [{"name": "Card", "mesh": 0}],
        "meshes": [{"name": "Card", "primitives": gl_prims}],
        "materials": [
            textured("CardFront", 0),
            textured("CardBack", 1),
            {"name": "CardEdge", "pbrMetallicRoughness": {
                "baseColorFactor": [0.93, 0.93, 0.9, 1.0], "metallicFactor": 0.0,
                "roughnessFactor": 0.7}},
        ],
        "samplers": [{"magFilter": 9729, "minFilter": 9987,
                      "wrapS": 33071, "wrapT": 33071}],
        "images": [{"name": "front", "bufferView": front_img, "mimeType": "image/png"},
                   {"name": "back", "bufferView": back_img, "mimeType": "image/png"}],
        "textures": [{"sampler": 0, "source": 0}, {"sampler": 0, "source": 1}],
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
    out = sys.argv[1] if len(sys.argv) > 1 else "assets/card.glb"
    print(f"wrote {out} ({write_glb(out)} bytes)")
