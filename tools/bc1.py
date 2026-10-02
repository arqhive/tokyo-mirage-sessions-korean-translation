# -*- coding: utf-8 -*-
"""GTX BC1(SRGB 포함, format 0x31/0x431) 인코더 — 바뀐 4x4 블록만 다시 압축한다.

안 바뀐 블록은 원본 8바이트를 그대로 둔다(글자 밖은 비트 단위로 원본과 같다).
블록 압축: 주성분 축으로 두 끝점 → 565 양자화 → 인덱스 배정 → 최소제곱으로 끝점 다듬기(2회).
BC1 규격상 c0 <= c1 이면 3색+투명 모드가 되므로 항상 c0 > c1 로 맞춘다(같으면 전부 인덱스 0).
"""
import os, sys
import numpy as np




import gtx_lib, gtx2, addrlib


def _to565(c):
    c = np.clip(np.round(c), 0, 255).astype(np.int32)
    return ((c[..., 0] * 31 + 127) // 255 << 11) | ((c[..., 1] * 63 + 127) // 255 << 5) | ((c[..., 2] * 31 + 127) // 255)


def _from565(v):
    r = (v >> 11) & 31; g = (v >> 5) & 63; b = v & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.int32)


def _palette(c0, c1):
    p0, p1 = _from565(c0), _from565(c1)
    return np.stack([p0, p1, (2 * p0 + p1) // 3, (p0 + 2 * p1) // 3], axis=-2)   # (..., 4, 3)


def _assign(px, pal):
    d = ((px[..., :, None, :] - pal[..., None, :, :]) ** 2).sum(-1)              # (n,16,4)
    idx = d.argmin(-1)
    err = np.take_along_axis(d, idx[..., None], -1)[..., 0].sum(-1)
    return idx, err


def encode_blocks(px):
    """px: (n, 16, 3) float RGB → (n, 8) uint8 BC1 블록."""
    n = px.shape[0]
    mean = px.mean(1, keepdims=True)
    d = px - mean
    cov = np.einsum('nki,nkj->nij', d, d)
    v = np.ones((n, 3))
    for _ in range(8):
        v = np.einsum('nij,nj->ni', cov, v)
        v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
    t = np.einsum('nki,ni->nk', d, v)
    tmin, tmax = t.min(1), t.max(1)
    inset = (tmax - tmin) / 16.0
    e0 = mean[:, 0] + (tmax - inset)[:, None] * v
    e1 = mean[:, 0] + (tmin + inset)[:, None] * v
    best_c0, best_c1 = _to565(e0), _to565(e1)
    best_idx, best_err = _assign(px, _palette(best_c0, best_c1))
    W = np.array([[1, 0], [0, 1], [2 / 3, 1 / 3], [1 / 3, 2 / 3]])
    idx = best_idx
    for _ in range(2):                                   # 인덱스 고정 → 끝점 최소제곱
        A = W[idx]                                       # (n,16,2)
        AtA = np.einsum('nki,nkj->nij', A, A) + np.eye(2) * 1e-6
        Atb = np.einsum('nki,nkc->nic', A, px)
        E = np.linalg.solve(AtA, Atb)                    # (n,2,3)
        c0, c1 = _to565(E[:, 0]), _to565(E[:, 1])
        idx2, err2 = _assign(px, _palette(c0, c1))
        better = err2 < best_err
        best_c0 = np.where(better, c0, best_c0); best_c1 = np.where(better, c1, best_c1)
        best_idx = np.where(better[:, None], idx2, best_idx); best_err = np.where(better, err2, best_err)
        idx = best_idx
    c0, c1, idx = best_c0.copy(), best_c1.copy(), best_idx.copy()
    # 4색 모드 보장: c0 > c1
    sw = c0 < c1
    c0[sw], c1[sw] = best_c1[sw], best_c0[sw]
    remap = np.array([1, 0, 3, 2])
    idx[sw] = remap[idx[sw]]
    eq = c0 == c1
    idx[eq] = 0
    bits = np.zeros(n, np.int64)
    for k in range(16):
        bits |= idx[:, k].astype(np.int64) << (2 * k)
    out = np.zeros((n, 8), np.uint8)
    out[:, 0] = c0 & 255; out[:, 1] = c0 >> 8; out[:, 2] = c1 & 255; out[:, 3] = c1 >> 8
    for k in range(4):
        out[:, 4 + k] = (bits >> (8 * k)) & 255
    return out


def encode(rgb_new, orig_gtx):
    """원본 GTX(BC1) 에서, 디코드 결과가 달라진 블록만 새로 압축해 넣은 GTX 바이트를 돌려준다."""
    info = gtx_lib.gtx_parse(orig_gtx)
    s = info['surf']
    if (s['format'] & 0x3F) != 0x31 or s['tileMode'] != 4:
        raise NotImplementedError('BC1/tileMode4 만 (format %#x)' % s['format'])
    old, _ = gtx2.decode(orig_gtx)
    H, W = s['height'], s['width']
    bh, bw = (H + 3) // 4, (W + 3) // 4
    blk = info['img_blk']
    buf = np.frombuffer(orig_gtx[blk['data']:blk['data'] + blk['size']], np.uint8).copy()
    bpp = addrlib.surfaceGetBitsPerPixel(s['format'])
    m = gtx2.addr_map(bw, bh, bpp, s['pitch'], s['height'] // 4, s['swizzle'])
    a = old[..., :3].reshape(bh, 4, bw, 4, 3).transpose(0, 2, 1, 3, 4).reshape(bh, bw, 16, 3)
    b = rgb_new[..., :3].reshape(bh, 4, bw, 4, 3).transpose(0, 2, 1, 3, 4).reshape(bh, bw, 16, 3)
    changed = np.any(a != b, axis=(2, 3))
    ys, xs = np.nonzero(changed)
    if len(ys):
        enc = encode_blocks(b[ys, xs].astype(np.float64))
        for k in range(8):
            buf[m[ys, xs] + k] = enc[:, k]
    out = orig_gtx[:blk['data']] + buf.tobytes() + orig_gtx[blk['data'] + blk['size']:]
    return out, int(changed.sum())


def selftest(gtx_bytes):
    """원본 전체를 다시 압축해 원본 디코드와의 PSNR 을 잰다(인코더 품질 확인용)."""
    old, _ = gtx2.decode(gtx_bytes)
    H, W = old.shape[:2]
    bh, bw = H // 4, W // 4
    px = old[..., :3].reshape(bh, 4, bw, 4, 3).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 3).astype(np.float64)
    enc = encode_blocks(px)
    dec = gtx_lib.bc1_decode_blocks(enc.reshape(bh, bw, 8))
    mse = ((dec.astype(float) - old[..., :3].astype(float)) ** 2).mean()
    return 10 * np.log10(255 ** 2 / max(mse, 1e-9))
