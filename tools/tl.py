"""번역 작업 헬퍼.

  python tl.py show System/System_common [시작] [개수]   미번역 항목 출력
  python tl.py todo [분류]                                분류별 남은 분량
  python tl.py stat                                        전체 진행률

번역 반영은 `tl.put(경로, {라벨: 한글})` 로 한다 (스크립트에서 호출).
"""
import os, sys, json
import text_io, mtext, josa_en


def path_of(rel):
    if not rel.endswith('.json'):
        rel += '.json'
    return os.path.join(text_io.TEXT, rel.replace('/', os.sep))


def put(rel, table, log=print):
    """{라벨: 한글} 을 JSON 의 ko 에 반영. 같은 라벨이 여러 개면 모두 채운다."""
    p = path_of(rel)
    j = text_io.load_json(p)
    n = miss = 0
    used = set()
    for en in j['entries']:
        if en['label'] in table:
            ko = table[en['label']]
            if ko:
                # 「ＴＯＰＩＣ가」 같은 조사 오류는 여기서 한 번에 막는다
                en['ko'] = josa_en.fix(ko)
                n += 1
            used.add(en['label'])
    for k in table:
        if k not in used:
            miss += 1
            log('  ! 없는 라벨: %s' % k)
    # 대사창은 줄 수가 고정이다. 원문보다 늘면 아래가 잘린다.
    NL = chr(10)
    for en in j['entries']:
        if en.get('ko') and en['ko'].count(NL) != en['ja'].count(NL):
            log('  ! 줄 수 %d->%d : %s' % (en['ja'].count(NL) + 1,
                                          en['ko'].count(NL) + 1, en['label']))
    text_io.save_json(p, j)
    log('%s: %d개 반영%s' % (rel, n, ', 라벨 불일치 %d' % miss if miss else ''))
    return n


def put_idx(rel, table, log=print):
    """{인덱스: 한글} 로 반영 (라벨이 비었거나 중복인 파일용)."""
    p = path_of(rel)
    j = text_io.load_json(p)
    n = 0
    for en in j['entries']:
        if en['i'] in table and table[en['i']]:
            en['ko'] = table[en['i']]
            n += 1
    text_io.save_json(p, j)
    log('%s: %d개 반영' % (rel, n))
    return n


def cmd_show(args):
    rel = args[0]
    start = int(args[1]) if len(args) > 1 else 0
    count = int(args[2]) if len(args) > 2 else 10 ** 9
    j = text_io.load_json(path_of(rel))
    shown = 0
    for en in j['entries']:
        if en['i'] < start:
            continue
        if en.get('ko'):
            continue
        print('%d\t%s\t%s' % (en['i'], en['label'], en['ja'].replace('\n', '\\n')))
        shown += 1
        if shown >= count:
            break
    print('-- %d개 (미번역 %d / 전체 %d)' % (
        shown, sum(1 for e in j['entries'] if not e.get('ko')), len(j['entries'])))


def cmd_todo(args):
    pref = args[0] if args else ''
    rows = []
    for p in text_io.iter_json():
        rel = os.path.relpath(p, text_io.TEXT).replace(os.sep, '/')[:-5]
        if not rel.startswith(pref):
            continue
        j = text_io.load_json(p)
        todo = [e for e in j['entries'] if not e.get('ko')]
        if not todo:
            continue
        rows.append((sum(len(mtext.plain(e['ja'])) for e in todo), len(todo), rel))
    rows.sort(reverse=True)
    for ch, n, rel in rows:
        print('%7d자 %5d개  %s' % (ch, n, rel))
    print('-- %d파일 / %d개 / %d자' % (len(rows), sum(r[1] for r in rows), sum(r[0] for r in rows)))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'stat'
    if cmd == 'stat':
        text_io.cmd_stat([])
    else:
        {'show': cmd_show, 'todo': cmd_todo}[cmd](sys.argv[2:])
