"""MSBT 메시지 raw bytes <-> 사람이 읽고 쓸 수 있는 태그 표기.

TMS 본문에는 `[` `]` `{` `}` 가 한 번도 안 쓰이므로 대괄호를 태그 구분자로 쓴다.

  [V:BTL_OPEN_0001_em2303]   보이스 큐        (g4 t0)  꼬리가 00cd 가 아니면 [V:이름,01cd]
  [C:2] ... [C:-]            강조색 / 해제    (g0 t3)  - = 0xffff
  [N:0]                      치환 변수        (g2 t0)
  [B:13]                     버튼 아이콘      (g3 t0)
  [R:g,t,hex]                그 밖의 태그(루비·글자크기 등) 원형 보존
  [/:g,t]                    닫는 태그 (0x000F)

encode(decode(x)) == x 가 전 메시지에서 성립해야 한다.
"""
import struct, re

TAG_RE = re.compile(r'\[([VCNBR/]):([^\]]*)\]')


def decode(b):
    """메시지 raw bytes -> 표기 문자열. 끝의 NUL 은 떼고 돌려준다."""
    out = []
    p = 0
    n = len(b)
    while p + 1 < n:
        ch = struct.unpack_from('>H', b, p)[0]
        if ch == 0x000E:
            g, t, sz = struct.unpack_from('>HHH', b, p + 2)
            a = b[p + 8:p + 8 + sz]
            p += 8 + sz
            out.append(_tag(g, t, a))
        elif ch == 0x000F:
            g, t = struct.unpack_from('>HH', b, p + 2)
            p += 6
            out.append('[/:%d,%d]' % (g, t))
        elif ch == 0x0000:
            p += 2
            break
        else:
            out.append(chr(ch))
            p += 2
    return ''.join(out)


def _tag(g, t, a):
    if (g, t) == (4, 0) and len(a) >= 4:
        ln = struct.unpack('>H', a[:2])[0]
        name = a[2:2 + ln].decode('utf-16-be')
        tail = a[2 + ln:]
        if tail == b'\x00\xcd':
            return '[V:%s]' % name
        return '[V:%s,%s]' % (name, tail.hex())
    if (g, t) == (0, 3) and len(a) == 2:
        v = struct.unpack('>H', a)[0]
        return '[C:-]' if v == 0xFFFF else '[C:%d]' % v
    if (g, t) == (2, 0) and len(a) == 2:
        return '[N:%d]' % struct.unpack('>H', a)[0]
    if (g, t) == (3, 0) and len(a) == 4:
        return '[B:%d]' % struct.unpack('>I', a)[0]
    return '[R:%d,%d,%s]' % (g, t, a.hex())


def encode(s, nul=True):
    """표기 문자열 -> 메시지 raw bytes (기본적으로 끝에 NUL 하나를 붙인다)."""
    out = bytearray()
    pos = 0
    for m in TAG_RE.finditer(s):
        out += s[pos:m.start()].encode('utf-16-be')
        out += _untag(m.group(1), m.group(2))
        pos = m.end()
    out += s[pos:].encode('utf-16-be')
    if nul:
        out += b'\x00\x00'
    return bytes(out)


def _ctrl(g, t, a):
    return struct.pack('>HHHH', 0x000E, g, t, len(a)) + a


def _untag(kind, arg):
    if kind == 'V':
        name, _, tail = arg.rpartition(',')
        if name and re.fullmatch(r'[0-9a-f]+', tail):
            tailb = bytes.fromhex(tail)
        else:
            name, tailb = arg, b'\x00\xcd'
        nb = name.encode('utf-16-be')
        return _ctrl(4, 0, struct.pack('>H', len(nb)) + nb + tailb)
    if kind == 'C':
        v = 0xFFFF if arg == '-' else int(arg)
        return _ctrl(0, 3, struct.pack('>H', v))
    if kind == 'N':
        return _ctrl(2, 0, struct.pack('>H', int(arg)))
    if kind == 'B':
        return _ctrl(3, 0, struct.pack('>I', int(arg)))
    if kind == 'R':
        g, t, hx = arg.split(',')
        return _ctrl(int(g), int(t), bytes.fromhex(hx))
    if kind == '/':
        g, t = arg.split(',')
        return struct.pack('>HHH', 0x000F, int(g), int(t))
    raise ValueError(kind)


def plain(s):
    """태그를 뺀 순수 본문."""
    return TAG_RE.sub('', s)


def tags(s):
    """태그 목록 (종류, 인자)."""
    return [(m.group(1), m.group(2)) for m in TAG_RE.finditer(s)]


def check(ja, ko):
    """번역문 경고 목록. 원문에 있던 태그가 빠지거나 늘었는지, 깨진 대괄호가 없는지."""
    msgs = []
    if not ko:
        return msgs
    # 짝이 안 맞는 대괄호 / 알 수 없는 태그
    stripped = TAG_RE.sub('', ko)
    for ch in '[]':
        if ch in stripped:
            msgs.append('태그가 아닌 %r 가 남아 있음' % ch)
            break
    ja_t, ko_t = tags(ja), tags(ko)
    if sorted(ja_t) != sorted(ko_t):
        miss = [t for t in ja_t if ko_t.count(t) < ja_t.count(t)]
        extra = [t for t in ko_t if ja_t.count(t) < ko_t.count(t)]
        if miss:
            msgs.append('태그 누락: ' + ', '.join('[%s:%s]' % t for t in dict.fromkeys(miss)))
        if extra:
            msgs.append('태그 추가: ' + ', '.join('[%s:%s]' % t for t in dict.fromkeys(extra)))
    return msgs


if __name__ == '__main__':
    import extract, msbt
    c = extract.open_pack('pack_031_message')
    ok = bad = 0
    for e in c.files:
        if not e['name'].endswith('.msbt'):
            continue
        m = msbt.MSBT(c.read(e))
        for i, t in enumerate(m.texts):
            s = decode(t)
            if encode(s) == t:
                ok += 1
            else:
                bad += 1
                if bad < 6:
                    print('MISMATCH', e['name'], m.label(i))
                    print('  orig', t.hex())
                    print('  back', encode(s).hex())
    print('메시지 왕복 %d/%d' % (ok, ok + bad))
