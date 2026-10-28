"""Build the existing manual-pad/visual profile with current runtime sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
HLE_FLAGS='''software-input-shadow irq-depth hardware-cd-fixes boot-static-input
software-nvram-shadow startup-scu-services cold-game-state system-flag-slot
resident-backup-callbacks resident-input-edges resident-player-input resident-game-ports
resident-system-config resident-session-stats resident-factory-config resident-state-publish
resident-credit-baseline resident-start-baseline coin-trial coin-main-clock start-trial
confirm-trial saturn-pad-input manual-pad-profile pad-frame-clock pad-timed-poll
pad-hblank-worker'''.split()
GAME_FLAGS='''test-copy-hooks test-vdp-cache test-irq-dispatch test-hardware-init boot-trial
test-game-video-init test-nvram-shadow test-game-startup-init prefetch-cold-palettes
test-word-copy-hook test-alt-long-copy-hook prefetch-cold-vdp2-word prefetch-cold-map
prefetch-cold-maps-rest prefetch-cold-map-fourth test-system-flag-slot
prefetch-attract-vdp2-word prefetch-attract-palette prefetch-attract-patterns
prefetch-attract-map prefetch-story-table prefetch-credit-vdp2-word prefetch-credit-palette
prefetch-credit-map prefetch-credit-maps-rest prefetch-credit-ui-words
prefetch-credit-ui-animation prefetch-credit-timeout-word prefetch-credit-timeout-animation
prefetch-credit-timeout-last-word reuse-difficulty-timeout-words reuse-post-difficulty-vdp2-word
reuse-title-vdp2-word reuse-title-palettes reuse-title-maps prefetch-post-difficulty-palettes
prefetch-post-difficulty-patterns prefetch-post-difficulty-converted-patterns
prefetch-post-difficulty-map prefetch-post-difficulty-map-second prefetch-scene-character-palette
irq-resource-cache prefetch-transition-word-table prefetch-idle-ui-table visible-boot-errors'''.split()
DIRECT_GAME_FLAGS='''test-copy-hooks test-vdp-cache test-irq-dispatch test-hardware-init boot-trial
test-game-video-init test-nvram-shadow test-game-startup-init test-system-flag-slot
visible-boot-errors experimental-sound-boot'''.split()
SOUND_FLAGS='''experimental-sound-boot experimental-sound-cd-dma
experimental-sound-dma-prefetch experimental-sound-align-pack
experimental-sound-stream-handoff'''.split()

def main():
    p=argparse.ArgumentParser()
    for name in ('source','stv-bios','rom-dir','descriptor','sega-dir','output-dir'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--experimental-sound',action='store_true',
        help='Separate experimental sound boot/DMA/stream candidate, never hardware acceptance')
    p.add_argument('--experimental-sound-pad-yield',action='store_true')
    p.add_argument('--loading-screen',action='store_true',help='NOW LOADING progress bar during early boot reads')
    p.add_argument('--experimental-mpr0-cart-ram',action='store_true',help='Opt-in MPR0 copy into a 4 MiB RAM cart')
    p.add_argument('--saroo-native-rom',action='store_true',help='SAROO SDRAM-backed MPR (stv2ss mcuapp.bin)')
    p.add_argument('--saroo-direct',action='store_true',help='SAROO maps the whole ST-V cart: no resource prefetch/copy redirection, native sound')
    p.add_argument('--saroo-native-assume',action='store_true',help='TEST ONLY: emulator ST-V cart provides the MPR')
    p.add_argument('--saroo-diag',action='store_true',help='SAROO hardware diagnostics with SD dumps every 10 s (stalls the game)')
    a=p.parse_args()
    if a.experimental_sound_pad_yield and not a.experimental_sound:p.error('pad yield requires experimental sound')
    out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=False)
    hle=out/'hle';game=out/'game'
    commands=[
        [sys.executable,str(ROOT/'tools/build_hle_ram.py'),'--source',str(a.source.resolve()),
         '--stv-bios',str(a.stv_bios.resolve()),'--output-dir',str(hle),
         '--difficulty-confirm-at-main','1650']+['--'+f for f in HLE_FLAGS],
        [sys.executable,str(ROOT/'tools/build_mpr_diag.py'),'--rom-dir',str(a.rom_dir.resolve()),
         '--descriptor',str(a.descriptor.resolve()),'--sega-dir',str(a.sega_dir.resolve()),
         '--resident-hle',str(hle/'HLE.BIN'),'--output-dir',str(game)]+['--'+f for f in (DIRECT_GAME_FLAGS if a.saroo_direct else GAME_FLAGS)+(SOUND_FLAGS if a.experimental_sound else [])+(['experimental-sound-pad-yield'] if a.experimental_sound_pad_yield else [])+(['experimental-mpr0-cart-ram'] if a.experimental_mpr0_cart_ram else [])+(['loading-screen'] if a.loading_screen else [])+(['saroo-native-rom'] if a.saroo_native_rom else [])+(['saroo-native-assume'] if a.saroo_native_assume else [])+(['saroo-diag'] if a.saroo_diag else [])]]
    (out/'build-profile.json').write_text(json.dumps(dict(commands=commands,
        experimental_sound=a.experimental_sound,
        experimental_sound_pad_yield=a.experimental_sound_pad_yield,
        experimental_mpr0_cart_ram=a.experimental_mpr0_cart_ram,
        loading_screen=a.loading_screen,
        saroo_native_rom=a.saroo_native_rom,saroo_native_assume=a.saroo_native_assume,saroo_diag=a.saroo_diag,
        note='Manual controller candidate; input callbacks disabled; '+
        ('experimental runtime sound boot/stream; legacy async SMPC sound polling remains isolated; ' if a.experimental_sound else 'sound isolated; ')+
        'no hardware acceptance'),indent=2)+'\n')
    with (out/'build.log').open('wb') as log:
        for command in commands:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
    manifest=json.loads((hle/'manifest.json').read_text())
    if not manifest['manual_pad_profile']['automatic_input_callback_disabled']:
        raise ValueError('Manual input profile was not established')
    for name in ('coin_trial','start_trial','confirm_trial'):
        if manifest[name].get('enabled') is not False:
            raise ValueError('Automatic guest input remains enabled: '+name)
    if a.experimental_sound:
        game_manifest=json.loads((game/'manifest.json').read_text())
        for name in ('experimental_sound_boot','experimental_sound_cd_dma','experimental_sound_dma_prefetch'):
            if name not in game_manifest:raise ValueError('Missing sound build feature: '+name)
    print(json.dumps(dict(game_dir=str(game),
        iso_sha256=hashlib.sha256((game/'boot-diag.iso').read_bytes()).hexdigest(),
        manual_callbacks_disabled=True,sound_isolated=not a.experimental_sound,
        experimental_sound=a.experimental_sound),indent=2))

if __name__=='__main__':main()
