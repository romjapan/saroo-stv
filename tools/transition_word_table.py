"""Bound the native four-word/8-byte display table through its finish record."""
def extract_table(data):
    if data[:8] != bytes.fromhex('ffff000000000000'):
        raise ValueError('unexpected initial table reset record')
    for offset in range(8, min(len(data), 2048)-7, 8):
        record = data[offset:offset+8]
        if record[6:8] == b'\xff\xff':
            if record != bytes.fromhex('000000000000ffff'):
                raise ValueError('unexpected finish record')
            return data[:offset+8]
    raise ValueError('missing bounded finish record')
