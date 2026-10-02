"""MSBT (MsgStdBn) 파서/빌더 — TMS 판.

TMS 의 MSBT 는 빅엔디언 UTF-16BE, 섹션 LBL1 / ATR1 / TXT2, 섹션 사이 정렬 패딩 0xAB.
build() 는 무변경 시 원본과 바이트 단위로 일치해야 한다(검증: tools/verify_msbt.py).
"""
import struct

PAD = 0xAB
HDR_SIZE = 0x20
SEC_HDR = 0x10


def _align(v, a=16):
    return (v + a - 1) // a * a


class MSBT:
    def __init__(self, data):
        d = self.raw = bytes(data)
        assert d[:8] == b'MsgStdBn', d[:8]
        bom = struct.unpack_from('>H', d, 8)[0]
        self.be = bom == 0xFEFF
        e = self.e = '>' if self.be else '<'
        self.head_rest = d[0x0A:0x0C]          # 보통 0000
        self.enc = d[0x0C]                     # 1 = UTF-16
        self.ver = d[0x0D]
        nsec = struct.unpack_from(e + 'H', d, 0x0E)[0]
        self.head_pad = d[0x10:0x12]
        self.file_size = struct.unpack_from(e + 'I', d, 0x12)[0]
        self.head_tail = d[0x16:0x20]

        self.sections = []                     # [(magic, body)] 원본 순서 유지
        p = HDR_SIZE
        for _ in range(nsec):
            magic = d[p:p + 4]
            size = struct.unpack_from(e + 'I', d, p + 4)[0]
            rest = d[p + 8:p + 16]
            self.sections.append([magic, d[p + 16:p + 16 + size], rest])
            p = _align(p + 16 + size)

        self._parse_labels()
        self._parse_texts()

    # ---------------------------------------------------------------- 섹션
    def section(self, magic):
        for m, body, _ in self.sections:
            if m == magic:
                return body
        return None

    def set_section(self, magic, body):
        for s in self.sections:
            if s[0] == magic:
                s[1] = body
                return
        raise KeyError(magic)

    # ---------------------------------------------------------------- LBL1
    def _parse_labels(self):
        e = self.e
        self.labels = {}                       # index -> name
        b = self.section(b'LBL1')
        if not b:
            return
        ngrp = struct.unpack_from(e + 'I', b, 0)[0]
        self.lbl_groups = ngrp
        for g in range(ngrp):
            cnt, off = struct.unpack_from(e + 'II', b, 4 + g * 8)
            q = off
            for _ in range(cnt):
                ln = b[q]
                nm = b[q + 1:q + 1 + ln].decode('utf-8', 'replace')
                idx = struct.unpack_from(e + 'I', b, q + 1 + ln)[0]
                self.labels[idx] = nm
                q += 1 + ln + 4

    def label(self, i):
        return self.labels.get(i, '')

    # ---------------------------------------------------------------- TXT2
    def _parse_texts(self):
        e = self.e
        self.texts = []                        # 메시지별 raw bytes (끝 NUL 포함)
        b = self.section(b'TXT2')
        if not b:
            return
        n = struct.unpack_from(e + 'I', b, 0)[0]
        offs = [struct.unpack_from(e + 'I', b, 4 + i * 4)[0] for i in range(n)]
        offs.append(len(b))
        for i in range(n):
            self.texts.append(b[offs[i]:offs[i + 1]])

    def build_txt2(self, texts=None):
        e = self.e
        texts = self.texts if texts is None else texts
        n = len(texts)
        head = 4 + n * 4
        out = bytearray(struct.pack(e + 'I', n))
        pos = head
        for t in texts:
            out += struct.pack(e + 'I', pos)
            pos += len(t)
        for t in texts:
            out += t
        return bytes(out)

    # ---------------------------------------------------------------- 직렬화
    def build(self, texts=None):
        e = self.e
        secs = [list(s) for s in self.sections]
        if texts is not None:
            for s in secs:
                if s[0] == b'TXT2':
                    s[1] = self.build_txt2(texts)
        body = bytearray()
        for magic, data, rest in secs:
            body += magic + struct.pack(e + 'I', len(data)) + rest + data
            body += bytes([PAD]) * (_align(len(body) + HDR_SIZE) - len(body) - HDR_SIZE)
        total = HDR_SIZE + len(body)
        hdr = bytearray(b'MsgStdBn')
        hdr += struct.pack('>H', 0xFEFF if self.be else 0xFFFE)
        hdr += self.head_rest
        hdr += bytes([self.enc, self.ver])
        hdr += struct.pack(e + 'H', len(secs))
        hdr += self.head_pad
        hdr += struct.pack(e + 'I', total)
        hdr += self.head_tail
        assert len(hdr) == HDR_SIZE, len(hdr)
        return bytes(hdr + body)


def load(path):
    with open(path, 'rb') as f:
        return MSBT(f.read())


if __name__ == '__main__':
    import sys
    m = load(sys.argv[1])
    print('BE=%s enc=%d ver=%d sections=%s size=%d/%d' % (
        m.be, m.enc, m.ver, [s[0].decode() for s in m.sections], m.file_size, len(m.raw)))
    print('labels=%d texts=%d' % (len(m.labels), len(m.texts)))
    print('roundtrip:', 'OK' if m.build() == m.raw else 'MISMATCH')
    for i in range(min(5, len(m.texts))):
        print(' [%s] %r' % (m.label(i), m.texts[i][:60]))
