# -*- coding: utf-8 -*-
"""번역 원문 대조 검수(추가·누락) 묶음 만들기 — 2026-10-13

  python -X utf8 tools/review_addmiss.py split [묶음 수]   → work/review_addmiss/part_NN.json
  … report / apply          검수자 결과(findings_NN)+내 판정(verdict.json) → 검수표.html / work/text 반영
  … spacing [묶음 수]        띄어쓰기 검수 묶음 → work/review_spacing/part_NN.json (지시.md 를 검수자에게)
  … spacing_report / spacing_apply   띄어쓰기 결과(findings_NN, exclude.json) → 검수표.html / 반영
  … linespace               설명 파일(Common/*Info) 줄바꿈 앞에 공백(한 줄 HELP 바에서 낱말이 붙는 문제)
같은 (원문, 번역) 쌍은 한 번만 넣는다(처음 나온 파일에). 파일 단위로 순서를 지켜 묶어 앞뒤 대사 흐름을 볼 수 있게 한다.
항목: id(파일#순번), file, label, ja, ko — ja/ko 는 mtext.plain(태그 뺀 글자), 줄바꿈은 그대로.
"""
import os, sys, json, glob
import extract, mtext

ROOT = extract.ROOT
TEXT = os.path.join(ROOT, 'work', 'text')
OUT = os.path.join(ROOT, 'work', 'review_addmiss')


def split(nparts):
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(glob.escape(TEXT) + '/**/*.json', recursive=True))
    seen, blocks = set(), []
    for p in files:
        rel = os.path.relpath(p, TEXT).replace(os.sep, '/')[:-5]
        items = []
        for en in json.load(open(p, encoding='utf-8'))['entries']:
            ko = en.get('ko') or ''
            if not ko:
                continue
            key = (en['ja'], ko)
            if key in seen:
                continue
            seen.add(key)
            items.append(dict(id='%s#%d' % (rel, en['i']), file=rel, label=en['label'],
                              ja=mtext.plain(en['ja']), ko=mtext.plain(ko)))
        if items:
            blocks.append((rel, items, sum(len(x['ja']) for x in items)))
    total = sum(b[2] for b in blocks)
    per = total / nparts
    parts, cur, size = [], [], 0
    for rel, items, n in blocks:
        if cur and size + n > per * 1.08 and len(parts) < nparts - 1:
            parts.append(cur); cur, size = [], 0
        cur += items; size += n
    parts.append(cur)
    for i, p in enumerate(parts, 1):
        json.dump(p, open(os.path.join(OUT, 'part_%02d.json' % i), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        print('part_%02d  항목 %5d · 원문 %6d자 · %s ~ %s' % (i, len(p), sum(len(x['ja']) for x in p), p[0]['file'], p[-1]['file']))
    print('합계 항목 %d · 원문 %d자' % (sum(len(p) for p in parts), total))


def split_spacing(nparts):
    """띄어쓰기 검수용 묶음 → work/review_spacing/part_NN.json. 같은 번역문은 한 번만, 항목은 id·label·ko(태그 뺀 글자)."""
    out = os.path.join(ROOT, 'work', 'review_spacing')
    os.makedirs(out, exist_ok=True)
    seen, blocks = set(), []
    for p in sorted(glob.glob(glob.escape(TEXT) + '/**/*.json', recursive=True)):
        rel = os.path.relpath(p, TEXT).replace(os.sep, '/')[:-5]
        items = []
        for en in json.load(open(p, encoding='utf-8'))['entries']:
            ko = mtext.plain(en.get('ko') or '')
            if not ko.strip() or ko in seen:
                continue
            seen.add(ko)
            items.append(dict(id='%s#%d' % (rel, en['i']), label=en['label'], ko=ko))
        if items:
            blocks.append((items, sum(len(x['ko']) for x in items)))
    per = sum(b[1] for b in blocks) / nparts
    parts, cur, size = [], [], 0
    for items, n in blocks:
        if cur and size + n > per * 1.08 and len(parts) < nparts - 1:
            parts.append(cur); cur, size = [], 0
        cur += items; size += n
    parts.append(cur)
    for i, p in enumerate(parts, 1):
        json.dump(p, open(os.path.join(out, 'part_%02d.json' % i), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        print('part_%02d  항목 %5d · %6d자 · %s ~ %s' % (i, len(p), sum(len(x['ko']) for x in p), p[0]['id'], p[-1]['id']))


SPACING = os.path.join(ROOT, 'work', 'review_spacing')


def _spacing_rows():
    items = {}
    for p in sorted(glob.glob(glob.escape(SPACING) + '/part_*.json')):
        for x in json.load(open(p, encoding='utf-8')):
            items[x['id']] = x
    ep = os.path.join(SPACING, 'exclude.json')
    exclude = json.load(open(ep, encoding='utf-8')) if os.path.exists(ep) else {}
    rows = []
    for p in sorted(glob.glob(glob.escape(SPACING) + '/findings_*.json')):
        for f in json.load(open(p, encoding='utf-8')):
            ko = items.get(f['id'], {}).get('ko', '')
            key = '%s|%s' % (f['id'], f['before'])
            ok = f['before'] in ko and f['before'] != f['after']
            rows.append(dict(f, ko=ko, key=key, verdict='제외' if key in exclude or not ok else '채택',
                             note=exclude.get(key, '' if ok else '번역문에 그 글자가 없음')))
    return rows


def spacing_report():
    import html
    rows = _spacing_rows()
    json.dump(rows, open(os.path.join(SPACING, '검수_합본.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    e = lambda s: html.escape(s or '').replace('\n', '<br>')
    rows.sort(key=lambda r: (r['verdict'] != '채택', r['id']))
    tr = ''.join('<tr class="%s"><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td><b>%s</b></td><td><b>%s</b></td><td>%s<br><small>%s</small></td></tr>'
                 % ('ok' if r['verdict'] == '채택' else 'no', i + 1, e(r['id']), e(r['type']), e(r['ko']), e(r['before']), e(r['after']),
                    e(r['verdict']), e(r['note'] or r['reason'])) for i, r in enumerate(rows))
    page = ('<!doctype html><meta charset="utf-8"><title>띄어쓰기 검수</title><style>body{font-family:sans-serif;font-size:14px;margin:16px}'
            'table{border-collapse:collapse;width:100%%}td,th{border:1px solid #bbb;padding:6px;vertical-align:top}th{background:#eee}'
            'tr.ok{background:#eefbe9}tr.no{color:#888}small{color:#666}b{white-space:pre}</style><h2>띄어쓰기 검수 — %d건 중 채택 %d</h2>'
            '<table><tr><th>#</th><th>위치</th><th>유형</th><th>지금 번역(전체)</th><th>지금</th><th>제안</th><th>판정·근거</th></tr>%s</table>'
            % (len(rows), sum(r['verdict'] == '채택' for r in rows), tr))
    open(os.path.join(SPACING, '검수표.html'), 'w', encoding='utf-8').write(page)
    print('건수 %d · 채택 %d · 제외 %d' % (len(rows), sum(r['verdict'] == '채택' for r in rows), sum(r['verdict'] == '제외' for r in rows)))


def spacing_apply():
    """채택 건을 work/text 에 반영. 같은 번역문(태그 뺀 글자)인 줄은 모두 함께 고친다."""
    want = {}
    for r in _spacing_rows():
        if r['verdict'] == '채택':
            want.setdefault(r['ko'], []).append((r['before'], r['after']))
    n = 0
    for p in sorted(glob.glob(glob.escape(TEXT) + '/**/*.json', recursive=True)):
        d = json.load(open(p, encoding='utf-8'))
        ch = False
        for en in d['entries']:
            ko = en.get('ko') or ''
            fx = want.get(mtext.plain(ko))
            if not fx:
                continue
            old = new = mtext.plain(ko)
            for b, a in fx:
                assert new.count(b) == 1, (p, en['i'], b)
                new = new.replace(b, a)
            ko = _replace_plain(ko, old, new)  # 태그가 섞여 있어도 바뀐 부분만 갈아 끼움
            assert mtext.plain(ko) == new and not mtext.check(en['ja'], ko), (p, en['i'])
            en['ko'] = ko; ch = True; n += 1
        if ch:
            json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('반영 %d줄 (번역문 %d종)' % (n, len(want)))


def linespace():
    """설명 파일(Common/*Info)의 줄바꿈 앞에 공백을 넣는다.
    전투 HELP 바 같은 한 줄 표시에서는 줄바꿈이 그냥 사라져 「무기로\\n통상」이 「무기로통상」으로 붙는다(10/13 실기 확인).
    줄 끝 공백은 여러 줄 창에서는 보이지 않는다. 이미 공백이 있는 곳·빈 줄은 건드리지 않는다."""
    import re
    n = m = 0
    for p in sorted(glob.glob(glob.escape(TEXT) + '/Common/*Info*.json')):
        d = json.load(open(p, encoding='utf-8'))
        ch = False
        for en in d['entries']:
            ko = en.get('ko') or ''
            new = re.sub(r'(?<=[^\s　])\n(?=[^\s　])', ' \n', ko)
            if new != ko:
                assert mtext.plain(new).replace(' \n', '\n') == mtext.plain(ko).replace(' \n', '\n') and not mtext.check(en['ja'], new), (p, en['i'])
                m += new.count(' \n') - ko.count(' \n'); n += 1
                en['ko'] = new; ch = True
        if ch:
            json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print(os.path.basename(p))
    print('줄 끝 공백: 항목 %d · 자리 %d' % (n, m))


def report():
    """findings_NN.json 을 모아 원문·지금·제안 표(HTML)와 합본 JSON 을 만든다. 표에는 verdict.json 의 판정(채택/제외·사유)을 붙인다."""
    import html
    items = {}
    for p in sorted(glob.glob(glob.escape(OUT) + '/part_*.json')):
        for x in json.load(open(p, encoding='utf-8')):
            items[x['id']] = x
    vp = os.path.join(OUT, 'verdict.json')
    verdict = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    rows = []
    for p in sorted(glob.glob(glob.escape(OUT) + '/findings_*.json')):
        for f in json.load(open(p, encoding='utf-8')):
            it = items.get(f['id'], {})
            v = verdict.get(f['id'], {})
            rows.append(dict(f, part=os.path.basename(p)[9:11], label=it.get('label', ''), ja=it.get('ja', ''), ko=it.get('ko', ''),
                             fix=v.get('fix', f.get('fix', '')), verdict=v.get('verdict', '미판정'), note=v.get('note', '')))
    for k, v in verdict.items():  # 검수자 결과에 없고 내가 직접 더한 것
        if k not in {r['id'] for r in rows}:
            it = items.get(k, {})
            rows.append(dict(id=k, type='추가', reason='', part='', label=it.get('label', ''), ja=it.get('ja', ''), ko=it.get('ko', ''),
                             fix=v.get('fix', ''), verdict=v.get('verdict', '미판정'), note=v.get('note', '')))
    json.dump(rows, open(os.path.join(OUT, '검수_합본.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    e = lambda s: html.escape(s or '').replace('\n', '<br>')
    order = {'채택': 0, '보류': 1, '미판정': 1, '제외': 2}
    rows.sort(key=lambda r: (order.get(r['verdict'], 1), r['id']))
    tr = ''.join(
        '<tr class="%s"><td>%d</td><td>%s<br><small>%s</small></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s<br><small>%s</small></td></tr>'
        % ('ok' if r['verdict'] == '채택' else 'no' if r['verdict'] == '제외' else '', i + 1, e(r['id']), e(r['label']), e(r['type']),
           e(r['ja']), e(r['ko']), e(r['fix']) if r['verdict'] != '제외' else '-', e(r['verdict']), e(r['note'] or r['reason']))
        for i, r in enumerate(rows))
    page = ('<!doctype html><meta charset="utf-8"><title>원문 대조 검수</title><style>body{font-family:sans-serif;font-size:14px;margin:16px}'
            'table{border-collapse:collapse;width:100%%}td,th{border:1px solid #bbb;padding:6px;vertical-align:top}th{background:#eee}'
            'tr.ok{background:#eefbe9}tr.no{color:#888}small{color:#666}</style><h2>원문 대조 검수 (추가·누락·오역) — %d건 중 채택 %d</h2>'
            '<table><tr><th>#</th><th>위치</th><th>유형</th><th>원문</th><th>지금 번역</th><th>제안</th><th>판정·이유</th></tr>%s</table>'
            % (len(rows), sum(r['verdict'] == '채택' for r in rows), tr))
    open(os.path.join(OUT, '검수표.html'), 'w', encoding='utf-8').write(page)
    print('건수 %d · 채택 %d · 보류 %d · 제외 %d · 미판정 %d' % (len(rows), *(sum(r['verdict'] == k for r in rows) for k in ('채택', '보류', '제외', '미판정'))))


def _replace_plain(raw, old, new):
    """태그가 섞인 raw 에서 본문 old→new 로 바뀐 부분만 갈아 끼운다. 바뀐 곳 앞뒤 글자로 raw 안 위치를 하나로 찾는다."""
    p = 0
    while p < min(len(old), len(new)) and old[p] == new[p]:
        p += 1
    s = 0
    while s < min(len(old), len(new)) - p and old[-1 - s] == new[-1 - s]:
        s += 1
    for k in range(0, 40):
        a, b = max(0, p - k), max(0, p - k)
        seg_old, seg_new = old[a:len(old) - s + k] if s - k >= 0 else None, new[b:len(new) - s + k] if s - k >= 0 else None
        if seg_old is None:
            break
        if seg_old and raw.count(seg_old) == 1:
            return raw.replace(seg_old, seg_new)
    raise ValueError('위치를 못 찾음: %r' % old)


def apply():
    """verdict.json 의 채택 건을 work/text 에 반영한다. 같은 (원문, 번역) 쌍은 다른 파일·줄도 함께 고친다."""
    items = {}
    for p in sorted(glob.glob(glob.escape(OUT) + '/part_*.json')):
        for x in json.load(open(p, encoding='utf-8')):
            items[x['id']] = x
    verdict = json.load(open(os.path.join(OUT, 'verdict.json'), encoding='utf-8'))
    want = {(items[k]['ja'], items[k]['ko']): v['fix'] for k, v in verdict.items() if v['verdict'] == '채택'}
    hit = {k: 0 for k in want}
    for p in sorted(glob.glob(glob.escape(TEXT) + '/**/*.json', recursive=True)):
        d = json.load(open(p, encoding='utf-8'))
        ch = False
        for en in d['entries']:
            ko = en.get('ko') or ''
            key = (mtext.plain(en['ja']), mtext.plain(ko))
            if key in want:
                en['ko'] = _replace_plain(ko, key[1], want[key])
                assert mtext.plain(en['ko']) == want[key], (p, en['i'])
                assert not mtext.check(en['ja'], en['ko']), (p, en['i'], mtext.check(en['ja'], en['ko']))
                hit[key] += 1; ch = True
                print('%s#%d' % (os.path.relpath(p, TEXT)[:-5].replace(os.sep, '/'), en['i']))
        if ch:
            json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    miss = [k for k, n in hit.items() if not n]
    print('반영 %d줄 · 채택 %d건 · 못 찾은 것 %d' % (sum(hit.values()), len(want), len(miss)))


if __name__ == '__main__':
    if sys.argv[1] == 'split':
        split(int(sys.argv[2]) if len(sys.argv) > 2 else 18)
    elif sys.argv[1] == 'report':
        report()
    elif sys.argv[1] == 'apply':
        apply()
    elif sys.argv[1] == 'spacing':
        split_spacing(int(sys.argv[2]) if len(sys.argv) > 2 else 18)
    elif sys.argv[1] == 'spacing_report':
        spacing_report()
    elif sys.argv[1] == 'spacing_apply':
        spacing_apply()
    elif sys.argv[1] == 'linespace':
        linespace()
