# UI 텍스처 전수조사 (2026-09-19)

`pack_030_etc.cpk` 의 GTX 2,292장 중 `Interface/` 1,816장을 전부 디코드해 확인했다 (실패 0).
도구: `tex_survey.py`(디렉터리별 대조표), `tex_text.py`(글자 영역만 자동 크롭·확대).

## 큰 그림

**이 게임의 UI 라벨은 원래 대부분 영어로 디자인돼 있다.** 일본판인데도
메뉴가 `Skills / Goods / Coordinate / Artists / Casting / Analysis / System / Save / Load / Mode / Setting`,
스테이터스가 `Health Condition / Next Exp / Resist / Parameter / Session Skill / Backup Skill`,
상점이 `BUY / SELL / SOLD OUT`, 전투 판정이 `MISS / GOOD / GREAT / CRITICAL! / BRILLIANT!`,
직업명이 `MASTER LORD / SNIPER / PEGASUS KNIGHT` 다. 원작 디자인이므로 손대지 않는다.

일본어가 박힌 것은 아래가 전부다.

## 번역 대상

| 파일 | 내용 |
|---|---|
| `Interface/m_window/m_window003` | **가장 중요**. 화면 하단 버튼 가이드 30개 |
| `Interface/result/result_001`<br>`Interface/shop/shop001`<br>`Interface/status_drc/status_drc001`<br>`Interface/camp/status001`<br>`Interface/fusion/fusion001` | 능력치·운세·내성 라벨 **세트 (여러 텍스처가 같은 세트를 공유)** |
| `Interface/Topic/topic_window` | 達成 · 閉じる · ジャンル · 依頼者 · 詳細 · タイムライン · 追加ビュー · 進行中 · 保留中 · 達成済み · 全て · 検索 |
| `Interface/A1/Camp/a1_camp001` | 게임패드 메뉴 설명문 5개 |
| `Interface/A1/others/a1_title001` | 타이틀 설명문 2개 (MSBT `Title/HELP_DEBUT`·`HELP_LOAD` 와 같은 내용의 텍스처판) |
| `Interface/Gimmick/mnt_tx_03`~`06` | 극중극 TV 드라마 제목 3개 + 「提供 宝箱社」 |
| `Interface/Intermission/Intermission001` | **진짜 장 제목 아틀라스** — 제목 13줄 + 장 라벨 9줄 |
| `Interface/offer/offer_UI001` | 達成 · 失敗 · オフ |
| `Interface/largemap/largemap_001` | 現在位置 · 渋谷 · 原宿 등 지명 |
| `Interface/party_panel/party_panel001` | リザーブ |
| `Interface/battle_02/battle_002` | ＳＰスキル使用可能! |

### m_window003 버튼 가이드 30개

```
閉じる      早送り      オート      オート中    MWオフ
スキップ    オートバトル  ステータス   プロフィール  戻る
素材ヘルプ   早送り中     情報切換     スキル情報   素材情報
操作を戻す   ソート      オートバトル中 セッションオート セッションオート中
ステータス情報 表示オフ    習得しない    表示オン    初期化する
耐性情報オン  耐性情報オフ  並べ替え     スキルヘルプ  ラージマップ
```

### 능력치·운세·내성 라벨 세트

```
力:  魔力:  技:  速さ:  守備:  魔防:  幸運:  攻撃力:  防御力:
悲運  不運  普通  強運  豪運
吸  弱  反  無  耐  一  ?
```

### 장 제목 (Intermission)

```
序章「フォースウォールの向う側」   第1章「シスターズ・アンコール」
第2章「渋谷カタストロフ」        第3章「オーディトリアムの想い」
第4章「絆つむぐエチュード」       第5章「暗黒竜グランギニョール」
第6章「戯曲ファイアーエムブレム」   終章「カーテンコール」
```

**위 목록은 개발 중 가제였다.** 사용자가 실기 화면을 캡처해 대조한 결과 실제로 나오는 것은
`Intermission001` 아틀라스이고, 최종 장 제목은 이렇다:

```
序章「リインカーネーション」      第1章「スタア誕生」
第2章「あの子に首ったけ」        第3章「ネクストジェネレーション」
第4章「ザ・オーディション」       第5章「トゥルー・カラーズ」
第6章「ファイアーエムブレム」      終章「ロング・グッドバイ」
        「インターミッション」× 5
```

`title00~07` / `intermission01~05` / `intermission_end01~05` 는 전부 "演出含め仮"(연출 포함 임시)
워터마크가 찍힌 **미사용 가제**다. 건드릴 필요 없다.

## 번역 대상이 아닌 것

| 분류 | 장수 | 이유 |
|---|---|---|
| `Interface/Notice` | 172 | 시부야 광고판·잡지 표지·TV 화면 등 배경 소품 |
| `Interface/AutoMap` | 235 | 지도 도형. 글자는 「仮データ」(임시 데이터) 플레이스홀더뿐 |
| `Interface/common/catalog_*` | 1,020 | 아이템·캐릭터·적 아이콘 |
| `Interface/Test` | 20 | 개발용 테스트 |
| `artwork`, `2d_bu_event`, `encount/chra_*`, `result/lvupchara*`, `camp/profileBG*`, `fusion/charaboard_*` | 약 140 | 캐릭터 일러스트 |

## 그 밖에 조사한 것

- `pack_999_etc_om` (테이블 51개): 일본어 **0건**. 전부 ASCII 리소스 경로 테이블.
- `pack_999_lua` (Lua 11,262개): 126개 파일에 일본어 문자열이 있으나 컴파일된 바이너리 안의
  디버그 식별자로 보인다 (`初回戦闘チュートリアル`, `オグマセリフ` 등). 실기에서 번역 안 된
  문구가 나오면 다시 볼 것.
- `pack_050_movie` (USM 24개, 4.1GB): 자막 확인 **미실시**. 장 제목 연출이 여기 있을 수 있다.

## 남은 기술 과제

텍스처를 실제로 교체하려면 **GTX 인코더**가 필요하다. 현재 `gtx2.py` 는 디코드 전용이다.
필요한 것:
1. RGBA8 / BC2 / BC3 인코딩 (BC4 는 `gtx_lib` 에 이미 있다)
2. 스위즐 (주소 매핑은 `gtx2.addr_map` 을 그대로 역방향으로 쓰면 된다)
3. 라벨별 bbox 를 찾아 **원래 상자 안에** 한글을 맞춰 그리기 —
   UV 좌표가 테이블/Lua에 박혀 있으므로 글자 상자 크기를 바꾸면 잘린다.


## 진행 상황 (2026-09-19)

교체 완료 — 텍스처 12장 / 라벨 162개:

| 텍스처 | 라벨 |
|---|---|
| `m_window003` | 30 (버튼 가이드) |
| `Intermission001` | 21 (장 제목 13 + 장 라벨 8) |
| `topic_window` | 16 |
| `a1_camp001` | 9 (게임패드 메뉴 설명문) |
| `result_001` / `shop001` / `status_drc001` / `camp status001` | 각 20 |
| `fusion001` | 19 (게이지 라벨 없음) |
| `offer_UI001` | 2 (오퍼 달성!·오퍼 실패) |
| `largemap_001` | 3 (시부야·하라주쿠·현재 위치) |
| `a1_title001` | 2 (게임패드 타이틀 HELP 설명문) |

### 라벨 배경 세 가지 — `_replace_one` 의 모드

| 모드 | 구조 | 예 |
|---|---|---|
| 기본 | 투명 배경, **알파가 글자** | 버튼 가이드, 능력치, 장 제목 |
| `invert` | **흰 판에 검은 글자** (알파는 판 모양) | topic_window 의 詳細·タイムライン·追尾ビュー |
| `overlay` | **불투명 배경판 위 RGB 글자** (알파는 판 모양) | largemap 의 現在位置, a1_title001 의 HELP 설명문 |

`overlay` 는 알파로 bbox 를 잡으면 배경판 전체가 잡혀 글자가 그만큼 커진다. **밝은 RGB**로
bbox 를 잡고, 지우기는 bbox 안에서만 더 낮은 임계값으로 해야 원본 획이 남지 않는다.

### 보류

- `Interface/party_panel/party_panel001` — リザーブ 3개.
  회색 마름모에 그라데이션과 하이라이트가 섞여 있어 원본 글자를 깨끗이 지우기 어렵다.
  지우면 회색 띠가 남고, 임계값을 낮추면 마름모 무늬가 뭉개진다. 중요도가 낮아 보류.
  좌표는 `tex_patch.RESERVE_BOXES` 에 남겨 뒀다.
- `Interface/battle_02/battle_002` — ＳＰスキル使用可能!. 위치를 아직 못 찾았다
  (행 투영으로는 다른 요소에 묻힌다).
- `Interface/Gimmick/mnt_tx_03`~`06` — 극중극 TV 제목 3개 + 「提供 宝箱社」.
  둥근 팝체 장식 글꼴에 테두리·그림자가 들어가 있어 Noto Sans KR 로는 분위기가 달라진다.
