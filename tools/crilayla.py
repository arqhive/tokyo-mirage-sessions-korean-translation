# -*- coding: utf-8 -*-
"""CRILAYLA 압축·해제 — CPK 안 파일을 원본처럼 압축해 넣기 위해(2026-09-27).

교체 파일을 무압축으로 넣으면 pack_030_etc 가 0.73GB → 1.23GB 로 커지고(교체분 124MB → 626MB),
실기(SDCafiine)에서 스플래시 뒤 검은 화면에서 멈췄다. Cemu 에서는 문제없었다.

형식: 'CRILAYLA' + <I 압축 영역 풀린 크기(=전체-0x100)> + <I 비트열 바이트 수> + 비트열 + 앞 0x100 바이트 원문.
  비트열은 바이트 순서를 뒤집어 저장하고, 각 바이트는 MSB 부터 읽는다.
  풀기는 끝에서 앞으로: 0 + 8비트 = 글자 하나, 1 + 13비트(거리-3) + 길이 코드 = 앞서 푼(뒤쪽) 자리에서 복사.
  길이 = 3 + (2비트, 다 1이면 3비트, 다 1이면 5비트, 다 1이면 8비트 반복) 값의 합.
→ 데이터[0x100:] 를 뒤집어 놓고 보면 거리 3~8194, 길이 3 이상인 보통 LZ77 이다.

  compress(data) → bytes 또는 None(0x100 바이트 이하이거나 줄지 않을 때)
  decompress(d)  → bytes
"""
import struct

MIN_D, MAX_D = 3, 8194
MAX_CHAIN = 24
GOOD = 258


def _matchlen(S, j, i, n):
    k = 0
    step = 32
    while i + k + step <= n and S[j + k:j + k + step] == S[i + k:i + k + step]:
        k += step
        if step < 4096:
            step <<= 1
    while i + k < n and S[j + k] == S[i + k]:
        k += 1
    return k


class _Bits:
    def __init__(self):
        self.out = bytearray(); self.acc = 0; self.n = 0

    def put(self, v, w):
        self.acc = (self.acc << w) | v; self.n += w
        while self.n >= 8:
            self.n -= 8
            self.out.append((self.acc >> self.n) & 0xFF)
        self.acc &= (1 << self.n) - 1

    def done(self):
        if self.n:
            self.out.append((self.acc << (8 - self.n)) & 0xFF)
            self.n = 0; self.acc = 0
        return bytes(self.out)


def _put_len(bw, n):
    for L in (2, 3, 5):
        m = (1 << L) - 1
        if n < m:
            bw.put(n, L); return
        bw.put(m, L); n -= m
    while True:
        if n < 255:
            bw.put(n, 8); return
        bw.put(255, 8); n -= 255


def compress(data):
    data = bytes(data)
    if len(data) <= 0x100:
        return None
    S = data[0x100:][::-1]
    n = len(S)
    head = {}
    prev = [-1] * n
    bw = _Bits()
    i = 0
    while i < n:
        best_l = 0; best_d = 0
        if i + 3 <= n:
            key = S[i:i + 3]
            j = head.get(key, -1); chain = 0
            while j >= 0 and i - j <= MAX_D and chain < MAX_CHAIN:
                d = i - j
                if d >= MIN_D and (best_l == 0 or (i + best_l < n and S[j + best_l] == S[i + best_l])):
                    l = _matchlen(S, j, i, n)
                    if l > best_l:
                        best_l, best_d = l, d
                        if l >= GOOD:
                            break
                j = prev[j]; chain += 1
        if best_l >= 3:
            bw.put(1, 1); bw.put(best_d - MIN_D, 13); _put_len(bw, best_l - 3)
            end = i + best_l
            # 긴 일치는 마지막 몇 자리만 사전에 넣는다(한결같은 칸이 많은 텍스처에서 속도)
            k0 = i if best_l < 64 else end - 16
            for k in range(k0, min(end, n - 2)):
                kk = S[k:k + 3]; prev[k] = head.get(kk, -1); head[kk] = k
            i = end
        else:
            bw.put(S[i], 9)             # 0 + 8비트
            if i + 3 <= n:
                prev[i] = head.get(key, -1); head[key] = i
            i += 1
    body = bw.done()[::-1]
    out = b'CRILAYLA' + struct.pack('<II', n, len(body)) + body + data[:0x100]
    return out if len(out) < len(data) else None


def decompress(d):
    assert d[:8] == b'CRILAYLA'
    usize, hsize = struct.unpack('<II', d[8:16])
    out = bytearray(usize + 0x100)
    out[:0x100] = d[16 + hsize:16 + hsize + 0x100]
    src = d[16:16 + hsize][::-1]
    pos = 0; acc = 0; nb = 0

    def get(w):
        nonlocal pos, acc, nb
        while nb < w:
            acc = (acc << 8) | src[pos]; pos += 1; nb += 8
        nb -= w
        v = (acc >> nb) & ((1 << w) - 1)
        acc &= (1 << nb) - 1
        return v
    w = usize - 1 + 0x100
    while w >= 0x100:
        if get(1):
            off = get(13) + 3; ln = 3
            for L in (2, 3, 5):
                v = get(L); ln += v
                if v != (1 << L) - 1:
                    break
            else:
                while True:
                    v = get(8); ln += v
                    if v != 255:
                        break
            for _ in range(ln):
                out[w] = out[w + off]; w -= 1
                if w < 0x100:
                    break
        else:
            out[w] = get(8); w -= 1
    return bytes(out)


def compress_verified(data):
    """압축하고 되풀어 원문과 같은지 확인. 줄지 않으면 b''."""
    z = compress(data)
    if z is None:
        return b''
    if decompress(z) != bytes(data):
        raise ValueError('CRILAYLA 되풀기 불일치')
    return z
