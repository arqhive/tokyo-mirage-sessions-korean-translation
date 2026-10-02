# -*- coding: utf-8 -*-
"""이펙트(pack_020_effect) 그림 주입 — translation/graphics/eft/*.png 를 .ptcl 텍스처에 넣는다(2026-09-28).

  python -X utf8 tools/eft_inject.py      → 검사만(바뀐 블록 수·다시 푼 오차)
목록 = translation/graphics/manifest.json done 중 pack_020_effect, 경로 'Effect/<파일>.ptcl@<텍스처 정보 위치>'.
PNG 는 원본 텍스처와 같은 크기 RGBA(GPT 납품). 텍스처 정보·형식은 tools/eft_survey.py.
방법: 원본을 풀어 PNG 와 다른 4x4 블록만 다시 압축 — BC1 은 색 8바이트, BC3 은 색 8바이트 + (알파가 바뀐 블록만) BC4 알파 8바이트.
      안 바뀐 블록과 텍스처 밖은 원본 바이트 그대로, 파일 크기 불변.
"""
import os, json
import numpy as np
from PIL import Image
import extract, gtx_lib, bc1
import eft_survey as ES

ROOT = extract.ROOT
GRAPHICS = os.path.join(ROOT, 'translation', 'graphics')


def targets():
    man = json.load(open(os.path.join(GRAPHICS, 'manifest.json'), encoding='utf-8'))
    return [e for e in man['done'] if e.get('pack') == 'pack_020_effect' and e['method'] == 'file']


def inject(b, off, rgba, ref=None):
    """ptcl 바이트 b 의 텍스처(정보 위치 off)에 rgba 를 넣은 새 바이트와 바뀐 블록 수.
    ref: 비교 기준 원본(같은 파일의 여러 텍스처를 차례로 넣을 때 원본 파일) — 데이터를 같이 쓰는 텍스처를 두 번 압축하지 않게."""
    o, w, h, tm, sw, fc, pos, size = [t for t in ES.textures(b) if t[0] == off][0]
    assert rgba.shape == (h, w, 4), (rgba.shape, w, h)
    bpb = ES.FMT[fc][1]
    old = ES.decode((ref or b)[pos:pos + size], w, h, tm, sw, fc)
    if fc == 4:
        assert rgba[..., 3].min() == 255, 'BC1 텍스처인데 투명 픽셀이 있음'
    bh, bw = h // 4, w // 4
    blk = lambda a: a.reshape(bh, 4, bw, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh, bw, 16, 4)
    nb, ob = blk(rgba), blk(old)
    ys, xs = np.nonzero(np.any(nb != ob, axis=(2, 3)))
    buf = bytearray(b)
    if len(ys):
        new = nb[ys, xs]
        col = bc1.encode_blocks(new[..., :3].astype(np.float64))
        base = pos + ES.addr(w, h, tm, sw, fc)[ys, xs] + (8 if fc == 8 else 0)
        arr = np.frombuffer(buf, np.uint8)
        arr = np.array(arr)
        for j in range(8):
            arr[base + j] = col[:, j]
        if fc == 8:
            ach = np.any(new[..., 3] != ob[ys, xs][..., 3], axis=1)
            if ach.any():
                N = int(ach.sum())
                aimg = new[ach][..., 3].reshape(N, 4, 4).transpose(1, 0, 2).reshape(4, N * 4)
                alp = gtx_lib.bc4_encode_blocks(np.ascontiguousarray(aimg))[0]
                abase = pos + ES.addr(w, h, tm, sw, fc)[ys[ach], xs[ach]]
                for j in range(8):
                    arr[abase + j] = alp[:, j]
        buf = arr.tobytes()
    nbytes = bytes(buf)
    assert len(nbytes) == len(b)
    d = np.nonzero(np.frombuffer(nbytes, np.uint8) != np.frombuffer(b, np.uint8))[0]
    assert len(d) == 0 or (d.min() >= pos and d.max() < pos + size), '텍스처 밖 바이트가 바뀜'
    return nbytes, len(ys)


def build(log=print):
    """{ptcl 경로: 새 바이트} — 같은 파일의 여러 텍스처를 차례로 넣는다."""
    c = extract.open_pack('pack_020_effect')
    by = {}
    for e in targets():
        fn, off = e['path'].split('@')
        by.setdefault(fn, []).append((int(off, 16), e))
    out = {}
    for fn, lst in sorted(by.items()):
        b = orig = c.read(fn)
        info = []
        for off, e in lst:
            rgba = np.asarray(Image.open(os.path.join(GRAPHICS, e['file'])).convert('RGBA'))
            b, n = inject(b, off, rgba, orig)
            t = [t for t in ES.textures(b) if t[0] == off][0]
            back = ES.decode(b[t[6]:t[6] + t[7]], *t[1:6]).astype(np.int32)
            err = np.abs(back - rgba).max(-1)
            info.append('%#x 블록 %d · 오차 평균 %.2f 최대 %d' % (off, n, err.mean(), err.max()))
        assert b != orig, fn
        out[fn] = b
        log('  %s: %s' % (fn.split('/')[-1], ' / '.join(info)))
    return out


if __name__ == '__main__':
    r = build()
    print('이펙트 파일 %d개 · 텍스처 %d장' % (len(r), len(targets())))
