# -*- coding: utf-8 -*-
"""USM(Sofdec2) 에서 영상 스트림을 뽑아 ffmpeg 로 프레임을 저장한다(영상 속 일본어 조사용).

  python usm_frames.py <팩이름> [초간격]
"""
import os, sys, struct, subprocess
import extract

# 예전엔 세션 임시 폴더의 ffmpeg.exe 를 가리켰는데 그 폴더가 지워졌다 → 파이썬 패키지 imageio-ffmpeg 에 든 ffmpeg 를 쓴다
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
OUT = os.path.join(extract.WORK, 'movie')


def stream_es(b, want=b'@SFV'):
    """USM 청크에서 한 스트림(@SFV 영상 / @SFA 음성 ADX)의 데이터 페이로드만 이어 붙인다."""
    out = bytearray(); pos = 0
    while pos + 32 <= len(b):
        sig = b[pos:pos + 4]
        size = struct.unpack('>I', b[pos + 4:pos + 8])[0]
        hs = b[pos + 9]; fs = struct.unpack('>H', b[pos + 10:pos + 12])[0]; typ = b[pos + 15]
        if sig == want and typ == 0:
            out += b[pos + 8 + hs:pos + 8 + size - fs]
        pos += 8 + size
        if size == 0:
            break
    return bytes(out)


def video_es(b):
    return stream_es(b, b'@SFV')


def audio_es(b):
    return stream_es(b, b'@SFA')


def main(pack, step='5'):
    c = extract.open_pack(pack)
    for e in c.files:
        n = e['name']
        if not n.endswith('.usm'):
            continue
        stem = os.path.basename(n)[:-4]
        d = os.path.join(OUT, stem)
        if os.path.isdir(d) and os.listdir(d):
            print('건너뜀', stem); continue
        os.makedirs(d, exist_ok=True)
        es = os.path.join(d, '_video.bin')
        open(es, 'wb').write(video_es(c.read(n)))
        r = subprocess.run([FFMPEG, '-y', '-i', es, '-vf', 'fps=1/%s,scale=640:-1' % step,
                            os.path.join(d, 'f%04d.png')], capture_output=True)
        os.remove(es)
        print(stem, len(os.listdir(d)), '프레임', r.returncode)


if __name__ == '__main__':
    main(*sys.argv[1:])
