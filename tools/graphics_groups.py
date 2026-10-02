# -*- coding: utf-8 -*-
"""2D 그래픽을 그림 내용으로 묶는다(현황판용, 2026-09-28).

  python -X utf8 tools/graphics_groups.py      → work/graphics_board/groups.json 만들고 요약 출력
묶는 기준(일본판 원본 그림으로 판단)
  같은 그림: ORB 특징점 + RANSAC 호모그래피 inlier 가 많으면(크기가 다르거나 일부만 잘린 같은 그림도 잡힘)
  닮은 틀  : 16x16 차이 해시(dHash) 거리가 아주 가깝고 가로세로 비가 같으면(같은 레이아웃의 광고·카드)
둘 중 하나라도 이어지면 한 묶음(연결 요소). 강한 연결(복사·해시 10 이하·inlier 40 이상)끼리는 소묶음.
어디에도 안 이어진 그림은 분야별 「그 외」.
특징은 원본 sha1 으로 캐시(work/graphics_board/_feat/).
"""
import os, json, hashlib, itertools
import numpy as np
import cv2
from PIL import Image
import extract, gtx2

ROOT = extract.ROOT
GRAPHICS = os.path.join(ROOT, 'translation', 'graphics')
OUT = os.path.join(ROOT, 'work', 'graphics_board')
FEAT = os.path.join(OUT, '_feat')
MIN_INLIERS = 25
STRONG_INLIERS = 40    # 이 이상이면 소묶음(같은 그림)
STRONG_DHASH = 10
DHASH_MAX = 18          # 256비트 중


def cat(path):
    if '/artwork/' in path: return '아트워크 포스터'
    if 'tv_tex' in path: return 'TV 광고'
    if '/Notice/' in path: return '공지·알림'
    if path.startswith('Event/'): return '컷신·이벤트 그림'
    return 'UI'


def _rgb(rgba):
    a = rgba[..., 3:4].astype(np.float32) / 255
    return (rgba[..., :3].astype(np.float32) * a + 96 * (1 - a)).astype(np.uint8)


def _dhash(gray):
    g = cv2.resize(gray, (17, 16), interpolation=cv2.INTER_AREA).astype(np.int16)
    return np.packbits((g[:, 1:] > g[:, :-1]).reshape(-1))


def features(path, raw):
    key = hashlib.sha1(raw).hexdigest()
    f = os.path.join(FEAT, key + '.npz')
    if os.path.exists(f):
        z = np.load(f)
        return dict(kp=z['kp'], des=z['des'], dh=z['dh'], ar=float(z['ar']))
    rgb = _rgb(gtx2.decode(raw)[0])
    h, w = rgb.shape[:2]
    s = 640 / max(h, w)
    small = cv2.resize(rgb, (max(8, int(w * s)), max(8, int(h * s))), interpolation=cv2.INTER_AREA) if s < 1 else rgb
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    orb = cv2.ORB_create(nfeatures=1000)
    kps, des = orb.detectAndCompute(gray, None)
    kp = np.array([k.pt for k in kps], np.float32).reshape(-1, 2)
    des = des if des is not None else np.zeros((0, 32), np.uint8)
    dh = _dhash(gray)
    os.makedirs(FEAT, exist_ok=True)
    np.savez(f, kp=kp, des=des, dh=dh, ar=w / h)
    return dict(kp=kp, des=des, dh=dh, ar=w / h)


def same_picture(a, b, bf):
    if len(a['des']) < 12 or len(b['des']) < 12:
        return 0
    m = bf.knnMatch(a['des'], b['des'], k=2)
    good = [x[0] for x in m if len(x) == 2 and x[0].distance < 0.75 * x[1].distance]
    if len(good) < MIN_INLIERS:
        return 0
    src = a['kp'][[g.queryIdx for g in good]]; dst = b['kp'][[g.trainIdx for g in good]]
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 6.0)
    return int(mask.sum()) if H is not None else 0


def build(log=print):
    man = json.load(open(os.path.join(GRAPHICS, 'manifest.json'), encoding='utf-8'))
    items = [e for e in man['done'] if e['kind'] == '2D' and e.get('pack', 'pack_030_etc') == 'pack_030_etc']
    pack = extract.open_pack('pack_030_etc')
    feats = [features(e['path'], pack.read(e['path'])) for e in items]
    n = len(items)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    edges = []                          # (i, j, 강함?, 설명)
    for i, j in itertools.combinations(range(n), 2):
        a, b = feats[i], feats[j]
        if items[i].get('copy_from') == items[j]['path'] or items[j].get('copy_from') == items[i]['path']:
            edges.append((i, j, True, '복사')); continue
        d = int(np.unpackbits(a['dh'] ^ b['dh']).sum())
        if d <= DHASH_MAX and abs(a['ar'] - b['ar']) < 0.02:
            edges.append((i, j, d <= STRONG_DHASH, '닮은 틀(해시 %d)' % d)); continue
        k = max(same_picture(a, b, bf), same_picture(b, a, bf))
        if k >= MIN_INLIERS:
            edges.append((i, j, k >= STRONG_INLIERS, '같은 그림(inlier %d)' % k))

    # 사용자 수동 배정: 같은 시리즈인데 그림 모양이 달라 못 잡은 것 → 기준 그림과 같은 묶음(소묶음은 따로)
    mp = os.path.join(GRAPHICS, 'board_groups_manual.json')
    if os.path.exists(mp):
        ix = {e['path']: i for i, e in enumerate(items)}
        man_ = {ix[it['path']]: ix[it['anchor']] for it in json.load(open(mp, encoding='utf-8'))['items'] if it['path'] in ix and it['anchor'] in ix}
        # 수동 배정한 그림은 원래 연결을 끊는다(같은 기준 그림으로 배정된 것끼리의 연결만 남김) — 두 묶음이 합쳐지지 않게
        edges = [ed for ed in edges if not ((ed[0] in man_ or ed[1] in man_) and man_.get(ed[0], -1) != man_.get(ed[1], -2))]
        for i, a in man_.items():
            edges.append((i, a, False, '수동: 같은 시리즈'))

    def comps(use):
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        for i, j, strong, _ in edges:
            if use(strong):
                parent[find(i)] = find(j)
        out_ = {}
        for i in range(n):
            out_.setdefault(find(i), []).append(i)
        return list(out_.values())
    big = comps(lambda st: True)
    sub_of = {}
    for m in comps(lambda st: st):
        for i in m:
            sub_of[i] = tuple(sorted(m))
    name = lambda i: items[i]['path'].split('/')[-1][:-4]
    groups = [m for m in big if len(m) > 1]
    rest = {}
    for m in big:
        if len(m) == 1:
            rest.setdefault(cat(items[m[0]]['path']), []).append(m[0])
    groups.sort(key=lambda m: (-len(m), items[min(m, key=lambda i: items[i]['path'])]['path']))
    out = []
    for gi, m in enumerate(groups, 1):
        subs = sorted({sub_of[i] for i in m}, key=lambda t: (-len(t), items[t[0]]['path']))
        cats = sorted({cat(items[i]['path']) for i in m})
        out.append(dict(id='g%d' % gi, title='묶음 %d · %s' % (gi, '·'.join(cats)),
                        subs=[sorted((items[i]['path'] for i in t)) for t in subs],
                        links=[(items[i]['path'], items[j]['path'], w) for i, j, st, w in edges if i in m and j in m]))
    for c_, m in sorted(rest.items()):
        out.append(dict(id='r_' + c_, title='그 외 · %s' % c_, subs=[sorted(items[i]['path'] for i in m)], links=[]))
    for g in out:
        g['paths'] = [p_ for sub in g['subs'] for p_ in sub]
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, 'groups.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log('2D %d장 → 묶음 %d개(%d장, 소묶음 %d) + 그 외 %d장' % (n, len(groups), sum(len(g) for g in groups), sum(len(g['subs']) for g in out[:len(groups)]), sum(len(m) for m in rest.values())))
    return out


if __name__ == '__main__':
    for g in build():
        print('%-28s %3d장 · 소묶음 %d' % (g['title'], len(g['paths']), len(g['subs'])))
        for sub in g['subs'][:12]:
            print('     ', ', '.join(p.split('/')[-1][:-4] for p in sub[:7]) + (' …' if len(sub) > 7 else ''))
