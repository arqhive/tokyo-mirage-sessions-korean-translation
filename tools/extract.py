"""CPK 목록/추출.

  python extract.py list                     모든 CPK 요약
  python extract.py list pack_031_message    한 CPK 의 파일 목록
  python extract.py dump pack_031_message [패턴]   work/extract/<pack>/ 로 추출
"""
import os, sys, fnmatch
import cpk as cpklib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, 'Tokyo Mirage Sessions FE [Game] [0005000010131d00]', 'content', 'Pack')
WORK = os.path.join(ROOT, 'work')


def pack_path(name):
    if not name.endswith('.cpk'):
        name += '.cpk'
    return os.path.join(PACK, name)


def open_pack(name):
    return cpklib.CPK(pack_path(name))


def cmd_list(args):
    if args:
        c = open_pack(args[0])
        pat = args[1] if len(args) > 1 else None
        n = 0
        for e in c.files:
            if pat and not fnmatch.fnmatch(e['name'], pat):
                continue
            print('%10d %10d  %s' % (e['size'], e['esize'], e['name']))
            n += 1
        print('-- %d files' % n)
        return
    for fn in sorted(os.listdir(PACK)):
        if not fn.endswith('.cpk'):
            continue
        c = cpklib.CPK(os.path.join(PACK, fn))
        exts = {}
        for e in c.files:
            exts[os.path.splitext(e['name'])[1].lower()] = exts.get(os.path.splitext(e['name'])[1].lower(), 0) + 1
        top = ' '.join('%s:%d' % kv for kv in sorted(exts.items(), key=lambda kv: -kv[1])[:5])
        print('%-32s %6.1fMB %5d files  %s' % (fn, os.path.getsize(c.path) / 1e6, len(c.files), top))
        c.close()


def cmd_dump(args):
    name = args[0]
    pat = args[1] if len(args) > 1 else '*'
    c = open_pack(name)
    out = os.path.join(WORK, 'extract', os.path.splitext(os.path.basename(name))[0])
    n = 0
    for e in c.files:
        if not fnmatch.fnmatch(e['name'], pat):
            continue
        p = os.path.join(out, e['name'].replace('/', os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(c.read(e))
        n += 1
    print('%d files -> %s' % (n, out))


if __name__ == '__main__':
    {'list': cmd_list, 'dump': cmd_dump}[sys.argv[1]](sys.argv[2:])
