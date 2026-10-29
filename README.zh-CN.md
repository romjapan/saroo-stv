# saroo-stv：在世嘉土星上运行 ST-V 街机游戏

[English](README.md) | 简体中文 | [日本語](README.ja.md)

saroo-stv 借助 SAROO 光驱模拟卡，在真实的世嘉土星上运行世嘉 ST-V 街机游戏。支持的游戏见下表。

Baku Baku Animal 已在真实的土星 + SAROO HW 1.3 上测试通过：满速运行，有声音，手柄可用，画面正确。

## 支持的游戏

| 游戏 | 真机状态 |
| --- | --- |
| Baku Baku Animal | 真机正常：满速、有声音、手柄可用、画面正确。 |
| Karaoke Quiz Intro Don Don! | 已在真机启动并可游玩（投币、开始、答题）。已知问题：真机仍有画面损坏，包括加载画面；正在调查。 |

## 工作原理

- **FPGA**：官方 SAROO FPGA 第 06 版，未修改。它支持 AA24 地址线，可以把常驻 ROM 镜像（Baku Baku 为 16 MiB，Introdon 为 26 MiB） 映射到 SAROO SDRAM，地址与原卡带相同。
- **MCU**：SAROO 的 MCU 程序（`mcuapp.bin`）需要增加两条命令：STVLOAD 把 SD 卡上的 ROM 文件载入 SDRAM，ROMCTL 开关 AA24 映射。补丁在 `saroo-mcu/` 目录，基于 SAROO 官方 v0.9 源码。
- **土星端（本仓库）**：光盘加载器和常驻运行时（`runtime/`）。负责加载 FPR 程序，在内存中给游戏打补丁，每处补丁都先核对原始字节。ST-V BIOS 的功能由 `hle/` 里重新编写的替代实现提供；运行时还负责把 ST-V 的输入和声音转接到土星硬件上。

## 版权声明

本仓库**不包含**任何 ST-V 或土星的 ROM、BIOS 和游戏数据。源码里只保留了十几字节长的特征码，用来在打补丁前核对位置。请自行准备合法取得的文件。生成的镜像放在 `build/` 目录，不会提交到仓库。

## 需要准备

- `sh-elf` GCC 工具链（`sh-elf-gcc`、`sh-elf-as`、`sh-elf-ld`）、Python 3 和 `xorriso`，运行环境为 Linux 或 WSL
- `ROMS/`：Baku Baku 的 ST-V ROM（`fpr17969.13`, `mpr17970.2`, `mpr17971.3`, `mpr17972.4`, `mpr17973.5`），以及 ST-V BIOS `stv-jp-20091.bin`
- `SEGA/`：土星光盘启动文件 `sys_sec.bin`、`sys_arej.bin`、`sys_aree.bin`、`sys_areu.bin`、`sys_aret.bin`。请从 SAROO 官方仓库（https://github.com/tpunix/SAROO）的 `Firm_Saturn/sega/` 目录复制。缺少任何一个，构建都会报错停止。
- 在真机上运行还需要：SAROO HW 1.3 或更新版本、官方 FPGA 06，以及用 `saroo-mcu/saroo-stv-mcu.patch` 编译的 MCU 程序（见 `saroo-mcu/README.zh-CN.md`）

## 构建

```sh
python3 tools/build_manual_candidate.py \
  --source hle/reloc_veneers.s \
  --stv-bios ROMS/stv-jp-20091.bin --rom-dir ROMS \
  --descriptor games/bakubaku.json --sega-dir SEGA \
  --loading-screen --saroo-native-rom --saroo-direct \
  --experimental-sound --experimental-sound-pad-yield \
  --output-dir build/hw
```

输出：
- `build/hw/game/boot-diag.iso`：给 SAROO 用的光盘镜像。如果加载器需要，请转换成 BIN/CUE。
- `build/hw/game/BAKUMPR.BIN`：放到 SD 卡的 `/SAROO/STV/` 目录。

`--saroo-diag` 只在排查问题时使用：它每 10 秒往 SD 卡写一次诊断文件，每次写入会让游戏停顿约一帧。

## Introdon

`ROMS/`: `epr18937.13`, `mpr18944.7`, `mpr18939.2`, `mpr18940.3`, `mpr18941.4`, `mpr18942.5`, `mpr18943.6`, `mpr18938.1` + `stv-jp-20091.bin`. `SEGA/`: 同上启动文件。

```sh
python3 tools/build_manual_candidate.py \
  --source hle/reloc_veneers.s \
  --stv-bios ROMS/stv-jp-20091.bin --rom-dir ROMS \
  --descriptor games/introdon.json --sega-dir SEGA \
  --loading-screen --saroo-native-rom --saroo-direct \
  --output-dir build/introdon
```

| 游戏 | 常驻镜像 | 大小 | SDRAM |
| --- | --- | --- | --- |
| Baku Baku | `SAROO/STV/BAKUMPR.BIN` | 16 MiB | `0x400000` |
| Introdon | `SAROO/STV/INTRODON.BIN` | 26 MiB (27,262,976 bytes) | `0x200000` |

Introdon ISO: `build/introdon/game/boot-diag.iso`. 常驻镜像: `build/introdon/game/INTRODON.BIN`.

## 许可证

MIT，见 `LICENSE`。
