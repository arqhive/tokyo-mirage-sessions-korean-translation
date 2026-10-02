# 환영이문록♯FE (Wii U) 한글 패치

「幻影異聞録♯FE」(Wii U, 일본판 `0005000010131D00`) 비공식 한국어 팬 패치입니다.
대사는 일본어판 원문을 기준으로 번역했습니다.

**제작: arqhive** · **최신 버전: [v0.1](../../releases/tag/v0.1)**

- 대사 전체를 한글화했습니다(이벤트·필드·사이드 스토리·TOPIC·메뉴·아이템·스킬 등 28,399개 메시지).
- 게임 폰트 10종에 한글을 새로 그려 넣었습니다.
- 글씨가 그려진 그림 259장(UI·공지·포스터·배경 광고 등)과 이펙트 그림 26장(필드 상호작용 표시·전투 돌입 배너 등)을 한글화했습니다.
- 이벤트 동영상 21편에 한글 자막을 넣었습니다(선택 패치).
- 타이틀 로고 영상과 타이틀 화면 로고를 한글 로고로 바꿨습니다.
- **가지고 있는 일본판 게임 파일로 한글판을 만드는 패처로 배포합니다.** 결과는 Wii U 실기(SDCafiine)와 Cemu 에서 바로 쓸 수 있습니다.

> 이 저장소에는 롬·그래픽·영상 같은 게임 데이터가 들어 있지 않습니다.
> 패치를 만들거나 적용하려면 본인이 소유한 게임에서 직접 덤프한 원본이 필요합니다.

## 사용자용: 패치 적용

### 준비물

- 일본판 「幻影異聞録♯FE」의 복호화된 게임 파일(타이틀 ID `0005000010131D00`). `content\Pack` 폴더에 `pack_031_message.cpk` 등이 있어야 합니다.
  - 북미판·유럽판(Tokyo Mirage Sessions ♯FE)과 Encore 판(Switch)에는 적용할 수 없습니다.
- Windows 10 이상. 패처에 파이썬이 들어 있어 따로 설치할 것이 없습니다.
- 빈 공간 약 6GB(결과 파일).
- Wii U 실기라면 Aroma 등 CFW 와 SDCafiine 플러그인.

### 배포 파일

| 파일 | 필수 | 내용 |
|---|---|---|
| `TMS_KO_v0.1_Patcher.zip` | ○ | 패처. 대사·폰트·그림·이펙트·타이틀 로고 영상 |
| `TMS_KO_v0.1_Movies.zip` | 선택 | 이벤트 동영상 21편의 한글 자막(약 3.4GB). 용량이 커서 [구글 드라이브](https://drive.google.com/file/d/16qqc3NX-3AZecIR2Mo_DmEXbTtlPON5z/view?usp=drive_link)에서 받습니다. |

### 적용 방법

1. [배포 페이지](../../releases/latest)에서 `TMS_KO_v0.1_Patcher.zip`을 받아 압축을 풉니다.
2. 동영상 자막도 넣으려면 [구글 드라이브](https://drive.google.com/file/d/16qqc3NX-3AZecIR2Mo_DmEXbTtlPON5z/view?usp=drive_link)에서 `TMS_KO_v0.1_Movies.zip`을 받아 같은 곳에 압축을 풉니다(`TMS_KO_v0.1\patcher\payload_movies` 폴더가 생깁니다).
3. 게임 폴더(또는 `content\Pack` 폴더)를 `패치하기.bat` 위에 끌어다 놓습니다. 그냥 실행하면 경로를 물어봅니다.
4. 원본 확인 → 한글판 만들기 → 결과 확인이 끝날 때까지 기다립니다(몇 분 정도). 원본 파일은 바뀌지 않습니다.
5. `TMS_KO_v0.1\출력` 폴더에 결과가 생깁니다.

#### Wii U 실기 (SDCafiine)

`출력\sdcafiine` 안의 내용을 SD 카드의 `wiiu\sdcafiine\`에 복사하고, SDCafiine 플러그인을 켠 채로 게임을 실행합니다.

```
sd:/wiiu/sdcafiine/0005000010131D00/KoreanTranslation/content/Pack/*.cpk
```

`pack_050_movie.cpk`는 약 4GB이지만 FAT32 한도(4GiB) 안이라 그대로 복사됩니다.

#### Cemu

`출력\cemu\TMS_Korean` 폴더를 Cemu 의 `graphicPacks` 폴더에 넣고, 그래픽팩 설정에서 `Tokyo Mirage Sessions FE → Mods → Korean Translation`을 켭니다.

#### 오류가 날 때

| 메시지 | 원인·해결 |
|---|---|
| pack_031_message.cpk 가 있는 폴더를 찾지 못했습니다 | 게임 폴더나 `content\Pack` 폴더를 넣어 주세요. 암호화된 상태(.app)로는 안 됩니다. |
| …cpk 가 일본판 원본과 다릅니다 | 이미 패치한 파일이거나 다른 판입니다. 원본 일본판 파일을 넣으세요. |
| 자막 영상 패치 일부가 없습니다 | `TMS_KO_v0.1_Movies.zip`을 패처와 같은 곳에 다시 풀어 주세요. |
| 결과가 기준과 다릅니다 | 패치 파일이 손상됐을 수 있습니다. zip 을 다시 받아 주세요. |

패처는 원본 CPK의 해시를 확인한 뒤 바뀐 파일만 바꿔 CPK를 다시 만들고, 결과가 제작 환경에서 확인한 빌드와 해시까지 같은지 검사합니다.
자세한 방법은 패처에 들어 있는 `README_KO.txt`를 참고하세요.

### 실행 환경

- **확인함**: Wii U 실기(SDCafiine), Cemu 2.6.

### 알려진 문제

- 타이틀 로고 영상의 조립 장면(시작 후 약 1.3~3.1초)에는 일본어 로고가 잠깐 보입니다. 영상을 끝까지 두거나 넘기면 한글 로고가 나옵니다.
- 3D 모델에 그려진 글자(간판·소품 등)는 일본어 그대로입니다. 바꿔 넣으면 실기에서 게임이 멈춰서 넣지 않았습니다.
- 프롤로그 영상 속 신문 제목은 영상의 일부라 일본어 그대로입니다.

## 개발자용: 도구

번역 원본(대사 JSON·대사 시트·용어집·그림 목록·검수 기록)에는 게임의 일본어 원문이 함께 들어 있어 **공개 저장소에는 넣지 않았습니다.**
이 저장소의 도구는 형식 분석과 빌드 방식을 참고하는 용도이며, 번역 원본 없이는 한글판을 빌드할 수 없습니다. 패치 적용은 위의 패처를 쓰세요.

### 요구 사항

- Python 3.11 이상. `pip install -r requirements.txt`(numpy, Pillow, openpyxl, imageio-ffmpeg, opencv-python, scipy).
- 일본판 게임 덤프(복호화된 `code`·`content`·`meta`)를 저장소 루트의 `Tokyo Mirage Sessions FE [Game] [0005000010131d00]/`에 둡니다.
- 한글 폰트: Noto Sans KR(`C:/Windows/Fonts/NotoSansKR-VF.ttf`), 자막용 나눔스퀘어라운드(`fonts/subtitle/`).

### 빌드

```bash
python -X utf8 tools/build.py              # 대사·폰트·2D·이펙트 → CPK 4개
python -X utf8 tools/build.py --movies     # + 동영상 CPK 2개
python -X utf8 tools/make_patcher.py v0.1  # 배포용 패처 zip (work/release/)
```

산출물은 `work/sdcafiine/0005000010131D00/TMS_KR/content/Pack/`에 생깁니다. 같은 입력이면 결과는 바이트 단위로 같습니다.

### 폴더 구조

```
patcher/           사용자용 패처 (패치하기.bat, patch.py, rules.txt, README_KO.txt)
tools/             빌드·패처·조사 도구
docs/              기술 문서, 전수조사 기록, 릴리즈 노트
licenses/          폰트 라이선스
```

### 기술 문서

파일 포맷, 한글화 방식, 밟아 본 함정은 [`docs/TECHNICAL.md`](docs/TECHNICAL.md)에 정리했습니다.

## 변경 내역

전체 내역은 [`CHANGELOG.md`](CHANGELOG.md)에 있습니다.

## 크레딧·라이선스

- 이 저장소의 도구 코드와 문서: [MIT License](LICENSE) (© 2026 arqhive).
- 게임 폰트의 한글 글자는 [Noto Sans KR](https://fonts.google.com/noto/specimen/Noto+Sans+KR)로 그렸습니다. SIL Open Font License 1.1 ([`licenses/OFL_NotoSansKR.txt`](licenses/OFL_NotoSansKR.txt)).
- 동영상 자막은 네이버 나눔스퀘어라운드로 그렸습니다(SIL Open Font License 1.1).
- 패처에 동봉하는 Python 은 PSF License 입니다.

## 면책

비공식 팬 번역이며 Nintendo, ATLUS, INTELLIGENT SYSTEMS와 관련이 없습니다. 「幻影異聞録♯FE」 관련 상표·저작권은 Nintendo와 ATLUS에 있습니다.
패치를 적용한 게임 파일의 배포를 금지합니다.
