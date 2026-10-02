# -*- coding: utf-8 -*-
"""배포용 패처 꾸리기 — 빌드된 CPK 와 원본을 파일 단위로 비교해 바뀐 파일만 담는다(2026-10-01).

  python -X utf8 tools/build.py --movies          # 먼저 전체 빌드(대사·폰트·2D·이펙트·영상)
  python -X utf8 tools/make_patcher.py v0.1 [--python <내장 파이썬 폴더>]

출력: work/release/TMS_KO_<버전>/                      패처 폴더(패치하기.bat · python · patcher · licenses · README_KO.txt)
      work/release/TMS_KO_<버전>_Patcher.zip           필수: 대사·폰트·2D·이펙트·타이틀 로고 영상
      work/release/TMS_KO_<버전>_Movies.zip             선택: 동영상 자막(약 3.4GB, 구글 드라이브 배포, 같은 패처 폴더에 풀면 됨)
패치 데이터(payload) = 바뀐 파일의 CPK 저장 형태 그대로(압축본은 압축된 채) + 풀린 크기. 원본 게임 데이터는 담지 않는다.
패처는 원본 CPK 해시를 확인하고 cpk_pack.repack 으로 다시 만든 뒤 결과 해시를 빌드본과 대조한다.
pack_050_movie 는 두 가지 결과가 있다: 타이틀 로고 영상만 바꾼 것(필수) / 자막 영상까지 바꾼 것(Movies 가 있을 때).
"""
import os, sys, json, shutil, hashlib, zipfile
import extract, cpk as cpklib, cpk_pack

ROOT = extract.ROOT
BUILT = os.path.join(ROOT, 'work', 'sdcafiine', '0005000010131D00', 'TMS_KR', 'content', 'Pack')
REL = os.path.join(ROOT, 'work', 'release')
PY_DEFAULT = os.path.join(ROOT, 'work', 'python_embed')
CORE = ['pack_031_message', 'pack_999_font', 'pack_030_etc', 'pack_020_effect']
TITLE = 'Movie/m00.usm'
PART_MAX = 1_900_000_000                     # GitHub 릴리즈 첨부 한 파일 2GB 미만


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''):
            h.update(b)
    return h.hexdigest()


def diff_pack(pack):
    """원본·빌드본 CPK 를 파일마다 저장 바이트로 비교 → {이름: (저장 바이트, 풀린 크기)}"""
    o, n = cpklib.CPK(extract.pack_path(pack)), cpklib.CPK(os.path.join(BUILT, pack + '.cpk'))
    on = {e['name']: e for e in o.files}
    out = {}
    for e in n.files:
        a = o.read(on[e['name']], raw=True); b = n.read(e, raw=True)
        if a != b or on[e['name']]['esize'] != e['esize']:
            out[e['name']] = (b, e['esize'])
    o.close(); n.close()
    return out


def write_part(root, part, rep):
    idx, off = {}, 0
    with open(os.path.join(root, part + '.bin'), 'wb') as f:
        for name in sorted(rep):
            data, esize = rep[name]
            f.write(data); idx[name] = [off, len(data), esize]; off += len(data)
    json.dump(idx, open(os.path.join(root, part + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    return off


def src_info(pack):
    p = extract.pack_path(pack)
    return dict(src_size=os.path.getsize(p), src_sha1=sha1_file(p))


def zip_dir(zpath, base, members):
    """members: base 기준 상대 경로 목록(폴더면 안을 전부). .bin 은 이미 압축돼 있거나 영상이라 저장만."""
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for m in members:
            full = os.path.join(base, m)
            files = [full] if os.path.isfile(full) else [os.path.join(r, f) for r, _, fs in os.walk(full) for f in fs]
            for fp in sorted(files):
                arc = os.path.relpath(fp, os.path.dirname(base)).replace(os.sep, '/')
                z.write(fp, arc, compress_type=zipfile.ZIP_STORED if fp.endswith(('.bin', '.usm')) else zipfile.ZIP_DEFLATED)
    return os.path.getsize(zpath)


def main():
    ver = sys.argv[1]
    py = sys.argv[sys.argv.index('--python') + 1] if '--python' in sys.argv else PY_DEFAULT
    assert os.path.isfile(os.path.join(py, 'python.exe')), '내장 파이썬이 없음: %s' % py
    name = 'TMS_KO_%s' % ver
    top = os.path.join(REL, name)
    if os.path.exists(top):
        shutil.rmtree(top)
    pdir = os.path.join(top, 'patcher')
    pay, mov = os.path.join(pdir, 'payload'), os.path.join(pdir, 'payload_movies')
    os.makedirs(pay); os.makedirs(mov)
    man = dict(version=ver, packs={})
    # 필수 팩
    for pack in CORE:
        rep = diff_pack(pack)
        size = write_part(pay, pack, rep)
        man['packs'][pack] = dict(src_info(pack), parts=[pack], out_sha1=sha1_file(os.path.join(BUILT, pack + '.cpk')))
        print('%-22s 바뀐 파일 %4d · 패치 데이터 %.1fMB' % (pack, len(rep), size / 1e6))
    # 영상 팩: 타이틀 로고(필수) / 자막 영상(선택)
    m50 = diff_pack('pack_050_movie'); m60 = diff_pack('pack_060_movie_credit')
    title = {TITLE: m50.pop(TITLE)}
    write_part(pay, 'core_050', title)
    tmp = os.path.join(REL, '_core_050.cpk')
    cpk_pack.repack(extract.pack_path('pack_050_movie'), tmp, title, log=lambda *a: None)
    s50 = src_info('pack_050_movie')
    man['packs']['pack_050_movie'] = dict(s50, parts=['core_050'], out_sha1=sha1_file(tmp), out_size=os.path.getsize(tmp))
    os.remove(tmp)
    print('pack_050_movie(타이틀) 바뀐 파일 1 · %.1fMB' % (len(title[TITLE][0]) / 1e6))
    json.dump(man, open(os.path.join(pay, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # 자막 영상: 크기로 나눠 2GB 미만 조각
    items = sorted(m50.items(), key=lambda kv: kv[0])
    parts, cur, cur_size = [], {}, 0
    for k, v in items:
        if cur and cur_size + len(v[0]) > PART_MAX * 0.85:
            parts.append(cur); cur, cur_size = {}, 0
        cur[k] = v; cur_size += len(v[0])
    if cur:
        parts.append(cur)
    mv = dict(version=ver, packs={}, parts=[])
    names50 = []
    for i, p in enumerate(parts, 1):
        nm = 'movies_050_%d' % i; write_part(mov, nm, p); names50.append(nm)
    write_part(mov, 'movies_060', m60)
    mv['parts'] = names50 + ['movies_060']
    mv['packs']['pack_050_movie'] = dict(s50, parts=['core_050'] + names50, out_sha1=sha1_file(os.path.join(BUILT, 'pack_050_movie.cpk')))
    mv['packs']['pack_060_movie_credit'] = dict(src_info('pack_060_movie_credit'), parts=['movies_060'],
                                                out_sha1=sha1_file(os.path.join(BUILT, 'pack_060_movie_credit.cpk')))
    json.dump(mv, open(os.path.join(mov, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('자막 영상: pack_050 %d개(%d조각) · pack_060 %d개' % (len(m50), len(parts), len(m60)))
    # 패처 본체·내장 파이썬·라이선스·안내
    lib = os.path.join(pdir, 'lib'); os.makedirs(lib)
    for f in ('cpk.py', 'cpk_pack.py'):
        shutil.copyfile(os.path.join(ROOT, 'tools', f), os.path.join(lib, f))
    for f in ('patch.py', 'rules.txt'):
        shutil.copyfile(os.path.join(ROOT, 'patcher', f), os.path.join(pdir, f))
    shutil.copyfile(os.path.join(ROOT, 'patcher', '패치하기.bat'), os.path.join(top, '패치하기.bat'))
    shutil.copytree(py, os.path.join(top, 'python'), ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(os.path.join(ROOT, 'licenses'), os.path.join(top, 'licenses'))
    shutil.copyfile(os.path.join(ROOT, 'patcher', 'README_KO.txt'), os.path.join(top, 'README_KO.txt'))
    # zip: 필수 1개 + 자막 영상 조각마다 1개(각자 payload_movies 일부 + manifest)
    core_members = ['패치하기.bat', 'README_KO.txt', 'python', 'licenses', 'patcher/patch.py', 'patcher/rules.txt', 'patcher/lib', 'patcher/payload']
    zp = os.path.join(REL, name + '_Patcher.zip')
    print('%s %.1fMB' % (os.path.basename(zp), zip_dir(zp, top, core_members) / 1e6))
    # 자막 영상은 구글 드라이브로 배포(크기 제한 없음) → zip 하나(2026-10-01 사용자 결정)
    zp = os.path.join(REL, '%s_Movies.zip' % name)
    size = zip_dir(zp, top, ['patcher/payload_movies'])
    print('%s %.2fGB' % (os.path.basename(zp), size / 1e9))


if __name__ == '__main__':
    main()
