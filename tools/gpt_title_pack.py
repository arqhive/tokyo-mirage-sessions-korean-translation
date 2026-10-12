# -*- coding: utf-8 -*-
"""타이틀 로고 영상(m00.usm) 조립 구간을 GPT 에게 맡기기 위한 작업 묶음 만들기(2026-10-13).

  python -X utf8 tools/gpt_title_pack.py      → work/GPT_타이틀영상/
조립 구간(0-based 프레임 약 36~94, 1.2~3.1초)은 일본어 로고 글자가 알록달록 깜빡이며 나타난다.
그 뒤(95~334)는 usm_logo.py 가 이미 한글 title_logo 로 바꿨다. GPT 는 조립 구간 프레임의 글자만 한글로 바꾼다.
프레임은 투명 배경 RGBA PNG 로 준다(영상 색 = 흰 바탕 합성이라 알파로 되돌려 원래 색을 복원).
"""
import os, sys, json, shutil, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
import extract, gtx2, usm_frames, usm_logo

ROOT = extract.ROOT
OUT = os.path.join(ROOT, 'work', 'GPT_타이틀영상')
KO_LOGO = usm_logo.KO_LOGO
W, H, FPS = 1280, 720, 30
WORK = range(30, 95)          # GPT 가 다룰 프레임(0-based). 95 부터는 이미 한글
CONT = range(95, 111)         # 이어지는 한글 프레임(참고용)


def rgba_from(col, a):
    """흰 바탕 합성 색 + 알파 → 원래 색 RGBA"""
    af = a.astype(np.float32)[..., None] / 255
    c = (col.astype(np.float32) - 255 * (1 - af)) / np.maximum(af, 1e-3)
    c = np.where(af > 0.004, c, 0)
    return np.dstack([np.clip(np.round(c), 0, 255).astype(np.uint8), a])


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    for d in ('원본_프레임', '참고_한글로고_이어지는_프레임', '글자자리_마스크', '기준그림', '결과_프레임'):
        os.makedirs(os.path.join(OUT, d))
    orig = extract.open_pack('pack_050_movie').read('Movie/m00.usm')
    col = usm_logo.decode(usm_frames.stream_es(orig, b'@SFV'))
    alp = usm_logo.decode_y(usm_frames.stream_es(orig, b'@ALP'))
    cur = open(os.path.join(ROOT, 'work', 'movie_ko', 'm00.usm'), 'rb').read()
    kcol = usm_logo.decode(usm_frames.stream_es(cur, b'@SFV'))
    kalp = usm_logo.decode_y(usm_frames.stream_es(cur, b'@ALP'))
    n = len(col)
    ja = gtx2.decode(extract.open_pack('pack_030_etc').read('Interface/title/title_logo.gtx'))[0]
    ko = gtx2.decode(open(KO_LOGO, 'rb').read())[0]
    Image.fromarray(ja, 'RGBA').save(os.path.join(OUT, '기준그림', '로고_일본어_원본.png'))
    Image.fromarray(ko, 'RGBA').save(os.path.join(OUT, '기준그림', '로고_한글_확정본.png'))
    # 글자 자리(로고 좌표): 일본어·한글 로고가 다른 곳을 넓힌 것
    diff = np.any(ja.astype(int) != ko.astype(int), axis=2) & ((ja[..., 3] > 8) | (ko[..., 3] > 8))
    text_zone = cv2.dilate(diff.astype(np.uint8) * 255, np.ones((15, 15), np.uint8))
    Image.fromarray(text_zone).save(os.path.join(OUT, '기준그림', '글자자리_로고좌표.png'))
    # 프레임별 변환: 완성 구간 정합값을 2차식으로 이어 조립 구간까지(usm_logo.register 와 같은 방식)
    fit = usm_logo.register([a.astype(np.float32) / 255 for a in alp], ja[..., 3].astype(np.float32) / 255)
    ks = [k for k in range(n) if fit[k]]
    P = {i: np.polyfit(ks, [fit[k][1][r, c] for k in ks], 2) for i, (r, c) in enumerate([(0, 0), (0, 2), (1, 2)])}
    info = []
    for k in WORK:
        s, tx, ty = (np.polyval(P[i], k) for i in range(3))
        w = np.array([[s, 0, tx], [0, s, ty]], np.float32)
        m = cv2.warpAffine(text_zone, w, (W, H), flags=cv2.INTER_NEAREST)
        Image.fromarray(m).save(os.path.join(OUT, '글자자리_마스크', 'f%04d.png' % k))
        Image.fromarray(rgba_from(col[k], alp[k]), 'RGBA').save(os.path.join(OUT, '원본_프레임', 'f%04d.png' % k))
        vis = float((alp[k][m > 0] > 30).mean()) if (m > 0).any() else 0
        info.append(dict(frame=k, time=round(k / FPS, 3), scale=round(float(s), 4), tx=round(float(tx), 1), ty=round(float(ty), 1),
                         text_zone_visible=round(vis, 3)))
    for k in CONT:
        Image.fromarray(rgba_from(kcol[k], kalp[k]), 'RGBA').save(os.path.join(OUT, '참고_한글로고_이어지는_프레임', 'f%04d.png' % k))
    json.dump(info, open(os.path.join(OUT, '프레임정보.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # 원본·현재 영상(타이틀 배경 위 합성) MP4
    bg = gtx2.decode(extract.open_pack('pack_030_etc').read('Interface/title/title_background.gtx'))[0][..., :3].astype(np.float32)
    F = ImageFont.truetype(r'C:\Windows\Fonts\malgunbd.ttf', 22)
    for name, cc, aa in (('원본_영상.mp4', col, alp), ('현재_한글판_영상.mp4', kcol, kalp)):
        p = subprocess.Popen([usm_logo.FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS),
                              '-i', '-', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', os.path.join(OUT, name)], stdin=subprocess.PIPE)
        for k in range(n):
            a = aa[k].astype(np.float32)[..., None] / 255
            im = Image.fromarray((bg * (1 - a) + cc[k].astype(np.float32) * a).clip(0, 255).astype(np.uint8))
            ImageDraw.Draw(im).text((10, 8), 'f%04d  %.2f초' % (k, k / FPS), font=F, fill=(255, 255, 0))
            p.stdin.write(np.asarray(im).tobytes())
        p.stdin.close(); p.wait()
    Image.fromarray(bg.astype(np.uint8)).save(os.path.join(OUT, '기준그림', '타이틀_배경.png'))
    print('작업 프레임 %d장(f%04d~f%04d) · 이어지는 한글 프레임 %d장 · %s' % (len(WORK), WORK[0], WORK[-1], len(CONT), OUT))
    print('글자 보이는 프레임:', [i['frame'] for i in info if i['text_zone_visible'] > 0.02][:3], '…')


if __name__ == '__main__':
    main()
