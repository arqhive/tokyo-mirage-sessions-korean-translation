"""원본 폰트에 맞춰 한글 (size, wght) 를 고른다.

  size : (한글 잉크폭 ↔ 원본 한자 잉크폭) + 0.7 × (잉크높이 ↔ 한자 잉크높이) 가중 점수
  wght : font_render.score — 2.0×pen(기둥 잉크두께) + 0.5×pen(기둥 폭) + 0.5×(1−최빈비율)
         pen 은 원본보다 가는 쪽에 3배 벌점 (사용자가 얇은 걸 먼저 알아챈다)
  기준 획은 **가나**에서 잰다. 한자는 획이 빽빽해 부적합.
"""
import os, sys, collections
import numpy as np
import bffnt_tool as bt, font_atlas as fa, font_render as fr

KANA = [chr(c) for c in list(range(0x3041, 0x3097)) + list(range(0x30A1, 0x30FB))]
HANZI = '漢字東京幻影異聞録戦闘中止開始選択装備能力回復攻撃防御'


def measure(font, sheets, chars):
    ink, wid, iw, ih = [], [], [], []
    for c in chars:
        g = font.charmap.get(ord(c))
        if g is None:
            continue
        cell = fa.get_glyph(sheets, font, g)
        ink += fr.stem_ink(cell)
        wid += fr.stems(cell)
        bb = fr.ink_bbox(cell)
        if bb:
            iw.append(bb[2] - bb[0]); ih.append(bb[3] - bb[1])
    return dict(ink=float(np.mean(ink)) if ink else 0, wid=float(np.mean(wid)) if wid else 0,
                w=float(np.median(iw)) if iw else 0, h=float(np.median(ih)) if ih else 0)


def hangul_measure(size, wght, f, char_w):
    cells = [fr.render(ch, size, wght, f.cell_w, f.cell_h, char_w) for ch in fr.REF_HANGUL]
    ink = [v for c in cells for v in fr.stem_ink(c)]
    wid = [v for c in cells for v in fr.stems(c)]
    bbs = [fr.ink_bbox(c) for c in cells]
    iw = [b[2] - b[0] for b in bbs if b]
    ih = [b[3] - b[1] for b in bbs if b]
    cnt = collections.Counter(wid)
    return dict(ink=float(np.mean(ink)) if ink else 0, wid=float(np.mean(wid)) if wid else 0,
                w=float(np.median(iw)) if iw else 0, h=float(np.median(ih)) if ih else 0,
                mode=cnt.most_common(1)[0][1] / len(wid) if wid else 0, cells=cells)


def calibrate(path, verbose=True):
    name = os.path.basename(path)[:-6]
    f = bt.load(path)
    sheets = fa.decode_sheets(f)
    kana = measure(f, sheets, KANA)
    hanzi = measure(f, sheets, HANZI)
    char_w = max(w[2] for g, w in f.widths.items() if g in f.charmap.values()) if f.widths else f.max_char_w
    char_w = min(char_w, f.cell_w)

    # 1) size — 한자 잉크 상자에 맞춘다
    best_size, best_s = None, 1e9
    for size in range(max(6, f.cell_h - 12), f.cell_h + 8):
        m = hangul_measure(size, 500, f, char_w)
        if m['h'] > f.cell_h or m['w'] > char_w:
            continue
        s = abs(m['w'] - hanzi['w']) + 0.7 * abs(m['h'] - hanzi['h'])
        if s < best_s:
            best_s, best_size = s, size
    if best_size is None:
        best_size = f.cell_h - 4

    # 2) wght — 가나 기둥에 맞춘다
    best_w, best_ws, best_m = None, 1e9, None
    for wght in range(300, 926, 25):
        m = hangul_measure(best_size, wght, f, char_w)
        s = (2.0 * fr._pen(m['ink'], kana['ink']) + 0.5 * fr._pen(m['wid'], kana['wid'])
             + 0.5 * (1 - m['mode']))
        if s < best_ws:
            best_ws, best_w, best_m = s, wght, m
    if verbose:
        print('%-22s cell %2dx%-2d charW %2d | 가나 ink %.2f 폭 %.2f · 한자 %dx%d'
              % (name, f.cell_w, f.cell_h, char_w, kana['ink'], kana['wid'], hanzi['w'], hanzi['h']))
        print('%-22s -> size %2d wght %3d   한글 ink %.2f 폭 %.2f · %dx%d  (예전 값 %s)'
              % ('', best_size, best_w, best_m['ink'], best_m['wid'], best_m['w'], best_m['h'],
                 fr.STYLES.get(name)))
    return name, best_size, best_w


if __name__ == '__main__':
    only = sys.argv[1] if len(sys.argv) > 1 else None
    res = {}
    for p in bt.all_fonts():
        if only and only not in p:
            continue
        n, s, w = calibrate(p)
        res[n] = (s, w)
    print()
    print('STYLES = {')
    for k, v in res.items():
        print("    %-24s (%d, %d)," % ("'%s':" % k, v[0], v[1]))
    print('}')
