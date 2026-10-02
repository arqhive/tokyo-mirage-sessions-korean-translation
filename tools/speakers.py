# -*- coding: utf-8 -*-
"""대사 줄마다 화자를 알아낸다.

두 가지 근거를 쓴다.
 1) 이벤트 스크립트(Lua 5.2 바이트코드, 빅엔디언)의 대사창 이름표.
    스크립트는 SetTalkerName("PC_HEROINE") 처럼 이름표(Common/CharacterName.msbt 라벨)를 정한 뒤
    대사 라벨("002")을 띄운다. 게임이 대사창에 실제로 표시하는 이름이 이것이다.
    바이트코드 상수표는 중복을 없애 저장하므로, 명령어(LOADK·RK 피연산자)를 순서대로 따라가며
    '마지막으로 나온 이름표'를 그 뒤 대사 라벨에 붙인다.
 2) 대사 앞 음성 태그 [V:EVT_..._pc1002] 의 인물 번호.
    스크립트 상수 CHRID_PC_TSUBASA_1002 에서 번호 → 인물(영문)을 얻는다.
"""
import struct, re, collections
import extract

# ── Lua 5.2 바이트코드 ───────────────────────────────────────────────
class R:
    def __init__(self, b, p=0):
        self.b, self.p = b, p

    def u8(self):
        v = self.b[self.p]; self.p += 1; return v

    def i32(self):
        v = struct.unpack('>i', self.b[self.p:self.p + 4])[0]; self.p += 4; return v

    def u32(self):
        v = struct.unpack('>I', self.b[self.p:self.p + 4])[0]; self.p += 4; return v

    def s(self):
        n = self.u32()
        if n == 0:
            return None
        v = self.b[self.p:self.p + n - 1]; self.p += n
        return v.decode('utf-8', 'replace')


def read_func(r):
    r.i32(); r.i32(); r.u8(); r.u8(); r.u8()
    code = [r.u32() for _ in range(r.i32())]
    consts = []
    for _ in range(r.i32()):
        t = r.u8()
        if t == 0:
            consts.append(None)
        elif t == 1:
            consts.append(bool(r.u8()))
        elif t == 3:
            consts.append(struct.unpack('>d', r.b[r.p:r.p + 8])[0]); r.p += 8
        elif t == 4:
            consts.append(r.s())
        else:
            raise ValueError('상수 종류 %d' % t)
    protos = [read_func(r) for _ in range(r.i32())]
    for _ in range(r.i32()):
        r.u8(); r.u8()
    r.s()                                              # source
    for _ in range(r.i32()):
        r.i32()                                        # lineinfo
    for _ in range(r.i32()):
        r.s(); r.i32(); r.i32()                        # locvars
    for _ in range(r.i32()):
        r.s()                                          # upvalue names
    return dict(code=code, consts=consts, protos=protos)


def load(b):
    assert b[:5] == b'\x1bLuaR', b[:5]
    r = R(b, 18)                                       # 헤더 12 + LUAC_TAIL 6
    return read_func(r)


# RK 를 쓰는 연산 (Lua 5.2 opcode 번호: 피연산자 위치)
_RK_B = {10, 13, 14, 15, 16, 17, 18, 24, 25, 26, 8}   # SETTABLE(B,C) ADD..POW(B,C) EQ LT LE SETTABUP(B,C)
_RK_C = {6, 7, 10, 12, 13, 14, 15, 16, 17, 18, 24, 25, 26, 8}


def const_stream(fn):
    """명령어 순서대로 참조되는 문자열 상수 (중첩 함수는 그 자리에서 이어 붙이지 않고 따로)."""
    out = []
    k = fn['consts']
    for ins in fn['code']:
        op = ins & 0x3F
        a = (ins >> 6) & 0xFF
        c = (ins >> 14) & 0x1FF
        bb = (ins >> 23) & 0x1FF
        bx = (ins >> 14) & 0x3FFFF
        if op == 1:                                    # LOADK
            v = k[bx]
            if isinstance(v, str):
                out.append(v)
        else:
            if op in _RK_B and bb & 0x100 and isinstance(k[bb & 0xFF], str):
                out.append(k[bb & 0xFF])
            if op in _RK_C and c & 0x100 and isinstance(k[c & 0xFF], str):
                out.append(k[c & 0xFF])
    return out


def walk(fn):
    yield fn
    for p in fn['protos']:
        yield from walk(p)


# ── 스크립트 → {대사 라벨: 이름표} ──────────────────────────────────
def talkers_of_script(b, name_labels, msg_labels):
    fn = load(b)
    res = {}
    for f in walk(fn):
        cur = None
        for s in const_stream(f):
            if s in name_labels:
                cur = s
            elif s in msg_labels and cur:
                res.setdefault(s, cur)
    return res


def chrid_map(lua_pack):
    """번호(1002 등) → (분류, 영문 이름)."""
    m = {}
    for f in lua_pack.files:
        b = lua_pack.read(f['name'])
        for t, nm, num in re.findall(rb'CHRID_([A-Z]+)_([A-Z0-9_]+?)_(\d{3,4})', b):
            m.setdefault(num.decode(), (t.decode(), nm.decode()))
    return m
