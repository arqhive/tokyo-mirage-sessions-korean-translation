"""한글 패치 빌드 — 번역 JSON + 폰트 -> CPK 2개 -> SDCafiine / Cemu.

  python build_patch.py                빌드만
  python build_patch.py --sample       translation/sample_ko.json 을 먼저 반영
  python build_patch.py --cemu         빌드 후 Cemu 실행 환경(정션+하드링크)까지 갱신
  python build_patch.py --sd D:        SD 카드로 복사

Cemu 함정 (지난 작업에서 다 밟았다):
  ① 덤프 폴더에 암호화 NUS(.app/title.tmd)와 복호화 code/content/meta 가 함께 있으면
     Cemu 가 keys.txt 없이 암호화본을 골라 "Unable to launch game" 을 낸다.
     → 복호화본만 보이는 폴더를 정션으로 따로 만든다 (cemu/TMS_JP).
  ② cpk_pack 은 새 파일을 만들어 갈아끼우므로 하드링크가 끊긴다 → 빌드 후 다시 건다.
  ③ Cemu 그래픽팩이 켜져 있으면 하드링크 파일을 덮어쓴다 → 설치된 팩도 같이 갱신한다.
"""
import os, sys, json, shutil, subprocess
import extract, text_io, mtext, cpk_pack, font_build, tex_patch

ROOT = extract.ROOT
TITLE_ID = '0005000010131D00'
OUT = os.path.join(ROOT, 'work', 'sdcafiine', TITLE_ID, 'TMS_KR', 'content', 'Pack')
GAME_DIR = os.path.join(ROOT, 'Tokyo Mirage Sessions FE [Game] [%s]' % TITLE_ID.lower())
CEMU_ROOT = os.path.normpath(os.path.join(ROOT, '..', 'Cemu_2.6'))
CEMU_DIR = os.path.join(CEMU_ROOT, 'games', 'TMS_JP')   # GamePaths 에 이미 등록된 폴더
GPACK = os.path.join(CEMU_ROOT, 'portable', 'graphicPacks', 'TMS_Korean')

RULES = """[Definition]
titleIds = %s
name = Korean Translation
path = "Tokyo Mirage Sessions FE/Mods/Korean Translation"
description = 환영이문록♯FE 일본판 한글화 (pack_031_message / pack_999_font 교체)
version = 7
""" % TITLE_ID
SAMPLE = os.path.join(ROOT, 'translation', 'sample_ko.json')


def apply_sample():
    with open(SAMPLE, encoding='utf-8') as f:
        table = json.load(f)
    n = 0
    for key, rows in table.items():
        if key.startswith('_'):
            continue
        p = os.path.join(text_io.TEXT, key.replace('/', os.sep) + '.json')
        if not os.path.exists(p):
            print('  ! 없는 파일:', key)
            continue
        j = text_io.load_json(p)
        for en in j['entries']:
            if en['label'] in rows:
                en['ko'] = rows[en['label']]
                n += 1
        text_io.save_json(p, j)
    print('샘플 번역 %d개 반영' % n)


def build(log=print, skip_tex=False):
    os.makedirs(OUT, exist_ok=True)

    log('[1/4] MSBT 재생성')
    replace = text_io.build_texts()
    log('  교체 대상 %d 파일' % len(replace))

    log('[2/4] 폰트 아틀라스 재구성')
    texts = []
    for p in text_io.iter_json():
        for en in text_io.load_json(p)['entries']:
            texts.append(mtext.plain(en.get('ko') or en['ja']))
    chars = font_build.needed_chars(texts)
    log('  필요 글자 %d자 (한글 %d)' % (len(chars), len(font_build.hangul_chars(''.join(chars)))))
    fonts = font_build.build_all(chars, log)

    log('[3/4] UI 텍스처')
    tex = {} if skip_tex else tex_patch.build(log)

    log('[4/4] CPK 재패킹')
    made = []
    made.append(cpk_pack.repack(extract.pack_path('pack_031_message'),
                                os.path.join(OUT, 'pack_031_message.cpk'), replace, log))
    made.append(cpk_pack.repack(extract.pack_path('pack_999_font'),
                                os.path.join(OUT, 'pack_999_font.cpk'), fonts, log))
    if tex:
        # 713MB 짜리라 재패킹에 시간이 걸린다. 교체분은 비압축으로 들어가 4MB 쯤 커진다.
        made.append(cpk_pack.repack(extract.pack_path('pack_030_etc'),
                                    os.path.join(OUT, 'pack_030_etc.cpk'), tex, log))
    return made


def verify(made, replaced=None, log=print):
    """빌드한 CPK 를 다시 읽어 교체분이 실제로 들어갔는지 확인.

    pack_030_etc 는 713MB / 4,181개라 전수 비교가 비싸다. 파일이 많으면 교체분만 본다.
    """
    import cpk as cpklib
    for path in made:
        c = cpklib.CPK(path)
        src = cpklib.CPK(extract.pack_path(os.path.basename(path)))
        names = {e['name'] for e in c.files}
        if len(c.files) > 2000:
            targets = [n for n in (replaced or ()) if n in names]
            ok = 0
            for n in targets:
                if c.read(c.by_name(n)) != src.read(src.by_name(n)):
                    ok += 1
            log('  %s: 파일 %d개, 교체 확인 %d/%d' % (os.path.basename(path), len(c.files), ok, len(targets)))
        else:
            same = diff = 0
            for e in c.files:
                if c.read(e) == src.read(src.by_name(e['name'])):
                    same += 1
                else:
                    diff += 1
            log('  %s: 원본과 동일 %d, 교체됨 %d' % (os.path.basename(path), same, diff))
        c.close(); src.close()


# ---------------------------------------------------------------- Cemu
def _link(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
        return 'hardlink'
    except OSError:
        shutil.copy2(src, dst)
        return 'copy'


def setup_cemu(made, log=print):
    """games/TMS_JP = 깨끗한 일본판 원본(정션+하드링크), 패치는 그래픽팩으로 얹는다.

    ① 덤프 폴더를 Cemu 에 직접 물리면 암호화 NUS 를 골라 "Unable to launch game" 이 난다.
    ③ 원본과 패치를 갈라 두면 그래픽팩 토글만으로 한글/일본어를 오갈 수 있다."""
    pack = os.path.join(CEMU_DIR, 'content', 'Pack')
    os.makedirs(pack, exist_ok=True)
    for sub in ('code', 'meta'):
        dst = os.path.join(CEMU_DIR, sub)
        if not os.path.exists(dst):
            subprocess.run(['cmd', '/c', 'mklink', '/J', dst, os.path.join(GAME_DIR, sub)],
                           check=True, capture_output=True)
            log('  정션 생성: %s' % sub)
    n_link = n_copy = 0
    for fn in sorted(os.listdir(extract.PACK)):
        if not fn.endswith('.cpk'):
            continue
        dst = os.path.join(pack, fn)
        if os.path.exists(dst):
            continue                                  # 원본은 한 번만 걸면 된다
        if _link(os.path.join(extract.PACK, fn), dst) == 'hardlink':
            n_link += 1
        else:
            n_copy += 1
    log('  원본 Pack: 하드링크 %d, 복사 %d 신규  (%s)' % (n_link, n_copy, CEMU_DIR))

    # ② cpk_pack 이 파일을 갈아끼우면 하드링크가 끊기므로 빌드할 때마다 다시 건다
    gp = os.path.join(GPACK, 'content', 'Pack')
    os.makedirs(gp, exist_ok=True)
    with open(os.path.join(GPACK, 'rules.txt'), 'w', encoding='utf-8') as f:
        f.write(RULES)
    for p in made:
        _link(p, os.path.join(gp, os.path.basename(p)))
    log('  그래픽팩 갱신: %s  (Cemu 에서 켜야 적용된다)' % GPACK)
    rpx = os.path.join(CEMU_DIR, 'code', 'Stainless.rpx')
    log('  실행: "%s" -g "%s"' % (os.path.join(CEMU_ROOT, 'Cemu.exe'), rpx))


def copy_sd(drive, made, log=print):
    dst = os.path.join(drive + os.sep, 'sdcafiine', TITLE_ID, 'TMS_KR', 'content', 'Pack')
    os.makedirs(dst, exist_ok=True)
    for p in made:
        shutil.copy2(p, os.path.join(dst, os.path.basename(p)))
        log('  -> %s' % os.path.join(dst, os.path.basename(p)))


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--sample' in args:
        apply_sample()
    made = build(skip_tex='--skip-tex' in args)
    verify(made, replaced=list(tex_patch.TARGETS))
    if '--cemu' in args:
        setup_cemu(made)
    if '--sd' in args:
        copy_sd(args[args.index('--sd') + 1], made)
    print('\n완료. 산출물: %s' % OUT)
