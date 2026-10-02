# -*- coding: utf-8 -*-
"""현재 번역 전체를 JSON 하나로 뽑는다(화자 정보 포함).

  python export_text.py            -> translation/tms_text_all.<날짜>.json

구성
  messages       : work/text (pack_031_message 의 MSBT 전문, 현재 번역)
                   각 줄에 speaker(대사창 이름), speaker_src('script' | 'voice'), speaker_label(이름표 라벨 또는 음성 번호)
  textures       : translation/tex_ko.json (그림 속 UI 라벨)
  movie_subtitles: translation/movie_subs_ko.py (동영상 자막 334줄, 북미판 타이밍)
  epilogue_cards : translation/epilogue_cards.json (엔딩 에필로그 카드 39장)

화자
  script — 이벤트 스크립트의 SetTalkerName/OpenMessageWindowEx 이름표. 게임이 대사창에 표시하는 이름 그대로.
  voice  — 스크립트에서 못 찾은 음성 대사. 음성 태그 끝의 인물 번호(pc1002 등)를
           '같은 번호로 스크립트 이름표가 붙은 대사'의 다수결 이름으로 바꾼다. 그래도 없으면 스크립트 상수(CHRID_…)의 영문 이름.
"""
import os, sys, json, glob, re, datetime, collections, importlib.util
import extract, speakers

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, '..'))
TEXT = os.path.join(PROJ, 'work', 'text')
VOICE_RE = re.compile(r'^\[V:[^\]]*?_((?:pc|np|mr|em|nm|sp)(\d+))(?:,[0-9a-f]+)?\]')


def main():
    cn = json.load(open(os.path.join(TEXT, 'Common', 'CharacterName.json'), encoding='utf-8'))
    name_ko = {e['label']: (e['ko'] or e['ja']) for e in cn['entries']}
    lua = extract.open_pack('pack_999_lua')
    by_stem = collections.defaultdict(list)
    for f in lua.files:
        by_stem[os.path.basename(f['name'])[:-4]].append(f['name'])
    chr_en = speakers.chrid_map(lua)

    files = []
    for p in sorted(glob.glob(os.path.join(TEXT, '**', '*.json'), recursive=True)):
        rel = os.path.relpath(p, TEXT)[:-5].replace(os.sep, '/')
        d = json.load(open(p, encoding='utf-8'))
        labels = {e['label'] for e in d['entries']}
        talk = {}
        for n in by_stem.get(os.path.basename(rel), []):
            try:
                talk.update(speakers.talkers_of_script(lua.read(n), set(name_ko), labels))
            except Exception:
                pass
        files.append((rel, d, talk))

    # 음성 번호 → 이름표 (다수결)
    vote = collections.defaultdict(collections.Counter)
    for rel, d, talk in files:
        for e in d['entries']:
            m = VOICE_RE.match(e['ja'] or '')
            if m and e['label'] in talk:
                vote[m.group(1)][talk[e['label']]] += 1
    voice_label = {v: c.most_common(1)[0][0] for v, c in vote.items()}

    out_files, n_script, n_voice, n_msg, n_hint = [], 0, 0, 0, 0
    for rel, d, talk in files:
        ents = []
        for e in d['entries']:
            n_msg += 1
            x = dict(i=e['i'], label=e['label'], ja=e['ja'], ko=e['ko'])
            if e['label'] in talk:
                x.update(speaker=name_ko.get(talk[e['label']], talk[e['label']]), speaker_src='script',
                         speaker_label=talk[e['label']])
                n_script += 1
            else:
                m = VOICE_RE.match(e['ja'] or '')
                if m:
                    vid = m.group(1)
                    if vid in voice_label:
                        x.update(speaker=name_ko.get(voice_label[vid], voice_label[vid]), speaker_src='voice',
                                 speaker_label=vid)
                        n_voice += 1
                    else:
                        # 화면에 뜨는 이름을 모르는 음성(주로 적 몬스터). 내부 코드명만 참고로 남긴다.
                        t, en = chr_en.get(m.group(2), ('', ''))
                        x.update(speaker_label=vid, speaker_hint=('%s %s' % (t, en)).strip() or vid)
                        n_hint += 1
            ents.append(x)
        out_files.append(dict(file=rel, count=len(ents), entries=ents))

    tex = json.load(open(os.path.join(PROJ, 'translation', 'tex_ko.json'), encoding='utf-8'))
    groups = []
    for k, v in tex.items():
        if k.startswith('_') or not isinstance(v, list):
            continue
        groups.append(dict(group=k, count=len(v), labels=[dict(ja=a, ko=b) for a, b in v]))

    spec = importlib.util.spec_from_file_location('movie_subs_ko', os.path.join(PROJ, 'translation', 'movie_subs_ko.py'))
    ms = importlib.util.module_from_spec(spec); spec.loader.exec_module(ms)
    movies = []
    sub = os.path.join(PROJ, 'work', 'movie_sub')
    for stem in sorted(ms.SUBS):
        blocks = open(os.path.join(sub, stem + '.en.srt'), encoding='utf-8').read().strip().split('\n\n')
        ents = []
        for b, (ko, src) in zip(blocks, ms.SUBS[stem]):
            L = b.split('\n')
            t0, t1 = L[1].split(' --> ')
            ents.append(dict(no=int(L[0]), start=t0, end=t1, en='\n'.join(L[2:]), ko=ko, basis=src))
        movies.append(dict(movie=stem, count=len(ents), entries=ents))

    epi = json.load(open(os.path.join(PROJ, 'translation', 'epilogue_cards.json'), encoding='utf-8'))
    cards = [dict(card=k, **v) for k, v in epi.items() if not k.startswith('_')]

    today = datetime.date.today().isoformat()
    doc = dict(
        title='幻影異聞録♯FE (Tokyo Mirage Sessions #FE) 일본판 0005000010131D00 — 한글 번역 전체',
        generated=today,
        note='messages = pack_031_message.cpk 의 MSBT 전문(현재 번역), textures = 그림 속 UI 라벨, '
             'movie_subtitles = 동영상 자막(북미판 타이밍), epilogue_cards = 엔딩 에필로그 카드. '
             '태그 표기: [V:보이스큐] · [C:2]…[C:-] 강조색 · [N:n] 치환변수 · [B:n] 버튼 아이콘. '
             'ja/ko 의 줄바꿈 개수는 반드시 같아야 한다(대사창 줄 수 고정).',
        speaker_note='speaker = 대사창 화자. speaker_src 가 script 면 이벤트 스크립트의 이름표(게임이 실제 표시하는 이름), '
                     'voice 면 음성 태그의 인물 번호로 추정한 이름. speaker 가 없는 줄은 화자 정보를 찾지 못한 것'
                     '(메뉴·도움말 등 화자가 없는 문구 포함). speaker_hint 는 화면 이름을 모르는 음성(주로 적)의 게임 내부 코드명.',
        messages=dict(source='pack_031_message.cpk / Message/JP_Japanese/**/*.msbt', files=out_files,
                      counts=dict(files=len(out_files), messages=n_msg, speaker_script=n_script, speaker_voice=n_voice,
                                  speaker_hint_only=n_hint)),
        textures=dict(source='translation/tex_ko.json (pack_030_etc.cpk 그림 속 라벨)', groups=groups,
                      counts=dict(groups=len(groups), labels=sum(g['count'] for g in groups))),
        movie_subtitles=dict(source='북미판 @SBT 타이밍 + translation/movie_subs_ko.py. basis J=일본어 음성, E=영어 자막, N=화면 글자, ★=존댓말',
                             movies=movies, counts=dict(movies=len(movies), lines=sum(m['count'] for m in movies))),
        epilogue_cards=dict(source='Event/images/61~99_*_ss_* (그림에만 있던 문장, 새로 번역)', cards=cards,
                            counts=dict(cards=len(cards))),
    )
    dst = os.path.join(PROJ, 'translation', 'tms_text_all.%s.json' % today)
    json.dump(doc, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('메시지 %d (파일 %d) · 화자: 스크립트 %d / 음성 %d / 내부코드만 %d / 없음 %d'
          % (n_msg, len(out_files), n_script, n_voice, n_hint, n_msg - n_script - n_voice - n_hint))
    print('그래픽 라벨 %d · 자막 %d줄 · 에필로그 %d장' % (doc['textures']['counts']['labels'],
                                                  doc['movie_subtitles']['counts']['lines'], len(cards)))
    print('→', dst, '%.1f MB' % (os.path.getsize(dst) / 1e6))
    return voice_label, chr_en


if __name__ == '__main__':
    main()
