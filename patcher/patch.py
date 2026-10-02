# -*- coding: utf-8 -*-
"""환영이문록♯FE 한글 패치 적용기 — 일본판 content/Pack 폴더의 CPK 로 한글판 CPK 를 만든다.

  패치하기.bat 에 게임 폴더(또는 content/Pack 폴더)를 끌어다 놓거나, 실행한 뒤 경로를 입력한다.
  python patch.py <게임 폴더 또는 content/Pack 폴더>

결과(원본 파일은 바뀌지 않는다):
  출력/sdcafiine/0005000010131D00/KoreanTranslation/content/Pack/*.cpk   Wii U 실기(SDCafiine)용
  출력/cemu/TMS_Korean/                                                  Cemu 그래픽팩용(같은 파일을 하드 링크로)
자막 영상 패치(TMS_KO_*_Movies.zip)를 이 폴더에 풀어 두면 동영상 자막도 함께 넣는다.
"""
import os, sys, json, time, hashlib, shutil, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'lib'))
import cpk_pack

PAYLOAD = os.path.join(HERE, 'payload')
MOVIES = os.path.join(HERE, 'payload_movies')
OUT = os.path.join(TOP, '출력')
TID = '0005000010131D00'


def sha1_file(path, label=''):
    h = hashlib.sha1(); n = os.path.getsize(path); done = 0; t = time.time()
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 24)
            if not b:
                break
            h.update(b); done += len(b)
            if n > 1 << 29 and time.time() - t > 2:
                print('\r  %s 확인 중 %d%%' % (label, done * 100 // n), end='', flush=True); t = time.time()
    if n > 1 << 29:
        print('\r' + ' ' * 50 + '\r', end='', flush=True)     # 진행률 줄을 지우고 결과 줄만 남긴다
    return h.hexdigest()


def find_pack(arg):
    """게임 폴더·content 폴더·Pack 폴더 어느 것을 줘도 pack_031_message.cpk 가 있는 폴더를 찾는다."""
    arg = arg.strip().strip('"')
    for cand in (arg, os.path.join(arg, 'Pack'), os.path.join(arg, 'content', 'Pack')):
        if os.path.isfile(os.path.join(cand, 'pack_031_message.cpk')):
            return cand
    return None


def load_part(root, pack):
    """payload 폴더의 <팩>.json(파일 목록) + <팩>.bin(이어 붙인 데이터) → repack 용 {이름: (데이터, 풀린 크기)}"""
    idx = json.load(open(os.path.join(root, pack + '.json'), encoding='utf-8'))
    rep = {}
    with open(os.path.join(root, pack + '.bin'), 'rb') as f:
        for name, (off, size, esize) in idx.items():
            f.seek(off); rep[name] = (f.read(size), esize)
    return rep


def link_or_copy(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def main():
    man = json.load(open(os.path.join(PAYLOAD, 'manifest.json'), encoding='utf-8'))
    movies = os.path.isfile(os.path.join(MOVIES, 'manifest.json'))
    print('환영이문록♯FE 한글 패치 %s\n' % man['version'])
    if movies:
        mv = json.load(open(os.path.join(MOVIES, 'manifest.json'), encoding='utf-8'))
        miss = [p for p in mv['parts'] if not os.path.isfile(os.path.join(MOVIES, p + '.bin'))]
        if mv['version'] != man['version']:
            print('[오류] 자막 영상 패치 버전(%s)이 패처 버전(%s)과 다릅니다.' % (mv['version'], man['version'])); return 1
        if miss:
            print('[오류] 자막 영상 패치 일부가 없습니다: %s\n       Movies 압축 파일을 이 폴더에 다시 풀어 주세요.' % ', '.join(miss)); return 1
        print('자막 영상 패치: 있음 — 동영상 자막도 넣습니다.')
    else:
        print('자막 영상 패치: 없음 — 대사·폰트·그림·타이틀 로고 영상만 넣습니다.')
    arg = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else None
    if not arg:
        print('\n일본판 「환영이문록♯FE」 게임 폴더(또는 content\\Pack 폴더) 경로를 입력하세요. 폴더를 이 창에 끌어다 놓아도 됩니다.')
        arg = input('> ')
    src = find_pack(arg)
    if not src:
        print('[오류] pack_031_message.cpk 가 있는 폴더를 찾지 못했습니다: %s' % arg); return 1
    print('원본 폴더: %s\n' % src)
    plan = dict(man['packs'])
    if movies:
        plan.update(mv['packs'])
    # 1) 원본 확인
    print('[1/3] 원본 확인')
    for pack in sorted(plan):
        p = os.path.join(src, pack + '.cpk')
        if not os.path.isfile(p):
            print('[오류] 원본에 %s.cpk 가 없습니다.' % pack); return 1
        if os.path.getsize(p) != plan[pack]['src_size'] or sha1_file(p, pack) != plan[pack]['src_sha1']:
            print('[오류] %s.cpk 가 일본판 원본과 다릅니다(이미 패치했거나 다른 판).' % pack); return 1
        print('  %-24s 일치' % pack)
    # 2) 만들기
    print('\n[2/3] 한글판 만들기')
    sd = os.path.join(OUT, 'sdcafiine', TID, 'KoreanTranslation', 'content', 'Pack')
    os.makedirs(sd, exist_ok=True)
    for pack in sorted(plan):
        t = time.time()
        rep = {}
        for part in plan[pack]['parts']:
            root = MOVIES if part.startswith('movies') else PAYLOAD
            rep.update(load_part(root, part))
        dst = os.path.join(sd, pack + '.cpk')
        cpk_pack.repack(os.path.join(src, pack + '.cpk'), dst, rep, log=lambda *a: None)
        want = plan[pack]['out_sha1']
        if sha1_file(dst, pack) != want:
            print('[오류] %s.cpk 결과가 기준과 다릅니다. 패치 파일이 손상됐을 수 있습니다.' % pack); return 1
        print('  %-24s 교체 %4d개 · %.0f초 · 결과 확인 일치' % (pack, len(rep), time.time() - t))
    # 3) Cemu 그래픽팩
    print('\n[3/3] Cemu 그래픽팩')
    gp = os.path.join(OUT, 'cemu', 'TMS_Korean')
    os.makedirs(os.path.join(gp, 'content', 'Pack'), exist_ok=True)
    shutil.copyfile(os.path.join(HERE, 'rules.txt'), os.path.join(gp, 'rules.txt'))
    for pack in sorted(plan):
        link_or_copy(os.path.join(sd, pack + '.cpk'), os.path.join(gp, 'content', 'Pack', pack + '.cpk'))
    print('  %s' % gp)
    print('\n완료.\n  Wii U(SDCafiine): 출력\\sdcafiine 폴더 안의 내용을 SD 카드 wiiu\\sdcafiine\\ 에 복사합니다.'
          '\n  Cemu: 출력\\cemu\\TMS_Korean 폴더를 Cemu 의 graphicPacks 폴더에 넣고 그래픽팩에서 켭니다.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\n중단했습니다.'); sys.exit(1)
    except Exception:
        traceback.print_exc(); print('[오류] 예상하지 못한 문제가 생겼습니다.'); sys.exit(1)
