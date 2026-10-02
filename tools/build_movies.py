# -*- coding: utf-8 -*-
"""한글 자막을 구운 영상(work/movie_ko/*.usm)으로 영상 CPK 두 개를 다시 만든다.

  python build_movies.py
출력: work/sdcafiine/0005000010131D00/TMS_KR/content/Pack/pack_050_movie.cpk
                                                        pack_060_movie_credit.cpk
검증: 교체한 영상은 다시 읽어 바이트 일치, 나머지 영상은 원본과 일치, 파일 크기 < 4GiB(FAT32).
"""
import os
import extract, cpk as cpklib, cpk_pack

HERE = os.path.dirname(os.path.abspath(__file__))
KO = os.path.join(HERE, '..', 'work', 'movie_ko')
OUT = os.path.join(HERE, '..', 'work', 'sdcafiine', '0005000010131D00', 'TMS_KR', 'content', 'Pack')
FAT32_MAX = 4294967295


def build(pack):
    src = extract.pack_path(pack)
    orig = cpklib.CPK(src)
    names = {os.path.basename(f['name'])[:-4]: f['name'] for f in orig.files if f['name'].endswith('.usm')}
    replace = {}
    for fn in sorted(os.listdir(KO)):
        if fn.endswith('.usm') and fn[:-4] in names:
            replace[names[fn[:-4]]] = open(os.path.join(KO, fn), 'rb').read()
    dst = os.path.join(OUT, pack + '.cpk')
    cpk_pack.repack(src, dst, replace)
    new = cpklib.CPK(dst)
    same_rep = all(new.read(n) == b for n, b in replace.items())
    same_rest = all(new.read(f['name']) == orig.read(f['name']) for f in orig.files if f['name'] not in replace)
    size = os.path.getsize(dst)
    print('%-22s 교체 %2d개 · 교체분 일치 %s · 나머지 원본과 일치 %s · 크기 %d (원본 %d) · FAT32 %s'
          % (pack, len(replace), same_rep, same_rest, size, os.path.getsize(src), '가능' if size <= FAT32_MAX else '★초과'))
    return dst


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for p in ('pack_050_movie', 'pack_060_movie_credit'):
        build(p)
