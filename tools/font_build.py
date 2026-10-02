"""필요한 글자만으로 BFFNT 아틀라스를 재구성한다.

한글 글리프를 넣을 자리는 '빈칸 재활용'이나 '시트 증설'로 만들지 않는다.
번역이 끝나면 한자 대부분이 쓰이지 않으므로, **최종 텍스트에 실제로 쓰이는 글자만** 남겨
아틀라스를 새로 짜면 기존 칸 안에 여유롭게 들어간다.
  - 원본에 있던 글자: 원본 셀 비트맵과 CWDH 를 그대로 옮긴다 (모양이 변하면 안 된다)
  - 한글: font_render 로 새로 그리고, 폭은 원본 한자의 최빈 char_w 를 쓴다
  - CMAP 은 전부 버리고 SCAN(방식 2) 한 블록, CWDH 도 0..N-1 한 블록, alter_index=0
"""
import os, sys, collections
import numpy as np
import bffnt_tool as bt, font_atlas as fa, font_render as fr

# 번역이 없어도 항상 들어가야 하는 글자 (UI·숫자·기호)
ALWAYS = (''.join(chr(c) for c in range(0x20, 0x7F))
          + ''.join(chr(c) for c in range(0xFF01, 0xFF5F))          # 전각 영숫자
          + '　、。・ー〜…‥「」『』（）［］【】〈〉《》！？：；／＼％＆＊＋－＝＜＞')


def hangul_chars(text):
    return {c for c in text if 0xAC00 <= ord(c) <= 0xD7A3 or 0x3130 <= ord(c) <= 0x318F}


def needed_chars(texts):
    """번역/원문 전체에서 실제로 쓰이는 글자 집합."""
    s = set(ALWAYS)
    for t in texts:
        s.update(t)
    s.discard('\n')
    return s


def hanzi_baseline(font, sheets):
    """원본 한자 글리프의 잉크 아랫선(셀 안 y) 중앙값 — 한글을 이 줄에 맞춰 앉힌다."""
    bots = []
    for code, g in font.charmap.items():
        if not (0x4E00 <= code <= 0x9FFF):
            continue
        bb = fr.ink_bbox(fa.get_glyph(sheets, font, g))
        if bb:
            bots.append(bb[3])
        if len(bots) >= 400:
            break
    return int(np.median(bots)) if bots else font.cell_h


def hanzi_char_w(font):
    """원본 한자(전각)의 최빈 char_w — 한글 폭의 기준."""
    cnt = collections.Counter()
    for code, g in font.charmap.items():
        if 0x4E00 <= code <= 0x9FFF and g in font.widths:
            cnt[font.widths[g][2]] += 1
    if not cnt:
        return min(font.max_char_w, font.cell_w)
    return cnt.most_common(1)[0][0]


# 고정폭 본문 폰트(FOT-*)는 반각 띄어쓰기·부호도 한 칸(한자 폭)을 차지한다. 원문 일본어는 이 글자들을
# 거의 안 쓰지만(띄어쓰기 55회) 번역문은 많이 써서 대사창을 넘쳤다(2026-09-28 실기) → 번역문용으로 좁힌다.
NARROW = set(',.!?:;()~\'"-')


def narrow(name, c, w, hz_w):
    """(left, glyph_w, char_w) — FOT-* 폰트의 띄어쓰기는 한자 폭의 0.42, 반각 부호는 잉크 폭 + 앞 1 + 뒤 여백."""
    if not name.startswith('FOT-'):
        return w
    if c == ' ':
        return (0, 0, round(hz_w * 0.42))
    if c in NARROW:
        left = max(1, round(hz_w / 24))
        return (left, w[1], left + w[1] + max(2, round(hz_w / 12)))
    return w


def rebuild(path, chars, log=print):
    """-> (새 bffnt bytes, 통계 dict)"""
    name = os.path.basename(path)[:-6]
    f = bt.load(path)
    src_sheets = fa.decode_sheets(f)
    size, wght = fr.STYLES[name]
    hz_w = hanzi_char_w(f)
    base = hanzi_baseline(f, src_sheets)

    keep = sorted(c for c in chars if ord(c) in f.charmap)
    new_hangul = sorted(c for c in chars if ord(c) not in f.charmap and
                        (0xAC00 <= ord(c) <= 0xD7A3 or 0x3130 <= ord(c) <= 0x318F))
    dropped = sorted(c for c in chars if ord(c) not in f.charmap and c not in new_hangul)
    order = keep + new_hangul

    total = len(order)
    per = f.per_sheet
    nsheets = max(1, (total + per - 1) // per)
    if nsheets > f.num_sheets:
        log('  ! %s: 글리프 %d개 > 원본 시트 용량 %d, 시트를 %d장으로 늘림'
            % (name, total, f.capacity, nsheets))

    sheets = [np.zeros((f.sheet_h, f.sheet_w), np.uint8) for _ in range(nsheets)]
    widths = {}
    cmap = {}
    moved = 0
    for i, c in enumerate(order):
        cmap[ord(c)] = i
        if ord(c) in f.charmap:
            g = f.charmap[ord(c)]
            fa.put_glyph(sheets, f, i, fa.get_glyph(src_sheets, f, g))
            widths[i] = narrow(name, c, f.widths.get(g, (0, hz_w, hz_w)), hz_w)
            moved += 1
        else:
            cell = fr.render(c, size, wght, f.cell_w, f.cell_h, hz_w, baseline=base)
            fa.put_glyph(sheets, f, i, cell)
            widths[i] = (0, hz_w, hz_w)

    f.alter_index = 0
    data = f.build(sheets=fa.encode_sheets(sheets), widths=widths,
                   cmaps=[bt.CMAP.scan(cmap)])
    stat = dict(name=name, total=total, moved=moved, hangul=len(new_hangul),
                dropped=len(dropped), sheets=nsheets, orig_sheets=f.num_sheets,
                capacity=f.per_sheet * nsheets, size=size, wght=wght)
    return data, stat


# BC4 는 재인코딩에 손실이 있다(픽셀 최대 오차 18, 평균 0.7). 글자가 바뀌면 오차가 이보다 훨씬 크다.
TOL = 24


def verify(path, data, chars, log=print):
    """원본에 있던 글자가 원본과 같은 모양으로 옮겨졌는지 전수 대조 (BC4 손실은 허용)."""
    old = bt.load(path)
    new = bt.BFFNT(data)
    os_ = fa.decode_sheets(old)
    ns = fa.decode_sheets(new)
    bad = blank = 0
    for c in sorted(chars):
        code = ord(c)
        if code not in new.charmap:
            continue
        ncell = fa.get_glyph(ns, new, new.charmap[code])
        if code in old.charmap:
            ocell = fa.get_glyph(os_, old, old.charmap[code])
            if np.abs(ocell.astype(int) - ncell.astype(int)).max() > TOL:
                bad += 1
                if bad <= 3:
                    log('    어긋남 U+%04X %r' % (code, c))
        elif 0xAC00 <= code <= 0xD7A3 and ncell.max() == 0:
            blank += 1
    return bad, blank


def build_all(chars, log=print):
    out = {}
    for p in bt.all_fonts():
        data, st = rebuild(p, chars, log)
        b, bl = verify(p, data, chars, log)
        st['mismatch'], st['blank'] = b, bl
        log('  %-22s 글리프 %5d (원본재사용 %5d + 한글 %4d) 시트 %2d/%2d  어긋남 %d 빈한글 %d'
            % (st['name'], st['total'], st['moved'], st['hangul'], st['sheets'],
               st['orig_sheets'], b, bl))
        out['Font/%s.bffnt' % st['name']] = data
    return out


if __name__ == '__main__':
    import text_io, mtext
    texts = []
    for p in text_io.iter_json():
        j = text_io.load_json(p)
        for en in j['entries']:
            texts.append(mtext.plain(en.get('ko') or en['ja']))
    chars = needed_chars(texts)
    print('필요 글자 %d자 (한글 %d)' % (len(chars), len(hangul_chars(''.join(chars)))))
    build_all(chars)
