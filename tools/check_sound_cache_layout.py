"""Validate experimental cache extents against their actual source arrays."""
import re
from pathlib import Path


def validate(ram, sizes):
    if len(ram) != len(sizes) or not ram:
        raise ValueError('Cache array mismatch')
    ranges = sorted(zip(ram, sizes))
    for base, size in ranges:
        if size <= 0 or base & 3 or size & 3:
            raise ValueError('Invalid aligned extent')
        # 202b0000..202b7fff is boot staging, reused only after runtime's
        # SOUND_BOOT_STAGE_RELEASED handshake. This validator checks geometry.
        allowed = (0x202b0000 <= base < base+size <= 0x202f8000 or
                   0x20256000 <= base < base+size <= 0x2025e000 or
                   0x20274000 <= base < base+size <= 0x2027ff00 or
                   0x202a5000 <= base < base+size <= 0x202aff00)
        if not allowed:
            raise ValueError('Cache outside reserved area or into loader stack')
    if any(a+n > b for (a,n),(b,_) in zip(ranges,ranges[1:])):
        raise ValueError('Overlapping cache extents')
    return sum(sizes)


def arrays(text):
    result = {}
    for name in ('cache_src','cache_ram','cache_size','expected'):
        match = re.search(r'\b'+name+r'\[(\d+)\]\s*=\s*\{([^}]+)\}',text)
        if not match:
            raise ValueError('Missing array '+name)
        values = [int(v.strip(),0) for v in match[2].split(',')]
        if len(values) != int(match[1]):
            raise ValueError('Array length '+name)
        result[name] = values
    if len({len(v) for v in result.values()}) != 1:
        raise ValueError('Array sizes disagree')
    return result


if __name__ == '__main__':
    root=Path(__file__).resolve().parents[1]
    spec=arrays((root/'runtime/sound_cd_dma.c').read_text())
    print('cache bytes:',validate(spec['cache_ram'],spec['cache_size']))
