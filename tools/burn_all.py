# -*- coding: utf-8 -*-
"""자막 21개 영상 일괄 굽기 + 시청용 MP4.

  python burn_all.py [영상이름...]
출력: work/movie_ko/<영상>.usm            (게임용)
      work/movie_ko/preview/<영상>.mp4    (게임용 USM 에서 뽑은 영상 + 원본 음성, 확인용)
"""
import os, sys, subprocess, time
import extract, usm_frames, usm_burn

SUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'movie_sub')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'movie_ko')
PREV = os.path.join(OUT, 'preview')
CREDIT = {'m6189_01'}


def preview(usm_path, stem):
    b = open(usm_path, 'rb').read()
    v = os.path.join(PREV, '_%s.m1v' % stem); open(v, 'wb').write(usm_frames.video_es(b))
    aud = usm_frames.audio_es(b)
    cmd = [usm_frames.FFMPEG, '-y', '-r', '30', '-i', os.path.basename(v)]
    a = None
    if aud:
        a = os.path.join(PREV, '_%s.adx' % stem); open(a, 'wb').write(aud)
        cmd += ['-i', os.path.basename(a), '-c:a', 'aac', '-b:a', '160k', '-shortest']
    cmd += ['-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', stem + '.mp4']
    r = subprocess.run(cmd, cwd=PREV, capture_output=True)
    os.remove(v)
    if a:
        os.remove(a)
    return r.returncode == 0


def main(want):
    os.makedirs(PREV, exist_ok=True)
    stems = sorted(f[:-len('.ko.srt')] for f in os.listdir(SUB) if f.endswith('.ko.srt'))
    tot_old = tot_new = 0
    for stem in stems:
        if want and stem not in want:
            continue
        t = time.time()
        pack = 'pack_060_movie_credit' if stem in CREDIT else 'pack_050_movie'
        c = extract.open_pack(pack)
        name = [f['name'] for f in c.files if os.path.basename(f['name']) == stem + '.usm'][0]
        old = len(c.read(name))
        dst = os.path.join(OUT, stem + '.usm')
        # 가장 큰 프레임이 원본보다 커지면 게임 버퍼가 모자랄 수 있다 → 화질 값을 한 단계씩 올려 다시 굽는다
        for q in (2, 3, 4, 5):
            info = usm_burn.main(stem, os.path.join(SUB, stem + '.ko.srt'), dst, pack, q)
            if info['max_chunk'] <= info['old_max_chunk']:
                break
            print('  %s: 최대 청크 %d > 원본 %d → q=%d 로 다시' % (stem, info['max_chunk'], info['old_max_chunk'], q + 1), flush=True)
        ok = preview(dst, stem)
        tot_old += old; tot_new += info['filesize']
        print('%-12s 원본 %6.1fMB → %6.1fMB  (%+.1fMB)  미리보기 %s  %.0f초'
              % (stem, old / 1e6, info['filesize'] / 1e6, (info['filesize'] - old) / 1e6, 'OK' if ok else '실패', time.time() - t),
              flush=True)
    print('합계 원본 %.1fMB → %.1fMB (%+.1fMB)' % (tot_old / 1e6, tot_new / 1e6, (tot_new - tot_old) / 1e6))


if __name__ == '__main__':
    main(set(sys.argv[1:]))
