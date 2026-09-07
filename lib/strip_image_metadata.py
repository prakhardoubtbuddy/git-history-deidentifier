import struct
# git-filter-repo --blob-callback body.
#
# WHY THIS EXISTS: --replace-text silently skips BINARY blobs. Git treats a blob as
# binary if there is a NUL byte in the first 8000 bytes, and replace-text then passes
# it through byte-identical -- same blob SHA in, same blob SHA out, no warning and
# nothing in the run summary. So every name and path embedded in an image survives
# every text-based pass. A blob-callback, unlike replace-text, does receive binary.
#
# Image metadata is where a designer's machine ends up on the record: PNG tEXt chunks
# and JPEG APP1/APP13 segments routinely carry the absolute source path of the .psd
# it was exported from -- drive letter, user account, and often ANOTHER client's
# project name when a file was reused between jobs.
#
# DO NOT "fix" this by pattern-replacing bytes inside an image. Compressed pixel data
# is effectively random, so a path-shaped regex matches inside it by coincidence and
# corrupts the picture. Same length, still opens, wrong image -- only a before/after
# comparison catches it. Parse the container and drop whole metadata sections instead:
# every other byte is copied through untouched, so the image cannot be damaged.
d = blob.data
new = None

if d.startswith(b'\x89PNG\r\n\x1a\n'):
    out = bytearray(d[:8])
    i, hit = 8, False
    while i + 8 <= len(d):
        ln = struct.unpack('>I', d[i:i + 4])[0]
        typ = d[i + 4:i + 8]
        if typ in (b'tEXt', b'iTXt', b'zTXt', b'eXIf'):
            hit = True                      # drop: text/EXIF metadata only
        else:
            out += d[i:i + 12 + ln]         # keep: IHDR, PLTE, IDAT, IEND, colour profile
        i += 12 + ln
        if typ == b'IEND':
            break
    if hit:
        new = bytes(out)

elif d[:2] == b'\xff\xd8':
    out = bytearray(b'\xff\xd8')
    i, hit = 2, False
    while i + 4 <= len(d):
        if d[i] != 0xFF:
            out += d[i:]
            break
        marker = d[i + 1]
        if marker == 0xDA:                  # start of scan: image data to EOF
            out += d[i:]
            break
        ln = struct.unpack('>H', d[i + 2:i + 4])[0]
        if marker in (0xE1, 0xED):          # APP1 = EXIF/XMP, APP13 = Photoshop IRB
            hit = True
        else:
            out += d[i:i + 2 + ln]          # keep JFIF, quantisation, Huffman, frame
        i += 2 + ln
    if hit:
        new = bytes(out)

if new is not None and new != d:
    blob.data = new
