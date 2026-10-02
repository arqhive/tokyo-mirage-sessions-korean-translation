# -*- coding: utf-8 -*-
"""한글판 빌드 — 대사·폰트·2D 그래픽(+ 선택: 동영상)을 CPK 로 다시 만든다.

  python -X utf8 tools/build.py              대사·폰트·2D·이펙트
  python -X utf8 tools/build.py --movies     + 동영상 CPK 두 개(work/movie_ko/*.usm, 자막 구운 영상)
  python -X utf8 tools/build.py --packs pack_030_etc,pack_031_message   지정한 팩만
이펙트: pack_020_effect 는 manifest done 의 이펙트 항목(translation/graphics/eft/*.png, GPT 확정본)을 tools/eft_inject.py 로 넣는다.
출력: work/sdcafiine/0005000010131D00/TMS_KR/content/Pack/<팩>.cpk

그래픽 목록 = translation/graphics/manifest.json 의 done
  file      translation/graphics/2D/<경로> GTX 그대로(크기·모양 원본과 같은지 검사)
  tex_patch tex_patch.build() 가 translation/tex_ko.json 으로 만든 GTX
  copy      copy_from 과 원본 그림이 같은지 확인하고 그 결과를 그대로 복사
  original  원본 그대로(넣지 않음)
압축: 원본에서 CRILAYLA 로 압축돼 있던 파일은 교체본도 압축해서 넣는다(tools/crilayla.py, work/layla_cache 에 캐시).
      무압축으로 넣었더니 pack_030_etc 가 1.23GB 가 되고 실기에서 스플래시 뒤 멈췄다(2026-09-27, Cemu 는 정상).
3D 모델 텍스처는 넣지 않는다 — 원본처럼 압축해도 실기에서 부팅이 멈춰 2026-09-28 포기(도구·목록은 git 이력에만).
검증: 교체분을 다시 읽어 일치(압축본은 저장 바이트 그대로 비교, 압축은 만들 때 되풀어 확인) · 나머지 파일 원본과 같음(작은 팩만) · FAT32 4GiB 이하.
"""
import os, json, sys, time, hashlib
from concurrent.futures import ProcessPoolExecutor
import extract, text_io, mtext, font_build, tex_patch, cpk_pack, gtx2
import cpk as cpklib
import crilayla

ROOT = extract.ROOT
OUT = os.path.join(ROOT, 'work', 'sdcafiine', '0005000010131D00', 'TMS_KR', 'content', 'Pack')
GRAPHICS = os.path.join(ROOT, 'translation', 'graphics')
FAT32_MAX = 4294967295
CACHE = os.path.join(ROOT, 'work', 'layla_cache')


def load_manifest():
    """pack_030_etc 의 완료 2D (이펙트 팩 항목은 eft_inject 가 따로 만든다)"""
    done = json.load(open(os.path.join(GRAPHICS, 'manifest.json'), encoding='utf-8'))['done']
    return [e for e in done if e.get('pack', 'pack_030_etc') == 'pack_030_etc']


def collect_2d(done, log):
    c = extract.open_pack('pack_030_etc')
    src = {}
    tp = None
    for e in done:
        if e['kind'] != '2D':
            continue
        if e['method'] == 'file':
            src[e['path']] = open(os.path.join(GRAPHICS, e['file']), 'rb').read()
        elif e['method'] == 'tex_patch':
            tp = tp or tex_patch.build(lambda *a: None)
            src[e['path']] = tp[e['path']]
    copies = 0
    for e in done:
        if e['method'] == 'copy':
            assert c.read(e['path']) == c.read(e['copy_from']), ('원본 그림이 다름', e['path'])
            src[e['path']] = src[e['copy_from']]; copies += 1
    for n, b in src.items():
        o = c.read(n)
        assert len(o) == len(b), (n, len(o), len(b))
        assert gtx2.decode(o)[0].shape == gtx2.decode(b)[0].shape, n
    want = {e['path'] for e in done if e['kind'] == '2D' and e['method'] != 'original'}
    miss = sorted(want - set(src))
    log('  2D %d장(복사 %d 포함)%s' % (len(src), copies, ' · 빠짐 %s' % miss if miss else ''))
    return src


def compress_like_original(pack, rep, log):
    """원본에서 압축돼 있던 교체 파일 → (CRILAYLA 압축본, 풀린 크기). 캐시(sha1)로 한 번만 압축."""
    c = cpklib.CPK(extract.pack_path(pack))
    was = {e['name']: e['size'] < e['esize'] for e in c.files}
    c.close()
    os.makedirs(CACHE, exist_ok=True)
    todo = {n: b for n, b in rep.items() if was.get(n)}
    key = {n: hashlib.sha1(b).hexdigest() for n, b in todo.items()}
    miss = sorted({key[n]: n for n in todo if not os.path.exists(os.path.join(CACHE, key[n]))}.values())
    if miss:
        with ProcessPoolExecutor(max_workers=min(16, os.cpu_count() or 4)) as ex:
            for n, z in zip(miss, ex.map(crilayla.compress_verified, [todo[n] for n in miss], chunksize=1)):
                open(os.path.join(CACHE, key[n]), 'wb').write(z)
    out = dict(rep); a = b = 0
    for n, data in todo.items():
        z = open(os.path.join(CACHE, key[n]), 'rb').read()
        if z:
            out[n] = (z, len(data)); a += len(data); b += len(z)
    log('  %s: 압축 %d개(새로 %d) %.1fMB → %.1fMB · 무압축 %d개' % (pack, sum(isinstance(v, tuple) for v in out.values()),
        len(miss), a / 1e6, b / 1e6, sum(not isinstance(v, tuple) for v in out.values())))
    return out


def verify(dst, src_pack, replaced, log):
    new = cpklib.CPK(dst); old = cpklib.CPK(extract.pack_path(src_pack))
    rep_ok = all((new.read(n, raw=True) == b[0]) if isinstance(b, tuple) else (new.read(n) == b) for n, b in replaced.items())
    size = os.path.getsize(dst)
    if len(old.files) < 3000:
        rest_ok = all(new.read(e['name'], raw=True) == old.read(e, raw=True) for e in old.files if e['name'] not in replaced)
    else:
        rest_ok = '생략(파일 많음)'
    log('  %-24s 교체 %4d · 교체분 일치 %s · 나머지 원본과 같음 %s · %d바이트 %s'
        % (os.path.basename(dst), len(replaced), rep_ok, rest_ok, size, '' if size <= FAT32_MAX else '★FAT32 초과'))
    return rep_ok and rest_ok is not False and size <= FAT32_MAX


def main(movies=False, only=None):
    log = lambda *a: print(*a, flush=True)
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    done = load_manifest()
    log('2D 그래픽 완료 %d장' % len(done))
    want = lambda pk: only is None or pk in only
    msg = fonts = tex = eft = None
    if want('pack_031_message') or want('pack_999_font'):
        log('[1/5] 대사(MSBT)')
        msg = text_io.build_texts(); log('  교체 %d 파일' % len(msg))
    if want('pack_999_font'):
        log('[2/5] 폰트')
        texts = [mtext.plain(en.get('ko') or en['ja']) for p in text_io.iter_json() for en in text_io.load_json(p)['entries']]
        fonts = font_build.build_all(font_build.needed_chars(texts), lambda *a: None); log('  폰트 %d 파일' % len(fonts))
    if want('pack_030_etc'):
        log('[3/5] 2D 그래픽')
        tex = collect_2d(done, log)
    if want('pack_020_effect'):
        log('[+] 이펙트 그림')
        import eft_inject
        eft = eft_inject.build(log)
    log('[4/4] CPK 재작성')
    ok = True
    jobs = [('pack_031_message', msg), ('pack_999_font', fonts), ('pack_030_etc', tex), ('pack_020_effect', eft)]
    jobs = [(pk, rep) for pk, rep in jobs if rep is not None and want(pk)]
    for pack, rep in jobs:
        t = time.time()
        dst = os.path.join(OUT, pack + '.cpk')
        rep = compress_like_original(pack, rep, log)
        cpk_pack.repack(extract.pack_path(pack), dst, rep, lambda *a: None)
        ok &= verify(dst, pack, rep, log)
        log('    (%.0f초)' % (time.time() - t))
    if movies:
        log('[+] 동영상 CPK')
        import build_movies
        for p in ('pack_050_movie', 'pack_060_movie_credit'):
            build_movies.build(p)
    log('완료 %.0f분%s' % ((time.time() - t0) / 60, '' if ok else ' ★검증 실패 있음'))


if __name__ == '__main__':
    only = None
    if '--packs' in sys.argv:
        only = set(sys.argv[sys.argv.index('--packs') + 1].split(','))
    main(movies='--movies' in sys.argv, only=only)
