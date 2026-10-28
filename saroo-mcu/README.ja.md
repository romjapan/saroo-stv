# SAROO MCU パッチ（STVLOAD / ROMCTL）

[English](README.md) | [简体中文](README.zh-CN.md) | 日本語

saroo-stv を動かすには、SAROO の MCU プログラム（`mcuapp.bin`）にコマンドを 2 つ追加する必要があります。`saroo-stv-mcu.patch` は、このコマンドを SAROO 公式ファームウェア **v0.9**（https://github.com/tpunix/SAROO、コミット `c31bf61`）に追加するパッチです。変更するのは `Firm_MCU/Saturn/cdc.h` と `Firm_MCU/Saturn/saturn_main.c` の 2 ファイルだけで、71 行の追加のみ（削除はありません）。

| コマンド | 番号 | 内容 |
|---|---|---|
| `SSCMD_STVLOAD` | `0x40` | `FILERD` と同様の読み込みですが、CS0 の背後にある SDRAM 32 MiB 全体を書き込み先にできます。読み込みの区切りごとに 16 MiB 単位の FMC バンクを切り替え、終了後はバンク 0 に戻します。 |
| `SSCMD_ROMCTL` | `0x41` | `SS_ARG` のビット 0 で CS0 の AA24 アドレッシング（FPGA 06 の `st_reg_ctrl[12]`）をオン・オフします。戻り値は `ST_CTRL[15:8]` です。 |

メニューからゲームを起動するとき（`SSCMD_STARTUP`）に AA24 とバンク選択はクリアされるので、通常のサターンゲームには影響しません。

AA24 は公式 FPGA ビルド 06 がすでに対応しているため、FPGA の変更は不要です。

## ビルド

```sh
git clone https://github.com/tpunix/SAROO
cd SAROO
git checkout c31bf61
git apply /path/to/saroo-stv/saroo-mcu/saroo-stv-mcu.patch
```

Keil MDK で `Firm_MCU/ssmaster.uvprojx` を開き、**App** ターゲットをビルドします。プロジェクトの設定はそのまま使ってください。
- **Use MicroLIB は必ずオンのままにしてください。** オフにすると MCU が起動直後に停止し、サターンは SEGA ロゴで止まります。
- 最適化レベルは `-Os` です。

出力される `mcuapp.bin` は約 62 KB で、ITCM の上限 64 KiB に収まります。

このパッチは ArmClang 6.24（Keil MDK Community）で確認済みです。ビルド日付の 1 バイトを除き、実機でテストしたバイナリと一致します。

## インストール

1. SD カードの `/SAROO/mcuapp.bin`（公式 v0.9 のファイル）をバックアップします。
2. 新しい `mcuapp.bin` を `/SAROO/mcuapp.bin` にコピーします。電源を入れるたびに自動で読み込まれるので、メニューでのアップデート操作は不要です。コピー後に一度電源を入れ直してください。
3. saroo-stv のビルドで生成された `BAKUMPR.BIN` を `/SAROO/STV/` に、ゲームイメージを `/SAROO/ISO/<名前>/` に置きます。

元に戻すときは、公式の `mcuapp.bin` をコピーし直すだけです。チップのフラッシュにある MCU ブートローダーは一切変更しません。
