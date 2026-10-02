# -*- coding: utf-8 -*-
"""2D 그래픽 현황판 — 작업 대기(GPT) · 이펙트 · 완료 2D 를 비슷한 그림끼리 묶어 원본 | 한글로 보여 준다(검수용).

  python -X utf8 tools/graphics_board.py           작업용(완전 동결 뺌) → work/graphics_board/index.html
  python -X utf8 tools/graphics_board.py --final   최종 확정판(동결본 포함 완료 전부) → work/graphics_board/final.html
서버 없이 브라우저로 바로 연다(그림은 img/ 공용).
목록: translation/graphics/manifest.json 의 done 중 kind 2D
  file(한글 GTX) · tex_patch(tex_ko.json 으로 그린 것) · copy(같은 그림 복사) · original(원본 그대로)
그림은 최종 파일이 안 바뀌면 전에 만든 것을 다시 쓴다(img/_pics.json).
"""
import os, json, html, hashlib, threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
import extract, gtx2

ROOT = extract.ROOT
GRAPHICS = os.path.join(ROOT, 'translation', 'graphics')
OUT = os.path.join(ROOT, 'work', 'graphics_board')
IMG = os.path.join(OUT, 'img')
E = html.escape
METHOD = {'file': '한글', 'tex_patch': 'tex_patch', 'copy': '같은 그림 복사', 'original': '원본 그대로'}


def cat(path):
    if '/artwork/' in path: return '아트워크 포스터'
    if 'tv_tex' in path: return 'TV 광고'
    if '/Notice/' in path: return '공지·알림'
    if path.startswith('Event/'): return '컷신·이벤트 그림'
    return 'UI'


def flat(rgba, dark=(24, 24, 30)):
    im = Image.fromarray(rgba, 'RGBA')
    bg = Image.new('RGB', im.size, dark); bg.paste(im, (0, 0), im)
    return bg


def pair(a, b, maxw=1024):
    s = min(1.0, maxw / max(a.width, 1))
    if s < 1:
        a = a.resize((round(a.width * s), round(a.height * s)), Image.LANCZOS)
        b = b.resize((round(b.width * s), round(b.height * s)), Image.LANCZOS)
    sh = Image.new('RGB', (a.width + b.width + 10, max(a.height, b.height)), (40, 40, 40))
    sh.paste(a, (0, 0)); sh.paste(b, (a.width + 10, 0))
    return sh


def one(a, maxw=1024):
    return a.resize((maxw, round(a.height * maxw / a.width)), Image.LANCZOS) if a.width > maxw else a


def _base(path):
    return path.split('/')[-1][:-4]


KO_HINT = {}          # 경로 → 대표 한글 문구(번역 기록에서), main 에서 채움


def sub_title(sub):
    """소묶음 이름.
    같은 종류(예: tv_tex, notice_tex)끼리면 번호 나열, 아니면 가장 많이 겹치는 이름 앞부분 + 계열.
    아트워크가 있으면 그 포스터 계열. 번역 기록이 있으면 대표 한글 문구를 괄호로."""
    import re
    from collections import Counter
    names = [re.sub(r'^\d+_', '', _base(p)) for p in sub]
    art = [_base(p) for p in sub if '/artwork/' in p]
    fam = [re.match(r'^(.*?)(\d+)$', n) for n in names]
    if art:
        t = '%s 포스터 계열' % art[0]
    elif len(sub) > 1 and all(fam) and len({m.group(1) for m in fam}) == 1:
        nums = [m.group(2) for m in fam]
        t = '%s %s' % (fam[0].group(1).rstrip('_'), '·'.join(nums[:6]) + ('…' if len(nums) > 6 else ''))
    elif len(sub) > 1:
        cnt = Counter()
        for n in names:
            parts = n.split('_')
            for k in range(1, len(parts)):
                cnt['_'.join(parts[:k])] += 1
        best = max(cnt.items(), key=lambda kv: (kv[1] >= 2, kv[1] * len(kv[0]))) if cnt else None
        if best and best[1] >= 2:
            odd = [n for n in names if not (n == best[0] or n.startswith(best[0] + '_'))]
            t = '%s 계열' % best[0] + ((' + ' + ', '.join(odd)) if 0 < len(odd) <= 2 else (' 외 %d' % len(odd) if odd else ''))
        else:
            t = '%s 외 %d' % (_base(sub[0]), len(sub) - 1)
    else:
        t = _base(sub[0])
    hint = next((KO_HINT[p] for p in sub if KO_HINT.get(p)), '')
    return t + (' 「%s」' % hint if hint else '')


def group_title(g):
    if g['id'].startswith('r_'):
        return g['title']
    head = sub_title(g['subs'][0])
    return '%s — %s%s' % (g['title'].split(' · ')[0], head, (' 등 소묶음 %d' % len(g['subs'])) if len(g['subs']) > 1 else '')


def _tr_pairs(t):
    """manifest 의 translations — [[원문, 한글]] · [{ja/ko...}] · {원문: 한글} 어느 쪽이든 '원문 → 한글' 목록으로."""
    if not t:
        return []
    if isinstance(t, dict):
        return ['%s → %s' % kv for kv in t.items()]
    out = []
    for x in t:
        if isinstance(x, (list, tuple)) and len(x) >= 2:
            out.append('%s → %s' % (x[0], x[1]))
        elif isinstance(x, dict):
            src = x.get('ja') or x.get('source') or x.get('original') or x.get('jp') or ''
            dst = x.get('ko') or x.get('target') or x.get('korean') or x.get('translation') or ''
            out.append('%s → %s' % (src, dst) if src or dst else json.dumps(x, ensure_ascii=False))
        else:
            out.append(str(x))
    return out


def _eft_rgba(raw, key):
    """'Effect/x.ptcl@0xOFF' 의 텍스처를 raw(ptcl 바이트)에서 풀어 RGBA."""
    import eft_survey as ES
    off = int(key.split('@')[1], 16)
    t = [t for t in ES.textures(raw) if t[0] == off][0]
    o, w, h, tm, sw, fc, pos, size = t
    return ES.decode(raw[pos:pos + size], w, h, tm, sw, fc)


def excluded():
    """translation/graphics/board_exclude.json 의 경로(작업용 현황판에서 뺌, 빌드와는 무관)."""
    p = os.path.join(GRAPHICS, 'board_exclude.json')
    return {e['path'] for e in json.load(open(p, encoding='utf-8'))['items']} if os.path.exists(p) else set()


def main(final=False):
    man = json.load(open(os.path.join(GRAPHICS, 'manifest.json'), encoding='utf-8'))
    PK = lambda e: e.get('pack', 'pack_030_etc')
    items = sorted((e for e in man['done'] if e['kind'] == '2D' and PK(e) == 'pack_030_etc'), key=lambda e: (cat(e['path']), e['path']))
    eft_done = [e for e in man['done'] if PK(e) == 'pack_020_effect']
    todo = man.get('todo', [])
    skipped = sum(1 for e in man['skipped'] if e['kind'] == '2D')
    by = {e['path']: e for e in items}
    pack = extract.open_pack('pack_030_etc')
    epack = extract.open_pack('pack_020_effect')
    lock = threading.Lock()
    tp = {}
    if any(e['method'] == 'tex_patch' for e in items):
        import tex_patch
        tp = tex_patch.build(lambda *a: None)
    eft_new = {}
    if eft_done:
        import eft_inject
        eft_new = eft_inject.build(lambda *a: None)
    os.makedirs(IMG, exist_ok=True)
    pics_p = os.path.join(IMG, '_pics.json')
    try:
        old = json.load(open(pics_p, encoding='utf-8'))
    except Exception:
        old = {}
    new = {}

    def after_bytes(e):
        if e['method'] == 'file':
            return open(os.path.join(GRAPHICS, e['file']), 'rb').read()
        if e['method'] == 'tex_patch':
            return tp.get(e['path'])
        if e['method'] == 'copy':
            return after_bytes(by[e['copy_from']])
        return None

    def work(e, is_todo=False):
        path = e['path']
        name = path.replace('/', '__').replace('@', '_').replace('.gtx', '').replace('.ptcl', '') + ('__todo' if is_todo else '') + '.png'
        if PK(e) == 'pack_020_effect':
            fn = path.split('@')[0]
            with lock:
                raw = epack.read(fn)
            a = eft_new.get(fn) if not is_todo else None
            key = 'eft:' + (hashlib.sha1(a).hexdigest() if a else 'original')
            dst = os.path.join(IMG, name)
            with lock:
                new[name] = key
            if old.get(name) == key and os.path.exists(dst):
                return name
            before = flat(_eft_rgba(raw, path))
            img = pair(before, flat(_eft_rgba(a, path))) if a else one(before)
        else:
            a = None if is_todo else after_bytes(e)
            key = hashlib.sha1(a).hexdigest() if a else 'original'
            dst = os.path.join(IMG, name)
            with lock:
                new[name] = key
            if old.get(name) == key and os.path.exists(dst):
                return name
            with lock:
                raw = pack.read(path)
            before = flat(gtx2.decode(raw)[0])
            img = pair(before, flat(gtx2.decode(a)[0])) if a else one(before)
        img.save(dst, compress_level=1)
        return name

    with ThreadPoolExecutor(8) as ex:
        names = list(ex.map(work, items))
        eft_names = list(ex.map(work, eft_done))
        todo_names = list(ex.map(lambda e: work(e, True), todo))
    for fn in os.listdir(IMG):
        if fn.endswith('.png') and fn not in new:
            os.remove(os.path.join(IMG, fn))
    json.dump(new, open(pics_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

    from collections import Counter
    import graphics_groups
    gp = os.path.join(OUT, 'groups.json')
    groups = json.load(open(gp, encoding='utf-8')) if os.path.exists(gp) else None
    if not groups or 'subs' not in groups[0] or {x for g in groups for x in g['paths']} != set(by):
        groups = graphics_groups.build()           # 목록이 바뀌었으면 다시 묶는다(특징은 캐시)
    frozen = excluded()
    ex = set() if final else frozen
    shown = []
    for g in groups:                               # 제외한 파일을 빼고, 빈 소묶음·묶음은 없앤다(묶음 번호는 그대로)
        subs = [[p for p in s if p not in ex] for s in g['subs']]
        subs = [s for s in subs if s]
        if subs:
            shown.append(dict(g, subs=subs, paths=[p for s in subs for p in s]))
    groups = shown
    n_ex = sum(1 for p in by if p in ex)
    # 작업 대기(todo) 항목의 수동 배정: 기준 그림이 있는 묶음 안에 작업 대기 소묶음으로 넣고, 맨 위 작업 대기 구역에선 뺀다
    mp = os.path.join(GRAPHICS, 'board_groups_manual.json')
    todo_in = {}
    if os.path.exists(mp):
        tpaths = {e['path'] for e in todo}
        for it in json.load(open(mp, encoding='utf-8'))['items']:
            if it['path'] in tpaths:
                gid = next((g['id'] for g in groups if it['anchor'] in g['paths']), None)
                if gid:
                    todo_in.setdefault(gid, []).append(it['path'])
    name_of = dict(zip((e['path'] for e in items), names))
    tk = json.load(open(os.path.join(ROOT, 'translation', 'tex_ko.json'), encoding='utf-8'))
    for e in items:
        pairs = _tr_pairs(e.get('translations'))
        v = tk.get('gtx_' + _base(e['path']))
        if not pairs and isinstance(v, list):
            pairs = _tr_pairs(v)
        if pairs:
            ko = pairs[0].split(' → ', 1)[-1].strip()
            KO_HINT[e['path']] = ko[:18] + ('…' if len(ko) > 18 else '')
    vis = [e for e in items if e['path'] not in ex]
    cc = Counter(cat(e['path']) for e in vis); mc = Counter(e['method'] for e in vis)
    wc = Counter(e.get('made_by') for e in vis + eft_done if e.get('made_by'))

    def card(e, img_name, kind, lab_pair, tag, note):
        path = e['path']; c_ = '이펙트' if PK(e) == 'pack_020_effect' else cat(path)
        tr = ' · '.join(_tr_pairs(e.get('translations'))[:6])
        lab = '<div class="lab"><span>원본</span><span>한글</span></div>' if lab_pair else '<div class="lab"><span>%s</span></div>' % E(lab_pair is None and '원본 그대로(한글화 안 함)' or '원본 (작업 대기)')
        return ('<div class="card" data-k="%s" data-c="%s" data-p="%s">%s<img loading="lazy" src="img/%s"><div class="t">%s%s</div>'
                '<div class="w"><b class="pk">%s</b> · %s · %s</div>%s</div>'
                % (kind, E(c_), E(path.lower()), lab, E(img_name), tag, E(path), E(PK(e)), E(c_), E(note),
                   '<div class="w">%s</div>' % E(tr) if tr else ''))

    out = ['<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>2D 그래픽 현황</title><style>%s</style></head><body>' % CSS]
    out.append('<header><h1>환영이문록♯FE %s</h1><div class="sum">' % ('최종 확정판 — 완료 전부(동결본 포함), 비슷한 그림끼리 묶음' if final else '2D 그래픽 현황 — 비슷한 그림끼리 묶음'))
    out.append('<div style="border:1px solid #ffb347"><small>작업 대기 (GPT)</small><b>%d</b><small>%s</small></div>'
               % (len(todo), ' · '.join('%s %d' % (p, n) for p, n in sorted(Counter(PK(e) for e in todo).items()))))
    out.append('<div><small>완료 2D</small><b>%d</b><small>한글 %d · 복사 %d%s</small></div>' % (
        len(vis) + len(eft_done), mc['file'] + len(eft_done), mc['copy'], (' · 이펙트 %d' % len(eft_done)) if eft_done else ''))
    out.append('<div><small>작업자</small><b>%d</b><small>%s</small></div>' % (sum(wc.values()), ' · '.join('%s %d' % kv for kv in wc.most_common())))
    out.append('<div><small>원본 그대로</small><b>%d</b><small>한글화 안 함</small></div>' % mc['original'])
    out.append('<div><small>완전 동결</small><b>%d</b><small>%s</small></div>' % (sum(1 for p in by if p in frozen), '[동결] 표시 · 수정 금지' if final else '현황판에서 뺌 · 수정 금지 · 빌드엔 들어감'))
    out.append('<div><small>건너뜀 2D</small><b>%d</b><small>여기엔 안 보임</small></div></div>' % skipped)
    out.append('<div class="ctl">보기: <button data-k="all" class="on">전체</button><button data-k="m:todo">작업 대기 %d</button>' % len(todo)
               + ''.join('<button data-k="c:%s">%s %d</button>' % (E(c), E(c), cc[c]) for c in sorted(cc))
               + ('<button data-k="c:이펙트">이펙트 %d</button>' % (len(eft_done) + sum(PK(e) == 'pack_020_effect' for e in todo)))
               + ''.join('<button data-k="m:%s">%s %d</button>' % (m, E(METHOD[m]), mc[m]) for m in ('copy', 'tex_patch', 'original') if mc[m])
               + ' <input id="q" placeholder="경로 검색"> <small id="dn" style="color:#9aa0a8"></small></div></header>')
    # 구역 목록: 작업 대기 → 이펙트 완료 → 기존 묶음
    sections = []
    todo_name = {e['path']: n for e, n in zip(todo, todo_names)}
    todo_by = {e['path']: e for e in todo}
    moved = {p for v in todo_in.values() for p in v}
    todo_card = lambda e: card(e, todo_name[e['path']], 'todo', False, '<b style="color:#ffb347">[작업 대기] </b>',
                               '%s · %s%s' % (e.get('what', ''), e.get('size', ''), (' · ' + e['note']) if e.get('note') else ''))
    if todo:
        subs = {}
        for e, n in zip(todo, todo_names):
            if e['path'] not in moved:
                subs.setdefault(PK(e), []).append((e, n))
        sections.append(('todo', '작업 대기 (GPT) — 전수조사로 새로 찾은 것', [
            ('%s · %s' % (pk, {'pack_020_effect': '이펙트', 'pack_030_etc': '2D'}.get(pk, '')),
             [todo_card(e) for e, n in lst]) for pk, lst in sorted(subs.items())], '#ffb347'))
    if eft_done:
        sections.append(('eft', '이펙트 (pack_020_effect) — 상호작용 표시·전투 배너·크레디트', [
            (None, [card(e, n, e['method'], True, '', '%s · %s' % (e.get('made_by', ''), e.get('note', ''))) for e, n in zip(eft_done, eft_names)])], None))
    for g in groups:
        subs = []
        for sub in g['subs']:
            cards = []
            for path in sub:
                e = by[path]; m = e['method']
                tag = ('' if m == 'file' else '<b style="color:#ffb347">[%s] </b>' % E(METHOD[m])) + ('<b style="color:#7fc8ff">[동결] </b>' if final and path in frozen else '')
                note = e.get('made_by') or e.get('note') or ''
                if m == 'copy':
                    note = '같은 그림: ' + e['copy_from']
                cards.append(card(e, name_of[path], m, False if m == 'original' and False else (None if m == 'original' else True), tag, note))
            subs.append((sub_title(sub) if len(g['subs']) > 1 or g['id'] in todo_in else None, cards))
        if g['id'] in todo_in:
            subs.append(('작업 대기 (GPT)', [todo_card(todo_by[p]) for p in todo_in[g['id']]]))
        sections.append((g['id'], group_title(g), subs, None))
    out.append('<nav id="toc"><b>묶음 목차</b>')
    for sid, title, subs, color in sections:
        out.append('<a href="#%s" id="toc-%s"%s>%s <small>%d</small></a>' % (sid, sid, (' style="color:%s"' % color) if color else '', E(title), sum(len(c) for _, c in subs)))
    out.append('</nav><main>')
    for sid, title, subs, color in sections:
        n = sum(len(c) for _, c in subs)
        out.append('<section class="grp" id="%s"><h2%s>%s <small>%d장%s</small></h2>' % (
            sid, (' style="border-color:%s"' % color) if color else '', E(title), n, (' · 소묶음 %d' % len(subs)) if len(subs) > 1 else ''))
        for st, cards in subs:
            out.append('<div class="sub">')
            if st:
                out.append('<h3>%s <small>%d장</small></h3>' % (E(st), len(cards)))
            out.append('<div class="grid">' + ''.join(cards) + '</div></div>')
        out.append('</section>')
    out.append(ZOOM)
    html_name = 'final.html' if final else 'index.html'
    open(os.path.join(OUT, html_name), 'w', encoding='utf-8').write(''.join(out))
    print('2D %d장 · 이펙트 %d · 작업 대기 %d · 그림 새로 만듦 %d · %s' % (len(items), len(eft_done), len(todo),
          sum(1 for n in new if old.get(n) != new[n]), os.path.join(OUT, html_name)))



CSS = ('*{box-sizing:border-box}body{background:#17191d;color:#e6e6e6;font-family:"Malgun Gothic","Noto Sans KR",sans-serif;margin:0}'
       'header{position:sticky;top:0;z-index:5;background:#101215;border-bottom:1px solid #333;padding:12px 16px}'
       'h1{font-size:18px;margin:0 0 8px}.sum{display:flex;gap:10px;flex-wrap:wrap}.sum div{background:#23262c;border-radius:8px;padding:8px 14px;min-width:92px}'
       '.sum b{display:block;font-size:22px}.sum small{color:#9aa0a8}.ctl{margin-top:8px;font-size:13px}.ctl button{background:#2c3037;color:#ddd;border:0;border-radius:4px;padding:4px 10px;margin:2px;cursor:pointer}'
       '.ctl button.on{background:#ffd24a;color:#111}.ctl input{background:#23262c;color:#eee;border:1px solid #444;border-radius:4px;padding:4px 8px;width:220px}'
       'main{padding:16px 16px 16px 276px}h2{font-size:16px;margin:26px 0 10px;border-left:4px solid #ffd24a;padding-left:8px}h2 small,h3 small{color:#9aa0a8;font-weight:normal}'
       'h3{font-size:13px;margin:14px 0 6px;color:#c9d1d9;border-left:3px solid #4fc27a;padding-left:6px}.grp{border-bottom:1px solid #2c3037;padding-bottom:10px}'
       '#toc{position:fixed;left:0;top:118px;bottom:0;width:260px;overflow:auto;background:#121417;border-right:1px solid #2c3037;padding:10px;font-size:12px}'
       '#toc a{display:block;color:#c9d1d9;text-decoration:none;padding:3px 4px;border-radius:3px}#toc a:hover{background:#23262c}#toc small{color:#9aa0a8}'
       '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(460px,1fr));gap:12px}'
       '.card{background:#23262c;border-radius:8px;padding:8px}.card img{width:100%;height:auto;display:block;border-radius:4px;background:#111;cursor:zoom-in}'
       '.card .t{font-size:12px;margin-top:6px;word-break:break-all}.pk{color:#7fd1ff;font-weight:normal}.card .w{font-size:11px;color:#9aa0a8}.lab{display:flex;justify-content:space-around;font-size:11px;color:#9aa0a8;margin-bottom:3px}'
       '#zoom{position:fixed;inset:0;background:#0b0c0e;display:none;z-index:9;cursor:grab;overflow:hidden}#zoom.drag{cursor:grabbing}'
       '#zoom img{position:absolute;left:0;top:0;transform-origin:0 0;image-rendering:pixelated;max-width:none;max-height:none;user-select:none;-webkit-user-drag:none}'
       '#zb{position:fixed;top:10px;right:12px;z-index:10;display:none;gap:6px;align-items:center;background:#101215cc;padding:6px 8px;border-radius:6px;font-size:13px}'
       '#zb button{background:#2c3037;color:#eee;border:0;border-radius:4px;padding:4px 10px;cursor:pointer;font-size:14px}#zb span{min-width:52px;text-align:center}')

ZOOM = ('</main><div id="zoom"><img draggable="false"></div>'
        '<div id="zb"><button data-z="prev">◀ 이전</button><span id="zn"></span><button data-z="next">다음 ▶</button><button data-z="out">－</button><span id="zp">100%</span><button data-z="in">＋</button>'
        '<button data-z="fit">화면 맞춤</button><button data-z="one">1:1</button><button data-z="x">닫기 (Esc)</button></div><script>'
        'const z=document.getElementById("zoom"),zi=z.querySelector("img"),zb=document.getElementById("zb"),zp=document.getElementById("zp"),zn=document.getElementById("zn");let L=[],I=0;'
        'let S=1,X=0,Y=0,drag=null;'
        'function ap(){zi.style.transform=`translate(${X}px,${Y}px) scale(${S})`;zp.textContent=Math.round(S*100)+"%"}'
        'function fit(){const w=innerWidth,h=innerHeight;S=Math.min(w*0.96/zi.naturalWidth,h*0.92/zi.naturalHeight);X=(w-zi.naturalWidth*S)/2;Y=(h-zi.naturalHeight*S)/2;ap()}'
        'function one(){const w=innerWidth,h=innerHeight;S=1;X=Math.round((w-zi.naturalWidth)/2);Y=Math.round((h-zi.naturalHeight)/2);ap()}'
        'function zoomAt(f,cx,cy){const n=Math.min(16,Math.max(0.1,S*f));X=cx-(cx-X)*n/S;Y=cy-(cy-Y)*n/S;S=n;ap()}'
        'function show(i){I=(i+L.length)%L.length;const src=L[I].src;zn.textContent=(I+1)+" / "+L.length;zi.onload=one;if(zi.src==src&&zi.complete)one();else zi.src=src}'
        'function open_(img){L=[...document.querySelectorAll("main .card img")].filter(i=>i.offsetParent!==null);if(!L.includes(img))L=[img];z.style.display="block";zb.style.display="flex";show(L.indexOf(img))}'
        'function close_(){z.style.display="none";zb.style.display="none"}'
        'document.querySelectorAll(".card img").forEach(i=>i.onclick=()=>open_(i));'
        'z.addEventListener("wheel",e=>{e.preventDefault();let d=e.deltaY*(e.deltaMode==1?16:e.deltaMode==2?400:1);d=Math.max(-120,Math.min(120,d));zoomAt(Math.exp(-d*0.0015),e.clientX,e.clientY)},{passive:false});'
        'z.onmousedown=e=>{drag=[e.clientX-X,e.clientY-Y];z.classList.add("drag")};'
        'addEventListener("mousemove",e=>{if(drag){X=e.clientX-drag[0];Y=e.clientY-drag[1];ap()}});'
        'addEventListener("mouseup",()=>{drag=null;z.classList.remove("drag")});'
        'z.ondblclick=e=>{S>=2?fit():zoomAt(4/S,e.clientX,e.clientY)};'
        'zb.onclick=e=>{const k=e.target.dataset.z;if(!k)return;const cx=innerWidth/2,cy=innerHeight/2;'
        'if(k=="prev")show(I-1);else if(k=="next")show(I+1);else if(k=="in")zoomAt(1.5,cx,cy);else if(k=="out")zoomAt(1/1.5,cx,cy);else if(k=="fit")fit();else if(k=="one")one();else close_()};'
        'addEventListener("keydown",e=>{if(z.style.display!="block")return;if(e.key=="ArrowLeft"){e.preventDefault();show(I-1)}else if(e.key=="ArrowRight"){e.preventDefault();show(I+1)}else if(e.key=="Escape")close_();else if(e.key=="+"||e.key=="=")zoomAt(1.5,innerWidth/2,innerHeight/2);else if(e.key=="-")zoomAt(1/1.5,innerWidth/2,innerHeight/2);else if(e.key=="0")fit();else if(e.key=="1")one()});'
        'const bs=document.querySelectorAll(".ctl button"),q=document.getElementById("q"),dn=document.getElementById("dn");let k="all";'
        'function f(){const t=q.value.toLowerCase();let n=0;document.querySelectorAll("main .card").forEach(c=>{const ok=(k=="all"||(k.startsWith("c:")?c.dataset.c==k.slice(2):c.dataset.k==k.slice(2)))&&c.dataset.p.includes(t);c.style.display=ok?"":"none";n+=ok});document.querySelectorAll(".sub").forEach(s=>{s.style.display=[...s.querySelectorAll(".card")].some(c=>c.style.display!="none")?"":"none"});document.querySelectorAll(".grp").forEach(g=>{const v=[...g.querySelectorAll(".card")].filter(c=>c.style.display!="none").length;g.style.display=v?"":"none";const a=document.getElementById("toc-"+g.id);if(a)a.style.display=v?"":"none"});'
         'dn.textContent="(보이는 것 "+n+"장)"}'
        'bs.forEach(b=>b.onclick=()=>{bs.forEach(x=>x.classList.remove("on"));b.classList.add("on");k=b.dataset.k;f()});q.oninput=f;f();'
        '</script></body></html>')


if __name__ == '__main__':
    import sys
    main(final='--final' in sys.argv)
