# 기술 문서 — 환영이문록♯FE (Wii U) 한글화

Wii U 일본판 `WUP-P-ASEJ` / titleId `0005000010131D00` 기준.
대사·폰트·그림 속 글자(2D·이펙트)·동영상 자막·타이틀 로고 영상을 한글화한다. 북미판(`00050000101ed800`)은 참고용으로만 썼고(덤프는 2026-09-28 삭제) 리소스를 옮겨 넣지 않는다.

**v0.1 (2026-09-28)** — 첫 검수판. 대사·폰트·2D·이펙트·동영상 자막·타이틀 영상 로고 전부 들어간 상태로 실기(SDCafiine) 부팅·표시 확인.

## 진행 상황

| 분야 | 상태 |
|---|---|
| 대사(MSBT 996개, 28,399메시지) | 번역·검수 완료 |
| 폰트(BFFNT 10개) | 한글 글리프 재구성 완료 |
| 2D 그래픽(GTX) | 완료 259장(한글 211 · 같은 그림 복사 33 · 원본 그대로 15), 전부 동결 |
| 이펙트 그림(ptcl) | 완료 26장 — 필드 상호작용 표시 10 · 전투 돌입 배너 12 · 극중 드라마 크레디트 3 · 「비탕으로 GO!」 1 |
| 3D 그래픽(모델 텍스처) | **포기**(2026-09-28) — 원본처럼 압축해 넣어도 실기에서 부팅이 멈춤. 원본 그대로 |
| 동영상 자막(21개) | 자막 구워 넣기 완료 |
| 타이틀 로고 영상(m00) | 3.2초부터 한글 로고(그 앞 조립 연출 1.3~3.1초는 원본) |

작업하지 않기로 한 2D 95장은 `translation/graphics/manifest.json` 의 `skipped` 에 사유와 함께 있다. 대사 밖 한글화 대상 전수조사는 [`전수조사_2026-09-28.md`](전수조사_2026-09-28.md).

## 폴더

```
환영이문록/
  tools/                  도구 (빌드·CPK·MSBT·폰트·텍스처·영상)
  translation/
    graphics/             확정 그래픽 최종본 (2D/·eft/ 그림은 git 제외, manifest.json·현황판 묶음 설정만 추적)
    tex_ko.json           그림 속 UI 라벨 번역 (tex_patch 가 GTX 로 그림)
    movie_subs_ko.py      동영상 자막 번역
    epilogue_cards.json   엔딩 에필로그 카드
    glossary.md           용어집·표기 규칙
    tms_message.xlsx      대사 번역 시트
    review/               대사 검수 기록
  work/                   (git 은 text·movie_sub 만 추적)
    text/                 대사 번역 JSON (분류/파일.json) — 번역 원본
    movie_sub/            자막 정렬(*.ko.srt, *.align.tsv)
    movie_ko/             자막 구운 USM + 타이틀 로고 영상(m00.usm)
    extract/              추출물(폰트 원본 등)
    layla_cache/          CRILAYLA 압축 캐시
    graphics_board/       2D 현황판(graphics_board.py, --final 은 동결본 포함 최종판)
    sdcafiine/            빌드 산출물
  docs/                   조사 기록
  fonts/                  (git 제외) 폰트
  Tokyo Mirage Sessions FE [...]/   (git 제외) 게임 덤프 — 일본판 본편·업데이트·DLC
```

## 빌드

```bash
pip install -r requirements.txt
python -X utf8 tools/build.py            # 대사·폰트·2D·이펙트 → CPK 4개
python -X utf8 tools/build.py --movies   # + 동영상 CPK 2개
python -X utf8 tools/build.py --packs pack_031_message,pack_999_font   # 지정한 팩만
```

산출물은 `work/sdcafiine/0005000010131D00/TMS_KR/content/Pack/`.
SD 카드 `wiiu/sdcafiine/0005000010131D00/KoreanTranslation/content/Pack/` 에 복사한다.

| CPK | 내용 |
|---|---|
| `pack_031_message` | 대사 |
| `pack_999_font` | 폰트 |
| `pack_030_etc` | 2D 그래픽 |
| `pack_020_effect` | 이펙트 그림(`tools/eft_inject.py`) |
| `pack_050_movie`, `pack_060_movie_credit` | 동영상 자막, 타이틀 로고 영상 |

FAT32 는 파일 하나가 4GiB 미만이어야 한다. `pack_050_movie` 는 자막을 구우면서 원본보다 작게 맞췄다. 빌드는 교체분 재확인·FAT32 크기를 검사한다.

## 대사 작업 흐름

```bash
python tools/text_io.py export     # CPK -> work/text/*.json (기존 ko 는 보존)
python tools/xlsx_io.py out        # JSON -> translation/tms_message.xlsx
python tools/xlsx_io.py in         # xlsx -> JSON
python tools/text_io.py check      # 태그 누락 등 경고
```

## 그래픽

`translation/graphics/manifest.json` 의 `done` 항목마다 `method` 가 있다.

| method | 뜻 |
|---|---|
| `file` | `2D/<경로>` GTX 를 그대로 넣음 |
| `tex_patch` | `tools/tex_patch.py` 가 `tex_ko.json` 으로 그림 |
| `copy` | `copy_from` 과 원본 그림이 같아 그 결과를 복사 |
| `original` | 원본 그대로 |

3D 모델 텍스처(2026-09-27까지 123장 작업)는 2026-09-28 포기했다. 모델 파일(`.apak`)의 텍스처 영역만 바꾸고 CPK 에 원본처럼 압축해 넣었지만, 실기(SDCafiine)에서 부팅이 멈췄다(Cemu 는 정상, 게임 원본 팩은 SD 에서도 정상). 주입 도구·목록·그림은 지웠고 git 이력에만 남아 있다. 참고로 `.apak` 항목 앞 32비트 값은 원래 경로의 djb2 해시다(내용과 무관).
작업 과정(GPT·Claude 세션별 작업 폴더, 비교 그림, 리뷰 기록)은 2026-09-27 정리하며 저장소 밖으로 옮겼다. 스크립트는 git 이력(`c8f3fdf`)에 남아 있다.

## 동영상 자막

USM 영상에 자막을 구워 다시 넣는다. ffmpeg 는 `imageio-ffmpeg` 패키지에 든 것을 쓴다.
번역은 `translation/movie_subs_ko.py`, 타이밍은 북미판 자막(`work/movie_sub/*.align.tsv`)을 쓴다.
`tools/burn_all.py` 가 굽고 `tools/build_movies.py`(또는 `build.py --movies`)가 CPK 를 만든다.
원본 I프레임 위치에 키프레임을 강제한다. 원본은 장면 전환마다 I프레임이 들어가 GOP 가 불규칙하다.
타이틀 로고 영상은 `tools/usm_logo.py` 가 만든다(색 @SFV + 알파 @ALP 두 영상을 모두 다시 굽는다).

## 게임 구조

- **텍스트** = `pack_031_message.cpk` — MSBT 996개, `MsgStdBn`, **UTF-16BE**, 섹션 LBL1/ATR1/TXT2, 정렬 패딩 `0xAB`. 태그는 9종뿐이다(표기법은 `mtext.py` 머리말).
- **폰트** = `pack_999_font.cpk` — BFFNT(FFNT v3, BE) 10개, 시트 1024×1024, `format 12` = BC4.
- **2D** = `pack_030_etc.cpk` 의 GTX(대부분 BC1 sRGB).
- **3D** = `pack_000_map`·`pack_010_character` 의 `.apak`/`.bfres` 안 FTEX(한글화 안 함).

## 밟아 본 함정

1. **CPK TOC base** = `min(TocOffset, 0x800, ContentOffset)`. TocOffset 만 보면 틀린다.
2. **CPK 파일 공유** — 내용이 같은 파일 여러 개가 같은 `FileOffset` 을 쓴다. `(원본offset, sha1)` 로 묶어야 무변경 재패킹이 바이트 일치한다.
3. **ETOC 없는 CPK** 는 마지막 파일 뒤 정렬 패딩을 파일에 쓰지 않는다(`ContentSize` 에는 포함).
4. **BFFNT 오프셋**은 전부 '블록 시작 + 8'. 블록 `size` 는 magic·size 필드를 포함한 전체 크기다.
5. **폰트 셀 스텝 = (cellW+1, cellH+1)**, 시트마다 스위즐이 회전(`(sheet_index % 4) << 9`), 시트는 상하 반전 저장.
6. **BC4 재인코딩은 손실**이 있다(픽셀 최대 18, 평균 0.7). 글리프 대조는 허용 오차 24로 본다.
7. **CPK 교체 파일은 원본처럼 CRILAYLA 압축**해서 넣는다. 무압축으로 넣으면 팩이 커지고(2D 0.73 → 1.23GB) 실기에서 스플래시 뒤 멈춘다(Cemu 는 정상).
8. **CPK 전 파일 검증**을 `read(name)` 으로 하면 수십 분 걸린다. 큰 팩은 교체분만 다시 읽는다.
9. **대사 폰트(FOT-*)는 고정폭**이라 반각 띄어쓰기·부호도 한자 폭을 차지해 대사창(24px 폰트 약 23.8칸·3줄)을 넘친다. `font_build.narrow()` 로 띄어쓰기 0.42폭, 반각 부호는 잉크 폭만큼 좁힌다.
10. **알파 영상(@ALP)은 밝기 0~255 전체 범위**다. rgb 로 거쳐 인코딩하면 16~235 로 좁혀져 투명한 곳이 뿌옇게 된다 → Y 평면을 그대로 굽는다.
11. **타이틀 화면**은 영상(m00.usm)이 도는 동안엔 영상 속 로고, A 로 넘기면 `Interface/title/title_logo.gtx` 가 보인다.

## Cemu 테스트

- `tools/build_patch.py --cemu` 는 대사·폰트만 빌드해 Cemu 그래픽팩 `TMS_Korean` 을 갱신한다.
- 덤프 폴더를 직접 물리면 암호화 NUS 를 골라 "Unable to launch game" 이 난다. 복호화본만 보이는 정션 폴더를 쓴다.
