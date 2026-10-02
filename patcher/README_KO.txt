환영이문록♯FE (Wii U) 한글 패치 v0.1
제작: arqhive

「幻影異聞録♯FE」(Wii U, 일본판) 비공식 한국어 팬 패치입니다.
대사·폰트·그림 속 글자·이펙트·타이틀 로고 영상을 한글로 바꿉니다. 동영상 자막은 따로 받는 선택 패치입니다.

- TMS_KO_v0.1_Patcher.zip (필수)
  가지고 있는 일본판 게임 파일로 한글판 CPK를 만드는 패처입니다.
- TMS_KO_v0.1_Movies.zip (선택, 약 3.4GB)
  이벤트 동영상 21개에 한글 자막을 넣습니다.
  용량이 커서 배포 페이지(GitHub)에 적힌 구글 드라이브 링크에서 받습니다.


[준비물]

- 일본판 「幻影異聞録♯FE」(타이틀 ID 0005000010131D00)의 복호화된 게임 파일.
  content\Pack 폴더 안에 pack_031_message.cpk 등이 있어야 합니다.
  북미판·유럽판(Tokyo Mirage Sessions ♯FE)과 Encore판(Switch)에는 적용할 수 없습니다.
- 윈도우 PC와 약 6GB의 여유 공간.
- Wii U 실기: Aroma 등 CFW와 SDCafiine 플러그인, SD 카드.
- 에뮬레이터: Cemu 2.6.


[한글판 만들기]

1. TMS_KO_v0.1_Patcher.zip 을 폴더째 압축을 풉니다.
2. 동영상 자막도 넣으려면 TMS_KO_v0.1_Movies.zip 을 같은 곳에 압축을 풉니다.
   TMS_KO_v0.1\patcher\payload_movies 폴더가 생기면 됩니다.
3. 게임 폴더(또는 content\Pack 폴더)를 "패치하기.bat"에 끌어다 놓습니다.
   그냥 실행하면 경로를 묻습니다.
4. 원본 확인 → 한글판 만들기 → 결과 확인이 차례로 진행됩니다. 몇 분 걸립니다.
   결과는 TMS_KO_v0.1\출력 폴더에 생깁니다. 원본 파일은 바뀌지 않습니다.

- 이미 패치한 파일이나 다른 판을 넣으면 원본 확인 단계에서 멈춥니다.
- 자막 영상 패치는 나중에 추가해도 됩니다. 2번을 한 뒤 3번을 다시 하면 됩니다.


[Wii U 실기 (SDCafiine)]

1. 출력\sdcafiine 폴더 안의 내용을 SD 카드의 wiiu\sdcafiine\ 에 복사합니다.
   다음과 같이 파일이 놓이면 됩니다.

     sd:/wiiu/sdcafiine/0005000010131D00/KoreanTranslation/content/Pack/*.cpk

2. SDCafiine 플러그인을 켠 상태로 게임을 실행합니다.

- pack_050_movie.cpk 는 약 4GB입니다. FAT32 SD 카드에 들어가는 크기(4GiB 미만)입니다.


[Cemu]

1. 출력\cemu\TMS_Korean 폴더를 Cemu 의 graphicPacks 폴더에 복사합니다.
2. Cemu 의 그래픽팩 설정에서 Tokyo Mirage Sessions FE → Mods → Korean Translation 을 켭니다.
3. 게임을 실행합니다.


[알려진 문제]

- 타이틀 로고 영상의 조립 장면(시작 후 약 1.3~3.1초)에는 일본어 로고가 잠깐 보입니다.
  영상을 끝까지 두거나 넘기면 한글 로고가 나옵니다.
- 3D 모델에 그려진 글자(간판·소품 등)는 일본어 그대로입니다.
- 프롤로그 영상 속 신문 제목은 일본어 그대로입니다.


[면책]

비공식 팬 번역이며 Nintendo, ATLUS, INTELLIGENT SYSTEMS와 관련이 없습니다.
「幻影異聞録♯FE」 관련 상표·저작권은 Nintendo와 ATLUS에 있습니다.
패치를 적용한 게임 파일의 배포를 금지합니다.
게임 폰트의 한글 글자는 Noto Sans KR(SIL Open Font License 1.1)로 만들었습니다. 라이선스 전문은 licenses 폴더에 있습니다.
