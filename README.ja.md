# saroo-stv：セガサターンで ST-V アーケードゲームを動かす

[English](README.md) | [简体中文](README.zh-CN.md) | 日本語

saroo-stv は、光学ドライブエミュレーターカートリッジ SAROO を使い、実機のセガサターンでセガ ST-V のアーケードゲームを動かすプロジェクトです。対応ゲームは下表のとおりです。

バクバクアニマルは実機のサターン + SAROO HW 1.3 で動作確認済みです。フルスピードで動作し、サウンド・コントローラー入力・画面表示とも正常です。

## 対応ゲーム

| ゲーム | 実機での状態 |
| --- | --- |
| Baku Baku Animal | 実機で正常動作：フルスピード、サウンド・入力・画面表示とも正常。 |
| Karaoke Quiz Intro Don Don! | 実機で起動し、プレイ可能です（コイン・スタート・解答）。既知の問題：ロード画面を含め、実機で表示が乱れます。調査中です。 |

## 仕組み

- **FPGA**：SAROO 公式 FPGA ビルド 06（改造なし）。AA24 アドレス線に対応しており、常駐 ROM イメージ（Baku Baku は 16 MiB、Introdon は 26 MiB）を元のカートリッジと同じアドレスで SAROO の SDRAM にマッピングできます。
- **MCU**：SAROO の MCU プログラム（`mcuapp.bin`）にコマンドを 2 つ追加する必要があります。STVLOAD は SD カード上の ROM ファイルを SDRAM に読み込み、ROMCTL は AA24 マッピングを切り替えます。パッチは `saroo-mcu/` にあり、SAROO 公式 v0.9 のソースに適用します。
- **サターン側（このリポジトリ）**：CD ローダーと常駐ランタイム（`runtime/`）。FPR プログラムを読み込み、RAM 上でゲームにパッチを当てます。パッチを当てる前には必ず元のバイト列を確認します。ST-V BIOS の機能は `hle/` にある独自実装の代替コードが提供し、ランタイムが ST-V の入力とサウンドをサターンのハードウェアに対応させます。

## 著作権について

このリポジトリには ST-V やサターンの ROM、BIOS、ゲームデータは**一切含まれていません**。ソースには、パッチ適用前に位置を確認するための十数バイト程度のシグネチャのみが含まれます。正規に入手したファイルをご自身で用意してください。生成されたイメージは `build/` に置かれます（リポジトリにはコミットされません）。

## 必要なもの

- `sh-elf` GCC ツールチェーン（`sh-elf-gcc`、`sh-elf-as`、`sh-elf-ld`）、Python 3、`xorriso`（Linux または WSL）
- `ROMS/`：バクバクアニマルの ST-V ROM（`fpr17969.13`, `mpr17970.2`, `mpr17971.3`, `mpr17972.4`, `mpr17973.5`）と ST-V BIOS `stv-jp-20091.bin`
- `SEGA/`：サターンのディスク起動用ファイル `sys_sec.bin`、`sys_arej.bin`、`sys_aree.bin`、`sys_areu.bin`、`sys_aret.bin`。SAROO 公式リポジトリ（https://github.com/tpunix/SAROO）の `Firm_Saturn/sega/` からコピーしてください。1 つでも欠けているとビルドはエラーで止まります。
- 実機で動かす場合：SAROO HW 1.3 以降、公式 FPGA 06、`saroo-mcu/saroo-stv-mcu.patch` を当ててビルドした MCU プログラム（`saroo-mcu/README.ja.md` を参照）

## ビルド

```sh
python3 tools/build_manual_candidate.py \
  --source hle/reloc_veneers.s \
  --stv-bios ROMS/stv-jp-20091.bin --rom-dir ROMS \
  --descriptor games/bakubaku.json --sega-dir SEGA \
  --loading-screen --saroo-native-rom --saroo-direct \
  --experimental-sound --experimental-sound-pad-yield \
  --output-dir build/hw
```

出力：
- `build/hw/game/boot-diag.iso`：SAROO 用のディスクイメージ。ローダーが必要とする場合は BIN/CUE に変換してください。
- `build/hw/game/BAKUMPR.BIN`：SD カードの `/SAROO/STV/` にコピーしてください。

`--saroo-diag` はデバッグ時のみ使ってください。10 秒ごとに診断ファイルを SD カードへ書き込み、書き込みのたびにゲームが約 1 フレーム止まります。

## Introdon

`ROMS/`: `epr18937.13`, `mpr18944.7`, `mpr18939.2`, `mpr18940.3`, `mpr18941.4`, `mpr18942.5`, `mpr18943.6`, `mpr18938.1` + `stv-jp-20091.bin`. `SEGA/`: 上記と同じ起動ファイル。

```sh
python3 tools/build_manual_candidate.py \
  --source hle/reloc_veneers.s \
  --stv-bios ROMS/stv-jp-20091.bin --rom-dir ROMS \
  --descriptor games/introdon.json --sega-dir SEGA \
  --loading-screen --saroo-native-rom --saroo-direct \
  --output-dir build/introdon
```

| ゲーム | 常駐イメージ | サイズ | SDRAM |
| --- | --- | --- | --- |
| Baku Baku | `SAROO/STV/BAKUMPR.BIN` | 16 MiB | `0x400000` |
| Introdon | `SAROO/STV/INTRODON.BIN` | 26 MiB (27,262,976 bytes) | `0x200000` |

Introdon ISO: `build/introdon/game/boot-diag.iso`. 常駐イメージ: `build/introdon/game/INTRODON.BIN`.

## ライセンス

MIT（`LICENSE` を参照）。
