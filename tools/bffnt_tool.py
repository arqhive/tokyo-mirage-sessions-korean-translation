"""BFFNT (FFNT v3, Wii U, 빅엔디언) 파서/빌더.

함정:
  * FINF 의 tglp/cwdh/cmap 오프셋과 CWDH/CMAP 의 nextOffset 은 모두 '블록 시작 + 8'.
  * 블록 본문은 4바이트 정렬.
  * TGLP 의 sheetDataOffset 은 절대 파일 오프셋이고 그 앞에 패딩이 있다.
  * 셀 스텝은 (cellW+1, cellH+1) — 셀 사이에 1px 간격이 있다.
build() 는 무변경 시 원본과 바이트 일치해야 한다.
"""
import struct, os, sys

BE = '>'


def _u8(d, p):   return d[p]
def _u16(d, p):  return struct.unpack_from(BE + 'H', d, p)[0]
def _u32(d, p):  return struct.unpack_from(BE + 'I', d, p)[0]


class CMAP:
    def __init__(self, code_begin, code_end, method, pad, entries):
        self.code_begin, self.code_end = code_begin, code_end
        self.method, self.pad = method, pad
        self.entries = entries          # {charcode: glyph_index}

    @classmethod
    def parse(cls, d, blk):
        p = blk + 8
        cb, ce, method, pad = _u16(d, p), _u16(d, p + 2), _u16(d, p + 4), _u16(d, p + 6)
        q = p + 12                      # + nextOffset(u32)
        ent = {}
        if method == 0:                 # DIRECT
            g0 = _u16(d, q)
            for i, c in enumerate(range(cb, ce + 1)):
                ent[c] = g0 + i
        elif method == 1:               # TABLE
            for i, c in enumerate(range(cb, ce + 1)):
                g = _u16(d, q + i * 2)
                if g != 0xFFFF:
                    ent[c] = g
        elif method == 2:               # SCAN
            n = _u16(d, q)
            for i in range(n):
                c, g = struct.unpack_from(BE + 'HH', d, q + 2 + i * 4)
                if g != 0xFFFF:
                    ent[c] = g
        else:
            raise ValueError('cmap method %d' % method)
        return cls(cb, ce, method, pad, ent)

    def body(self):
        if self.method == 0:
            first = self.entries[self.code_begin]
            return struct.pack(BE + 'H', first)
        if self.method == 1:
            out = bytearray()
            for c in range(self.code_begin, self.code_end + 1):
                out += struct.pack(BE + 'H', self.entries.get(c, 0xFFFF))
            return bytes(out)
        items = sorted(self.entries.items())
        out = bytearray(struct.pack(BE + 'H', len(items)))
        for c, g in items:
            out += struct.pack(BE + 'HH', c, g)
        return bytes(out)

    @classmethod
    def scan(cls, entries):
        items = sorted(entries)
        return cls(items[0], items[-1], 2, 0, dict(entries))


class BFFNT:
    def __init__(self, data):
        d = self.raw = bytes(data)
        assert d[:4] == b'FFNT', d[:4]
        self.header_size = _u16(d, 6)
        self.version = _u32(d, 8)
        self.file_size = _u32(d, 12)
        self.num_blocks = _u16(d, 16)
        self.head_pad = d[18:self.header_size]

        finf = self.header_size
        assert d[finf:finf + 4] == b'FINF'
        self.finf_size = _u32(d, finf + 4)
        self.font_type = _u8(d, finf + 8)
        self.height = _u8(d, finf + 9)
        self.width = _u8(d, finf + 10)
        self.ascent = _u8(d, finf + 11)
        self.line_feed = _u16(d, finf + 12)
        self.alter_index = _u16(d, finf + 14)
        self.def_left = struct.unpack_from(BE + 'b', d, finf + 16)[0]
        self.def_glyph_w = _u8(d, finf + 17)
        self.def_char_w = _u8(d, finf + 18)
        self.encoding = _u8(d, finf + 19)
        tglp = _u32(d, finf + 20) - 8
        cwdh = _u32(d, finf + 24) - 8
        cmap = _u32(d, finf + 28) - 8

        # ---- TGLP
        assert d[tglp:tglp + 4] == b'TGLP'
        self.tglp_size = _u32(d, tglp + 4)
        p = tglp + 8
        self.cell_w, self.cell_h, self.num_sheets, self.max_char_w = d[p], d[p + 1], d[p + 2], d[p + 3]
        self.sheet_size = _u32(d, p + 4)
        self.baseline = _u16(d, p + 8)
        self.format = _u16(d, p + 10)
        self.columns = _u16(d, p + 12)
        self.rows = _u16(d, p + 14)
        self.sheet_w = _u16(d, p + 16)
        self.sheet_h = _u16(d, p + 18)
        self.sheet_off = _u32(d, p + 20)
        self.tglp_gap = d[p + 24:self.sheet_off]        # 시트 데이터 앞 패딩 (원형 보존)
        self.sheets = [d[self.sheet_off + i * self.sheet_size:self.sheet_off + (i + 1) * self.sheet_size]
                       for i in range(self.num_sheets)]

        # ---- CWDH 체인
        self.widths = {}                                # glyph -> (left, glyph_w, char_w)
        self.cwdh_chain = []
        b = cwdh
        while b is not None:
            assert d[b:b + 4] == b'CWDH', (b, d[b:b + 4])
            size = _u32(d, b + 4)
            start, end = _u16(d, b + 8), _u16(d, b + 10)
            nxt = _u32(d, b + 12)
            q = b + 16
            for g in range(start, end + 1):
                self.widths[g] = (struct.unpack_from(BE + 'b', d, q)[0], d[q + 1], d[q + 2])
                q += 3
            self.cwdh_chain.append((start, end, size))
            b = nxt - 8 if nxt else None

        # ---- CMAP 체인
        self.cmaps = []
        self.charmap = {}
        b = cmap
        while b is not None:
            assert d[b:b + 4] == b'CMAP', (b, d[b:b + 4])
            cm = CMAP.parse(d, b)
            self.cmaps.append(cm)
            self.charmap.update(cm.entries)
            nxt = _u32(d, b + 8 + 8)
            b = nxt - 8 if nxt else None

        self.tail = d[self._blocks_end():]              # 남는 블록(있다면) 원형 보존

    def _blocks_end(self):
        return len(self.raw)

    # ---------------------------------------------------------------- 정보
    @property
    def cell_step(self):
        return self.cell_w + 1, self.cell_h + 1

    @property
    def per_sheet(self):
        return self.columns * self.rows

    @property
    def capacity(self):
        return self.per_sheet * self.num_sheets

    def glyph_count(self):
        return max(self.charmap.values()) + 1 if self.charmap else 0

    # ---------------------------------------------------------------- 직렬화
    def build(self, sheets=None, widths=None, cmaps=None, num_sheets=None):
        sheets = self.sheets if sheets is None else sheets
        widths = self.widths if widths is None else widths
        cmaps = self.cmaps if cmaps is None else cmaps
        ns = len(sheets)

        # CWDH: 원본 체인 모양을 유지하되, 새로 주면 0..N-1 한 블록으로
        if widths is self.widths and len(self.cwdh_chain) > 1:
            chain = self.cwdh_chain
        else:
            chain = [(0, max(widths), None)]

        blocks = []                                      # [(magic, body_without_next, has_next_field)]

        tglp_body = bytearray()
        tglp_body += bytes([self.cell_w, self.cell_h, ns, self.max_char_w])
        tglp_body += struct.pack(BE + 'I', len(sheets[0]))
        tglp_body += struct.pack(BE + 'HHHHHH', self.baseline, self.format,
                                 self.columns, self.rows, self.sheet_w, self.sheet_h)

        cwdh_blocks = []
        for start, end, _ in chain:
            body = bytearray(struct.pack(BE + 'HH', start, end))
            for g in range(start, end + 1):
                l, gw, cw = widths.get(g, (self.def_left, self.def_glyph_w, self.def_char_w))
                body += struct.pack(BE + 'bBB', l, gw, cw)
            cwdh_blocks.append(bytes(body))

        cmap_blocks = []
        for cm in cmaps:
            body = struct.pack(BE + 'HHHH', cm.code_begin, cm.code_end, cm.method, cm.pad) + cm.body()
            cmap_blocks.append(body)

        nblocks = 1 + 1 + len(cwdh_blocks) + len(cmap_blocks)

        # 1차 배치로 오프셋 계산 (TGLP 시트 데이터 앞 패딩 포함)
        def layout(gap):
            pos = self.header_size
            finf_off = pos
            pos += self.finf_size
            tglp_off = pos
            tglp_total = 8 + len(tglp_body) + 4 + len(gap) + ns * len(sheets[0])
            pos += tglp_total
            cw_offs, cm_offs = [], []
            for b in cwdh_blocks:
                cw_offs.append(pos)
                pos += _pad4(8 + 8 + len(b) - 4)         # start/end(4) + next(4) + data
            for b in cmap_blocks:
                cm_offs.append(pos)
                pos += _pad4(8 + len(b) + 4)
            return finf_off, tglp_off, cw_offs, cm_offs, pos, tglp_total

        gap = self.tglp_gap
        finf_off, tglp_off, cw_offs, cm_offs, total, tglp_total = layout(gap)
        # 시트 데이터는 sheet_off 정렬을 유지: 원본과 같은 간격이면 그대로, 아니면 4바이트 정렬
        out = bytearray()
        out += b'FFNT' + struct.pack(BE + 'HH', 0xFEFF, self.header_size)
        out += struct.pack(BE + 'II', self.version, total)
        out += struct.pack(BE + 'H', nblocks) + self.head_pad

        out += b'FINF' + struct.pack(BE + 'I', self.finf_size)
        out += bytes([self.font_type, self.height, self.width, self.ascent])
        out += struct.pack(BE + 'HH', self.line_feed, self.alter_index)
        out += struct.pack(BE + 'bBBB', self.def_left, self.def_glyph_w, self.def_char_w, self.encoding)
        out += struct.pack(BE + 'III', tglp_off + 8, cw_offs[0] + 8, cm_offs[0] + 8)
        assert len(out) == self.header_size + self.finf_size, (len(out), self.finf_size)

        out += b'TGLP' + struct.pack(BE + 'I', tglp_total)
        out += tglp_body
        out += struct.pack(BE + 'I', tglp_off + 8 + len(tglp_body) + 4 + len(gap))
        out += gap
        for s in sheets:
            out += s

        for i, b in enumerate(cwdh_blocks):
            size = _pad4(12 + len(b))
            nxt = cw_offs[i + 1] + 8 if i + 1 < len(cw_offs) else 0
            out += b'CWDH' + struct.pack(BE + 'I', size)
            out += b[:4] + struct.pack(BE + 'I', nxt) + b[4:]
            out += b'\0' * (_pad4(len(out)) - len(out))
        for i, b in enumerate(cmap_blocks):
            size = _pad4(8 + len(b) + 4)
            nxt = cm_offs[i + 1] + 8 if i + 1 < len(cm_offs) else 0
            out += b'CMAP' + struct.pack(BE + 'I', size)
            out += b[:8] + struct.pack(BE + 'I', nxt) + b[8:]
            out += b'\0' * (_pad4(len(out)) - len(out))
        struct.pack_into(BE + 'I', out, 12, len(out))
        return bytes(out)


def _pad4(v):
    return (v + 3) // 4 * 4


def load(path):
    with open(path, 'rb') as f:
        return BFFNT(f.read())


FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'work', 'extract', 'pack_999_font', 'Font')


def all_fonts():
    return [os.path.join(FONT_DIR, f) for f in sorted(os.listdir(FONT_DIR)) if f.endswith('.bffnt')]


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'info'
    for p in all_fonts():
        f = load(p)
        name = os.path.basename(p)
        if cmd == 'info':
            hangul = sum(1 for c in f.charmap if 0xAC00 <= c <= 0xD7A3)
            print('%-26s cell %2dx%-2d step %2dx%-2d sheets %d %dx%d fmt %-2d  %3dx%-3d=%5d칸  글리프 %5d  한글 %d' % (
                name, f.cell_w, f.cell_h, *f.cell_step, f.num_sheets, f.sheet_w, f.sheet_h,
                f.format, f.columns, f.rows, f.capacity, f.glyph_count(), hangul))
        elif cmd == 'verify':
            ok = f.build() == f.raw
            print('%-26s %s' % (name, 'OK' if ok else 'MISMATCH (%d vs %d)' % (len(f.build()), len(f.raw))))
