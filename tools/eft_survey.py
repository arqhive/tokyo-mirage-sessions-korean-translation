# -*- coding: utf-8 -*-
"""이펙트 팩(pack_020_effect) 텍스처 전수조사 — 모든 .ptcl 의 텍스처를 형식대로 풀어 고유 그림만 시트로 모은다(2026-09-28).

  python -X utf8 tools/eft_survey.py      → work/eft_survey/sheet_NN.png, index.json
EFTF(v0x42) 텍스처 정보(각 0x38바이트, 앞부분 파일 안 여기저기에 있음):
  +0 가로(u16) 세로(u16) · +4 타일모드(4 또는 2) · +8 스위즐 · +0xC 정렬 · +0x2C 형식(4=BC1, 8=BC3)
  +0x30 데이터 크기 · +0x34 데이터 영역(헤더 +0x14 위치) 안 시작
"""
import os, json, struct, hashlib
import numpy as np
from PIL import Image, ImageDraw
import extract, gtx2, gtx_lib, addrlib

ROOT = extract.ROOT
OUT = os.path.join(ROOT, 'work', 'eft_survey')
FMT = {4: (0x31, 8), 8: (0x33, 16)}


def textures(b):
    """ptcl 바이트 → [(정보 위치, 가로, 세로, 타일모드, 스위즐, 형식코드, 데이터 절대 위치, 크기)]"""
    if b[:4] != b'EFTF':
        return []
    toff, tsize = struct.unpack('>II', b[0x14:0x1C])
    out = []
    for o in range(0x20, toff - 0x38, 4):
        w, h = struct.unpack('>HH', b[o:o + 4])
        if not (4 <= w <= 2048 and 4 <= h <= 2048):
            continue
        f = struct.unpack('>14I', b[o:o + 56])
        if f[3] not in (0x100, 0x200, 0x400, 0x800, 0x1000, 0x2000) or f[1] not in (2, 4) or f[11] not in FMT:
            continue
        size, off = f[12], f[13]
        if 0 < size and off + size <= tsize:
            out.append((o, w, h, f[1], f[2], f[11], toff + off, size))
    return out


def addr(w, h, tm, sw, fc):
    """블록 (세로, 가로) → 데이터 안 바이트 위치"""
    fmt, bpb = FMT[fc]
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    info = addrlib.getSurfaceInfo(fmt, w, h, 1, 1, tm, 0, 0)
    if tm == 4:
        return gtx2.addr_map(bw, bh, bpb * 8, info.pitch, info.height, sw)
    return np.array([[addrlib.computeSurfaceAddrFromCoordMicroTiled(x, y, bpb * 8, info.pitch, tm) for x in range(bw)] for y in range(bh)], np.int64)


def decode(data, w, h, tm, sw, fc):
    bpb = FMT[fc][1]
    m = addr(w, h, tm, sw, fc)
    blk = np.ascontiguousarray(np.frombuffer(data, np.uint8)[m[..., None] + np.arange(bpb)])
    if fc == 8:
        a = gtx_lib.bc4_decode_blocks(np.ascontiguousarray(blk[..., :8]))
        rgb = gtx_lib.bc1_decode_blocks(np.ascontiguousarray(blk[..., 8:]))
    else:
        rgb = gtx_lib.bc1_decode_blocks(blk); a = np.full(rgb.shape[:2], 255, np.uint8)
    return np.dstack([rgb, a])[:h, :w]


def main():
    os.makedirs(OUT, exist_ok=True)
    c = extract.open_pack('pack_020_effect')
    uniq = {}
    for e in c.files:
        if not e['name'].endswith('.ptcl'):
            continue
        b = c.read(e)
        for (o, w, h, tm, sw, fc, pos, size) in textures(b):
            data = b[pos:pos + size]
            k = hashlib.sha1(data + struct.pack('>HHII', w, h, tm, fc)).hexdigest()[:16]
            u = uniq.setdefault(k, dict(w=w, h=h, tm=tm, sw=sw, fc=fc, files=[], data=data))
            u['files'].append('%s@%#x' % (e['name'].split('/')[-1], o))
    keys = sorted(uniq, key=lambda k: (uniq[k]['files'][0]))
    T, cols, per = 150, 8, 64
    idx = []
    for s in range(0, len(keys), per):
        chunk = keys[s:s + per]
        sh = Image.new('RGB', (cols * (T + 4), ((len(chunk) + cols - 1) // cols) * (T + 26)), (15, 15, 15)); d = ImageDraw.Draw(sh)
        for i, k in enumerate(chunk):
            u = uniq[k]
            try:
                img = decode(u['data'], u['w'], u['h'], u['tm'], u['sw'], u['fc'])
                im = Image.fromarray(img, 'RGBA')
                bg = Image.new('RGB', im.size, (70, 110, 150)); bg.paste(im, (0, 0), im)
                bg.thumbnail((T, T))
            except Exception as ex:
                bg = Image.new('RGB', (T, 20), (120, 0, 0))
            x, y = (i % cols) * (T + 4), (i // cols) * (T + 26)
            sh.paste(bg, (x, y + 24))
            d.text((x + 1, y), '%d %s' % (s + i, u['files'][0].split('@')[0][:22]), fill=(255, 255, 0))
            d.text((x + 1, y + 11), '%dx%d BC%d +%d' % (u['w'], u['h'], 1 if u['fc'] == 4 else 3, len(u['files']) - 1), fill=(160, 200, 255))
            idx.append(dict(no=s + i, key=k, w=u['w'], h=u['h'], fmt='BC1' if u['fc'] == 4 else 'BC3', uses=u['files']))
        sh.save(os.path.join(OUT, 'sheet_%02d.png' % (s // per)))
    json.dump(idx, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('고유 텍스처', len(keys), '· 시트', (len(keys) + per - 1) // per, '→', OUT)


if __name__ == '__main__':
    main()
