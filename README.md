# saroo-stv: Sega ST-V games on a Sega Saturn

English | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

saroo-stv runs Sega ST-V arcade games on a real Sega Saturn, using a SAROO
optical drive emulator cartridge. Supported games are listed below.

Baku Baku Animal was tested on a real Saturn with a SAROO HW 1.3: full speed, with sound,
controller input and correct graphics.

## Supported games

| Game | Real hardware status |
| --- | --- |
| Baku Baku Animal | Works on real hardware: full speed, sound, controller input and correct graphics. |
| Karaoke Quiz Intro Don Don! | Works on real hardware: correct graphics, controls, answers, TEST menu and saves that persist across power-off. Known issue: music volume sometimes changes during a song; cause not yet found. |

## How it works

- The SAROO FPGA is the official build 06, unmodified. Its AA24 support maps
  the resident ROM image (16 MiB for Baku Baku, 26 MiB for Introdon) into SAROO SDRAM at the original cart addresses.
- The SAROO MCU app (`mcuapp.bin`) needs two extra commands: STVLOAD loads
  the ROM file from SD into SDRAM, and ROMCTL switches the AA24 mapping.
  `saroo-mcu/` has the patch for the official SAROO v0.9 source.
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
  Python 3 and `xorriso`, on Linux or WSL
- `ROMS/`: the Baku Baku ST-V ROM set (`fpr17969.13`, `mpr17970.2`, `mpr17971.3`, `mpr17972.4`, `mpr17973.5`) and the ST-V BIOS
  `stv-jp-20091.bin`
- `SEGA/`: the Saturn disc boot files `sys_sec.bin`, `sys_arej.bin`, `sys_aree.bin`,
  `sys_areu.bin` and `sys_aret.bin`. Copy them from `Firm_Saturn/sega/` in the
  official SAROO repository (https://github.com/tpunix/SAROO). The build stops if any is missing.
- For hardware: SAROO HW 1.3+, official FPGA 06, and an MCU app built with
  `saroo-mcu/saroo-stv-mcu.patch` (see `saroo-mcu/README.md`)

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

## Introdon

`ROMS/`: `epr18937.13`, `mpr18944.7`, `mpr18939.2`, `mpr18940.3`, `mpr18941.4`, `mpr18942.5`, `mpr18943.6`, `mpr18938.1` + `stv-jp-20091.bin`. `SEGA/`: same boot files as above.

```sh
python3 tools/build_manual_candidate.py \
  --source hle/reloc_veneers.s \
  --stv-bios ROMS/stv-jp-20091.bin --rom-dir ROMS \
  --descriptor games/introdon.json --sega-dir SEGA \
  --loading-screen --saroo-native-rom --saroo-direct \
  --output-dir build/introdon
```

| Game | Resident image | Size | SDRAM |
| --- | --- | --- | --- |
| Baku Baku | `SAROO/STV/BAKUMPR.BIN` | 16 MiB | `0x400000` |
| Introdon | `SAROO/STV/INTRODON.BIN` | 26 MiB (27,262,976 bytes) | `0x200000` |

Introdon ISO: `build/introdon/game/boot-diag.iso`. Resident image: `build/introdon/game/INTRODON.BIN`.

| Saturn control | Introdon action |
| --- | --- |
| L | Insert coin |
| Start | Start game |
| A / B / C / X | Answers 1 / 2 / 3 / 4 |
| Console RESET | TEST menu; select the current item in the menu |
| R | SERVICE; move to the next item in the TEST menu |
| Hold A+B+C+Start for about 2 seconds | Save and return to the SAROO menu |

### TEST menu

On the title/attract screen, tap console RESET briefly (about 0.2–0.3 seconds)
to enter. Wait at least 1 second between RESET taps; holding RESET does not
repeat. R moves to the next item; RESET selects/confirms. This is the
cartridge's own test menu, not the ST-V BIOS system test.

| Menu item | Function |
| --- | --- |
| INPUT TEST | Input test entry; detailed operation has not been verified. |
| SOUND TEST | Sound playback test. |
| GAME ASSIGNMENTS | Change game settings, such as difficulty EASY/NORMAL. |
| BACKUP DATA CLEAR | Clear saved game data. **Erases settings and records; use with care.** |
| QUIZ TEST | Quiz test entry; detailed operation has not been verified. |
| EXIT | Leave the test menu and return to the game. |

Verified example, starting with INPUT TEST selected and difficulty EASY:
press R twice to reach GAME ASSIGNMENTS → RESET to enter → RESET to change
EASY to NORMAL → R twice to the sub-page EXIT → RESET → R three times to
the main EXIT → RESET to return to the game. Wait about 5 seconds after returning.

Settings and records are saved automatically to Saturn internal memory as
`INTRODONP12` (about 476 bytes) and survive power-off. Changes during a running
game are saved when it ends or returns to attract; otherwise, saving occurs
after changes settle. Holding A+B+C+Start for about 2 seconds also attempts to
save before returning to the SAROO menu. If internal memory is full, unformatted or unavailable,
the game continues, but changes may not be saved. The game never formats memory
or deletes other games' saves.

## License

MIT, see `LICENSE`.
