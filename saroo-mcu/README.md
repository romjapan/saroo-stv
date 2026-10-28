# SAROO MCU patch (STVLOAD / ROMCTL)

English | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

saroo-stv needs two extra commands in the SAROO MCU app (`mcuapp.bin`).
`saroo-stv-mcu.patch` adds them to the official SAROO firmware **v0.9**
(https://github.com/tpunix/SAROO, commit `c31bf61`). It changes `Firm_MCU/Saturn/cdc.h` and
`Firm_MCU/Saturn/saturn_main.c` (71 added lines, nothing removed).

| Command | Code | What it does |
|---|---|---|
| `SSCMD_STVLOAD` | `0x40` | Like `FILERD`, but the destination may reach the full 32 MiB of SDRAM behind CS0. It switches the 16 MiB FMC bank per chunk and restores bank 0 afterwards. |
| `SSCMD_ROMCTL` | `0x41` | `SS_ARG` bit 0 turns CS0 AA24 addressing (FPGA 06 `st_reg_ctrl[12]`) on or off. Returns `ST_CTRL[15:8]`. |

When the menu starts a game (`SSCMD_STARTUP`), AA24 and the bank select are
cleared, so ordinary Saturn games are not affected.

The official FPGA build 06 already supports AA24. The FPGA is not changed.

## Build

```sh
git clone https://github.com/tpunix/SAROO
cd SAROO
git checkout c31bf61
git apply /path/to/saroo-stv/saroo-mcu/saroo-stv-mcu.patch
```

Open `Firm_MCU/ssmaster.uvprojx` in Keil MDK and build the **App** target.
Keep the project settings: **Use MicroLIB** must stay on (without it the MCU
stops at boot and the Saturn hangs at the SEGA logo), and the optimization is
`-Os`. The output is `mcuapp.bin`, about 62 KB, below the 64 KiB ITCM limit.

The patch was checked with ArmClang 6.24 (Keil MDK Community). The result
matches the binary tested on real hardware except for the build date byte.

## Install

1. Back up `/SAROO/mcuapp.bin` on the SD card (the official v0.9 file).
2. Copy the new `mcuapp.bin` to `/SAROO/mcuapp.bin`. It loads at every power
   on, so there is no update step in the menu. Power-cycle the console.
3. Put `BAKUMPR.BIN` (from the saroo-stv build) in `/SAROO/STV/` and the game
   image in `/SAROO/ISO/<name>/`.

To roll back, copy the official `mcuapp.bin` back. The MCU boot loader in
chip flash is never touched.
