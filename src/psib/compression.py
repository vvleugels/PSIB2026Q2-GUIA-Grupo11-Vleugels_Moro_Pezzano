"""Educational, self-contained lossless image codecs and RGB-safe JPEG.

PSIC v1: magic, big-endian JSON-header length, JSON header, payload. Headers
carry shape, uint8 dtype, codec and decoding metadata; sizes include all bytes.
"""
import heapq
import json
import struct
import numpy as np
import cv2

MAGIC = b'PSIC\x01'


def _image(image):
    image = np.asarray(image)
    if image.dtype != np.uint8 or image.ndim not in (2, 3) or not image.size:
        raise ValueError('Expected a nonempty uint8 grayscale or RGB image')
    if image.ndim == 3 and image.shape[2] != 3:
        raise ValueError('Expected three RGB channels')
    return image


def _pack(image, codec, payload, **metadata):
    header = json.dumps(dict(shape=list(image.shape), dtype='uint8', codec=codec,
                             **metadata), separators=(',', ':')).encode()
    return MAGIC + struct.pack('>I', len(header)) + header + payload


def encode_lossless(image, codec='huffman'):
    """Encode uint8 image using huffman, rle_horizontal or rle_vertical."""
    image = _image(image)
    if codec == 'huffman':
        counts = np.bincount(image.ravel(), minlength=256)
        heap = [(int(n), i, i) for i, n in enumerate(counts) if n]
        heapq.heapify(heap)
        serial = 256
        while len(heap) > 1:
            a, b = heapq.heappop(heap), heapq.heappop(heap)
            heapq.heappush(heap, (a[0]+b[0], serial, (a[2], b[2])))
            serial += 1
        codes = {}
        def visit(node, bits):
            if isinstance(node, int): codes[node] = bits or '0'
            else:
                visit(node[0], bits+'0'); visit(node[1], bits+'1')
        visit(heap[0][2], '')
        # Pack in bounded chunks rather than materializing an image-sized bit string.
        payload = bytearray(); buffer = 0; pending = 0; bit_count = 0
        for value in image.ravel():
            bits = codes[int(value)]; n = len(bits)
            buffer = (buffer << n) | int(bits, 2); pending += n; bit_count += n
            while pending >= 8:
                pending -= 8; payload.append((buffer >> pending) & 255)
            buffer &= (1 << pending)-1
        if pending: payload.append(buffer << (8-pending))
        return _pack(image, codec, bytes(payload), codes=codes, bit_count=bit_count)
    if codec not in ('rle_horizontal', 'rle_vertical'):
        raise ValueError('Unknown lossless codec')
    planes = image[:, :, None] if image.ndim == 2 else image
    payload = bytearray()
    for channel in range(planes.shape[2]):
        lines = planes[:, :, channel]
        if codec == 'rle_vertical': lines = lines.T
        for line in lines:
            starts = np.r_[0, np.flatnonzero(line[1:] != line[:-1])+1]
            lengths = np.diff(np.r_[starts, len(line)])
            for start, length in zip(starts, lengths):
                payload.extend(struct.pack('>IB', int(length), int(line[start])))
    return _pack(image, codec, bytes(payload))


def decode_lossless(data):
    """Decode PSIC v1 bytes, validating metadata, payload and scanline boundaries."""
    try:
        if data[:5] != MAGIC or len(data) < 9: raise ValueError('Invalid format/version')
        length = struct.unpack('>I', data[5:9])[0]
        if length > len(data)-9: raise ValueError('Truncated header')
        header = json.loads(data[9:9+length]); payload = data[9+length:]
        shape = header['shape']
        if (not isinstance(shape, list) or len(shape) not in (2, 3)
                or any(type(n) is not int or n <= 0 for n in shape)
                or (len(shape) == 3 and shape[2] != 3) or header['dtype'] != 'uint8'):
            raise ValueError('Unsupported shape/dtype')
        size = int(np.prod(shape, dtype=object))
        codec = header['codec']
        if codec == 'huffman':
            codes = {int(k): v for k, v in header['codes'].items()}
            tree = {}
            for symbol, bits in codes.items():
                if not 0 <= symbol <= 255 or not bits or len(bits) > 255 or set(bits)-{'0', '1'}:
                    raise ValueError('Invalid Huffman code')
                node = tree
                for bit in bits:
                    if 'value' in node: raise ValueError('Non-prefix-free code')
                    node = node.setdefault(bit, {})
                if node: raise ValueError('Duplicate/prefix code')
                node['value'] = symbol
            count = header['bit_count']
            if type(count) is not int or count < size or (count+7)//8 != len(payload):
                raise ValueError('Invalid bit count')
            if count % 8 and payload[-1] & ((1 << (8-count % 8))-1):
                raise ValueError('Nonzero padding')
            output = bytearray(); node = tree
            for i in range(count):
                bit = str((payload[i//8] >> (7-i % 8)) & 1)
                if bit not in node: raise ValueError('Invalid code')
                node = node[bit]
                if 'value' in node:
                    output.append(node['value']); node = tree
                    if len(output) > size: raise ValueError('Excess symbols')
            if node is not tree or len(output) != size: raise ValueError('Incomplete payload')
            return np.frombuffer(output, np.uint8).reshape(shape).copy()
        if codec not in ('rle_horizontal', 'rle_vertical') or len(payload) % 5:
            raise ValueError('Invalid codec or RLE payload')
        # Each run contributes at least one sample; prevent impossible allocations.
        if size > (len(payload)//5)*max(shape[:2]): raise ValueError('Truncated RLE data')
        image = np.empty(shape, np.uint8)
        planes = image[:, :, None] if len(shape) == 2 else image
        offset = 0
        for channel in range(planes.shape[2]):
            lines = planes[:, :, channel]
            if codec == 'rle_vertical': lines = lines.T
            for line in lines:
                pos = 0
                while pos < len(line):
                    if offset+5 > len(payload): raise ValueError('Truncated run')
                    n, value = struct.unpack('>IB', payload[offset:offset+5]); offset += 5
                    if n == 0 or pos+n > len(line): raise ValueError('Invalid scanline run')
                    line[pos:pos+n] = value; pos += n
        if offset != len(payload): raise ValueError('Trailing runs')
        return image
    except (KeyError, TypeError, OverflowError, struct.error, UnicodeError) as exc:
        raise ValueError('Malformed compressed image') from exc


def jpeg_roundtrip(image, quality):
    """Return complete JPEG bytes and same-size uint8 decoded RGB/grayscale image."""
    image = _image(image)
    if type(quality) is not int or not 1 <= quality <= 100:
        raise ValueError('JPEG quality must be an integer in 1..100')
    source = cv2.cvtColor(image, cv2.COLOR_RGB2BGR) if image.ndim == 3 else image
    ok, encoded = cv2.imencode('.jpg', source, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok: raise RuntimeError('JPEG encoding failed')
    decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR if image.ndim == 3 else cv2.IMREAD_GRAYSCALE)
    if decoded is None: raise RuntimeError('JPEG decoding failed')
    if image.ndim == 3: decoded = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
    if decoded.shape != image.shape: raise RuntimeError('JPEG changed image dimensions')
    return encoded.tobytes(), decoded
