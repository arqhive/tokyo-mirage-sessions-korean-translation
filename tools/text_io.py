"""MSBT <-> 번역 작업용 JSON.

  python text_io.py export          CPK -> work/text/<분류>/<파일>.json  (기존 ko 는 보존)
  python text_io.py stat            번역 진행률/분량 통계
  python text_io.py check           번역문 경고 (태그 누락 등)

JSON 형식: {"file": "Message/JP_Japanese/Battle/COMMON.msbt",
            "entries": [{"i":0, "label":"NOT_MOVE", "ja":"...", "ko":""}, ...]}
"""
import os, sys, json, collections
import extract, msbt, mtext

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = os.path.join(ROOT, 'work', 'text')
PACK_NAME = 'pack_031_message'
PREFIX = 'Message/JP_Japanese/'


def json_path(inner):
    rel = inner[len(PREFIX):] if inner.startswith(PREFIX) else inner
    return os.path.join(TEXT, os.path.splitext(rel)[0].replace('/', os.sep) + '.json')


def iter_json():
    for dp, _, fns in os.walk(TEXT):
        for fn in sorted(fns):
            if fn.endswith('.json'):
                yield os.path.join(dp, fn)


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def cmd_export(args):
    c = extract.open_pack(PACK_NAME)
    n_file = n_msg = n_keep = 0
    for e in c.files:
        if not e['name'].endswith('.msbt'):
            continue
        m = msbt.MSBT(c.read(e))
        p = json_path(e['name'])
        old = {}
        if os.path.exists(p):
            for en in load_json(p)['entries']:
                if en.get('ko'):
                    old[(en['i'], en['ja'])] = en['ko']
        entries = []
        for i, t in enumerate(m.texts):
            ja = mtext.decode(t)
            ko = old.get((i, ja), '')
            if ko:
                n_keep += 1
            entries.append(dict(i=i, label=m.label(i), ja=ja, ko=ko))
        save_json(p, dict(file=e['name'], entries=entries))
        n_file += 1
        n_msg += len(entries)
    print('%d 파일 / %d 메시지 -> %s  (기존 번역 %d 유지)' % (n_file, n_msg, TEXT, n_keep))


def build_texts(warn=True):
    """work/text 의 JSON 으로 MSBT 를 다시 만들어 {내부경로: bytes} 반환."""
    c = extract.open_pack(PACK_NAME)
    by_name = {e['name']: e for e in c.files}
    out = {}
    warns = 0
    for p in iter_json():
        j = load_json(p)
        e = by_name[j['file']]
        m = msbt.MSBT(c.read(e))
        texts = list(m.texts)
        changed = False
        for en in j['entries']:
            ko = en.get('ko') or ''
            if not ko:
                continue
            if warn:
                for w in mtext.check(en['ja'], ko):
                    print('  경고 %s [%s] %s' % (j['file'], en['label'], w))
                    warns += 1
            texts[en['i']] = mtext.encode(ko)
            changed = True
        if changed:
            out[j['file']] = m.build(texts)
    if warn and warns:
        print('경고 %d건' % warns)
    return out


def cmd_stat(args):
    tot = done = 0
    ja_ch = ko_ch = 0
    per = collections.Counter()
    per_done = collections.Counter()
    for p in iter_json():
        j = load_json(p)
        cat = os.path.relpath(p, TEXT).split(os.sep)[0]
        for en in j['entries']:
            tot += 1
            ja_ch += len(mtext.plain(en['ja']))
            per[cat] += len(mtext.plain(en['ja']))
            if en.get('ko'):
                done += 1
                ko_ch += len(mtext.plain(en['ko']))
                per_done[cat] += len(mtext.plain(en['ja']))
    print('메시지 %d / %d 번역 (%.2f%%)' % (done, tot, 100 * done / max(tot, 1)))
    print('원문 %d자, 번역분 원문 %d자' % (ja_ch, ko_ch))
    print()
    print('%-16s %10s %10s %7s' % ('분류', '원문자수', '완료', '%'))
    for cat, n in per.most_common():
        print('%-16s %10d %10d %6.1f%%' % (cat, n, per_done[cat], 100 * per_done[cat] / n))


def cmd_check(args):
    n = 0
    for p in iter_json():
        j = load_json(p)
        for en in j['entries']:
            for w in mtext.check(en['ja'], en.get('ko') or ''):
                print('%s [%s] %s' % (j['file'], en['label'], w))
                n += 1
    print('경고 %d건' % n)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'stat'
    {'export': cmd_export, 'stat': cmd_stat, 'check': cmd_check}[cmd](sys.argv[2:])
