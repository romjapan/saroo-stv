# SAROO MCU 补丁（STVLOAD / ROMCTL）

[English](README.md) | 简体中文 | [日本語](README.ja.md)

saroo-stv 需要 SAROO 的 MCU 程序（`mcuapp.bin`）多支持两条命令。`saroo-stv-mcu.patch` 把这两条命令加到 SAROO 官方固件 **v0.9**（https://github.com/tpunix/SAROO，提交 `c31bf61`）上，只修改 `Firm_MCU/Saturn/cdc.h` 和 `Firm_MCU/Saturn/saturn_main.c` 两个文件：新增 71 行，没有删除任何代码。

| 命令 | 编号 | 作用 |
|---|---|---|
| `SSCMD_STVLOAD` | `0x40` | 和 `FILERD` 类似，但目标地址可以覆盖 CS0 后面完整的 32 MiB SDRAM。每读一段就切换一次 16 MiB 的 FMC 存储体，结束后切回第 0 个。 |
| `SSCMD_ROMCTL` | `0x41` | `SS_ARG` 第 0 位开关 CS0 的 AA24 寻址（FPGA 06 的 `st_reg_ctrl[12]`），返回 `ST_CTRL[15:8]`。 |

从菜单启动游戏时（`SSCMD_STARTUP`），会清除 AA24 和存储体选择，普通土星游戏不受影响。

官方 FPGA 第 06 版本身已经支持 AA24，不需要改 FPGA。

## 编译

```sh
git clone https://github.com/tpunix/SAROO
cd SAROO
git checkout c31bf61
git apply /path/to/saroo-stv/saroo-mcu/saroo-stv-mcu.patch
```

用 Keil MDK 打开 `Firm_MCU/ssmaster.uvprojx`，编译 **App** 目标。保持工程原有设置不变：
- **Use MicroLIB 必须勾选**。不勾的话 MCU 一启动就停住，土星会卡在 SEGA 标志。
- 优化级别是 `-Os`。

编译出来的 `mcuapp.bin` 约 62 KB，不超过 64 KiB 的 ITCM 上限。

本补丁用 ArmClang 6.24（Keil MDK Community 版）验证过：除了记录编译日期的 1 个字节，编译结果和实机测试用的程序完全一致。

## 安装

1. 先备份 SD 卡上的 `/SAROO/mcuapp.bin`（也就是官方 v0.9 的文件）。
2. 把新的 `mcuapp.bin` 复制到 `/SAROO/mcuapp.bin`。它每次开机都会自动加载，不需要在菜单里升级。复制完后断电重开一次。
3. 把 saroo-stv 构建出来的 `BAKUMPR.BIN` 放到 `/SAROO/STV/`，游戏镜像放到 `/SAROO/ISO/<名字>/`。

想恢复官方版本，把官方的 `mcuapp.bin` 复制回去就行。芯片闪存里的 MCU 引导程序完全不会被改动。
