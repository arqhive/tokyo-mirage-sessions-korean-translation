# -*- coding: utf-8 -*-
"""USM -> MP4 (영상만, 음성은 별도 ADX 라 없음). 사용자가 직접 보고 자막 필요 여부를 판단하기 위한 변환.
  python usm_mp4.py <출력폴더> <영상이름...>
"""
import os, sys, subprocess
import extract, usm_frames

FF = usm_frames.FFMPEG
PACKS = ['pack_049_movie_camp', 'pack_050_movie', 'pack_060_movie_credit']


def main(out, *want):
    os.makedirs(out, exist_ok=True)
    want = set(want)
    for pk in PACKS:
        c = extract.open_pack(pk)
        for e in c.files:
            n = e['name']
            if not n.endswith('.usm'):
                continue
            stem = os.path.basename(n)[:-4]
            if want and stem not in want:
                continue
            dst = os.path.join(out, stem + '.mp4')
            if os.path.exists(dst):
                print('건너뜀', stem); continue
            b = c.read(n)
            tmp = os.path.join(out, '_%s.bin' % stem)
            open(tmp, 'wb').write(usm_frames.video_es(b))
            aud = usm_frames.audio_es(b)                     # 음성 = ADX (없는 영상도 있다)
            cmd = [FF, '-y', '-i', tmp]
            atmp = None
            if aud:
                atmp = os.path.join(out, '_%s.adx' % stem)
                open(atmp, 'wb').write(aud)
                cmd += ['-i', atmp]
            cmd += ['-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast', '-pix_fmt', 'yuv420p']
            if aud:
                cmd += ['-c:a', 'aac', '-b:a', '160k', '-shortest']
            cmd += [dst]
            r = subprocess.run(cmd, capture_output=True)
            os.remove(tmp)
            if atmp:
                os.remove(atmp)
            if r.returncode:
                print(r.stderr.decode('utf-8', 'ignore')[-400:])
            print(stem, r.returncode, round(os.path.getsize(dst) / 1e6, 1), 'MB' if os.path.exists(dst) else '실패')


if __name__ == '__main__':
    main(*sys.argv[1:])
