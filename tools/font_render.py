"""Noto Sans KR VF 로 원본 폰트에 맞춘 한글 글리프 렌더.

지난 작업에서 네 번을 갈아엎고 얻은 결론이다. 다시 건드리기 전에 읽을 것:

  * **공통 격자**가 핵심이다. 글자마다 자기 잉크폭에 맞춰 따로 축소하면 가로 배율이 미세하게
    달라져(84/21=4.00 vs 87/22=3.95) 같은 획이 글자마다 굵게/가늘게 찍힌다 = '얼룩덜룩'.
    → `_draw`: 펜 위치를 SS 의 배수에 두고 캔버스 전체를 정확히 SS 배로 축소(Image.BOX).
      세로 창과 가로 오프셋도 REF_HANGUL 에서 한 번만 구해 모든 글자에 공통 적용한다.
  * 힌팅을 켜고 목표 크기로 직접 렌더하면 획이 글자마다 2px/3px 로 제각각 스냅돼 같은 증상이 난다.
  * 굵기 기준은 **원본 가나**의 세로기둥이다(한자는 획이 빽빽해 부적합).
    잣대는 `stem_ink` = 기둥을 가로지르는 픽셀값 합/255. 정수 폭만으로는 회색 농도를 못 잡는다.

  다시 하지 말 것: 잉크 총량 매칭, 런랭스 평균 매칭, 128 중심 S커브 대비 보정,
                   목표 크기 직접 렌더+힌팅, LANCZOS 축소.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = 'C:/Windows/Fonts/NotoSansKR-VF.ttf'
SS = 4
PAD = 6

# 세로 창·가로 오프셋을 정하는 기준 글자.
# 받침 유무뿐 아니라 위로 솟는 초성(ㅊ·ㅎ)과 아래로 처지는 모음·받침(ㅠ·ㄹ·ㅆ)도 넣어야
# 창이 좁아 글자가 잘리지 않는다.
REF_HANGUL = ('가나다라마바사아자차카타파하강경관국글김날놀단달램로만말물박번분빛산성술신'
              '똑뚝쁨쓸쫑찢흙옳핥뷰퓨츄휴헿쨍뿅')

# 폰트별 최종 (size, wght).
# 제약: 한글 공통 창의 높이 ≤ 원본 한자 잉크 높이. 이걸 어기면 글자가 원본보다 위로
# 삐져나와 메시지 창 상단에서 잘린다(실기에서 첫 줄이 잘려 드러났다).
# 그 제약 안에서 stem_ink 가 원본 가나와 맞도록 wght 를 고른다.
STYLES = {
    'FOT-SeuratPro-B_12':  (11, 900),
    'FOT-SeuratPro-DB_18': (17, 525),
    'FOT-SkipStd_12x12':   (13, 500),
    'FOT-SkipStd_16x16':   (16, 575),
    'FOT-SkipStd_18x18':   (17, 625),
    'FOT-SkipStd_24x24':   (24, 525),
    'FOT-SkipStd_30x30':   (30, 550),
    'debugFont':           (15, 475),
    'gameFont1_16x16':     (15, 475),
    'gameFont1_24x24':     (23, 450),
}

_font_cache = {}


def _font(px, wght):
    k = (px, wght)
    if k not in _font_cache:
        f = ImageFont.truetype(FONT_PATH, px)
        try:
            f.set_variation_by_axes([wght])
        except Exception:
            pass
        _font_cache[k] = f
    return _font_cache[k]


def _draw(ch, size, wght):
    """한 글자를 공통 격자에 그린다. 펜 위치는 SS 의 배수, 축소는 정확히 SS 배."""
    W = H = size + PAD * 2
    im = Image.new('L', (W * SS, H * SS), 0)
    ImageDraw.Draw(im).text((PAD * SS, PAD * SS), ch, font=_font(size * SS, wght), fill=255)
    return np.array(im.resize((W, H), Image.BOX))


def ink_bbox(a, thr=24):
    ys = np.nonzero(a.max(1) > thr)[0]
    xs = np.nonzero(a.max(0) > thr)[0]
    if len(ys) == 0:
        return None
    return xs[0], ys[0], xs[-1] + 1, ys[-1] + 1


_win_cache = {}


def ref_window(size, wght):
    """(top, bot, left) — 모든 글자가 들어가는 공통 틀.

    세로는 REF_HANGUL 전체의 min(top)~max(bot) 이다. 중앙값으로 잡으면 창을 벗어나는
    글자의 위/아래가 **잘린다**(실기에서 첫 줄 윗부분이 잘려 드러났다).
    가로 기준점만 중앙값을 쓴다.
    """
    k = (size, wght)
    if k not in _win_cache:
        tops, bots, lefts = [], [], []
        for c in REF_HANGUL:
            bb = ink_bbox(_draw(c, size, wght))
            if bb:
                lefts.append(bb[0]); tops.append(bb[1]); bots.append(bb[3])
        _win_cache[k] = (min(tops), max(bots), int(np.median(lefts)))
    return _win_cache[k]


def render(ch, size, wght, cell_w, cell_h, char_w, baseline=None):
    """글자 하나를 (cell_h, cell_w) 셀 이미지로. 세로는 공통 틀, 가로는 char_w 안에서 가운데.

    baseline: 셀 안에서 글자 잉크의 **아랫선**이 놓일 y. 원본 한자의 잉크 하단 중앙값을
    넘기면 원문과 같은 줄에 앉는다. 없으면 셀 중앙에 놓는데, 그러면 원본보다 2px 위로
    떠서 메시지 창 상단에서 잘린다.
    """
    a = _draw(ch, size, wght)
    top, bot, left = ref_window(size, wght)
    h = bot - top
    if baseline is None:
        y0 = (cell_h - h) // 2
    else:
        y0 = baseline - h
    y0 = max(0, min(y0, cell_h - h)) if cell_h >= h else 0
    cell = np.zeros((cell_h, cell_w), np.uint8)
    strip = a[top:bot]
    bb = ink_bbox(strip)
    if bb is None:
        return cell
    x0, x1 = bb[0], bb[2]
    w = x1 - x0
    dx = max(0, (char_w - w) // 2)
    src = strip[:, x0:x1]
    hh = min(strip.shape[0], cell_h - y0)
    ww = min(w, cell_w - dx)
    if hh > 0 and ww > 0:
        cell[y0:y0 + hh, dx:dx + ww] = src[:hh, :ww]
    return cell


# ---------------------------------------------------------------- 측정
def stems(cell, thr=24, min_run=0.6):
    """글자 높이의 min_run 이상 이어지는 세로기둥의 폭 목록 (1~6px 만)."""
    bb = ink_bbox(cell, thr)
    if bb is None:
        return []
    x0, y0, x1, y1 = bb
    h = y1 - y0
    col = (cell[y0:y1, x0:x1] > thr).sum(0) >= h * min_run
    out, run = [], 0
    for v in list(col) + [False]:
        if v:
            run += 1
        else:
            if 1 <= run <= 6:
                out.append(run)
            run = 0
    return out


def stem_ink(cell, thr=24, min_run=0.6):
    """세로기둥을 가로지르는 '잉크 기준 두께' 목록 — 반쯤 걸친 회색 열까지 센다."""
    bb = ink_bbox(cell, thr)
    if bb is None:
        return []
    x0, y0, x1, y1 = bb
    sub = cell[y0:y1, x0:x1].astype(np.float32)
    h = y1 - y0
    solid = (sub > thr).sum(0) >= h * min_run
    out = []
    i = 0
    n = len(solid)
    while i < n:
        if not solid[i]:
            i += 1
            continue
        j = i
        while j < n and solid[j]:
            j += 1
        lo = max(0, i - 1)
        hi = min(n, j + 1)
        if j - i <= 6:
            out.append(float(sub[:, lo:hi].sum() / 255.0 / h))
        i = j
    return out


def _pen(new, old, under=3.0):
    """원본보다 가는 쪽에 under 배 벌점."""
    d = new - old
    return abs(d) * (under if d < 0 else 1.0)


def score(cells, ref_ink, ref_w, ref_mode_ratio=None):
    ink = [v for c in cells for v in stem_ink(c)]
    wid = [v for c in cells for v in stems(c)]
    if not ink or not wid:
        return 1e9
    import collections
    cnt = collections.Counter(wid)
    mode_ratio = cnt.most_common(1)[0][1] / len(wid)
    return (2.0 * _pen(float(np.mean(ink)), ref_ink)
            + 0.5 * _pen(float(np.mean(wid)), ref_w)
            + 0.5 * (1 - mode_ratio))
