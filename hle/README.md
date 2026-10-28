# Native ST-V BIOS replacement (HLE)

`reloc_veneers.s` is a clean SH-2 reimplementation of the ST-V BIOS services
that the games call. It contains no Sega BIOS bytes. The Saturn build
(`tools/build_hle_ram.py`, called by `tools/build_manual_candidate.py`)
assembles this file and relocates it into Low Work RAM.

Standalone build and static checks (needs `sh-elf-as`, `sh-elf-ld`,
`sh-elf-objcopy`, `sh-elf-objdump` and Python 3):

```sh
make test-build       # stv-native-hle.bin + symbol/layout verification
make test-shienryu    # same source with the Shienryu profile
make tests/smpc_smoke.bin tests/smpc_smoke_pressed.bin   # SMPC input test images
make clean
```

Replaced BIOS entries:

| ST-V BIOS entry | Service |
|---:|---|
| `0x0EFC` | VBlank fixed-point clock update |
| `0x0ECC` | signed accumulate/saturate |
| `0x2C64` | memmove |
| `0x2CAC` | memset |
| `0x372C` | channel address |
| `0x3E4E` | packed status test |
| `0x4596` | workspace byte mirror |
| `0x4680` | cart-layout nibble |
| `0x3842` | channel dispatch (selectors 0/10/1/20) |
| `0x4114` | bootstrap game handoff (non-returning) |

The file also provides the resident runtime used after handoff: IRQ
dispatch, handler/vector tables, SMPC pad input and hardware init.
