"""CPK 재패킹 — 교체 파일은 비압축으로 저장하고 나머지는 원본 바이트를 그대로 옮긴다.

무변경 재패킹이 원본과 바이트 단위로 일치해야 한다. 그러려면 함정 둘을 지켜야 한다:
  ① 내용이 같은 파일 여러 개가 같은 FileOffset 을 공유한다 → (원본offset, sha1) 로 묶어 공유를 유지.
  ② ETOC 가 없는 CPK 는 마지막 파일 뒤 정렬 패딩을 파일에 쓰지 않는다 (ContentSize 에는 포함).
"""
import struct, os, hashlib
import cpk as cpklib


def _up(v, a):
    return (v + a - 1) // a * a


def _utf_patch_rows(chunk_payload, updates):
    """@UTF 테이블의 행별(0x50) 정수 칼럼을 제자리 수정. updates: {행번호: {칼럼: 값}}"""
    b = bytearray(chunk_payload)
    t0 = 8
    rows_off, = struct.unpack('>H', b[t0 + 2:t0 + 4])
    str_off, = struct.unpack('>I', b[t0 + 4:t0 + 8])
    ncol, roww, nrow = struct.unpack('>HHI', b[t0 + 16:t0 + 24])
    sizes = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 8, 7: 8, 8: 4, 9: 8, 10: 4, 11: 8}
    fmts = {0: '>B', 1: '>b', 2: '>H', 3: '>h', 4: '>I', 5: '>i', 6: '>Q', 7: '>q'}
    cols, p = [], t0 + 24
    for _ in range(ncol):
        fl = b[p]
        no, = struct.unpack('>I', b[p + 1:p + 5])
        e = b.index(0, t0 + str_off + no)
        name = b[t0 + str_off + no:e].decode()
        p += 5
        if fl & 0xF0 == 0x30:
            p += sizes[fl & 0xF]
        cols.append((name, fl & 0xF0, fl & 0xF))
    for r, vals in updates.items():
        q = t0 + rows_off + r * roww
        for name, st, typ in cols:
            if st != 0x50:
                continue
            if name in vals:
                struct.pack_into(fmts[typ], b, q, vals[name])
            q += sizes[typ]
    return bytes(b)


def _read_chunk(f, off):
    f.seek(off)
    hd = f.read(16)
    sz, = struct.unpack('<Q', hd[8:16])
    return hd, f.read(sz)


def repack(src_path, dst_path, replace, log=print):
    """replace: {'Message/JP_Japanese/Battle/COMMON.msbt': bytes 또는 (CRILAYLA 압축본, 풀린 크기)}"""
    c = cpklib.CPK(src_path)
    hdr, rows = c.hdr, c.rows
    align = hdr['Align']
    content_off = hdr['ContentOffset']
    base = c.base
    names = [((r['DirName'] or '') + '/' + (r['FileName'] or '')).lstrip('/') for r in rows]
    missing = set(replace) - set(names)
    assert not missing, missing

    f = open(src_path, 'rb')
    order = sorted(range(len(rows)), key=lambda i: (rows[i]['FileOffset'], i))

    tmp = dst_path + '.tmp'
    os.makedirs(os.path.dirname(os.path.abspath(dst_path)), exist_ok=True)
    out = open(tmp, 'wb')
    f.seek(0)
    out.write(f.read(content_off))          # 헤더 + TOC + GTOC (뒤에서 패치)
    pos = content_off
    updates = {}
    shared = {}                              # (원본offset, sha1) -> (새offset, size, esize)
    last_end = pos
    for i in order:
        r = rows[i]
        if names[i] in replace:
            data = replace[names[i]]
            if isinstance(data, tuple):          # 압축해서 넣는 파일
                data, esize = data
                size = len(data)
            else:
                size = esize = len(data)
        else:
            f.seek(base + r['FileOffset'])
            data = f.read(r['FileSize'])
            size, esize = r['FileSize'], r['ExtractSize']
        key = (r['FileOffset'], hashlib.sha1(data).digest())
        if key in shared:                    # ① 같은 내용을 공유하던 파일은 계속 공유
            off, size, esize = shared[key]
        else:
            off = pos
            out.write(data)
            pos += len(data)
            last_end = pos
            pos = _up(pos, align)
            out.write(b'\0' * (pos - last_end))
            shared[key] = (off, size, esize)
        updates[i] = dict(FileOffset=off - base, FileSize=size, ExtractSize=esize)
    content_size = pos - content_off

    etoc_off = hdr.get('EtocOffset')
    if etoc_off:
        f.seek(etoc_off)
        out.write(f.read(hdr['EtocSize']))
    else:                                    # ② 꼬리 패딩은 파일에 남기지 않는다
        out.truncate(last_end)
    out.close()

    upd_hdr = {0: dict(ContentSize=content_size)}
    if etoc_off:
        upd_hdr[0]['EtocOffset'] = content_off + content_size
    _, toc_payload = _read_chunk(f, hdr['TocOffset'])
    _, hdr_payload = _read_chunk(f, 0)
    new_toc = _utf_patch_rows(toc_payload, updates)
    new_hdr = _utf_patch_rows(hdr_payload, upd_hdr)
    with open(tmp, 'r+b') as o:
        o.seek(16)
        o.write(new_hdr)
        o.seek(hdr['TocOffset'] + 16)
        o.write(new_toc)
    f.close()
    c.close()
    if os.path.exists(dst_path):
        os.remove(dst_path)
    os.replace(tmp, dst_path)
    log('CPK 작성: %s (%d bytes, 교체 %d개)' % (dst_path, os.path.getsize(dst_path), len(replace)))
    return dst_path


if __name__ == '__main__':
    import sys, extract
    name = sys.argv[1] if len(sys.argv) > 1 else 'pack_031_message'
    src = extract.pack_path(name)
    dst = os.path.join(extract.WORK, 'test', name + '.cpk')
    repack(src, dst, {})
    a, b = open(src, 'rb').read(), open(dst, 'rb').read()
    print('무변경 재패킹:', 'OK (바이트 일치)' if a == b else '불일치 %d vs %d' % (len(a), len(b)))
