# saroo-stv: Sega ST-V games on a Sega Saturn

English | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

saroo-stv runs Sega ST-V arcade games on a real Sega Saturn, using a SAROO
optical drive emulator cartridge. The first title is **Baku Baku Animal**.

Tested on a real Saturn with a SAROO HW 1.3: full speed, with sound,
controller input and correct graphics.

## How it works

- The SAROO FPGA is the official build 06, unmodified. Its AA24 support maps
  the whole 16 MiB MPR ROM into SAROO SDRAM at the original cart addresses.
- The SAROO MCU app (`mcuapp.bin`) needs two extra commands: STVLOAD loads
  the ROM file from SD into SDRAM, and ROMCTL switches the AA24 mapping. It
  is not part of this repository.
- This repository is the Saturn side, a CD loader plus resident runtime
  (`runtime/`). It loads the FPR program and patches the game in RAM,
  checking the original bytes before each patch. A native ST-V BIOS
  replacement (`hle/`) provides the BIOS services, and the runtime maps
  ST-V inputs and sound onto Saturn hardware.

## Legal

This repository contains **no** ST-V or Saturn ROM, BIOS or game data. The
source keeps only short byte signatures (about a dozen bytes each) to check
patch sites before patching. You must supply your own legally obtained files. Generated
images stay in `build/`, which is not committed.

## Requirements

- An `sh-elf` GCC toolchain (`sh-elf-gcc`, `sh-elf-as`, `sh-elf-ld`) and
  Python 3, on Linux or WSL
- `ROMS/`: the Baku Baku ST-V ROM set (`fpr17969.13`, `mpr17970.2`, `mpr17971.3`, `mpr17972.4`, `mpr17973.5`) and the ST-V BIOS
  `stv-jp-20091.bin`
- `SEGA/`: the Saturn disc boot files `sys_sec.bin`, `sys_arej.bin`, `sys_aree.bin`,
  `sys_areu.bin` and `sys_aret.bin`. Copy them from `Firm_Saturn/sega/` in the
  official SAROO repository (https://github.com/tpunix/SAROO). The build stops if any is missing.
- For hardware: SAROO HW 1.3+, official FPGA 06, and an MCU app with the
  STVLOAD/ROMCTL commands

## Build

```sh
python3 tools/build_manual_candidate.py \
  --source hle/reloc_veneers.s \
  --stv-bios ROMS/stv-jp-20091.bin --rom-dir ROMS \
  --descriptor games/bakubaku.json --sega-dir SEGA \
  --loading-screen --saroo-native-rom --saroo-direct \
  --experimental-sound --experimental-sound-pad-yield \
  --output-dir build/hw
```

Outputs:
- `build/hw/game/boot-diag.iso`: the disc image for SAROO. Convert it to
  BIN/CUE if your loader needs that.
- `build/hw/game/BAKUMPR.BIN`: copy this to `/SAROO/STV/` on the SD card.

Add `--saroo-diag` only for debugging. It writes diagnostic dumps to SD every
10 s, and each write stalls the game for about one frame.

## License

MIT, see `LICENSE`.
