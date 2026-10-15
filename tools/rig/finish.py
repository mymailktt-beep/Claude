"""Paint the dealer's white long-sleeve blouse onto the rigged model and shrink its textures."""
import io, json, sys, random
sys.path.insert(0, '/home/user/Claude/tools')
from shrink_glb_textures import read_glb, write_glb
from PIL import Image, ImageDraw, ImageFilter, ImageOps

src, dst = sys.argv[1], sys.argv[2]
gltf, binary = read_glb(src)
tris = json.load(open(src.replace('.glb', '-sleeves.json')))
mats = {m['name']: m for m in gltf['materials']}
img_of = lambda name: gltf['textures'][mats[name]['pbrMetallicRoughness']['baseColorTexture']['index']]['source']
def get(i):
    bv = gltf['bufferViews'][gltf['images'][i]['bufferView']]; o = bv.get('byteOffset', 0)
    return Image.open(io.BytesIO(binary[o:o + bv['byteLength']])).convert('RGB')

edits = {}
# sleeves: the arm skin above the wrist becomes white cotton
ai = img_of('Material13462'); arm = get(ai); W, H = arm.size
mask = Image.new('L', (W, H), 0); d = ImageDraw.Draw(mask)
for k in range(0, len(tris), 6):
    pts = [((tris[k + j] % 1) * W, (tris[k + j + 1] % 1) * H) for j in (0, 2, 4)]
    d.polygon(pts, fill=255, outline=255)
mask = mask.filter(ImageFilter.MaxFilter(5))
rnd = random.Random(3)
cloth = Image.new('RGB', (W, H), (238, 240, 242))
noise = Image.effect_noise((W, H), 6).convert('L')
cloth = Image.composite(cloth, Image.new('RGB', (W, H), (226, 229, 233)), noise.point(lambda v: 255 if v > 128 else 140))
cloth = cloth.filter(ImageFilter.GaussianBlur(0.8))
edits[ai] = Image.composite(cloth, arm, mask)
ti = img_of('Material13458'); tor = get(ti); TW_, TH_ = tor.size
tt = json.load(open(src.replace('.glb', '-torso.json')))
tm = Image.new('L', (TW_, TH_), 0); d2 = ImageDraw.Draw(tm)
for k in range(0, len(tt), 6):
    d2.polygon([((tt[k + j] % 1) * TW_, (tt[k + j + 1] % 1) * TH_) for j in (0, 2, 4)], fill=255, outline=255)
tm = tm.filter(ImageFilter.MaxFilter(5))
edits[ti] = Image.composite(cloth.resize((TW_, TH_)), tor, tm)
# the top: from pale blue to a crisp white
si = img_of('Cotton_Oxford_FCL1PSC011_FRONT_4174'); top = get(si)
g = ImageOps.grayscale(top); lo, hi = g.getextrema()
edits[si] = Image.merge('RGB', [g.point(lambda v: int(222 + 30 * (v - lo) / max(1, hi - lo)))] * 3)

# hair: the video's dealer is dark-haired
hi_ = img_of('Material13385'); hair = get(hi_)
edits[hi_] = Image.eval(hair, lambda v: int(v * 0.42))
caps = {'Material13454': 1024, 'Material13458': 1024, 'Material13462': 1024, 'Cotton_Oxford_FCL1PSC011_FRONT_4174': 512,
        'Material13385': 512, 'Material13466': 256, 'Stretch_Denim_FCL1PSD003_FRONT_4181': 256, 'shoes_r_Shape__0': 128}
cap_of = {}
for m in gltf['materials']:
    for key in ('baseColorTexture',):
        t = m.get('pbrMetallicRoughness', {}).get(key)
        if t: cap_of[gltf['textures'][t['index']]['source']] = max(cap_of.get(gltf['textures'][t['index']]['source'], 0), caps.get(m['name'], 128))
    if 'normalTexture' in m: cap_of[gltf['textures'][m['normalTexture']['index']]['source']] = 128
# the skirt's normal map is not worth its bytes behind the table
for m in gltf['materials']: m.pop('normalTexture', None)

new = {}
for i, img in enumerate(gltf['images']):
    bv = gltf['bufferViews'][img['bufferView']]; o = bv.get('byteOffset', 0); raw = binary[o:o + bv['byteLength']]
    im = Image.open(io.BytesIO(raw)); im.load()
    alpha = im.mode in ('RGBA', 'LA', 'P') and im.convert('RGBA').getchannel('A').getextrema()[0] < 250
    if i in edits: im = edits[i]
    cap = cap_of.get(i, 128)
    if max(im.size) > cap: im = im.resize((cap, cap * im.size[1] // im.size[0]), Image.LANCZOS)
    buf = io.BytesIO()
    if alpha: im.convert('RGBA').save(buf, 'PNG', optimize=True); img['mimeType'] = 'image/png'
    else: im.convert('RGB').save(buf, 'JPEG', quality=84, optimize=True); img['mimeType'] = 'image/jpeg'
    new[img['bufferView']] = buf.getvalue()
    print(i, len(raw), '->', len(new[img['bufferView']]), im.size)
packed = bytearray()
for vi, bv in enumerate(gltf['bufferViews']):
    o = bv.get('byteOffset', 0); data = new.get(vi, binary[o:o + bv['byteLength']])
    packed += b'\0' * (-len(packed) % 4); bv['byteOffset'] = len(packed); bv['byteLength'] = len(data); packed += data
gltf['buffers'] = [{'byteLength': len(packed) + (-len(packed) % 4)}]
write_glb(dst, gltf, bytes(packed))
print('written', dst, len(packed))
