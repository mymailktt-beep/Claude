#!/usr/bin/env python3
"""Recompress the textures inside a GLB so it loads faster on phones.

Opaque PNG/JPEG textures are re-encoded as JPEG and capped at a maximum
size; textures with real transparency stay PNG. Geometry, skins and
animations are copied unchanged.

Usage: python3 tools/shrink_glb_textures.py in.glb out.glb [max_px] [small_px]
  max_px    cap for colour and normal maps (default 1024)
  small_px  cap for minor textures: eyes, teeth, glasses (default 256)
Requires: Pillow
"""
import io
import json
import struct
import sys

from PIL import Image

MINOR = ("Teeth", "Cornea", "Eyeball", "glasses", "Eyelashes")


def read_glb(path):
    b = open(path, "rb").read()
    jl, = struct.unpack("<I", b[12:16])
    gltf = json.loads(b[20:20 + jl])
    off = 20 + jl
    bl, = struct.unpack("<I", b[off:off + 4])
    return gltf, b[off + 8:off + 8 + bl]


def write_glb(path, gltf, binary):
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    binary += b"\0" * (-len(binary) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(binary)))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(binary), 0x004E4942) + binary)


def image_users(gltf):
    """image index -> names of the materials that use it"""
    users = {}

    def visit(name, obj):
        if isinstance(obj, dict):
            if "index" in obj and set(obj) <= {"index", "texCoord", "scale", "strength", "extensions"}:
                src = gltf["textures"][obj["index"]]["source"]
                users.setdefault(src, set()).add(name)
            for v in obj.values():
                visit(name, v)

    for m in gltf.get("materials", []):
        visit(m.get("name", ""), m)
    return users


def main():
    src, dst = sys.argv[1], sys.argv[2]
    max_px = int(sys.argv[3]) if len(sys.argv) > 3 else 1024
    small_px = int(sys.argv[4]) if len(sys.argv) > 4 else 256
    gltf, binary = read_glb(src)
    users = image_users(gltf)
    new_data = {}
    for i, img in enumerate(gltf.get("images", [])):
        bv = gltf["bufferViews"][img["bufferView"]]
        o = bv.get("byteOffset", 0)
        raw = binary[o:o + bv["byteLength"]]
        im = Image.open(io.BytesIO(raw))
        im.load()
        alpha = im.mode in ("RGBA", "LA", "P") and (
            im.convert("RGBA").getchannel("A").getextrema()[0] < 250)
        cap = small_px if any(k in n for n in users.get(i, ()) for k in MINOR) else max_px
        if max(im.size) > cap:
            im = im.resize((cap, cap * im.size[1] // im.size[0]) if im.size[0] >= im.size[1]
                           else (cap * im.size[0] // im.size[1], cap), Image.LANCZOS)
        buf = io.BytesIO()
        if alpha:
            im.convert("RGBA").save(buf, "PNG", optimize=True)
            img["mimeType"] = "image/png"
        else:
            im.convert("RGB").save(buf, "JPEG", quality=86, optimize=True, progressive=False)
            img["mimeType"] = "image/jpeg"
        out = buf.getvalue()
        if len(out) >= len(raw) and img["mimeType"] == ("image/png" if raw[:4] == b"\x89PNG" else "image/jpeg"):
            out = raw          # keep the original when re-encoding does not help
        new_data[img["bufferView"]] = out
        print(f"image {i}: {len(raw):>8} -> {len(out):>8} bytes  {im.size}  {sorted(users.get(i, []))}")

    # Repack every buffer view in order, 4-byte aligned.
    packed = bytearray()
    for vi, bv in enumerate(gltf["bufferViews"]):
        o = bv.get("byteOffset", 0)
        data = new_data.get(vi, binary[o:o + bv["byteLength"]])
        packed += b"\0" * (-len(packed) % 4)
        bv["byteOffset"] = len(packed)
        bv["byteLength"] = len(data)
        packed += data
    gltf["buffers"] = [{"byteLength": len(packed) + (-len(packed) % 4)}]
    write_glb(dst, gltf, bytes(packed))
    print(f"{src}: {len(binary)} bytes of data -> {dst}: {len(packed)}")


if __name__ == "__main__":
    main()
