"""텍스처를 PNG 로 빼고, 편집한 PNG 를 다시 넣는다.

로고처럼 자동 재현이 어려운 그림은 직접 편집하는 게 낫다.
RGBA8 텍스처라 무손실로 오간다. **크기는 원본과 똑같아야 한다.**

  python tex_io.py out Interface/title/title_logo      -> work/tex/_edit/title_logo.png
  python tex_io.py out "Interface/title/*"             여러 장
  python tex_io.py in  Interface/title/title_logo      편집한 PNG 를 확인 (미리보기만)
  python tex_io.py list                                 편집 대상으로 잡힌 PNG 목록

`in` 으로 확인한 뒤 build_patch.py 를 돌리면 패치에 들어간다
(work/tex/_edit/ 안의 PNG 는 tex_patch.build() 가 자동으로 집어 온다).
"""
import os, sys, fnmatch
import numpy as np
from PIL import Image
import extract, gtx2

EDIT_DIR = os.path.join(extract.WORK, 'tex', '_edit')
MAP_FILE = os.path.join(EDIT_DIR, '_paths.txt')


def _load_map():
    m = {}
    if os.path.exists(MAP_FILE):
        for line in open(MAP_FILE, encoding='utf-8'):
            line = line.strip()
            if line and '\t' in line:
                stem, inner = line.split('\t', 1)
                m[stem] = inner
    return m


def _save_map(m):
    os.makedirs(EDIT_DIR, exist_ok=True)
    with open(MAP_FILE, 'w', encoding='utf-8') as f:
        for k, v in sorted(m.items()):
            f.write('%s\t%s\n' % (k, v))


def cmd_out(args):
    pat = args[0]
    if not pat.endswith('.gtx'):
        pat += '.gtx' if '*' not in pat else ''
    c = extract.open_pack('pack_030_etc')
    m = _load_map()
    os.makedirs(EDIT_DIR, exist_ok=True)
    n = 0
    for e in c.files:
        name = e['name']
        if not name.lower().endswith('.gtx'):
            continue
        if not (fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(name, pat + '*')):
            continue
        img, info = gtx2.decode(c.read(e))
        stem = os.path.basename(name)[:-4]
        p = os.path.join(EDIT_DIR, stem + '.png')
        Image.fromarray(img, 'RGBA').save(p)
        m[stem] = name
        n += 1
        print('%-44s %dx%d -> %s' % (name, info['surf']['width'], info['surf']['height'], p))
    _save_map(m)
    print('%d장. 편집 후 그대로 저장하면 된다 (크기·RGBA 유지).' % n)


def load_edited(log=print):
    """편집된 PNG 를 {내부경로: gtx bytes} 로. build_patch 가 쓴다."""
    m = _load_map()
    if not m:
        return {}
    c = extract.open_pack('pack_030_etc')
    out = {}
    for stem, inner in m.items():
        p = os.path.join(EDIT_DIR, stem + '.png')
        if not os.path.exists(p):
            continue
        raw = c.read(inner)
        orig, info = gtx2.decode(raw)
        im = Image.open(p).convert('RGBA')
        arr = np.array(im)
        if arr.shape != orig.shape:
            log('  ! %s: 크기가 다르다 %s vs %s — 건너뜀' % (stem, arr.shape[:2][::-1], orig.shape[:2][::-1]))
            continue
        if np.array_equal(arr, orig):
            continue                       # 손대지 않은 것은 넣지 않는다
        out[inner] = gtx2.encode(arr, raw)
        log('  %-30s 편집본 반영' % stem)
    return out


def cmd_in(args):
    data = load_edited()
    print('반영 대상 %d장' % len(data))


def cmd_list(args):
    m = _load_map()
    for stem, inner in sorted(m.items()):
        p = os.path.join(EDIT_DIR, stem + '.png')
        print('%-28s %s  %s' % (stem, '있음' if os.path.exists(p) else '없음', inner))


if __name__ == '__main__':
    {'out': cmd_out, 'in': cmd_in, 'list': cmd_list}[sys.argv[1]](sys.argv[2:])
