# -*- coding: utf-8 -*-
"""영문·숫자 뒤 조사를 한국어 **발음** 기준으로 고른다.

「ＴＯＰＩＣ가」가 아니라 「ＴＯＰＩＣ이」다(토픽 → ㄱ받침).
받침 판정은 글자 모양이 아니라 읽는 소리로 해야 한다:
  · 약어는 마지막 알파벳의 이름 — L 엘, M 엠, N 엔, R 알 만 받침이 있다.
  · 단어로 읽히는 것은 사전에 적는다(TOPIC=토픽, FEEL=필 …).
  · 숫자는 마지막 자리 — 0 영, 1 일, 3 삼, 6 육, 7 칠, 8 팔 에 받침이 있다.
"""
import re

# 받침 종류: 0=없음, 1=ㄹ, 2=그 밖.
# 「으로/로」만 ㄹ을 따로 본다 — 「ＨＰ１로」가 맞고 「ＨＰ１으로」는 틀리다.
_ALPHA_KIND = {'L': 1, 'R': 1, 'M': 2, 'N': 2}

# 약어가 아니라 한 단어로 읽는 것. 값은 위의 받침 종류
_WORDS = {
    'TOPIC': 2,     # 토픽
    'FEEL': 1,      # 필
    'GIRL': 1,      # 걸
    'REINCARNATION': 2,   # 리인카네이션
    'GAME': 2,      # 게임
    'RAIN': 2,      # 레인
    'LUCK': 2,      # 럭
    'ON': 2,        # 온
    'MARK': 0,      # 마크
    'KIRIA': 0, 'TIKI': 0, 'SWEET': 0, 'FLY': 0,
    'ME': 0, 'GO': 0, 'SET': 0, 'FACE': 0,
    'NINJA': 0, 'KAWAII': 0, 'COMPLEX': 0, 'ANZU': 0,
    'TOKYO': 0, 'STORE': 0, 'LIVE': 0, 'TERADETH': 0,
    'MAX': 0, 'OFF': 0, 'BEASTIE': 0,
}

# 영 0, 일 1(ㄹ), 이 2, 삼 3, 사 4, 오 5, 육 6, 칠 7(ㄹ), 팔 8(ㄹ), 구 9
_DIGIT_KIND = {'0': 2, '1': 1, '2': 0, '3': 2, '4': 0,
               '5': 0, '6': 2, '7': 1, '8': 1, '9': 0}

# 조사 짝: (받침 있을 때, 받침 없을 때)
_PAIRS = [('은', '는'), ('이', '가'), ('을', '를'), ('과', '와'),
          ('으로', '로'), ('이나', '나'), ('이란', '란'), ('이라', '라')]
_FORMS = {}
for _a, _b in _PAIRS:
    _FORMS[_a] = (_a, _b)
    _FORMS[_b] = (_a, _b)

_FULL = {chr(0xFF21 + i): chr(65 + i) for i in range(26)}
_FULL.update({chr(0xFF41 + i): chr(65 + i) for i in range(26)})
_FULL.update({chr(0xFF10 + i): chr(48 + i) for i in range(10)})


def _norm(s):
    return ''.join(_FULL.get(c, c.upper()) for c in s)


def batchim_kind(token):
    """영문/숫자 토큰을 한국어로 읽었을 때의 받침. 0 없음 / 1 ㄹ / 2 그 밖. 모르면 None."""
    t = _norm(token)
    if not t:
        return None
    if t in _WORDS:
        return _WORDS[t]
    if t[-1].isdigit():
        return _DIGIT_KIND[t[-1]]
    if t[-1].isalpha():
        # 약어로 보고 마지막 글자 이름으로 판정
        return _ALPHA_KIND.get(t[-1], 0)
    return None


_TOKEN = re.compile(r'([A-Za-zＡ-Ｚａ-ｚ0-9０-９]+)\s*'
                    r'(으로|이나|이란|이라|은|는|이|가|을|를|과|와|로|나|란|라)'
                    r'(?![A-Za-zＡ-Ｚａ-ｚ0-9０-９가-힣])')


def fix(text):
    """문자열 안의 '영문/숫자 + 조사'를 발음에 맞게 고친다."""
    def rep(m):
        tok, jo = m.group(1), m.group(2)
        k = batchim_kind(tok)
        if k is None or jo not in _FORMS:
            return m.group(0)
        a, b = _FORMS[jo]
        # 「으로/로」는 ㄹ받침도 '로' 쪽이다
        pick = a if (k == 2 or (k == 1 and a != '으로')) else b
        return m.group(0)[:m.end(1) - m.start(0)] + pick
    return _TOKEN.sub(rep, text)
