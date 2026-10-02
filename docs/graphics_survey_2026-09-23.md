# 그래픽 전수조사 2차 (2026-09-23) — 중간 기록

사용자 요청: "로고 제외하고 안 된 부분 싹 다 찾기". 주간 토큰 한도로 **중단**. 복구 후 이어서.

## 완료된 한글화 (claude_001~004)
battle_002, m_window003, offer_UI001, Intermission001, fusion001, status001, status_drc001, shop001, result_001,
party_panel001, mnt_tx_03~06 (드라마 카드: 제1화/제9화/최종화 + 제공 보물상자사). 게임 빌드 통합은 아직.
(mnt_tx 는 03~06 뿐 — 01/02/07~19 는 컬러바·캐릭터·카운트다운, 글자 없음)

## 검수 끝난 범위와 결과

### 꼭 할 것 (플레이어가 정보로 읽음)
- `Event/images/61~99_*_ss_*` **39장** — 엔딩 캐릭터 에필로그 카드(칭호·이름·본문 5~6줄). MSBT 에 같은 문장 없음(1문장만 확인).
- `Event/images/20_starttext` — 시작 면책 문구 「このゲームはフィクションです…」
- `Event/images/30_s1006_b_13_1` — 「来週に続く…」
- `Event/extras/images/m3083_01_00` — 곡 제목 카드 「雨音のメモリー／詞・曲 夏海」(세로쓰기)

### 하면 좋은 것 (대사에 이름이 나옴)
- `Event/images/00~11_*` 방송국·프로그램 로고 11장: 大東放送, ダイバーTV, 秘湯へGO!, ハクション刑事 魔帆, レンチンアイドル まもりん,
  マスカレイダー雷牙/凰牙, 季節外れのUFO, イドラTV, tvヒノデ, 4テレ (10_atv 는 영어뿐)
- `Interface/Notice/notice_tex075` — 라이가 쇼 포스터(행사 안내·약도, 문장 많음)
- `Interface/Notice/tv_tex000~028` — TV 화면 13종(문장형 광고)
- `Interface/AutoMap` 仮データ — 같은 그림 118장, 그중 18장은 실제 던전층 슬롯(d009/d011~d014 등). 게임에서 보이는지 확인 필요.

### 풍경 (낮음)
- Notice 나머지(광고판·깃발·포스터·잡지·자판기), Event/bustup/bg 잡지진열대·간판 6장

### 자리표시/미사용
- catalog_chara 164장(キャラNNN), catalog_item 60장(アイテムNNN), catalog_em/mr/pc 는 "?" 1종
- Event/bustup/play_demo_m01~06 315장 = 연필 콘티(메모 손글씨), m1016_03 16장 仮素材, bg 의 欠番/共有に変更 23장, title 로고 자리표시 4장

## 남은 것
1. **일반 UI 약 340장 재검수** — 중단됨. 마지막 메모: `camp/profileBG*` 에 작은 일본어 이름 발견, camp002 카드 이름 확인 중이었음.
   대상: fusion, Gimmick, Topic, artwork, encount, Intermission, 2d_bu_event, Test, camp, result, battle, A1/*, 기타 소수 폴더.
   자료: `work/tex/_text/Interface_*.png`(글자영역 확대), `work/tex/Interface/...`, `work/tex/_sheets/Interface_*.png`
2. **3D 모델 텍스처** — 추출 완료(`tools/bfres_tex.py` → `work/tex/_models`, 12,634장, 중복·단색 제외 5,983장).
   대조표 616장 `work/tex/_msheets/*.png` + `_index.json`(시트→파일 목록). 검수는 **시작 직후 중단(결과 없음)**.
   추출 실패 386장(tileMode 2 등 미지원: fmt0x34/0x431/0x433 tm2, fmt0x820 tm4).
3. 이펙트 `pack_020_effect` .ptcl 1,694개 — 텍스처 추출기 없음.
4. 동영상 36개(USM) — ffmpeg 없음(설치하려면 사용자 허락 필요).
5. DLC 팩 — 미확인.
6. 참고: 영어판이 간판을 어떻게 처리했는지는 **확인된 정보 없음**(근거 없이 말했다가 정정함). 우선순위 기준 = 플레이어가 읽어야 이해되는가.
