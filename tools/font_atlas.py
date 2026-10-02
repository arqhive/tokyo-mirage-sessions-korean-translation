"""BFFNT 시트 <-> 그레이스케일 이미지.

함정:
  ② 시트마다 뱅크 스위즐이 회전한다: swizzle = (sheet_index % 4) << 9.
     gtx_lib 의 tileMode4 하드코딩 deswizzle 은 시트 0 에서만 맞다 → addrlib 로 매핑을 뽑아 쓴다.
  ③ 시트는 상하 반전으로 저장돼 있다 (img[::-1]).
"""
import numpy as np
import addrlib, gtx_lib

FMT_BC4 = 0x34
_MAP = {}


def addr_map(w, h, swz):
    """저장 순서 <-> 선형 순서 블록 인덱스 매핑. linear[i] = stored[map[i]]"""
    key = (w, h, swz)
    m = _MAP.get(key)
    if m is None:
        n = (w // 4) * (h // 4)
        probe = np.arange(n, dtype='>u8').tobytes()
        lin = addrlib.deswizzle(w, h, h, FMT_BC4, 4, swz, w // 4, 64, probe)
        m = _MAP[key] = np.frombuffer(lin, '>u8').astype(np.int64)
    return m


def sheet_swizzle(i):
    return (i % 4) << 9


def decode_sheet(data, w, h, sheet_index):
    m = addr_map(w, h, sheet_swizzle(sheet_index))
    stored = np.frombuffer(data, np.uint8).reshape(-1, 8)
    linear = stored[m].reshape(h // 4, w // 4, 8)
    img = gtx_lib.bc4_decode_blocks(np.ascontiguousarray(linear))
    return img[::-1].copy()                       # ③ 상하 반전 복원


def encode_sheet(img, sheet_index):
    h, w = img.shape
    blocks = gtx_lib.bc4_encode_blocks(np.ascontiguousarray(img[::-1]))
    linear = blocks.reshape(-1, 8)
    m = addr_map(w, h, sheet_swizzle(sheet_index))
    stored = np.zeros_like(linear)
    stored[m] = linear
    return stored.tobytes()


def decode_sheets(font):
    return [decode_sheet(s, font.sheet_w, font.sheet_h, i) for i, s in enumerate(font.sheets)]


def encode_sheets(imgs):
    return [encode_sheet(im, i) for i, im in enumerate(imgs)]


# ---------------------------------------------------------------- 셀 좌표
def cell_rect(font, glyph):
    """글리프 번호 -> (시트번호, x, y, 폭, 높이).  셀 스텝은 (cellW+1, cellH+1)."""
    per = font.per_sheet
    sheet, rem = divmod(glyph, per)
    row, col = divmod(rem, font.columns)
    sx, sy = font.cell_step
    return sheet, col * sx, row * sy, font.cell_w, font.cell_h


def get_glyph(sheets, font, glyph):
    s, x, y, w, h = cell_rect(font, glyph)
    return sheets[s][y:y + h, x:x + w]


def put_glyph(sheets, font, glyph, cell):
    s, x, y, w, h = cell_rect(font, glyph)
    sheets[s][y:y + h, x:x + w] = cell[:h, :w]


# ---------------------------------------------------------------- 검증
if __name__ == '__main__':
    import sys, os
    from PIL import Image
    import bffnt_tool as bt

    cmd = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    out = os.path.join(bt.FONT_DIR, '..', '..', '..', 'font_preview')
    out = os.path.normpath(out)

    if cmd == 'verify':                           # 스위즐 왕복 검사
        ok = bad = 0
        for p in bt.all_fonts():
            f = bt.load(p)
            for i, s in enumerate(f.sheets):
                m = addr_map(f.sheet_w, f.sheet_h, sheet_swizzle(i))
                stored = np.frombuffer(s, np.uint8).reshape(-1, 8)
                back = np.zeros_like(stored)
                back[m] = stored[m]
                if back.tobytes() == s:
                    ok += 1
                else:
                    bad += 1
        print('스위즐 매핑 전단사 %d/%d 시트' % (ok, ok + bad))

    elif cmd == 'preview':                        # 글자 몇 개를 그려서 눈으로 확인
        os.makedirs(out, exist_ok=True)
        text = 'ＡＢＣあア漢字幻影異聞録東京ミラージュセッションズ'
        for p in bt.all_fonts():
            f = bt.load(p)
            sheets = decode_sheets(f)
            cw, ch = f.cell_w, f.cell_h
            canvas = np.zeros((ch, cw * len(text)), np.uint8)
            for i, c in enumerate(text):
                g = f.charmap.get(ord(c))
                if g is None:
                    continue
                canvas[:, i * cw:(i + 1) * cw] = get_glyph(sheets, f, g)
            Image.fromarray(canvas).save(os.path.join(out, os.path.basename(p) + '.png'))
        print('미리보기 ->', out)

    elif cmd == 'sheet':                          # 시트 통째로 PNG
        os.makedirs(out, exist_ok=True)
        f = bt.load([p for p in bt.all_fonts() if sys.argv[2] in p][0])
        for i, im in enumerate(decode_sheets(f)):
            Image.fromarray(im).save(os.path.join(out, '%s_sheet%d.png' % (sys.argv[2], i)))
        print('시트 %d장 ->' % f.num_sheets, out)
