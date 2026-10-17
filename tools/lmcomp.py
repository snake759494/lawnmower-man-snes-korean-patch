"""$80:C706 압축 해제기(역방향 LZ, 매직 $6502) 파이썬 구현과 무압축 래퍼."""
import struct

T_BASE = [6, 10, 10, 18]
T_BITS = [1, 1, 1, 1, 2, 3, 3, 4, 4, 5, 7, 14]


def s2f(a): return ((a >> 16) & 0x7f) * 0x8000 + (a & 0x7fff)


def decompress(rom, bank, addr):
    """반환: (출력 bytes, 압축 데이터 총 길이)"""
    base = s2f((bank << 16) | addr)
    h = rom[base:base + 0x26]
    magic, outlen, clen, lit, bb16 = struct.unpack('<5H', h[:10])
    assert magic == 0x6502, hex(magic)
    tab = h[10:10 + 28]
    b8d = struct.unpack('<4H', tab[0:8]); b95 = struct.unpack('<4H', tab[8:16]); b9d = tab[16:28]
    out = bytearray(outlen)
    y = 0x26 + clen
    if not (bb16 & 0x8000): y -= 1
    st = {'y': y, 'bb': bb16 & 0xff}

    def bit():
        c = st['bb'] >> 7; st['bb'] = (st['bb'] << 1) & 0xff
        if st['bb'] == 0:
            st['y'] -= 1; b = rom[base + st['y']]
            c = b >> 7; st['bb'] = ((b << 1) | 1) & 0xff
        return c

    def bits(n):
        v = 0
        for _ in range(n): v = (v << 1) | bit()
        return v

    x = outlen
    while True:
        for _ in range(lit):
            x -= 1; st['y'] -= 1; out[x] = rom[base + st['y']]
        if x == 0:
            assert st['y'] == 0x26, (st['y'])
            return bytes(out), 0x26 + clen
        if not bit(): ln, idx = 1, 0
        elif not bit(): ln, idx = 2, 1
        elif not bit(): ln, idx = 3, 2
        elif not bit(): ln, idx = 4, 3
        elif not bit(): ln, idx = bits(3) + 5, 3
        else:
            st['y'] -= 1; ln, idx = (rom[base + st['y']] - 1) & 0xff, 3
        k = idx; add = 0
        if bit():
            if bit(): add = T_BASE[k]; k += 8
            else: add = 2; k += 4
        lit = bits(T_BITS[k]) + add
        off = 0; k = idx
        if bit():
            if bit(): k += 8; off = b95[idx]
            else: k += 4; off = b8d[idx]
        ext = bits(b9d[k])
        src = off + 1 + ext + x
        for _ in range(ln + 1):
            x -= 1; src -= 1; out[x] = out[src]


def raw_wrap(data):
    """해제 루틴이 전부 리터럴로 복사하도록 만든 무압축 스트림."""
    n = len(data)
    h = struct.pack('<5H', 0x6502, n, n, n, 0xFF80) + bytes(28)
    return h + bytes(data)
