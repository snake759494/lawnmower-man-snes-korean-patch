# -*- coding: utf-8 -*-
"""론머맨 한글 패치 빌더"""
import os, struct, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'translation'))
from lmcomp import s2f, raw_wrap
from texts import STRINGS, MESSAGES_KO, PROLOGUE
import pic
import hashlib, argparse

ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'translation'))
WORK = os.path.join(ROOT, 'work')
GAL = os.path.join(WORK, 'galmuri')
ASAR = os.path.join(WORK, 'asar', 'asar.exe')
SOURCE_SHA256 = 'a179a1188220b59787c49a78a0dde79b89380e3a8a8a0ab558f0102c5796f873'
F7 = ImageFont.truetype(os.path.join(GAL, 'Galmuri7.ttf'), 8)
F9 = ImageFont.truetype(os.path.join(GAL, 'Galmuri9.ttf'), 10)


def is_ko(ch): return '가' <= ch <= '힣'


def glyph7(ch):
    im = Image.new('L', (8, 8)); ImageDraw.Draw(im).text((0, -1), ch, font=F7, fill=255)
    return (np.array(im) > 127).astype(np.uint8)


def tile2bpp(a):
    out = bytearray(16)
    for y in range(8):
        for x in range(8):
            v = int(a[y, x])
            if v & 1: out[y * 2] |= 0x80 >> x
            if v & 2: out[y * 2 + 1] |= 0x80 >> x
    return bytes(out)


def tile4bpp(a):
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            v = int(a[y, x])
            for p in range(4):
                if v >> p & 1: out[(p // 2) * 16 + y * 2 + (p & 1)] |= 0x80 >> x
    return bytes(out)


# 원본 글꼴 문자 코드
ASC = {'.': 0x5B, ',': 0x5C, "'": 0x62, '!': 0x5F, '-': 0x5D, '/': 0x63, '©': 0x61, ' ': 0x20, ':': None}
for d in range(10): ASC[str(d)] = 0x37 + d
for c in range(ord('A'), ord('Z') + 1): ASC[chr(c)] = c
SHOP = [0x67, 0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E]


def tokens(text):
    out, i = [], 0
    while i < len(text):
        if text.startswith('{SHOP}', i): out.append(('shop',)); i += 6; continue
        out.append(('ch', text[i])); i += 1
    return out


def width(text):
    return sum(8 if t[0] == 'shop' else 1 for t in tokens(text))


class Data:
    """확장 영역($A08000~) 배치. 뱅크 경계를 넘지 않게 놓는다."""
    def __init__(self, rom):
        self.rom = rom; self.addr = 0xA08000

    def put(self, b):
        if (self.addr & 0x7FFF) + len(b) > 0x8000:
            self.addr = ((self.addr >> 16) + 1) << 16 | 0x8000
        a = self.addr; o = s2f(a); self.rom[o:o + len(b)] = b; self.addr += len(b)
        assert self.addr < 0xC00000
        return a


def build_record(data, speed, lines, player):
    kos = []; body = bytearray()
    for x, y, text in lines:
        text = text.replace('{P}', str(player))
        w = width(text)
        if x is None: x = (32 - w) // 2
        assert x + w <= 32, (text, x, w)
        body += bytes([0x80, x, y])
        for t in tokens(text):
            if t[0] == 'shop': body += bytes(SHOP); continue
            ch = t[1]
            if is_ko(ch):
                if ch not in kos: kos.append(ch)
                body += bytes([0x84, kos.index(ch) + 1])
            else:
                code = ASC.get(ch); assert code, repr(ch)
                body += bytes([code])
    body += b'\xff'
    assert len(kos) <= 127, (len(kos), lines)
    tiles = b''.join(tile2bpp(glyph7(c)) for c in kos)
    src = data.put(tiles) if tiles else 0
    head = bytes([speed]) + struct.pack('<H', len(tiles)) + struct.pack('<I', src)[:3]
    return data.put(head + bytes(body)), len(kos)


def patch_strings(rom, data):
    stats = {}
    for addr, (speed, lines) in STRINGS.items():
        o = s2f(addr)
        assert rom[o] in (0, 1), hex(addr)
        if any('{P}' in t for _, _, t in lines):
            p1, n1 = build_record(data, speed, lines, 1)
            p2, n2 = build_record(data, speed, lines, 2)
            stub = b'\xfd' + struct.pack('<I', p1)[:3] + struct.pack('<I', p2)[:3]
            stats[addr] = max(n1, n2)
        else:
            p1, stats[addr] = build_record(data, speed, lines, 1)
            stub = b'\xfe' + struct.pack('<I', p1)[:3]
        end = rom.index(b'\xff', o)        # 원본 문자열 길이 이상인지 확인
        while rom[end + 1] not in (0, 1) and rom[end + 1] == 0xFF: end += 1
        assert len(stub) <= end - o + 1, hex(addr)
        rom[o:o + len(stub)] = stub
    return stats


def msg_glyph(ch):
    g = glyph7(ch); a = np.zeros((8, 8), np.uint8)
    a[1:, 1:][g[:-1, :-1] == 1] = 1          # 오른쪽 아래 그림자(원본 HUD 글꼴 방식)
    a[g == 1] = 3
    return a


def patch_messages(rom, data):
    tab = s2f(0x848420); ptrs = list(struct.unpack('<18H', rom[tab:tab + 36]))
    uniq = sorted(set(ptrs))
    region_start, region_end = min(uniq), 0x8500
    eng = {}
    for p in uniq:
        o = s2f(0x840000 | p); e = rom.index(b'\xff', o + 1)
        eng[p] = rom[o + 1:e].decode()
    newpos = {}; blob = bytearray(); sizes = [0] * 18; srcs = [0] * 18
    glyph_ptr = {}
    for p in uniq:
        ko = MESSAGES_KO[p]; chars = []
        enc = bytearray()
        for ch in ko:
            if ch == ' ': enc.append(0x20); continue
            if ch not in chars: chars.append(ch)
            enc.append(chars.index(ch) + 1)
        assert len(chars) <= 31 and len(ko) <= 16
        x = (16 - len(ko)) // 2
        newpos[p] = region_start + len(blob)
        blob += bytes([x]) + enc + b'\xff'
        tiles = b''.join(tile2bpp(msg_glyph(c)) for c in chars)
        glyph_ptr[p] = (data.put(tiles), len(tiles))
    assert region_start + len(blob) <= region_end
    o = s2f(0x840000 | region_start); rom[o:o + (region_end - region_start)] = b'\xff' * (region_end - region_start)
    rom[o:o + len(blob)] = blob
    for i, p in enumerate(ptrs):
        struct.pack_into('<H', rom, tab + i * 2, newpos[p])
        srcs[i], sizes[i] = glyph_ptr[p]
    banks = {s >> 16 for s in srcs}
    assert len(banks) == 1
    msz = data.put(struct.pack('<18H', *sizes)); msrc = data.put(struct.pack('<18H', *[s & 0xFFFF for s in srcs]))
    return msz, msrc, banks.pop()


def prologue_image():
    img = Image.new('L', (256, 112)); d = ImageDraw.Draw(img)
    for i, line in enumerate(PROLOGUE):
        w = F9.getlength(line)
        assert w <= 224, (line, w)
        d.text((int((256 - w) // 2), 14 + i * 16), line, font=F9, fill=255)
    return (np.array(img) > 127).astype(np.uint8)


def patch_prologue(rom, data):
    e = list(pic.entry(rom, 24))
    idx = prologue_image()
    gfx, _ = pic.gfx(rom, 24); gfx = bytearray(gfx)
    w, h = e[0], e[1]; fa = 0
    for cy in range(h):
        for cx in range(w):
            tb = (fa & 7) * 2 | (fa & 0x3F8) << 2
            for dy in range(2):
                for dx in range(2):
                    t = tb + dy * 16 + dx
                    gfx[t * 32:t * 32 + 32] = tile4bpp(idx[cy * 16 + dy * 8:cy * 16 + dy * 8 + 8, cx * 16 + dx * 8:cx * 16 + dx * 8 + 8])
            fa += 1
    base = s2f(0x85E960) + 24 * 32
    for k in range(2):
        a = data.put(raw_wrap(gfx[k * 0x2000:(k + 1) * 0x2000]))
        struct.pack_into('<H', rom, base + 8 + k * 2, a & 0xFFFF)
        struct.pack_into('<H', rom, base + 16 + k * 2, (a >> 16) * 0x101)


def put_tiles4(rom, img, addrs):
    """img(8의 배수 크기)를 4bpp 타일로 잘라 addrs[행][열] 파일 오프셋에 기록"""
    for ty, row in enumerate(addrs):
        for tx, a in enumerate(row):
            if a is None: continue
            rom[a:a + 32] = tile4bpp(img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8])


def patch_graphics(rom):
    # 타이틀 로고: 32x32 스프라이트 7개(224x32), 128px 폭 시트, 행 간격 $200
    # data/title_logo_ko.png = 원본 로고와 같은 5색(0 투명, 1 흰색, 2~4 회색) 인덱스 그림
    logo = np.array(Image.open(os.path.join(ROOT, 'data', 'title_logo_ko.png')))
    assert logo.shape == (32, 224) and logo.max() <= 4
    bases = [0x7A000, 0x7A080, 0x7A100, 0x7A180, 0x7B000, 0x7B080, 0x7B100]
    put_tiles4(rom, logo, [[bases[tx // 4] + ty * 0x200 + (tx % 4) * 0x20 for tx in range(28)] for ty in range(4)])

    # PAUSED 스프라이트(48x8, 본체 1 / 그림자 4, 굵은 획)
    im = np.zeros((8, 48), np.uint8); x0 = 4
    for i, ch in enumerate('일시정지'):
        g = glyph7(ch); bold = g.copy(); bold[:, 1:] |= g[:, :-1]
        x = x0 + i * 10
        sh = np.zeros((8, 9), np.uint8); sh[1:, 1:] = bold[:-1, :8]
        for yy in range(8):
            for xx in range(9):
                if xx < 8 and bold[yy, xx]: im[yy, x + xx] = 1
                elif sh[yy, xx] and im[yy, x + xx] == 0: im[yy, x + xx] = 4
    B = 0x5CEBE
    put_tiles4(rom, im, [[B + n * 32 for n in (0x08, 0x09, 0x0A, 0x0B, 0x28, 0x29)]])

    # HUD 상자 32x16: 배경 1, 글자 $B
    def box(l1, l2):
        im = np.ones((16, 32), np.uint8)
        for row, text in ((0, l1), (8, l2)):
            x = (32 - 8 * len(text)) // 2
            for i, ch in enumerate(text):
                g = glyph7(ch); im[row:row + 8, x + i * 8:x + i * 8 + 8][g == 1] = 0xB
        return im
    # DEMO MODE 스프라이트(32x24, 원본 줄 위치 y=1, y=13 유지)
    im = np.zeros((24, 32), np.uint8)
    for y0, text in ((1, '데모'), (13, '플레이')):
        x = (32 - 8 * len(text)) // 2
        for i, ch in enumerate(text):
            g = glyph7(ch)[:7]
            im[y0:y0 + 7, x + i * 8:x + i * 8 + 8][g == 1] = 1
    put_tiles4(rom, im, [[0x85980 + r * 0x200 + i * 32 for i in range(4)] for r in range(3)])
    # HUD CONTINUE (40x8, 시트 3행 11~15열)
    im = np.ones((8, 40), np.uint8)
    for i, ch in enumerate('이어하기'):
        g = glyph7(ch); im[:, 4 + i * 8:12 + i * 8][g == 1] = 0xB
    im[7, :] = 1
    put_tiles4(rom, im, [[0x78800 + (3 * 16 + c) * 32 for c in range(11, 16)]])
    for addr, (l1, l2) in ((0x79800, ('접근', '거부')), (0x79900, ('스타트', '누르기'))):
        put_tiles4(rom, box(l1, l2), [[addr + i * 32 for i in range(4)], [addr + 128 + i * 32 for i in range(4)]])


def checksum(rom):
    struct.pack_into('<HH', rom, 0x7FDC, 0xFFFF, 0)
    s = sum(rom) & 0xFFFF
    struct.pack_into('<HH', rom, 0x7FDC, s ^ 0xFFFF, s)


def main():
    ap = argparse.ArgumentParser(description='론머맨 SNES 한글 ROM 빌드')
    ap.add_argument('source', help='원본 Lawnmower Man, The (USA).sfc (헤더 없음)')
    ap.add_argument('output', help='결과 ROM 경로')
    args = ap.parse_args()
    global OUT
    OUT = args.output
    rom = bytearray(open(args.source, 'rb').read())
    assert hashlib.sha256(rom).hexdigest() == SOURCE_SHA256, '원본 ROM 해시가 다릅니다(헤더 제거 필요 여부 확인)'
    rom += b'\xff' * 0x100000
    rom[0x7FD7] = 0x0B
    data = Data(rom)
    stats = patch_strings(rom, data)
    msz, msrc, mbank = patch_messages(rom, data)
    patch_prologue(rom, data)
    patch_graphics(rom)
    open(os.path.join(HERE, 'gen.asm'), 'w').write(
        f'!MsgSize = ${msz:06X}\n!MsgSrc = ${msrc:06X}\n!MsgBank = ${mbank:02X}\n')
    open(OUT, 'wb').write(rom)
    r = subprocess.run([ASAR, '--fix-checksum=off', os.path.join(HERE, 'hangul.asm'), OUT], capture_output=True, text=True)
    print(r.stdout, r.stderr)
    assert r.returncode == 0
    rom = bytearray(open(OUT, 'rb').read()); assert len(rom) == 0x200000
    checksum(rom); open(OUT, 'wb').write(rom)
    print('화면당 최대 한글', max(stats.values()), '/ 127, 데이터 끝', hex(data.addr))
    print('SHA-256', hashlib.sha256(rom).hexdigest())


if __name__ == '__main__':
    main()
