# -*- coding: utf-8 -*-
"""일본판 USM 영상에 한글 자막을 구워 넣고 같은 구조의 USM 으로 다시 포장한다.

  python usm_burn.py <영상이름> <자막.srt> <출력.usm>

원본 구조(Sofdec2, 영상 MPEG-1):
  CRID(@UTF: 파일·스트림 정보) → @SFV 헤더(VIDEO_HDRINFO) → #HEADER END
  → @SFV 메타(VIDEO_SEEKINFO: 키프레임 청크의 파일 오프셋) → #METADATA END
  → 데이터 청크(프레임 하나당 하나, 디코딩 순서, 32바이트 정렬) … → #CONTENTS END
  (음성이 있으면 @SFA 청크가 영상 청크 사이에 섞여 있다 — 그대로 옮긴다)

다시 포장할 때:
  · 헤더 영역은 원본을 복사하고 @UTF 의 숫자만 고친다(filesize, minbuf, avbps, ixsize, ofs_byte).
    헤더 크기가 변하지 않아 첫 데이터 청크 위치도 원본과 같다.
  · 영상 청크의 시각(time/rate)은 원본 값을 그대로 쓴다. 프레임 수·키프레임 위치를 원본과 똑같이 맞춰 인코딩한다.
"""
import os, sys, struct, subprocess, tempfile
import extract, usm_frames
from cpk import read_utf

FF = usm_frames.FFMPEG
FP = FF.replace('ffmpeg.exe', 'ffprobe.exe')
FONTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fonts', 'subtitle')


# ── USM 청크 ─────────────────────────────────────────────────────────
def chunks(b):
    out, pos = [], 0
    while pos + 32 <= len(b):
        sig = b[pos:pos + 4]
        size = struct.unpack('>I', b[pos + 4:pos + 8])[0]
        if size == 0:
            break
        hs = b[pos + 9]
        fs = struct.unpack('>H', b[pos + 10:pos + 12])[0]
        typ = b[pos + 15]
        out.append(dict(pos=pos, sig=sig, size=size, hs=hs, fs=fs, typ=typ,
                        hdr=b[pos + 8:pos + 8 + hs], payload=b[pos + 8 + hs:pos + 8 + size - fs]))
        pos += 8 + size
    return out


def make_chunk(sig, hdr, payload):
    """hdr(24바이트)의 패딩 필드를 새로 계산해 32바이트 정렬 청크를 만든다."""
    hs = len(hdr)
    body = hs + len(payload)
    pad = (-(8 + body)) % 32
    h = bytearray(hdr)
    h[2:4] = struct.pack('>H', pad)
    size = body + pad
    return sig + struct.pack('>I', size) + bytes(h) + payload + b'\0' * pad


# ── @UTF 숫자 고치기(제자리) ──────────────────────────────────────────
def utf_offsets(buf):
    """(행, 열이름) → (버퍼 안 절대 오프셋, struct 형식) 사전."""
    size = struct.unpack('>I', buf[4:8])[0]
    t0 = 8
    t = buf[8:8 + size]
    _, rows_off = struct.unpack('>HH', t[0:4])
    str_off, data_off, name_off = struct.unpack('>III', t[4:16])
    ncol, roww, nrow = struct.unpack('>HHI', t[16:24])

    def cstr(o):
        o += str_off
        e = t.index(b'\0', o)
        return t[o:e].decode('utf-8', 'replace')
    fmts = {0: '>B', 1: '>b', 2: '>H', 3: '>h', 4: '>I', 5: '>i', 6: '>Q', 7: '>q', 8: '>f', 9: '>d', 0xA: '>I', 0xB: '>II'}
    cols, p = [], 24
    for _ in range(ncol):
        flag = t[p]; nm = cstr(struct.unpack('>I', t[p + 1:p + 5])[0]); p += 5
        st, typ = flag & 0xF0, flag & 0x0F
        if st == 0x30:
            p += struct.calcsize(fmts[typ])
        cols.append((nm, st, typ))
    offs, p = {}, rows_off
    for r in range(nrow):
        for nm, st, typ in cols:
            if st == 0x50:
                offs[(r, nm)] = (t0 + p, fmts[typ])
                p += struct.calcsize(fmts[typ])
    return offs


def utf_patch(buf, patches):
    buf = bytearray(buf)
    offs = utf_offsets(bytes(buf))
    for key, val in patches.items():
        o, f = offs[key]
        buf[o:o + struct.calcsize(f)] = struct.pack(f, val)
    return bytes(buf)


# ── MPEG-1 영상 → 프레임 단위 조각 ──────────────────────────────────
def split_pictures(es):
    """코딩 순서의 그림 단위로 자른다. 시퀀스·GOP 헤더는 뒤따르는 그림에 붙인다."""
    starts = []
    i = 0
    while True:
        i = es.find(b'\x00\x00\x01', i)
        if i < 0:
            break
        code = es[i + 3]
        if code in (0x00, 0xB3, 0xB8):
            starts.append((i, code))
        i += 3
    pics, cur = [], None
    for k, (i, code) in enumerate(starts):
        if cur is None:
            cur = i
        if code == 0x00:
            nxt = starts[k + 1][0] if k + 1 < len(starts) else len(es)
            # 다음 그림 앞의 시퀀스/GOP 헤더는 다음 조각으로 넘긴다
            j = k + 1
            end = nxt
            pics.append(es[cur:end]); cur = None
    return pics


def pict_type(p):
    i = p.find(b'\x00\x00\x01\x00')
    return 'xIPBD'[(p[i + 5] >> 3) & 7]


# ── 인코딩 ───────────────────────────────────────────────────────────
def encode(es_in, srt, frames, workdir, keys=None, q=2):
    src = os.path.join(workdir, 'in.m1v'); open(src, 'wb').write(es_in)
    dst = os.path.join(workdir, 'out.m1v')
    vf = "subtitles=%s:fontsdir=%s:force_style='FontName=NanumSquareRound ExtraBold,FontSize=22,Outline=2,Shadow=0,MarginV=28'" % (
        os.path.basename(srt), os.path.relpath(FONTDIR, workdir).replace('\\', '/'))
    import shutil
    shutil.copy(srt, os.path.join(workdir, os.path.basename(srt)))
    # 원본의 I프레임 위치(장면 전환마다 추가된 것 포함)에 키프레임을 강제한다.
    # 닫힌 GOP 라 코딩 순서의 I 위치 = 표시 순서의 I 위치다.
    kf = []
    if keys:
        # k/30 초로 주면 반올림 때문에 다음 프레임에 걸린다 → 반 프레임 앞당겨 지정
        kf = ['-force_key_frames', ','.join('%.6f' % (max(0.0, (k - 0.5) / 30.0)) for k in keys)]
    cmd = [FF, '-y', '-r', '30', '-i', 'in.m1v', '-vf', vf,
           '-c:v', 'mpeg1video', '-r', '30', '-g', '100000', '-bf', '2', '-b_strategy', '0', '-flags', '+cgop',
           '-sc_threshold', '1000000000'] + kf + ['-q:v', str(q), '-qmin', '1',
           '-maxrate', '30M', '-bufsize', '4864k', '-frames:v', str(frames), 'out.m1v']
    r = subprocess.run(cmd, cwd=workdir, capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode('utf-8', 'ignore')[-800:])
    return open(dst, 'rb').read()


# ── 다시 포장 ────────────────────────────────────────────────────────
def rebuild(orig, new_pics):
    cs = chunks(orig)
    vdata = [c for c in cs if c['sig'] == b'@SFV' and c['typ'] == 0]
    assert len(vdata) == len(new_pics), '프레임 수가 다르다: 원본 %d / 새 %d' % (len(vdata), len(new_pics))
    ia = [i for i, a in enumerate(vdata) if pict_type(a['payload']) == 'I']
    ib = [i for i, b in enumerate(new_pics) if pict_type(b) == 'I']
    assert ia == ib, 'I프레임 위치가 원본과 다르다 (원본 %d개 / 새 %d개)' % (len(ia), len(ib))
    out = bytearray()
    vi = 0
    seek_chunk = None
    key_offsets = []
    for c in cs:
        if c['sig'] == b'@SFV' and c['typ'] == 0:
            if pict_type(new_pics[vi]) == 'I':
                key_offsets.append(len(out))
            out += make_chunk(c['sig'], c['hdr'], new_pics[vi]); vi += 1
        else:
            if c['sig'] == b'@SFV' and c['typ'] == 3:
                seek_chunk = (len(out), c)
            out += orig[c['pos']:c['pos'] + 8 + c['size']]
    # 헤더 숫자 고치기
    new_chunks = chunks(bytes(out))
    vnew = [c for c in new_chunks if c['sig'] == b'@SFV' and c['typ'] == 0]
    total_payload = sum(len(c['payload']) for c in vnew)
    max_payload = max(len(c['payload']) for c in vnew)
    max_chunk = max(8 + c['size'] for c in vnew)
    frames = len(vnew)
    crid = new_chunks[0]
    _, crid_rows = read_utf(crid['payload'])
    fps = 30.0
    avbps = int(round(total_payload * 8 * fps / frames))
    old_ix = max(8 + c['size'] for c in chunks(orig) if c['sig'] == b'@SFV' and c['typ'] == 0)
    minbuf0 = crid_rows[0]['minbuf'] + max(0, max_chunk - old_ix)
    patched = utf_patch(crid['payload'], {
        (0, 'filesize'): len(out), (0, 'avbps'): avbps, (0, 'minbuf'): minbuf0,
        (1, 'filesize'): total_payload, (1, 'avbps'): avbps, (1, 'minbuf'): max_payload,
    })
    o = crid['pos'] + 8 + crid['hs']
    out[o:o + len(patched)] = patched
    hdr = [c for c in new_chunks if c['sig'] == b'@SFV' and c['typ'] == 1][0]
    patched = utf_patch(hdr['payload'], {(0, 'ixsize'): max_chunk})
    o = hdr['pos'] + 8 + hdr['hs']
    out[o:o + len(patched)] = patched
    # 키프레임 위치표
    sk = [c for c in new_chunks if c['sig'] == b'@SFV' and c['typ'] == 3][0]
    _, rows = read_utf(sk['payload'])
    assert len(rows) == len(key_offsets), '키프레임 수가 다르다 %d/%d' % (len(rows), len(key_offsets))
    patched = utf_patch(sk['payload'], {(i, 'ofs_byte'): key_offsets[i] for i in range(len(rows))})
    o = sk['pos'] + 8 + sk['hs']
    out[o:o + len(patched)] = patched
    info = dict(frames=frames, filesize=len(out), payload=total_payload, max_chunk=max_chunk,
                old_max_chunk=old_ix, avbps=avbps, keyframes=len(key_offsets))
    return bytes(out), info


def main(stem, srt, out_path, pack='pack_050_movie', q=2):
    c = extract.open_pack(pack)
    name = [f['name'] for f in c.files if os.path.basename(f['name']) == stem + '.usm'][0]
    orig = c.read(name)
    es = usm_frames.video_es(orig)
    vch = [x for x in chunks(orig) if x['sig'] == b'@SFV' and x['typ'] == 0]
    frames = len(vch)
    keys = [i for i, x in enumerate(vch) if pict_type(x['payload']) == 'I']
    work = tempfile.mkdtemp(prefix='usm_')
    new_es = encode(es, os.path.abspath(srt), frames, work, keys, q)
    pics = split_pictures(new_es)
    data, info = rebuild(orig, pics)
    open(out_path, 'wb').write(data)
    print(stem, info)
    return info


if __name__ == '__main__':
    main(*sys.argv[1:4])
