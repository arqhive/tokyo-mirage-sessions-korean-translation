"""UI 텍스처에 박힌 일본어 라벨을 한글로 바꾼다.

대상 텍스처는 전부 RGBA8 / tileMode 4 / 밉맵 없음이라 `gtx2.encode` 로 무손실 교체된다.
글자는 RGB = 흰색 고정, **알파가 글자 모양**이다.

라벨 자리(UV)가 테이블·Lua 에 박혀 있으므로 **원래 글자 상자를 벗어나면 안 된다.**
높이에 맞춰 렌더하고 폭이 넘치면 줄인 뒤, 상자 안에서 가운데로 놓는다.

  python tex_patch.py preview    바꾼 결과를 PNG 로 확인
  python tex_patch.py build      {내부경로: gtx bytes} 를 만들어 반환 (build_patch 가 호출)
"""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import extract, gtx2

ROOT = extract.ROOT
TEX_KO = os.path.join(ROOT, 'translation', 'tex_ko.json')
FONT_PATH = 'C:/Windows/Fonts/NotoSansKR-VF.ttf'
SS = 4

_fcache = {}


def _font(px, wght=600):
    k = (px, wght)
    if k not in _fcache:
        f = ImageFont.truetype(FONT_PATH, px)
        try:
            f.set_variation_by_axes([wght])
        except Exception:
            pass
        _fcache[k] = f
    return _fcache[k]


MIN_SQUEEZE = 0.62          # 가로 압축 하한 — 이보다 좁히면 읽기 힘들다


def _ink(text, px, wght):
    pad = px // 2
    im = Image.new('L', (px * (len(text) + 1) + pad * 2, px * 2 + pad * 2), 0)
    ImageDraw.Draw(im).text((pad, pad), text, font=_font(px, wght), fill=255)
    a = np.array(im)
    ys, xs = np.nonzero(a > 12)
    if len(ys) == 0:
        return None
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


_WARN = []          # 과압축 라벨 기록 (빌드 로그로 뽑아 본다)


def render_label(text, box_w, box_h, glyph_h, wght=600, align='center'):
    """상자에 맞춘 글자 알파맵.

    **글자 크기는 모든 라벨이 공통(glyph_h)** 이다. 라벨마다 상자 폭에 맞춰 크기를 달리
    잡으면 짧은 라벨만 커져 들쭉날쭉해 보인다(원본 일본어는 전부 같은 크기다).
    폭이 넘칠 때만 가로로 눌러서 맞추고, 그래도 안 되면 그때 전체를 줄인다.
    """
    if not text:
        return np.zeros((box_h, box_w), np.uint8)
    a = _ink(text, max(8, glyph_h) * SS, wght)
    if a is None:
        return np.zeros((box_h, box_w), np.uint8)
    ih, iw = a.shape
    nh = min(box_h, max(1, int(round(ih / SS))))
    nw = max(1, int(round(iw / SS)))
    if nw > box_w:
        sq = box_w / nw
        if sq < MIN_SQUEEZE:                      # 가로 압축만으로 모자라면 세로도 줄인다
            nh = max(1, int(round(nh * (box_w / (nw * MIN_SQUEEZE)))))
        if sq < 0.72:                             # 빈 목록에서도 첫 경고를 기록한다
            _WARN.append((text, box_w, nw, sq))
        nw = box_w                                # 어떤 경우에도 상자를 넘지 않는다
    small = np.array(Image.fromarray(a).resize((nw, nh), Image.BOX))
    out = np.zeros((box_h, box_w), np.uint8)
    ox = {'left': 0, 'right': box_w - nw, 'center': (box_w - nw) // 2}[align]
    oy = (box_h - nh) // 2
    out[oy:oy + nh, ox:ox + nw] = small
    return out


def col_bboxes(alpha, y0, n, step, x0, x1, thr=48):
    """고정 격자(step) 로 나눈 각 줄의 잉크 bbox 목록.

    thr 을 낮게 잡으면 **옆 열 글자의 안티앨리어싱 자락**(알파 20~30)까지 물어서
    bbox 가 열 경계까지 늘어난다. 그러면 한글을 그 폭에 맞춰 그리다가 원본 글자
    범위를 넘고, 게임은 원본 범위만 잘라 쓰므로 끝 글자가 잘린다.
    """
    out = []
    for i in range(n):
        a, b = y0 + step * i, y0 + step * (i + 1)
        m = alpha[a:b, x0:x1] > thr
        xs = np.nonzero(m.any(0))[0]
        ys = np.nonzero(m.any(1))[0]
        out.append((x0 + int(xs[0]), a + int(ys[0]), x0 + int(xs[-1]) + 1, a + int(ys[-1]) + 1)
                   if len(xs) else None)
    return out


def patch_m_window003(img, table, log=print):
    """버튼 가이드 30개. 18줄 × 2열, 첫 줄 y=665, 줄 간격 20px, 열 경계 x=97."""
    a = img[..., 3]
    Y0, STEP, SPLIT = 665, 20, 97
    cols = [('m_window003_col1', 0, SPLIT, 18), ('m_window003_col2', SPLIT, 200, 12)]

    # 원본 글자 높이의 중앙값 — 모든 한글 라벨이 이 크기를 함께 쓴다
    all_boxes = {key: col_bboxes(a, Y0, rows, STEP, x0, x1) for key, x0, x1, rows in cols}
    heights = [b[3] - b[1] for bs in all_boxes.values() for b in bs if b]
    glyph_h = int(np.median(heights))

    n = 0
    for key, x0, x1, rows in cols:
        boxes = all_boxes[key]
        pairs = table[key]
        assert len(pairs) == rows, (key, len(pairs), rows)
        for i, ((ja, ko), bb) in enumerate(zip(pairs, boxes)):
            if bb is None:
                log('  ! %s[%d] %s : 원본 글자를 못 찾음' % (key, i, ja))
                continue
            # 격자 칸 전체를 지운다 (이웃 줄은 건드리지 않는다)
            cy0, cy1 = Y0 + STEP * i, Y0 + STEP * (i + 1)
            img[cy0:cy1, x0:x1, 3] = 0
            bw, bh = bb[2] - bb[0], bb[3] - bb[1]
            cell = render_label(ko, bw, bh, glyph_h)
            img[bb[1]:bb[3], bb[0]:bb[2], 3] = cell
            img[bb[1]:bb[3], bb[0]:bb[2], :3] = 255
            n += 1
    return n


def patch_status_labels(img, table, log=print):
    """능력치·운세 라벨. 다섯 텍스처가 **같은 자리에 같은 세트**를 갖고 있어 함수 하나로 처리된다.

    1열 x 396~450 : 力: 魔力: 技: 速さ: 守備: 魔防: 幸運: 悲運 不運 普通 強運 豪運  (y=0 부터 20px 간격)
    2열 x 450~508 : 攻撃力: 防御力: 만 일본어.
    x508 오른쪽에는 텍스처에 따라 프로필/Enemy Skill/Drop이 있어 보존한다.
    """
    a = img[..., 3]
    STEP = 20
    cols = [('status_col1', 396, 450, 12), ('status_col2', 450, 508, 2)]
    all_boxes = {k: col_bboxes(a, 0, rows, STEP, x0, x1) for k, x0, x1, rows in cols}
    heights = [b[3] - b[1] for bs in all_boxes.values() for b in bs if b]
    if not heights:
        log('  ! 능력치 라벨을 못 찾음')
        return 0
    glyph_h = int(np.median(heights))
    n = 0
    for key, x0, x1, rows in cols:
        for i, ((ja, ko), bb) in enumerate(zip(table[key], all_boxes[key])):
            if bb is None:
                log('  ! %s[%d] %s : 원본 글자를 못 찾음' % (key, i, ja))
                continue
            img[STEP * i:STEP * (i + 1), x0:x1, 3] = 0
            cell = render_label(ko, bb[2] - bb[0], bb[3] - bb[1], glyph_h)
            img[bb[1]:bb[3], bb[0]:bb[2], 3] = cell
            img[bb[1]:bb[3], bb[0]:bb[2], :3] = 255
            n += 1

    # 속성 내성 표시 (한 글자씩). 「一」과 「?」는 기호라 건드리지 않는다.
    for (ja, ko), (x0, x1, y0, y1) in zip(table['status_resist'], RESIST_BOXES):
        n += _replace_one(img, ko, x0, x1, y0, y1, log, ja)
    # 게이지 라벨 — fusion001 에는 없어서 못 찾으면 그냥 넘어간다
    for (ja, ko), (x0, x1, y0, y1) in zip(table['status_gauge'], GAUGE_BOXES):
        n += _replace_one(img, ko, x0, x1, y0, y1, None, ja)
    return n


RESIST_BOXES = [(200, 227, 18, 43), (200, 227, 43, 67), (200, 227, 67, 91),
                (200, 227, 91, 115), (227, 256, 18, 43)]
GAUGE_BOXES = [(0, 46, 422, 445)]


def _replace_one(img, ko, x0, x1, y0, y1, log, ja='', invert=False, glyph_h=None, overlay=False,
                 bright_thr=160, align='center', overlay_box=None, offset_y=0):
    """지정한 구간에서 글자를 찾아 그 자리에 한글을 그린다. 없으면 0 을 돌려준다.

    invert=True  : **흰 판에 검은 글자** (topic_window 의 詳細·タイムライン·追尾ビュー)
    overlay=True : **불투명한 배경판 위의 흰 글자** (largemap 의 現在位置 — 검은 알약 위).
                   알파를 지우면 배경판에 구멍이 나므로 알파는 두고 RGB 만 칠한다.
    """
    a = img[..., 3]
    m = a[y0:y1, x0:x1] > 24
    xs = np.nonzero(m.any(0))[0]
    ys = np.nonzero(m.any(1))[0]
    if len(xs) == 0:
        if log:
            log('  ! %s : 원본 글자를 못 찾음' % ja)
        return 0
    bb = (x0 + int(xs[0]), y0 + int(ys[0]), x0 + int(xs[-1]) + 1, y0 + int(ys[-1]) + 1)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    if invert:
        # 판은 살리고 글자만 새로 쓴다: 구간을 흰색으로 밀고 한글을 검게 얹는다
        cell = render_label(ko, bw, bh, glyph_h or bh)
        img[y0:y1, x0:x1, :3] = 255
        img[bb[1]:bb[3], bb[0]:bb[2], :3] = (255 - cell)[..., None]
        return 1
    if overlay:
        # 배경판은 알파로, 글자는 RGB 로 그려진 라벨.
        # 알파로 bbox 를 잡으면 배경판 전체가 잡혀 글자가 그만큼 커지므로 **밝은 RGB**로 잡는다.
        reg = img[y0:y1, x0:x1]
        bright = (reg[..., :3].min(-1) > bright_thr) & (reg[..., 3] > 128)
        if not bright.any():
            if log:
                log('  ! %s : 배경판 위 글자를 못 찾음' % ja)
            return 0
        bys, bxs = np.nonzero(bright)
        bb = (x0 + int(bxs.min()), y0 + int(bys.min()), x0 + int(bxs.max()) + 1, y0 + int(bys.max()) + 1)
        bw, bh = bb[2] - bb[0], bb[3] - bb[1]
        dark = (~bright) & (reg[..., 3] > 128)
        base = np.median(reg[..., :3][dark], axis=0).astype(np.uint8) if dark.any() else np.zeros(3, np.uint8)
        draw_box = overlay_box or bb
        dx0, dy0, dx1, dy1 = draw_box
        dy0 += offset_y
        dy1 += offset_y
        if not (x0 <= dx0 < dx1 <= x1 and y0 <= dy0 < dy1 <= y1):
            raise ValueError('overlay drawing box exceeds protected text region')
        cell = render_label(ko, dx1 - dx0, dy1 - dy0, glyph_h or bh, align=align)
        # 배경 전체를 단색으로 밀면 마름모의 그라데이션 같은 무늬가 뭉개진다 → 원본 글자 픽셀만 지운다.
        # 지우기는 bbox 안에서만 **더 낮은 임계값**으로 한다. bbox 용 임계값을 그대로 쓰면
        # 원본 글자 중 어두운 획(안티앨리어싱 포함)이 남아 한글과 겹쳐 보인다.
        gone = np.zeros_like(bright)
        gone[bys.min():bys.max() + 1, bxs.min():bxs.max() + 1] = (
            (reg[..., :3].min(-1) > 120) & (reg[..., 3] > 128)
        )[bys.min():bys.max() + 1, bxs.min():bxs.max() + 1]
        grown = gone.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                sh = np.zeros_like(gone)
                ys0, ys1 = max(0, dy), gone.shape[0] + min(0, dy)
                xs0, xs1 = max(0, dx), gone.shape[1] + min(0, dx)
                sh[ys0:ys1, xs0:xs1] = gone[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
                grown |= sh
        img[y0:y1, x0:x1, :3] = np.where(grown[..., None], base, reg[..., :3])
        sub = img[dy0:dy1, dx0:dx1, :3]
        # 중간 농도를 유지해야 작은 한글의 획이 계단처럼 굵어지지 않는다.
        coverage = cell[..., None].astype(np.float32) / 255.0
        img[dy0:dy1, dx0:dx1, :3] = np.rint(
            255.0 * coverage + sub.astype(np.float32) * (1.0 - coverage)
        ).astype(np.uint8)
        return 1
    img[y0:y1, x0:x1, 3] = 0
    cell = render_label(ko, bw, bh, glyph_h or bh)
    img[bb[1]:bb[3], bb[0]:bb[2], 3] = cell
    img[bb[1]:bb[3], bb[0]:bb[2], :3] = 255
    return 1


def patch_intermission(img, table, log=print):
    """장 제목 아틀라스.

    `title00~07` / `intermission01~05` 는 "演出含め仮"(연출 포함 임시) 워터마크가 찍힌
    **개발 중 가제**라 실기에 나오지 않는다(사용자가 실기와 대조해 확인). 실제로 쓰이는 건 이 파일이다.
      제목 13줄  : x 400~1024, y=5 부터 62px 간격
      장 라벨 9줄 : x  90~ 300, y=405 부터 48px 간격 (맨 아래 END 는 영어라 제외)
    """
    n = 0
    for i, (ja, ko) in enumerate(table['chapter_title']):
        n += _replace_one(img, ko, 400, 1024, 5 + 62 * i, 5 + 62 * (i + 1) - 4, log, ja)
    for i, (ja, ko) in enumerate(table['chapter_label']):
        n += _replace_one(img, ko, 90, 300, 405 + 48 * i, 405 + 48 * (i + 1) - 4, log, ja)
    return n


TOPIC_FILTER_BOXES = [
    (129, 181, 83, 101),        # ジャンル
    (129, 181, 104, 122),       # 依頼者
    (129, 181, 125, 143),       # ギフト
]

TOPIC_MISC_BOXES = [
    (10, 60, 107, 126, False),      # 閉じる: 검은 원 내부의 글자만. 원 테두리 제외.
    (282, 326, 86, 108, False),     # 概要
    (2, 166, 2, 78, False),         # 達成   (붓글씨 장식체 — 고딕으로 대체된다)
    (460, 508, 36, 60, True),       # 詳細      ↓ 흰 판에 검은 글자
    (456, 508, 66, 90, True),       # タイムライン (왼쪽 시계 아이콘은 범위 밖)
    (438, 504, 98, 122, True),      # 追尾ビュー
]


def patch_topic_window(img, table, log=print):
    """토픽 UI. 목록·필터·개별 라벨."""
    a = img[..., 3]
    boxes = col_bboxes(a, 255, 8, 20, 130, 215)[1:]      # 첫 줄 「???」는 건너뛴다
    heights = [b[3] - b[1] for b in boxes if b]
    glyph_h = int(np.median(heights)) if heights else 16
    n = 0
    for i, ((ja, ko), bb) in enumerate(zip(table['topic_list'], boxes)):
        if bb is None:
            log('  ! topic_list[%d] %s : 원본 글자를 못 찾음' % (i, ja))
            continue
        y0 = 255 + 20 * (i + 1)
        img[y0:y0 + 20, 130:215, 3] = 0
        # 게임이 자르는 칸은 글자 칸보다 **위로** 넓다. 그대로 두면 윗줄 글자의
        # 아래 획이 다음 탭에 가로 막대처럼 딸려 들어간다(「전체」 위의 막대).
        # 그래서 아래쪽을 넉넉히 비운다. 원본 일본어는 아래 획이 한쪽에 몰려 있어
        # (「み」) 걸리지 않았을 뿐, 한글은 받침이 가로로 넓어서 걸린다.
        # 세로는 bbox 가 아니라 **칸** 기준으로 잡는다. 「進行中」처럼 원본 잉크가
        # 얕은 줄은 bbox 를 쓰면 혼자 작아진다.
        y1, y2 = y0 + 1, y0 + 16
        cell = render_label(ko, bb[2] - bb[0], y2 - y1, glyph_h - 2)
        img[y1:y2, bb[0]:bb[2], 3] = cell
        img[y1:y2, bb[0]:bb[2], :3] = 255
        n += 1
    # 필터 3줄. 간격이 21px 로 고르지 않아 좌표를 직접 잡았다.
    # x181~189 는 패널 테두리(세로 막대)라 절대 건드리면 안 된다.
    for (ja, ko), (x0, x1, y0, y1) in zip(table['topic_filter'], TOPIC_FILTER_BOXES):
        n += _replace_one(img, ko, x0, x1, y0, y1, log, ja, glyph_h=13)
    for i, ((ja, ko), (x0, x1, y0, y1, inv)) in enumerate(zip(table['topic_misc'], TOPIC_MISC_BOXES)):
        # 닫기 버튼은 불투명한 검은 원이다. 알파를 지우면 원에 구멍이 난다.
        n += _replace_one(img, ko, x0, x1, y0, y1, log, ja, invert=inv,
                          overlay=(i == 0), glyph_h=18 if i == 0 else None,
                          overlay_box=(10, 108, 60, 126) if i == 0 else None)
    return n


def _grow_mask(mask):
    padded = np.pad(mask, 1, mode='constant')
    return np.logical_or.reduce([padded[y:y + mask.shape[0], x:x + mask.shape[1]]
                                 for y in range(3) for x in range(3)])


def _camp_help_background(img):
    """같은 배경의 9개 행과 상점 행에서 흰 글자에 가리지 않은 픽셀을 모은다.

    모든 행에서 글자에 가린 부분만 주변 색으로 보간한다. 추정 복원은 글자 아래로 제한.
    """
    samples = [img[722 + 33*i:754 + 33*i, 550:984, :3] for i in range(9)]
    samples.append(img[722:754, 1614:2048, :3])
    background = np.minimum.reduce(samples).astype(np.float32)
    # 배너는 어두운 색이다. 남은 공통 흰 글자와 가장자리만 보간 대상으로 잡는다.
    hidden = _grow_mask(background.min(-1) > 32)
    background[hidden] = np.median(background[~hidden], axis=0)
    for _ in range(200):
        p = np.pad(background, ((1, 1), (1, 1), (0, 0)), mode='edge')
        average = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) * .25
        delta = np.max(np.abs(average[hidden] - background[hidden])) if hidden.any() else 0
        background[hidden] = average[hidden]
        if delta < .01:
            break
    return np.rint(background).astype(np.uint8)


def patch_a1_camp(img, table, log=print):
    """불투명 배너의 글자만 교체한다. 배경/알파/로고는 보존, x974 오른쪽 정렬."""
    background = _camp_help_background(img)
    pairs = table['a1_camp_help']
    assert len(pairs) == 9
    for i, (ja, ko) in enumerate(pairs):
        y = 722 + 33*i
        region = img[y:y + 32, 550:984, :3]
        text_mask = _grow_mask(region.min(-1) > 32)
        region[text_mask] = background[text_mask]
        # 원문 글자는 위에서 8..24px, 오른쪽 끝은 974. 모든 행의 크기를 맞춘다.
        cell = render_label(ko, 424, 17, 18, align='right')
        coverage = cell[..., None].astype(np.float32) / 255.0
        target = img[y + 8:y + 25, 550:974, :3]
        target[:] = np.rint(255.0 * coverage + target * (1.0 - coverage)).astype(np.uint8)
    return len(pairs)


OFFER_BOXES = [(241, 790, 305, 410), (274, 755, 418, 502)]


def patch_offer(img, table, log=print):
    """사이드 스토리 결과 문구 (큰 기울임 장식체 → 고딕으로 대체)."""
    n = 0
    for (ja, ko), (x0, x1, y0, y1) in zip(table['offer_result'], OFFER_BOXES):
        n += _replace_one(img, ko, x0, x1, y0, y1, log, ja)
    return n


LARGEMAP_BOXES = [(275, 320, 236, 266, False),     # 渋谷   (왼쪽 화살표 아이콘은 범위 밖)
                  (320, 366, 236, 266, False),     # 原宿
                  (20, 98, 344, 377, True)]        # 現在位置 (검은 알약 위 → overlay)


def patch_largemap(img, table, log=print):
    n = 0
    for (ja, ko), (x0, x1, y0, y1, ov) in zip(table['largemap'], LARGEMAP_BOXES):
        n += _replace_one(img, ko, x0, x1, y0, y1, log, ja, overlay=ov,
                          offset_y=1 if ov else 0)
    return n


def patch_a1_title(img, table, log=print):
    """게임패드 타이틀 화면 HELP 설명문 2줄.

    배경이 불투명한 검은 띠(알파 전부 255)이고 글자는 RGB 로 그려져 있어 overlay 로 다룬다.
    줄은 y722/755 에서 시작한다. HELP 오른쪽 둥근 끝을 보존하려 x125부터 처리한다.
    """
    n = 0
    for i, (ja, ko) in enumerate(table['a1_title_help']):
        n += _replace_one(img, ko, 125, 620, 722 + 33 * i, 722 + 33 * (i + 1), log, ja,
                          overlay=True, align='left')
    return n


RESERVE_BOXES = [(188, 282, 448, 482), (282, 376, 448, 482), (376, 470, 448, 482)]


def patch_party_panel(img, table, log=print):
    """빈 슬롯의 「リザーブ」 3개 — **현재 TARGETS 에서 빠져 있다.**

    회색 마름모에 그라데이션과 하이라이트가 섞여 있어 원본 글자를 깨끗이 지우기 어렵다
    (지우면 회색 띠가 남고, 임계값을 낮추면 마름모 무늬가 뭉개진다). 중요도가 낮아 보류.
    """
    n = 0
    # 마름모에 밝은 하이라이트가 있어 임계값 160 으로는 배경까지 글자로 잡힌다 → 220
    for (ja, ko), (x0, x1, y0, y1) in zip(table['party_reserve'], RESERVE_BOXES):
        n += _replace_one(img, ko, x0, x1, y0, y1, log, ja, overlay=True, bright_thr=220)
    return n


TARGETS = {
    'Interface/m_window/m_window003.gtx': patch_m_window003,
    'Interface/largemap/largemap_001.gtx': patch_largemap,
    'Interface/A1/others/a1_title001.gtx': patch_a1_title,
    'Interface/offer/offer_UI001.gtx': patch_offer,
    'Interface/Intermission/Intermission001.gtx': patch_intermission,
    'Interface/Topic/topic_window.gtx': patch_topic_window,
    'Interface/A1/Camp/a1_camp001.gtx': patch_a1_camp,
    'Interface/result/result_001.gtx': patch_status_labels,
    'Interface/shop/shop001.gtx': patch_status_labels,
    'Interface/status_drc/status_drc001.gtx': patch_status_labels,
    'Interface/camp/status001.gtx': patch_status_labels,
    'Interface/fusion/fusion001.gtx': patch_status_labels,
}

PREVIEW_CROP = {
    'm_window003': (0, 655, 200, 1030),
    'Intermission001': (80, 0, 1024, 840),
    'topic_window': (0, 0, 512, 430),
    'a1_camp001': (540, 715, 1000, 1024),
    'offer_UI001': (230, 295, 790, 512),
    'largemap_001': (0, 230, 400, 385),
    'a1_title001': (40, 705, 640, 785),
    'party_panel001': (180, 430, 480, 500),
}
DEFAULT_CROP = (390, 0, 550, 250)


def build(log=print):
    with open(TEX_KO, encoding='utf-8') as f:
        table = json.load(f)
    c = extract.open_pack('pack_030_etc')
    out = {}
    for name, fn in TARGETS.items():
        raw = c.read(name)
        img, _ = gtx2.decode(raw)
        n = fn(img, table, log)
        out[name] = gtx2.encode(img, raw)
        log('  %-44s 라벨 %d개 교체' % (name.split('/')[-1], n))
    # 손으로 편집한 PNG(work/tex/_edit)가 있으면 얹는다 — 로고처럼 자동 재현이 안 되는 것들
    import tex_io
    out.update(tex_io.load_edited(log))
    return out


def cmd_preview(args):
    data = build()
    outdir = os.path.join(extract.WORK, 'tex', '_patched')
    os.makedirs(outdir, exist_ok=True)
    for name, raw in data.items():
        stem = name.split('/')[-1][:-4]
        img, _ = gtx2.decode(raw)
        im = Image.fromarray(img, 'RGBA')
        bg = Image.new('RGB', im.size, (22, 22, 28))
        bg.paste(im, (0, 0), im)
        crop = bg.crop(PREVIEW_CROP.get(stem, DEFAULT_CROP))
        crop = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
        p = os.path.join(outdir, stem + '.png')
        crop.save(p)
        print('->', p)


def cmd_build(args):
    build()


if __name__ == '__main__':
    {'preview': cmd_preview, 'build': cmd_build}[sys.argv[1] if len(sys.argv) > 1 else 'preview'](sys.argv[2:])
