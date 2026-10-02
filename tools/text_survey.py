# -*- coding: utf-8 -*-
"""대사 파일(MSBT) 밖 일본어 문자열 전수조사(2026-09-28).

  python -X utf8 tools/text_survey.py      → work/text_survey/report.json, report.md
대상: 모든 팩의 그림·영상·소리·모델이 아닌 파일, DLC(Lua), 실행 파일(본편·업데이트 Stainless.rpx, 압축 섹션은 풀어서).
인코딩: UTF-16BE·UTF-16LE·UTF-8·Shift-JIS. 가나가 한 글자 이상 든 2글자 이상 문자열만(무작위 바이트가 한자로 읽히는 오탐 방지).
대사 원문(work/text 의 ja)에 그대로 있거나 그 일부인 문자열은 「대사에 있음」으로 따로 센다.
"""
import os, re, json, glob, struct, zlib
import extract, text_io, cpk as C

ROOT = extract.ROOT
OUT = os.path.join(ROOT, 'work', 'text_survey')
SKIP_EXT = ('.gtx', '.usm', '.apak', '.bfres', '.ptcl', '.pspk', '.fphb', '.msbt', '.bffnt', '.acb', '.awb', '.adx', '.hca', '.bfsar', '.bars', '.bwav')
KANA = re.compile(r'[ぁ-ゖァ-ヺー]')
JP = re.compile(r'[　-〿ぁ-ゖァ-ヺー一-鿿！-～！？…「」『』・ー]{2,}')


CHARSET = set()          # main() 에서 대사 원문 글자로 채움(가짜 문자열 거르기)


def _ok(s):
    """진짜 일본어 문자열로 볼 만한가: 3글자 이상, 모든 글자가 대사 원문에 쓰인 글자, 가나 40% 이상."""
    if len(s) < 3 or any(ch not in CHARSET for ch in s):
        return False
    return len(KANA.findall(s)) / len(s) >= 0.4


def strings(b):
    out = set()
    for enc in ('utf-16-be', 'utf-16-le'):
        for start in (0, 1):
            t = b[start:len(b) - ((len(b) - start) % 2)].decode(enc, errors='replace')
            out |= {m.group() for m in JP.finditer(t)}
    out |= {m.group() for m in JP.finditer(b.decode('utf-8', errors='replace'))}
    for start in (0, 1):
        out |= {m.group() for m in JP.finditer(b[start:].decode('shift_jis', errors='replace'))}
    return {s for s in out if _ok(s)}


LUA_STR = re.compile(r'"((?:[^"\\\n]|\\.)*)"' + "|'((?:[^'\\\\\\n]|\\\\.)*)'")


def lua_literals(b):
    """Lua: 소스(텍스트)면 주석을 빼고 따옴표 문자열만, 바이트코드면 일반 검색."""
    if b[:4] == b'\x1bLua':
        return strings(b)
    out = set()
    for enc in ('utf-8', 'shift_jis'):
        t = b.decode(enc, errors='replace')
        t = re.sub(r'--\[(=*)\[.*?\]\1\]', '', t, flags=re.S)
        for line in t.split('\n'):
            q = None; cut = len(line); i = 0
            while i < len(line):
                ch = line[i]
                if q:
                    if ch == '\\':
                        i += 2; continue
                    if ch == q:
                        q = None
                elif ch in '"\'':
                    q = ch
                elif line.startswith('--', i):
                    cut = i; break
                i += 1
            for x, y in LUA_STR.findall(line[:cut]):
                out |= {m.group() for m in JP.finditer(x or y)}
    return {s for s in out if _ok(s)}



def rpx_sections(p):
    b = open(p, 'rb').read()
    shoff = struct.unpack('>I', b[0x20:0x24])[0]; shentsize, shnum = struct.unpack('>HH', b[0x2E:0x32])
    for i in range(shnum):
        o = shoff + i * shentsize
        name, typ, flags, addr, off, size = struct.unpack('>6I', b[o:o + 24])
        d = b[off:off + size]
        if flags & 0x08000000 and size >= 4:
            try:
                d = zlib.decompress(d[4:])
            except Exception:
                continue
        yield 'section%d' % i, d


def sources():
    for pk in sorted(os.listdir(extract.PACK)):
        if not pk.endswith('.cpk') or pk.startswith(('pack_031', 'pack_05', 'pack_049', 'pack_060', 'pack_040', 'pack_039', 'pack_999_sound', 'pack_999_font')):
            continue
        c = extract.open_pack(pk[:-4])
        for e in c.files:
            if not e['name'].lower().endswith(SKIP_EXT):
                yield pk[:-4], e['name'], (lambda c=c, e=e: c.read(e))
    dlc = os.path.join(ROOT, 'Tokyo Mirage Sessions FE [DLC] [0005000c10131d00]', 'content')
    for cp in glob.glob(os.path.join(glob.escape(dlc), '*', '*.cpk')):
        c = C.CPK(cp)
        for e in c.files:
            if not e['name'].lower().endswith(SKIP_EXT):
                yield 'DLC/' + os.path.basename(cp)[:-4], e['name'], (lambda c=c, e=e: c.read(e))
    for tag, folder in (('rpx_update', '[Update] [0005000e10131d00]'), ('rpx_base', '[Game] [0005000010131d00]')):
        p = os.path.join(ROOT, 'Tokyo Mirage Sessions FE %s' % folder, 'code', 'Stainless.rpx')
        for sec, d in rpx_sections(p):
            yield tag, sec, (lambda d=d: d)


def main():
    os.makedirs(OUT, exist_ok=True)
    ja_all = '\n'.join((en.get('ja') or '') for p in text_io.iter_json() for en in text_io.load_json(p)['entries'])
    CHARSET.update(ja_all)
    CHARSET.update('ー・…！？「」『』　')
    rep = {}
    n_files = 0
    for pk, name, read in sources():
        n_files += 1
        try:
            b = read()
        except Exception as ex:
            rep.setdefault(pk, {})[name] = dict(error=str(ex)); continue
        ss = lua_literals(b) if name.lower().endswith('.lua') else strings(b)
        if not ss:
            continue
        new = sorted(s for s in ss if s not in ja_all)
        rep.setdefault(pk, {})[name] = dict(total=len(ss), not_in_msbt=new[:200], n_new=len(new))
    json.dump(rep, open(os.path.join(OUT, 'report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    lines = ['# MSBT 밖 일본어 문자열 조사', '', '검사한 파일 %d개' % n_files, '']
    for pk in sorted(rep):
        files = {k: v for k, v in rep[pk].items() if v.get('n_new')}
        lines.append('## %s — 일본어 든 파일 %d · 대사에 없는 문자열 든 파일 %d' % (pk, len(rep[pk]), len(files)))
        for n, v in sorted(files.items(), key=lambda kv: -kv[1]['n_new'])[:60]:
            lines.append('- `%s` 새 문자열 %d/%d: %s' % (n, v['n_new'], v['total'], ' · '.join(v['not_in_msbt'][:12])))
        lines.append('')
    open(os.path.join(OUT, 'report.md'), 'w', encoding='utf-8').write('\n'.join(lines))
    print('검사', n_files, '→', os.path.join(OUT, 'report.md'))


if __name__ == '__main__':
    main()
