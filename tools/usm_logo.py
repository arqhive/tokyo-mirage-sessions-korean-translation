# -*- coding: utf-8 -*-
"""타이틀 로고 영상(Movie/m00.usm) 한글화 — 영상 속 일본어 로고를 한글 title_logo.gtx 로 바꿔 끼운다(2026-09-28).

  python -X utf8 tools/usm_logo.py      → work/movie_ko/m00.usm (영상 팩 빌드: build.py --movies 가 집어 감)
                                          work/movie_logo/비교.mp4 (원본 | 한글, 타이틀 배경 위 합성 — 확인용)
구조: CRID → @SFV(색) · @ALP(알파, alpha_type 1) 두 MPEG-1 영상(1280x720, 335프레임, 13프레임마다 I) + @CUE. 음성 없음.
      색 영상은 로고를 흰 바탕에 합친 색(투명한 곳 = 흰색, 밝기 16~235), 알파 영상은 밝기(Y)가 투명도이고 0~255 전체 범위.
      → 알파는 Y 평면을 변환 없이 읽고 굽는다(rgb 로 거치면 16~235 로 좁혀져 투명한 곳이 16 = 옅은 막이 낀다).
내용: 0~1.3초 반짝이 · 1.3~3.1초 로고 조립(글자 깜빡임) · 3.1초~ 완성 로고가 배율 0.91→1.00 으로 천천히 커짐.
      완성 구간의 로고는 Interface/title/title_logo.gtx(일본어 원본)를 옮겨 놓은 것뿐이다(ECC 아핀 정합 cc>0.995, 알파 차 1% 미만).
방법: 프레임마다 원본 로고 그림을 영상 알파에 맞춰(ECC) 변환을 구하고, 맞는 프레임(완성 구간)은 한글 title_logo 를
      같은 변환으로 그려 넣는다(색 = 흰 바탕 합성, 알파 = 한글 로고 알파). 조립 구간은 원본 그대로(사용자 선택).
      두 영상을 원본과 같은 프레임 수·I프레임 위치로 다시 굽고, 헤더 숫자(filesize·avbps·minbuf·ixsize·키프레임 위치)를 고친다.
"""
import os, sys, struct, subprocess, tempfile, json
import numpy as np, cv2
import extract, gtx2, usm_frames, usm_burn as ub
from cpk import read_utf

ROOT = extract.ROOT
FF = usm_frames.FFMPEG
W, H, FPS = 1280, 720, 30
OUT_USM = os.path.join(ROOT, 'work', 'movie_ko', 'm00.usm')
OUT_DIR = os.path.join(ROOT, 'work', 'movie_logo')
KO_LOGO = os.path.join(ROOT, 'translation', 'graphics', '2D', 'Interface', 'title', 'title_logo.gtx')
CC_OK = 0.995


def decode(es):
    """MPEG-1 ES → (프레임 수, H, W, 3) uint8"""
    r = subprocess.run([FF, '-loglevel', 'error', '-f', 'mpegvideo', '-i', '-', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                       input=es, capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, H, W, 3)


def decode_y(es):
    """알파 영상: 밝기(Y) 평면을 변환 없이 그대로 → (N,H,W). 원본 알파는 0~255 전체 범위를 쓴다(투명 = 0)."""
    r = subprocess.run([FF, '-loglevel', 'error', '-f', 'mpegvideo', '-i', '-', '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-'],
                       input=es, capture_output=True, check=True)
    fr = W * H * 3 // 2
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, fr)[:, :W * H].reshape(-1, H, W)


def encode(frames, keys, q=2, yplane=False):
    """(N,H,W,3) → MPEG-1 ES. 원본 I프레임 위치에 키프레임을 강제(usm_burn.encode 와 같은 설정)."""
    kf = ','.join('%.6f' % max(0.0, (k - 0.5) / FPS) for k in keys)
    if yplane:                                           # 알파: Y 평면 그대로(범위 변환 없음), 색차는 128
        n = len(frames)
        buf = np.concatenate([frames.reshape(n, -1), np.full((n, W * H // 2), 128, np.uint8)], axis=1)
        frames, pix = buf, 'yuv420p'
    else:
        pix = 'rgb24'
    cmd = [FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', pix, '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
           '-c:v', 'mpeg1video', '-r', str(FPS), '-g', '100000', '-bf', '2', '-b_strategy', '0', '-flags', '+cgop',
           '-sc_threshold', '1000000000', '-force_key_frames', kf, '-q:v', str(q), '-qmin', '1',
           '-maxrate', '30M', '-bufsize', '4864k', '-frames:v', str(len(frames)), '-f', 'mpeg1video', '-']
    r = subprocess.run(cmd, input=np.ascontiguousarray(frames).tobytes(), capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode('utf-8', 'ignore')[-800:])
    return r.stdout


def register(alphas, logo_a):
    """프레임마다 원본 로고 알파 → 영상 알파 아핀 변환(ECC). 뒤(완성)에서 앞으로 이어 가며 맞춘다."""
    a = alphas[-1]
    ys, xs = np.nonzero(a > 0.5); ly, lx = np.nonzero(logo_a > 0.5)
    s = np.sqrt(len(ys) / len(ly))
    w = np.array([[s, 0, xs.mean() - s * lx.mean()], [0, s, ys.mean() - s * ly.mean()]], np.float32)
    out = [None] * len(alphas)
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-6)
    for k in range(len(alphas) - 1, -1, -1):
        if alphas[k].max() < 0.2:
            break
        try:
            cc, w2 = cv2.findTransformECC(logo_a, alphas[k], w.copy(), cv2.MOTION_AFFINE, crit, None, 5)
        except cv2.error:
            break
        if cc < CC_OK:
            break
        out[k] = (float(cc), w2); w = w2
    return out


def rebuild(orig, new):
    """{b'@SFV': [그림…], b'@ALP': [그림…]} 로 데이터 청크를 바꾸고 헤더 숫자를 고친다(usm_burn.rebuild 의 두 영상판)."""
    cs = ub.chunks(orig)
    for sig, pics in new.items():
        v = [c for c in cs if c['sig'] == sig and c['typ'] == 0]
        assert len(v) == len(pics), (sig, len(v), len(pics))
        assert [i for i, c in enumerate(v) if ub.pict_type(c['payload']) == 'I'] == [i for i, p in enumerate(pics) if ub.pict_type(p) == 'I'], sig
    out = bytearray(); idx = {s: 0 for s in new}; keyofs = {s: [] for s in new}
    for c in cs:
        if c['sig'] in new and c['typ'] == 0:
            p = new[c['sig']][idx[c['sig']]]; idx[c['sig']] += 1
            if ub.pict_type(p) == 'I':
                keyofs[c['sig']].append(len(out))
            out += ub.make_chunk(c['sig'], c['hdr'], p)
        else:
            out += orig[c['pos']:c['pos'] + 8 + c['size']]
    nc = ub.chunks(bytes(out))
    crid = nc[0]
    _, rows = read_utf(crid['payload'])
    stmid = {struct.unpack('>I', s)[0]: s for s in new}              # CRID 행의 stmid = 청크 이름(@SFV·@ALP) 정수
    info = {}; patches = {(0, 'filesize'): len(out)}
    total_avbps = 0; grow = 0
    for r, row in enumerate(rows):
        s = stmid.get(row['stmid'])
        if not s:
            continue
        v = [c for c in nc if c['sig'] == s and c['typ'] == 0]
        ov = [c for c in cs if c['sig'] == s and c['typ'] == 0]
        pay = sum(len(c['payload']) for c in v); mx = max(8 + c['size'] for c in v)
        avbps = int(round(pay * 8 * FPS / len(v))); total_avbps += avbps
        grow += max(0, mx - max(8 + c['size'] for c in ov))
        patches.update({(r, 'filesize'): pay, (r, 'avbps'): avbps, (r, 'minbuf'): max(len(c['payload']) for c in v)})
        hdr = [c for c in nc if c['sig'] == s and c['typ'] == 1][0]
        p2 = ub.utf_patch(hdr['payload'], {(0, 'ixsize'): mx}); o = hdr['pos'] + 8 + hdr['hs']; out[o:o + len(p2)] = p2
        sk = [c for c in nc if c['sig'] == s and c['typ'] == 3][0]
        _, sr = read_utf(sk['payload'])
        assert len(sr) == len(keyofs[s]), (s, len(sr), len(keyofs[s]))
        p2 = ub.utf_patch(sk['payload'], {(i, 'ofs_byte'): keyofs[s][i] for i in range(len(sr))}); o = sk['pos'] + 8 + sk['hs']; out[o:o + len(p2)] = p2
        info[s.decode()] = dict(frames=len(v), payload=pay, max_chunk=mx, avbps=avbps, keyframes=len(keyofs[s]))
    patches[(0, 'avbps')] = total_avbps
    patches[(0, 'minbuf')] = rows[0]['minbuf'] + grow
    p2 = ub.utf_patch(crid['payload'], patches); o = crid['pos'] + 8 + crid['hs']; out[o:o + len(p2)] = p2
    return bytes(out), info


def main():
    os.makedirs(os.path.dirname(OUT_USM), exist_ok=True); os.makedirs(OUT_DIR, exist_ok=True)
    orig = extract.open_pack('pack_050_movie').read('Movie/m00.usm')
    col = decode(usm_frames.stream_es(orig, b'@SFV'))
    alp = decode_y(usm_frames.stream_es(orig, b'@ALP'))
    n = len(col); assert len(alp) == n
    ja = gtx2.decode(extract.open_pack('pack_030_etc').read('Interface/title/title_logo.gtx'))[0].astype(np.float32)
    ko = gtx2.decode(open(KO_LOGO, 'rb').read())[0].astype(np.float32)
    fit = register([a.astype(np.float32) / 255 for a in alp], ja[..., 3] / 255)
    ks = [k for k in range(n) if fit[k]]
    assert ks and ks[-1] == n - 1 and ks == list(range(ks[0], n)), '완성 구간이 끝까지 이어지지 않음'
    print('로고 교체 프레임 %d~%d (%d장, %.1f초부터) · 정합 cc 최저 %.4f' % (ks[0], n - 1, len(ks), ks[0] / FPS, min(fit[k][0] for k in ks)))
    kprem = ko[..., :3] * (ko[..., 3:] / 255)
    col2 = col.copy(); alp2 = alp.copy()
    for k in ks:
        w = fit[k][1]
        a = cv2.warpAffine(ko[..., 3] / 255, w, (W, H), flags=cv2.INTER_LINEAR)
        p = cv2.warpAffine(kprem, w, (W, H), flags=cv2.INTER_LINEAR)
        col2[k] = np.clip(np.round(p + 255 * (1 - a)[..., None]), 0, 255).astype(np.uint8)     # 흰 바탕 합성(원본과 같은 방식)
        alp2[k] = np.clip(np.round(a * 255), 0, 255).astype(np.uint8)
    cs = ub.chunks(orig)
    keys = {s: [i for i, c in enumerate([c for c in cs if c['sig'] == s and c['typ'] == 0]) if ub.pict_type(c['payload']) == 'I'] for s in (b'@SFV', b'@ALP')}
    es_c = encode(col2, keys[b'@SFV'])
    es_a = encode(alp2, keys[b'@ALP'], yplane=True)
    data, info = rebuild(orig, {b'@SFV': ub.split_pictures(es_c), b'@ALP': ub.split_pictures(es_a)})
    # 검증: 새 USM 을 다시 풀어 목표 프레임과 비교
    dc = decode(usm_frames.stream_es(data, b'@SFV')); da = decode_y(usm_frames.stream_es(data, b'@ALP'))
    assert len(dc) == n and len(da) == n
    ec = np.abs(dc.astype(int) - col2.astype(int)).mean(); ea = np.abs(da.astype(int) - alp2.astype(int)).mean()
    open(OUT_USM, 'wb').write(data)
    print('m00.usm %d바이트(원본 %d) · %s · 다시 푼 오차 색 %.2f 알파 %.2f' % (len(data), len(orig), info, ec, ea))
    print('알파 밝기 범위: 원본 %d~%d(투명 %d) · 새 %d~%d(투명 %d)' % (alp.min(), alp.max(), np.bincount(alp[-1].ravel()).argmax(),
          da.min(), da.max(), np.bincount(da[-1].ravel()).argmax()))
    # 확인용 비교 영상(타이틀 배경 위 합성)
    bg = gtx2.decode(extract.open_pack('pack_030_etc').read('Interface/title/title_background.gtx'))[0][..., :3].astype(np.float32)
    mp4 = os.path.join(OUT_DIR, '비교.mp4')
    pr = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '1280x360', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', mp4], stdin=subprocess.PIPE)
    for k in range(n):
        row = []
        for c_, a_ in ((col[k], alp[k]), (dc[k], da[k])):
            a = a_.astype(np.float32)[..., None] / 255
            row.append(cv2.resize((bg * (1 - a) + c_.astype(np.float32) * a).clip(0, 255).astype(np.uint8), (640, 360), interpolation=cv2.INTER_AREA))
        pr.stdin.write(np.hstack(row).tobytes())
    pr.stdin.close(); pr.wait()
    print('비교 영상', mp4)


if __name__ == '__main__':
    main()
