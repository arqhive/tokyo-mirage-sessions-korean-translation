# -*- coding: utf-8 -*-
"""pack_030_etc 의 목록 밖 GTX 전수 확인 시트(2026-09-28).

  python -X utf8 tools/gtx_survey.py      → work/gtx_survey/<묶음>_NN.png, index.json
목록 = translation/graphics/manifest.json 의 done·skipped. 그 밖의 GTX 를 전부 풀어 같은 그림은 하나로,
폴더 묶음별로 시트를 만든다. 배경처럼 큰 그림은 작은 글씨가 보이게 크게.
"""
import os, json, hashlib
import numpy as np
from PIL import Image, ImageDraw
import extract, gtx2

ROOT = extract.ROOT
OUT = os.path.join(ROOT, 'work', 'gtx_survey')


def group(n):
    p = n.split('/')
    if n.startswith('Interface/common/'):
        return 'common_' + p[2]
    return '_'.join(p[:2])


def main():
    os.makedirs(OUT, exist_ok=True)
    man = json.load(open(os.path.join(ROOT, 'translation', 'graphics', 'manifest.json'), encoding='utf-8'))
    listed = {e['path'] for e in man['done']} | {e['path'] for e in man['skipped']}
    c = extract.open_pack('pack_030_etc')
    uniq = {}
    for e in c.files:
        n = e['name']
        if not n.endswith('.gtx') or n in listed:
            continue
        b = c.read(e)
        try:
            a = gtx2.decode(b)[0]
        except Exception as ex:
            uniq.setdefault('ERR_' + n, dict(names=[n], err=str(ex)[:60]))
            continue
        k = hashlib.sha1(a.tobytes()).hexdigest()[:16]
        u = uniq.setdefault(k, dict(names=[], shape=a.shape[:2], img=a))
        u['names'].append(n)
    groups = {}
    for k, u in uniq.items():
        groups.setdefault(group(u['names'][0]), []).append(k)
    idx = []
    for g, keys in sorted(groups.items()):
        keys.sort(key=lambda k: uniq[k]['names'][0])
        big = g.startswith(('Event_bustup', 'Event_images', 'Event_extras', 'Interface_2d_bu_event', 'Interface_FacilityBg', 'Interface_Notice', 'Interface_artwork'))
        T, cols = (460, 4) if big else (170, 8)
        per = cols * (4 if big else 8)
        for s in range(0, len(keys), per):
            chunk = keys[s:s + per]
            rows = (len(chunk) + cols - 1) // cols
            sh = Image.new('RGB', (cols * (T + 4), rows * (T + 16)), (15, 15, 15)); d = ImageDraw.Draw(sh)
            for i, k in enumerate(chunk):
                u = uniq[k]
                x, y = (i % cols) * (T + 4), (i // cols) * (T + 16)
                d.text((x + 1, y), '%s%s' % (u['names'][0].split('/')[-1][:30], (' +%d' % (len(u['names']) - 1)) if len(u['names']) > 1 else ''), fill=(255, 255, 0))
                if 'img' in u:
                    im = Image.fromarray(u['img'], 'RGBA'); bg = Image.new('RGB', im.size, (70, 110, 150)); bg.paste(im, (0, 0), im)
                    bg.thumbnail((T, T)); sh.paste(bg, (x, y + 14))
                idx.append(dict(group=g, sheet='%s_%02d.png' % (g, s // per), names=u['names'], shape=list(u.get('shape', (0, 0)))))
            sh.save(os.path.join(OUT, '%s_%02d.png' % (g, s // per)))
    json.dump(idx, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    from collections import Counter
    cnt = Counter(i['group'] for i in idx)
    print('목록 밖 GTX 고유', len(uniq), '· 묶음', dict(cnt))
    print('시트', len(os.listdir(OUT)) - 1)


if __name__ == '__main__':
    main()
