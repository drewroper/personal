#!/usr/bin/env python3
"""Merriweather Post Pavilion's back: the front design (as on Drew's copy) with the shop's white
barcode sticker top-left, recreated crisp from the reference. Writes assets/40/<slug>-back.jpg;
make-wear.py then bakes the sleeve wear over it (so the sticker wears with the sleeve)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SLUG = 'animal-collective-merriweather-post-pavilion'
art = Image.open(ROOT / f'assets/40/{SLUG}.jpg').convert('RGB')
W = art.width
k = W / 597                                   # the reference scan is 597px wide
F = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
FB = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
INK = (24, 24, 26)


def text(d, xy, s, size, bold=False, squash=.82):
    """Condensed text: draw wide on a scratch layer, squeeze horizontally, paste."""
    f = ImageFont.truetype(FB if bold else F, int(size * k))
    w, h = d.textbbox((0, 0), s, font=f)[2:]
    lay = Image.new('L', (w + 4, h + 8), 0); ImageDraw.Draw(lay).text((2, 2), s, font=f, fill=255)
    lay = lay.resize((max(1, int(lay.width * squash)), lay.height), Image.LANCZOS)
    st.paste(Image.new('RGB', lay.size, INK), (int(xy[0] * k), int(xy[1] * k)), lay)
    return lay.width / k


def ean13(digits):
    L = ['0001101', '0011001', '0010011', '0111101', '0100011', '0110001', '0101111', '0111011', '0110111', '0001011']
    G = ['0100111', '0110011', '0011011', '0100001', '0011101', '0111001', '0000101', '0010001', '0001001', '0010111']
    R = ['1110010', '1100110', '1101100', '1000010', '1011100', '1001110', '1010000', '1000100', '1001000', '1110100']
    par = ['LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG', 'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL'][int(digits[0])]
    bits = '101' + ''.join((L if p == 'L' else G)[int(c)] for p, c in zip(par, digits[1:7])) + '01010' + ''.join(R[int(c)] for c in digits[7:]) + '101'
    return bits


# the sticker, drawn at the reference's scale then scaled to the art
sw, sh = 262, 136
st = Image.new('RGB', (int(sw * k), int(sh * k)), (246, 245, 241))
d = ImageDraw.Draw(st)
text(d, (8, 5), 'ANIMAL COLLECTIVE', 23, squash=.86)
text(d, (8, 33), 'Merriweather Post Pavilion', 17, squash=.84)
d.rectangle([int(8 * k), int(62 * k), int(25 * k), int(70 * k)], fill=INK)   # the Domino mark
text(d, (28, 59), '/WIGCD216', 10.5, squash=.9)
text(d, (8, 72), 'EAN 5034202021629', 10.5, squash=.9)
text(d, (8, 90), 'Please remove this', 10.5, bold=True, squash=.9)
text(d, (8, 102), 'sticker after purchase.', 10.5, bold=True, squash=.9)
d.line([(int(8 * k), int(114 * k)), (int(104 * k), int(114 * k))], fill=INK, width=max(1, int(.8 * k)))
d.line([(int(8 * k), int(101 * k)), (int(92 * k), int(101 * k))], fill=INK, width=max(1, int(.8 * k)))
text(d, (8, 120), '℗ + © 2009 Domino Recording Co. Ltd.   Made in the E.U.', 8.5, squash=.9)
bits = ean13('5034202021629')                 # a real, scannable EAN-13 (check digit 9)
x0, y0, mw = 138, 60, 1.2
for i, b in enumerate(bits):
    if b == '1':
        x = int((x0 + i * mw) * k)
        d.rectangle([x, int(y0 * k), int((x0 + (i + 1) * mw) * k) - 1, int((y0 + 26) * k)], fill=INK)

m = Image.new('L', st.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, st.width - 1, st.height - 1], radius=int(3 * k), fill=255)
back = art.copy()
back.paste(st, (int(8 * k), int(9 * k)), m)
out = ROOT / f'assets/40/{SLUG}-back.jpg'
back.save(out, 'JPEG', quality=92)
print(out)
