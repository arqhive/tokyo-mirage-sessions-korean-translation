"""범용 GTX 디코더 (tileMode 4 = 2D tiled thin1).

gtx_lib 은 BC1/BC3/BC4/BC5 의 블록 스위즐만 다룬다. TMS 의 Interface 텍스처는
RGBA8(0x1a) 이 가장 많고 BC2(0x32), SRGB BC1(0x431) 도 섞여 있어 bpp 별 주소 계산이 필요하다.
addrlib 의 computeSurfaceAddrFromCoordMacroTiled 를 numpy 로 옮겼다(`_addr_np` 가 원본과 대조 검증됨).
"""
import numpy as np
import struct
import addrlib, gtx_lib

_map_cache = {}


def _addr_np(w, h, bpp, pitch, height, swizzle_):
    """(h, w) 좌표별 저장 바이트 오프셋. tileMode 4, numSamples=1 고정."""
    y, x = np.mgrid[0:h, 0:w]
    y = y.astype(np.int64); x = x.astype(np.int64)

    # computePixelIndexWithinMicroTile
    if bpp == 8:
        pix = (32 * ((y & 4) >> 2) | 16 * (y & 1) | 8 * ((y & 2) >> 1) |
               4 * ((x & 4) >> 2) | 2 * ((x & 2) >> 1) | (x & 1))
    elif bpp == 16:
        pix = (32 * ((y & 4) >> 2) | 16 * ((y & 2) >> 1) | 8 * (y & 1) |
               4 * ((x & 4) >> 2) | 2 * ((x & 2) >> 1) | (x & 1))
    elif bpp in (32, 96):
        pix = (32 * ((y & 4) >> 2) | 16 * ((y & 2) >> 1) | 8 * ((x & 4) >> 2) |
               4 * (y & 1) | 2 * ((x & 2) >> 1) | (x & 1))
    elif bpp == 64:
        pix = (32 * ((y & 4) >> 2) | 16 * ((y & 2) >> 1) | 8 * ((x & 4) >> 2) |
               4 * ((x & 2) >> 1) | 2 * (y & 1) | (x & 1))
    elif bpp == 128:
        pix = (32 * ((y & 4) >> 2) | 16 * ((y & 2) >> 1) | 8 * ((x & 4) >> 2) |
               4 * ((x & 2) >> 1) | 2 * (x & 1) | (y & 1))
    else:
        pix = (32 * ((y & 4) >> 2) | 16 * ((y & 2) >> 1) | 8 * ((x & 4) >> 2) |
               4 * (y & 1) | 2 * ((x & 2) >> 1) | (x & 1))

    elem_off = (bpp * pix) // 8

    pipe = ((y >> 3) ^ (x >> 3)) & 1
    bank = (((y >> 5) ^ (x >> 3)) & 1) | 2 * (((y >> 4) ^ (x >> 4)) & 1)
    pipe_sw = (swizzle_ >> 8) & 1
    bank_sw = (swizzle_ >> 9) & 3
    bank_pipe = ((pipe + 2 * bank) ^ (pipe_sw + 2 * bank_sw)) % 8
    pipe = bank_pipe % 2
    bank = bank_pipe // 2

    macro_tiles_per_row = pitch // 32
    macro_tile_bytes = (bpp * 16 * 32) // 8
    macro_off = ((x // 32) + macro_tiles_per_row * (y // 16)) * macro_tile_bytes

    total = elem_off + (macro_off >> 3)
    return (bank << 9) | (pipe << 8) | (255 & total) | ((total & -256) << 3)


def addr_map(w, h, bpp, pitch, height, swizzle_):
    key = (w, h, bpp, pitch, height, swizzle_)
    m = _map_cache.get(key)
    if m is None:
        m = _map_cache[key] = _addr_np(w, h, bpp, pitch, height, swizzle_)
    return m


BCN = {0x31, 0x32, 0x33, 0x34, 0x35}


def _bc2_decode(blk):
    """BC2 (DXT3): 명시적 4bit 알파 8바이트 + BC1 컬러 8바이트 -> RGBA"""
    bh, bw, _ = blk.shape
    rgb = gtx_lib.bc1_decode_blocks(np.ascontiguousarray(blk[:, :, 8:16]))
    a = blk[:, :, 0:8].astype(np.uint64)
    bits = np.zeros((bh, bw), np.uint64)
    for i in range(8):
        bits |= a[:, :, i] << np.uint64(8 * i)
    idx = np.stack([((bits >> np.uint64(4 * k)) & np.uint64(0xF)).astype(np.uint8) for k in range(16)], -1)
    alpha = (idx * 17).reshape(bh, bw, 4, 4).transpose(0, 2, 1, 3).reshape(bh * 4, bw * 4)
    return np.dstack([rgb, alpha])


def decode(data):
    """GTX 바이트 -> (RGBA uint8 (h, w, 4), info).  알파가 없으면 255 로 채운다."""
    info = gtx_lib.gtx_parse(data)
    s = info['surf']
    if s['tileMode'] != 4:
        raise NotImplementedError('tileMode %d' % s['tileMode'])
    fmt = s['format'] & 0x3F
    bpp = addrlib.surfaceGetBitsPerPixel(s['format'])
    raw = data[info['img_blk']['data']:info['img_blk']['data'] + info['img_blk']['size']]
    W, H = s['width'], s['height']
    pitch = s['pitch']
    if fmt in BCN:
        w, h = (W + 3) // 4, (H + 3) // 4
        height = s['height'] // 4
    else:
        w, h = W, H
        height = s['height']
    m = addr_map(w, h, bpp, pitch, height, s['swizzle'])
    bpe = bpp // 8
    need = int(m.max()) + bpe
    buf = np.frombuffer(raw, np.uint8)
    if len(buf) < need:
        buf = np.concatenate([buf, np.zeros(need - len(buf), np.uint8)])
    idx = m[..., None] + np.arange(bpe)
    lin = buf[idx]                                  # (h, w, bpe)

    if fmt == 0x1A:                                 # RGBA8
        return lin[:H, :W, :4].copy(), info
    if fmt == 0x31:                                 # BC1
        rgb = gtx_lib.bc1_decode_blocks(np.ascontiguousarray(lin))[:H, :W]
        return np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)]), info
    if fmt == 0x32:                                 # BC2
        return _bc2_decode(lin)[:H, :W], info
    if fmt == 0x33:                                 # BC3
        a = gtx_lib.bc4_decode_blocks(np.ascontiguousarray(lin[:, :, 0:8]))
        rgb = gtx_lib.bc1_decode_blocks(np.ascontiguousarray(lin[:, :, 8:16]))
        return np.dstack([rgb, a])[:H, :W], info
    if fmt == 0x34:                                 # BC4 (1채널)
        g = gtx_lib.bc4_decode_blocks(np.ascontiguousarray(lin))[:H, :W]
        return np.dstack([g, g, g, np.full(g.shape, 255, np.uint8)]), info
    if fmt == 0x35:                                 # BC5 (2채널)
        r = gtx_lib.bc4_decode_blocks(np.ascontiguousarray(lin[:, :, 0:8]))[:H, :W]
        g = gtx_lib.bc4_decode_blocks(np.ascontiguousarray(lin[:, :, 8:16]))[:H, :W]
        z = np.zeros_like(r)
        return np.dstack([r, g, z, np.full(r.shape, 255, np.uint8)]), info
    raise NotImplementedError('format 0x%x' % s['format'])


def encode(rgba, orig):
    """원본 GTX 의 헤더·블록을 그대로 두고 이미지 데이터만 갈아끼운다 (RGBA8 전용, 무손실).

    TMS 의 UI 텍스처는 전부 RGBA8(0x1a) / tileMode 4 / 밉맵 없음 / 무압축이라
    스위즐만 역방향으로 하면 된다.
    """
    info = gtx_lib.gtx_parse(orig)
    s = info['surf']
    fmt = s['format'] & 0x3F
    if fmt != 0x1A:
        raise NotImplementedError('RGBA8 만 교체할 수 있다 (format %#x)' % s['format'])
    if s['tileMode'] != 4:
        raise NotImplementedError('tileMode %d' % s['tileMode'])
    H, W = rgba.shape[:2]
    if (W, H) != (s['width'], s['height']):
        raise ValueError('크기가 다르다: %dx%d vs %dx%d' % (W, H, s['width'], s['height']))

    m = addr_map(W, H, 32, s['pitch'], H, s['swizzle'])
    blk = info['img_blk']
    size = blk['size']
    buf = np.frombuffer(orig[blk['data']:blk['data'] + size], np.uint8).copy()
    idx = m[..., None] + np.arange(4)
    flat = idx.reshape(-1)
    keep = flat < size
    buf[flat[keep]] = rgba[..., :4].reshape(-1)[keep]
    return orig[:blk['data']] + buf.tobytes() + orig[blk['data'] + size:]


def _selftest():
    """numpy 주소 계산이 addrlib 원본과 같은지 확인."""
    import random
    random.seed(0)
    ok = True
    for bpp in (32, 64, 128):
        for swz in (0, 0x100, 0x200, 0x700):
            w, h, pitch = 64, 32, 64
            m = _addr_np(w, h, bpp, pitch, h, swz)
            for _ in range(40):
                x = random.randrange(w); y = random.randrange(h)
                want = addrlib.computeSurfaceAddrFromCoordMacroTiled(
                    x, y, bpp, pitch, h, 4, (swz >> 8) & 1, (swz >> 9) & 3)
                if int(m[y, x]) != want:
                    print('불일치 bpp=%d swz=%#x (%d,%d): %d vs %d' % (bpp, swz, x, y, m[y, x], want))
                    ok = False
    print('주소 계산 대조:', 'OK' if ok else '실패')
    return ok


if __name__ == '__main__':
    _selftest()
