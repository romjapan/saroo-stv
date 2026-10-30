# saroo-stv：在世嘉土星上运行 ST-V 街机游戏

[English](README.md) | 简体中文 | [日本語](README.ja.md)

saroo-stv 借助 SAROO 光驱模拟卡，在真实的世嘉土星上运行世嘉 ST-V 街机游戏。支持的游戏见下表。

Baku Baku Animal 已在真实的土星 + SAROO HW 1.3 上测试通过：满速运行，有声音，手柄可用，画面正确。

## 支持的游戏

| 游戏 | 真机状态 |
| --- | --- |
| Baku Baku Animal | 真机正常：满速、有声音、手柄可用、画面正确。 |
| Karaoke Quiz Intro Don Don! | 真机正常：画面、手柄、答案、TEST 菜单及断电后保留的存档均已验证。已知问题：音乐音量有时会在歌曲播放过程中变化；原因尚未找到。 |

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

| 土星操作 | Introdon 功能 |
| --- | --- |
| L | 投币 |
| Start | 开始游戏 |
| A / B / C / X | 答案 1 / 2 / 3 / 4 |
| 主机 RESET | 进入 TEST 菜单；在菜单中选择当前项目 |
| R | SERVICE；在 TEST 菜单中移到下一项 |
| 按住 A+B+C+Start 约 2 秒 | 保存并返回 SAROO 菜单 |

### TEST 菜单

在标题或吸引画面短按主机 RESET（约 0.2–0.3 秒）进入。两次 RESET 之间至少
间隔 1 秒；长按不会重复触发。R 移到下一项，RESET 选择或确认。这是卡带自己的
测试菜单，不是 ST-V BIOS 的系统测试菜单。

| 菜单项目 | 功能 |
| --- | --- |
| INPUT TEST | 输入测试入口；详细操作尚未验证。 |
| SOUND TEST | 声音播放测试。 |
| GAME ASSIGNMENTS | 修改游戏设置，例如难度 EASY/NORMAL。 |
| BACKUP DATA CLEAR | 清除游戏保存数据。**会擦除设置和记录，请谨慎使用。** |
| QUIZ TEST | 测验测试入口；详细操作尚未验证。 |
| EXIT | 离开测试菜单并返回游戏。 |

已验证的示例（初始选中 INPUT TEST，难度为 EASY）：R 两次移到 GAME ASSIGNMENTS
→ RESET 进入 → RESET 将 EASY 改为 NORMAL → R 两次移到子页 EXIT → RESET
→ R 三次移到主菜单 EXIT → RESET 返回游戏。返回后等待约 5 秒。

设置和记录会自动保存到土星内部记忆体的 `INTRODONP12`（约 476 字节），断电后
仍可保留。游戏进行中的变更在该局结束或回到吸引画面时保存；其他情况下在变更
稳定后保存。按住 A+B+C+Start 约 2 秒，也会在返回 SAROO 菜单前尝试保存。
内部记忆体已满、未格式化或
不可用时，游戏仍可继续，但变更可能无法保存。游戏不会格式化记忆体或删除
其他游戏的存档。

## 许可证

MIT，见 `LICENSE`。
