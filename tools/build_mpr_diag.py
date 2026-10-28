"""Hash-verified CD MPR diagnostics; optional guarded hooks, no game entry."""
import argparse, hashlib, json, os
from pathlib import Path
import build_boot_diag as boot

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--rom-dir',type=Path,required=True)
    p.add_argument('--descriptor',type=Path,required=True)
    p.add_argument('--sega-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,default=Path('build/mpr-diag'))
    p.add_argument('--test-copy-hooks',action='store_true')
    p.add_argument('--resident-hle',type=Path,
                   help='Relocate runtime and test copy hooks after native resident initialization')
    p.add_argument('--test-vdp-cache',action='store_true')
    p.add_argument('--test-irq-dispatch',action='store_true')
    p.add_argument('--test-irq-guard',action='store_true')
    p.add_argument('--test-hardware-init',action='store_true')
    p.add_argument('--boot-trial',action='store_true',help='Execute original game entry; isolated input/audio, NOT playable')
    p.add_argument('--visible-boot-errors',action='store_true')
    p.add_argument('--experimental-sound-boot',action='store_true',help='Boot-only native sound driver loading; not audible acceptance')
    p.add_argument('--experimental-sound-cd-dma',action='store_true',help='Guarded native sound DMA CD staging; diagnostic only')
    p.add_argument('--experimental-sound-dma-prefetch',action='store_true',help='Observed sound ranges only; runtime cache misses fatal')
    p.add_argument('--experimental-sound-align-pack',action='store_true',help='Even-align native sample destinations; diagnostic port patch')
    p.add_argument('--experimental-sound-stream-handoff',action='store_true',help='Master main-loop CD service for missing slave512-byte stream blocks')
    p.add_argument('--loading-screen',action='store_true',help='NOW LOADING bar on NBG0 until just before hardware_test (pre game video init only)')
    p.add_argument('--saroo-native-rom',action='store_true',help='SAROO (stv2ss mcuapp.bin, FPGA 06 AA24) loads all MPR banks into SDRAM at their guest addresses; verified per 64 KiB, CD fallback')
    p.add_argument('--saroo-native-assume',action='store_true',help='TEST ONLY: skip SAROO commands; expect an emulator ST-V cart (Yabause CartType=12) at the MPR addresses')
    p.add_argument('--saroo-diag',action='store_true',help='Hardware diagnostics: VBlank PC profile, input trace and SD dumps every 10 s (PADDIAG/PROFILE/TRACE/FAIL); each dump stalls the game')
    p.add_argument('--experimental-mpr0-cart-ram',action='store_true',help='Copy MPR0 into a detected 4 MiB RAM cart (identity window); CD fallback without cart')
    p.add_argument('--experimental-sound-pad-yield',action='store_true',help='Yield to guarded native pad acquisition before masking stream service')
    p.add_argument('--irq-resource-cache',action='store_true',help='Preload verified last MPR 64KiB for bounded IRQ-only RAM copies')
    p.add_argument('--prefetch-transition-word-table',action='store_true')
    p.add_argument('--prefetch-idle-ui-table',action='store_true')
    p.add_argument('--test-game-video-init',action='store_true',help='Call original cold video initializer before controlled handoff')
    p.add_argument('--test-nvram-shadow',action='store_true')
    p.add_argument('--test-nvram-guard',action='store_true')
    p.add_argument('--test-game-startup-init',action='store_true')
    p.add_argument('--prefetch-cold-palettes',action='store_true')
    p.add_argument('--test-word-copy-hook',action='store_true')
    p.add_argument('--test-alt-long-copy-hook',action='store_true')
    p.add_argument('--prefetch-cold-vdp2-word',action='store_true')
    p.add_argument('--prefetch-cold-map',action='store_true')
    p.add_argument('--prefetch-cold-maps-rest',action='store_true')
    p.add_argument('--prefetch-cold-map-fourth',action='store_true')
    p.add_argument('--test-system-flag-slot',action='store_true')
    p.add_argument('--prefetch-attract-vdp2-word',action='store_true')
    p.add_argument('--prefetch-attract-palette',action='store_true')
    p.add_argument('--prefetch-attract-patterns',action='store_true')
    p.add_argument('--prefetch-attract-map',action='store_true')
    p.add_argument('--prefetch-story-table',action='store_true')
    p.add_argument('--prefetch-credit-vdp2-word',action='store_true')
    p.add_argument('--prefetch-credit-palette',action='store_true')
    p.add_argument('--prefetch-credit-map',action='store_true')
    p.add_argument('--prefetch-credit-maps-rest',action='store_true')
    p.add_argument('--prefetch-credit-ui-words',action='store_true')
    p.add_argument('--prefetch-credit-ui-animation',action='store_true')
    p.add_argument('--prefetch-credit-timeout-word',action='store_true')
    p.add_argument('--prefetch-credit-timeout-animation',action='store_true')
    p.add_argument('--prefetch-credit-timeout-last-word',action='store_true')
    p.add_argument('--reuse-difficulty-timeout-words',action='store_true')
    p.add_argument('--reuse-post-difficulty-vdp2-word',action='store_true')
    p.add_argument('--reuse-title-vdp2-word',action='store_true')
    p.add_argument('--reuse-title-palettes',action='store_true')
    p.add_argument('--reuse-title-maps',action='store_true')
    p.add_argument('--prefetch-post-difficulty-palettes',action='store_true')
    p.add_argument('--prefetch-post-difficulty-patterns',action='store_true')
    p.add_argument('--prefetch-post-difficulty-converted-patterns',action='store_true')
    p.add_argument('--prefetch-post-difficulty-map',action='store_true')
    p.add_argument('--prefetch-post-difficulty-map-second',action='store_true')
    p.add_argument('--prefetch-scene-character-palette',action='store_true')
    a=p.parse_args();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    info={}
    if a.resident_hle and (a.resident_hle.parent/'manifest.json').exists():
        info=json.loads((a.resident_hle.parent/'manifest.json').read_text())
    if info.get('cold_game_state') and not a.test_game_startup_init:
        p.error('Cold game-state HLE requires the full startup initializer trial')
    if a.prefetch_cold_palettes and not (info.get('cold_game_state') and a.test_game_startup_init):
        p.error('--prefetch-cold-palettes requires cold-state HLE and full startup trial')
    if a.test_word_copy_hook and not a.prefetch_cold_palettes:
        p.error('--test-word-copy-hook requires --prefetch-cold-palettes')
    if a.test_alt_long_copy_hook and not a.test_word_copy_hook:
        p.error('--test-alt-long-copy-hook requires --test-word-copy-hook')
    if a.prefetch_cold_vdp2_word and not a.test_alt_long_copy_hook:
        p.error('--prefetch-cold-vdp2-word requires --test-alt-long-copy-hook')
    if a.prefetch_cold_map and not a.prefetch_cold_vdp2_word:
        p.error('--prefetch-cold-map requires --prefetch-cold-vdp2-word')
    if a.prefetch_cold_maps_rest and not a.prefetch_cold_map:
        p.error('--prefetch-cold-maps-rest requires --prefetch-cold-map')
    if a.prefetch_cold_map_fourth and not a.prefetch_cold_maps_rest:
        p.error('--prefetch-cold-map-fourth requires --prefetch-cold-maps-rest')
    if a.test_system_flag_slot and not (info.get('system_flag_slot') and a.test_game_startup_init):
        p.error('--test-system-flag-slot requires matching system-slot HLE and full startup')
    if a.prefetch_attract_vdp2_word and not a.prefetch_cold_vdp2_word:
        p.error('--prefetch-attract-vdp2-word requires pinned cold word')
    if a.prefetch_attract_palette and not a.prefetch_attract_vdp2_word:
        p.error('--prefetch-attract-palette requires attract word adaptation')
    if a.prefetch_attract_patterns and not a.prefetch_attract_palette:
        p.error('--prefetch-attract-patterns requires attract palette')
    if a.prefetch_attract_map and not a.prefetch_attract_patterns:
        p.error('--prefetch-attract-map requires attract patterns')
    if a.prefetch_story_table and not a.prefetch_attract_map:
        p.error('--prefetch-story-table requires attract map')
    if a.prefetch_credit_vdp2_word and not (a.prefetch_story_table and info.get('resident_credit_baseline')):
        p.error('--prefetch-credit-vdp2-word requires story prefetch and guarded resident credit baseline')
    if a.prefetch_credit_palette and not (a.prefetch_credit_vdp2_word and a.prefetch_attract_palette):
        p.error('--prefetch-credit-palette requires credit word and verified attract palette')
    if a.prefetch_credit_map and not a.prefetch_credit_palette:
        p.error('--prefetch-credit-map requires credit palette')
    if a.prefetch_credit_maps_rest and not a.prefetch_credit_map:
        p.error('--prefetch-credit-maps-rest requires first credit map')
    if a.prefetch_credit_ui_words and not a.prefetch_credit_maps_rest:
        p.error('--prefetch-credit-ui-words requires selection maps')
    if a.prefetch_credit_ui_animation and not a.prefetch_credit_ui_words:
        p.error('--prefetch-credit-ui-animation requires verified UI words')
    if a.prefetch_credit_timeout_word and not a.prefetch_credit_ui_animation:
        p.error('--prefetch-credit-timeout-word requires selection animation')
    if a.prefetch_credit_timeout_animation and not a.prefetch_credit_timeout_word:
        p.error('--prefetch-credit-timeout-animation requires timeout direct word')
    if a.prefetch_credit_timeout_last_word and not a.prefetch_credit_timeout_animation:
        p.error('--prefetch-credit-timeout-last-word requires timeout animation')
    if a.reuse_difficulty_timeout_words and not a.prefetch_credit_timeout_last_word:
        p.error('--reuse-difficulty-timeout-words requires timeout resources')
    if a.reuse_post_difficulty_vdp2_word and not a.reuse_difficulty_timeout_words:
        p.error('--reuse-post-difficulty-vdp2-word requires difficulty timeout resources')
    if a.reuse_title_vdp2_word and not a.prefetch_cold_vdp2_word:
        p.error('--reuse-title-vdp2-word requires verified cold word')
    if a.reuse_title_palettes and not (a.reuse_title_vdp2_word and a.prefetch_cold_palettes):
        p.error('--reuse-title-palettes requires title word and cold palettes')
    if a.reuse_title_maps and not (a.reuse_title_palettes and a.prefetch_cold_map_fourth):
        p.error('--reuse-title-maps requires title palettes and all cold maps')
    if a.prefetch_post_difficulty_palettes and not a.reuse_post_difficulty_vdp2_word:
        p.error('--prefetch-post-difficulty-palettes requires post-difficulty word')
    if a.prefetch_post_difficulty_patterns and not a.prefetch_post_difficulty_palettes:
        p.error('--prefetch-post-difficulty-patterns requires scene palettes')
    if a.prefetch_post_difficulty_converted_patterns and not a.prefetch_post_difficulty_patterns:
        p.error('--prefetch-post-difficulty-converted-patterns requires scene patterns')
    if a.prefetch_post_difficulty_map and not a.prefetch_post_difficulty_converted_patterns:
        p.error('--prefetch-post-difficulty-map requires scene converted patterns')
    if a.prefetch_post_difficulty_map_second and not a.prefetch_post_difficulty_map:
        p.error('--prefetch-post-difficulty-map-second requires first scene map')
    if a.prefetch_scene_character_palette and not a.prefetch_post_difficulty_map_second:
        p.error('--prefetch-scene-character-palette requires scene maps')
    if a.resident_hle and not a.test_copy_hooks:
        p.error('--resident-hle requires --test-copy-hooks')
    if a.test_vdp_cache and not a.resident_hle:
        p.error('--test-vdp-cache requires --resident-hle')
    if (a.test_irq_dispatch or a.test_irq_guard) and not a.test_vdp_cache:
        p.error('IRQ tests require --test-vdp-cache and an IRQ-depth HLE')
    if a.test_hardware_init and (not a.test_irq_dispatch or a.test_irq_guard):
        p.error('--test-hardware-init requires the positive --test-irq-dispatch test')
    if a.boot_trial and not a.test_hardware_init:
        p.error('--boot-trial requires --test-hardware-init')
    if a.test_game_video_init and not a.boot_trial:
        p.error('--test-game-video-init requires --boot-trial')
    if a.test_game_startup_init and not (a.test_game_video_init and a.test_nvram_shadow):
        p.error('--test-game-startup-init requires video-init and NV-shadow tests')
    if (a.test_nvram_shadow or a.test_nvram_guard) and not a.test_hardware_init:
        p.error('NV shadow tests require --test-hardware-init')
    if a.test_nvram_guard and not a.test_nvram_shadow:
        p.error('--test-nvram-guard requires --test-nvram-shadow')
    if a.test_irq_dispatch or a.test_irq_guard:
        info=json.loads((a.resident_hle.parent/'manifest.json').read_text())
        if not info.get('irq_depth') or info.get('sha256')!=hashlib.sha256(a.resident_hle.read_bytes()).hexdigest():
            p.error('IRQ tests require a matching --irq-depth HLE manifest')
        if a.test_hardware_init and not info.get('hardware_cd_fixes'):
            p.error('Hardware test requires the matching --hardware-cd-fixes HLE')
        if a.boot_trial and not info.get('boot_polls_isolated'):
            p.error('Boot trial requires a matching --boot-static-input HLE')
        if a.boot_trial and a.resident_hle.read_bytes()[0xfd8:0xfe0]!=bytes.fromhex('25fe00a0ffffe1fc'):
            p.error('Boot trial mask-shadow sync requires the verified native IMS literal at 0xfd8')
        if (a.test_nvram_shadow or a.test_nvram_guard) and not info.get('nvram_shadow'):
            p.error('NV tests require a matching --software-nvram-shadow HLE')
    records=json.loads(a.descriptor.read_text())['roms'][1:]
    if len(records)!=4: raise ValueError('Expected four MPR banks')
    banks=[];manifest=[]
    for i,r in enumerate(records):
        raw=(a.rom_dir/r['name']).read_bytes()
        if len(raw)!=0x400000 or hashlib.sha1(raw).hexdigest()!=r['sha1']:
            raise ValueError('ROM mismatch: '+r['name'])
        if r['operations']!=[{'type':'word_swap','offset':0x400000*(i+1)}]:
            raise ValueError('Unexpected map')
        data=bytearray(raw);data[0::2],data[1::2]=raw[1::2],raw[0::2]
        banks.append(bytes(data))
        manifest.append({'source':r['name'],'source_sha1':r['sha1'],
            'cd_file':f'MPR{i}.BIN','sha256':hashlib.sha256(data).hexdigest()})
    image=b''.join(banks)
    if a.experimental_sound_cd_dma and not a.experimental_sound_boot:
        p.error('--experimental-sound-cd-dma requires --experimental-sound-boot')
    if a.experimental_sound_align_pack and not a.experimental_sound_boot:
        p.error('--experimental-sound-align-pack requires --experimental-sound-boot')
    if a.experimental_sound_dma_prefetch and not a.experimental_sound_cd_dma:
        p.error('--experimental-sound-dma-prefetch requires --experimental-sound-cd-dma')
    if a.experimental_sound_stream_handoff and not a.experimental_sound_dma_prefetch:
        p.error('--experimental-sound-stream-handoff requires --experimental-sound-dma-prefetch')
    if a.experimental_sound_pad_yield and (not a.experimental_sound_stream_handoff or
        not info.get('manual_pad_profile') or not info.get('pad_hblank_worker')):
        p.error('--experimental-sound-pad-yield requires stream handoff and manual HBlank pad profile')
    if a.experimental_sound_dma_prefetch:
        from check_sound_cache_layout import arrays,validate
        sound_spec=arrays((Path(__file__).resolve().parent.parent/'runtime'/'sound_cd_dma.c').read_text())
        validate(sound_spec['cache_ram'],sound_spec['cache_size'])
        for src,size,expected in zip(sound_spec['cache_src'],sound_spec['cache_size'],sound_spec['expected']):
            off=src-0x02400000
            if off<0 or off+size>len(image):raise ValueError('Sound cache source outside ROM image')
            value=0x811c9dc5
            for byte in image[off:off+size]:value=((value^byte)*0x01000193)&0xffffffff
            if value!=expected:raise ValueError('Sound cache source hash mismatch at '+hex(src))
    if a.experimental_sound_boot:
        if not (a.boot_trial and a.resident_hle and a.visible_boot_errors):
            p.error('--experimental-sound-boot requires boot trial, resident HLE and visible errors')
        for address,size,expected in (
            (0x0295a48c,7342,'fe7c0ea7748807424ef4bc607389f8625b13022f1264aa4688fbc2a180c1a714'),
            (0x0295c13a,16472,'613dad1ffdfd69e945d0c46417b38209b9bbf139a0b147172c1fdc9b5ced645f')):
            offset=address-0x02400000
            if hashlib.sha256(image[offset:offset+size]).hexdigest()!=expected:
                raise ValueError('Unexpected sound startup payload')
    windows=[(0,23),(2043,23),(0x3ffff5,23),(0x7ffff5,23),
             (0xbffff5,23),(0xffffe9,23),(0x823457,23)]
    checks=[]
    for offset,size in windows:
        expected=','.join(hex(v) for v in image[offset:offset+size])
        checks.append('{'+hex(0x02400000+offset)+',{'+expected+'}}')
    source='''#include "cart_cd.h"
#define TRACE ((volatile u32 *)0x060ff000)
static void finish(u32 state,u32 code) {
 TRACE[0]=state;TRACE[1]=code;TRACE[2]=cd_error.code;TRACE[3]=cd_error.lba;
 *(volatile u16 *)0x25f80020=0;*(volatile u16 *)0x25f800ac=0;
 *(volatile u16 *)0x25f800ae=0;
 *(volatile u16 *)0x25e00000=state==0x50415353?0x83e0:0x801f;
 *(volatile u16 *)0x25f80000=0x8000;for(;;)__asm__ volatile("nop");
}
static const struct {u32 address;u8 expected[23];} checks[]={CHECKS};
void probe_main(void) {
 u8 *p=(u8 *)0x20202000;u32 i,j;
 TRACE[0]=0x4d505244;TRACE[1]=0;
 if(cd_init() || cart_cd_init()) finish(0x4641494c,1);
 for(i=0;i<7;i++) {
  p[0]=0xa5;p[24]=0x5a;
  if(cart_cd_read(checks[i].address,p+1,23)) finish(0x4641494c,0x100+i);
  for(j=0;j<23;j++) if(p[j+1]!=checks[i].expected[j]) finish(0x4641494c,0x200+i);
  if(p[0]!=0xa5 || p[24]!=0x5a) finish(0x4641494c,0x300+i);
  TRACE[1]=i+1;
 }
 p[1]=0x7d;
 if(cart_cd_read(0x03400000,p+1,0) || p[1]!=0x7d ||
    !cart_cd_read(0x03400000,p+1,1) ||
    !cart_cd_read(0x033fffff,p+1,2) ||
    !cart_cd_read(0xffffffff,p+1,1) ||
    !cart_cd_read(0x023fffff,p+1,1) || p[1]!=0x7d)
     finish(0x4641494c,0x400);
 finish(0x50415353,8);
}
'''.replace('CHECKS',','.join(checks))
    (out/'mpr_probe.c').write_text(source)
    runtime=Path(__file__).resolve().parent.parent/'runtime'
    extra_sources=[runtime/'cart_cd.c'];files={f'MPR{i}.BIN':data for i,data in enumerate(banks)}
    if a.saroo_native_assume and not a.saroo_native_rom:
        p.error('--saroo-native-assume requires --saroo-native-rom')
    if a.saroo_diag and not a.saroo_native_rom:
        p.error('--saroo-diag requires --saroo-native-rom')
    cart_defines=[]
    if a.experimental_mpr0_cart_ram:
        h=2166136261
        for byte in banks[0]:h=((h^byte)*16777619)&0xffffffff
        cart_defines+=['#define CART_MPR0_RAM 1',f'#define CART_MPR0_HASH 0x{h:08x}u']
        mpr0_cart_hash=h
    if a.saroo_native_rom:
        mpr=b''.join(banks)
        (out/'BAKUMPR.BIN').write_bytes(mpr)
        table=[]
        for blk in range(256):
            h=2166136261;chunk=mpr[blk<<16:(blk+1)<<16]
            for i in range(0,0x10000,4):h=((h^int.from_bytes(chunk[i:i+4],'big'))*16777619)&0xffffffff
            table.append(h)
        (out/'cart_saroo_expect.h').write_text('/* generated: word FNV-1a per 64 KiB of MPR0..3 */'+chr(10)+
            'static const u32 cart_saroo_expect[256]={'+','.join(f'0x{x:08x}u' for x in table)+'};'+chr(10)+
            '#define CART_SAROO_PROBE_WORDS 1'+chr(10)+'static const u32 cart_saroo_probe[4]={'+
            ','.join(f'0x{int.from_bytes(mpr[o:o+4],"big"):08x}u' for o in (0,4,0xff4724,0xff4728))+'};'+chr(10))
        cart_defines.append('#define CART_SAROO_ROM 1')
        if a.saroo_native_assume:cart_defines.append('#define CART_SAROO_ASSUME 1')
        if a.saroo_diag:cart_defines.append('#define CART_SAROO_DIAG 1')
        extra_sources.append(runtime/'saroo_rom.c')
    if cart_defines:
        generated=out/'cart_cd_gen.c'
        generated.write_text(chr(10).join(cart_defines)+chr(10)+(runtime/'cart_cd.c').read_text())
        extra_sources[0]=generated
    if a.test_copy_hooks:
        raw=(a.rom_dir/'fpr17969.13').read_bytes()
        if len(raw)!=0x100000 or hashlib.sha1(raw).hexdigest()!='1d226db72d6ef68fd294f60659df7f882b25def6':
            raise ValueError('FPR mismatch')
        files['FPR.BIN']=raw[0x1000:0xf1000]
        extra_sources.extend([runtime/'copy_hooks.c',runtime/'copy_long.s',runtime/'copy_word.s',runtime/'copy_alt_long.s'])
        expected=','.join(hex(v) for v in image[0x3ffff8:0x400010])
        tests='''
extern int copy_hooks_install(void);
extern void test_long_registers(void *,const void *,u32);
static void hook_test(void) {
 CdFile f;u32 i;u8 *p=(u8 *)0x20202000;
 volatile u32 *regs=(volatile u32 *)0x20202200;
 static const u8 expected[24]={EXPECTED};
 typedef void *(*Move)(void *,const void *,u32);
 Move move=(Move)0x06053c98;
 if(cd_find_root("FPR.BIN;1",&f) || f.size!=0xf0000 ||
    cd_read_at(&f,0,(void *)0x26010000,f.size)) finish(0x4641494c,0x600);
 /* Atomic preflight: corrupt site 0; site 1 MUST stay unmodified. */
 *(volatile u8 *)0x2604afd4=0x66;
 if(!copy_hooks_install() || *(volatile u32 *)0x26053c98!=0x2fd63450)
     finish(0x4641494c,0x601);
 *(volatile u8 *)0x2604afd4=0x67;
 if(copy_hooks_install()) finish(0x4641494c,0x602);
 TRACE[1]=9;
 p[0]=0xa5;p[25]=0x5a;
 if(move(p+1,(void *)0x027ffff8,24)!=p+1) finish(0x4641494c,0x603);
 for(i=0;i<24;i++) if(p[i+1]!=expected[i]) finish(0x4641494c,0x604);
 if(p[0]!=0xa5 || p[25]!=0x5a) finish(0x4641494c,0x605);
 TRACE[1]=10;
 test_long_registers(p+32,(void *)0x027ffff8,6);
 for(i=0;i<24;i++) if(p[32+i]!=expected[i]) finish(0x4641494c,0x606);
 if(regs[0]!=(u32)(p+32) || regs[1]!=(u32)(p+56) || regs[2]!=0 ||
    regs[3]!=0x02800010 || regs[4]!=(u32)(p+52) ||
    regs[5]!=((u32)expected[20]<<24 | (u32)expected[21]<<16 |
              (u32)expected[22]<<8 | expected[23])) finish(0x4641494c,0x607);
 TRACE[1]=11;
 for(i=0;i<16;i++) p[i]=(u8)i;
 if(move(p+2,p,8)!=p+2) finish(0x4641494c,0x608);
 for(i=0;i<8;i++) if(p[i+2]!=i) finish(0x4641494c,0x609);
 if(move(p,p+2,8)!=p) finish(0x4641494c,0x60a);
 for(i=0;i<8;i++) if(p[i]!=i) finish(0x4641494c,0x60b);
 test_long_registers(p+64,p,2);
 for(i=0;i<8;i++) if(p[64+i]!=i) finish(0x4641494c,0x60c);
 test_long_registers(p+64,(void *)0x02400000,0);
 if(regs[0]!=(u32)(p+64) || regs[1]!=(u32)(p+64) || regs[2]!=0 ||
    regs[3]!=0x02400000 || regs[4]!=0x22 || regs[5]!=0x11)
     finish(0x4641494c,0x60d);
 TRACE[1]=12;
}
'''.replace('EXPECTED',expected)
        source=source.replace('0x060ff000','0x0600e000')
        source=source.replace('static const struct',tests+'\nstatic const struct')
        source=source.replace('finish(0x50415353,8);','hook_test();finish(0x50415353,12);')
        if a.resident_hle:
            hle=a.resident_hle.read_bytes()
            if not 0<len(hle)<=0x10000: raise ValueError('Invalid HLE length')
            resident='''
 if(cd_find_root("HLE.BIN;1",&f) || f.size!=HLE_SIZE ||
    cd_read_at(&f,0,(void *)0x20210000,f.size)) finish(0x4641494c,0x610);
 *(volatile u8 *)0xfffffe92=0x10;
 *(volatile u32 *)0x2021f010=0; /* reserved diagnostic depth state */
 ((void (*)(void))0x00210800)();
 if(*(volatile u32 *)0x26000610!=0x00210260 ||
    *(volatile u32 *)0x2600063c!=0x002101e0) finish(0x4641494c,0x611);
 /* The native constructor erased every byte of the old IP area. */
 for(i=0;i<0x1000;i++) if(((volatile u8 *)0x26002000)[i])
    finish(0x4641494c,0x612);
 if(cd_find_root("MPR0.BIN;1",&f) || f.size!=0x400000)
    finish(0x4641494c,0x613);
'''.replace('HLE_SIZE',str(len(hle)))
            if info.get('nvram_shadow'):
                resident=resident.replace(' *(volatile u8 *)0xfffffe92=0x10;', '''
 for(i=0;i<0x10000;i++) ((volatile u8 *)0x20220000)[i]=0;
 *(volatile u8 *)0x2021ffff=0xa5;*(volatile u8 *)0x20230000=0x5a;
 *(volatile u8 *)0xfffffe92=0x10;''')
            source=source.replace(' /* Atomic preflight:',resident+'\n /* Atomic preflight:')
            source=source.replace('0x0600e000','0x2021e000')
            source=source.replace('hook_test();finish(0x50415353,12);',
                '''hook_test();
 ((void (*)(void))0x00210800)();
 TRACE[1]=13;
 /* Second constructor must not erase installed FPR jumps or LWRAM globals. */
 if(*(volatile u32 *)0x2604afd4!=0xd001402b ||
    *(volatile u32 *)0x26053c98!=0xd001402b ||
    *(volatile u32 *)0x2604afdc<0x00240000 ||
    *(volatile u32 *)0x2604afdc>=0x00250000 ||
    *(volatile u32 *)0x26053ca0<0x00240000 ||
    *(volatile u32 *)0x26053ca0>=0x00250000)
     finish(0x4641494c,0x614);
 if(((void *(*)(void *,const void *,u32))0x06053c98)(p+1,
       (void *)checks[2].address,23)!=p+1) finish(0x4641494c,0x615);
 for(j=0;j<23;j++) if(p[j+1]!=checks[2].expected[j]) finish(0x4641494c,0x616);
 finish(0x50415353,14);''')
        (out/'mpr_probe.c').write_text(source)
    if a.test_hardware_init:
        hardware=r'''
static void hardware_test(void) {
 u32 i,n;CdFile f;u8 *p=(u8 *)0x20204000;
 /* ST-169: defer SMPC command until >300us after VBLANK-IN. */
 for(i=0;i<12000000 && (*(volatile u16 *)0x25f80004&8);i++);
 if(i==12000000) finish(0x4641494c,0x901);
 for(i=0;i<12000000 && !(*(volatile u16 *)0x25f80004&8);i++);
 if(i==12000000) finish(0x4641494c,0x902);
 for(n=0;n<6;n++) {
  for(i=0;i<12000000 && (*(volatile u16 *)0x25f80004&4);i++);
  if(i==12000000) finish(0x4641494c,0x903);
  for(i=0;i<12000000 && !(*(volatile u16 *)0x25f80004&4);i++);
  if(i==12000000) finish(0x4641494c,0x904);
 }
 if(((int (*)(void))0x00211400)()!=0) finish(0x4641494c,0x905);
 /* DMA EN and IMS are write-only. Read documented DMA status instead. */
 TRACE[16]=*(volatile u32 *)0x25fe007c;
 if(TRACE[16]&0x733333)
     finish(0x4641494c,0x906);
 /* VDP1 TVMR..EWRR are write-only on hardware (reads return bus noise; the
    first real-SAROO run failed here with 0x907). No readback check. */
 TRACE[17]=*(volatile u16 *)0x25f8000e;
 TRACE[18]=*(volatile u16 *)0x25f80000;
 /* Existing Yabause omits RAMCTL/cycle reads even though VDP2 manual
    defines RAMCTL R/W. Verify stored fields independently via GDB. */
 /* TVMD readback is emulator behaviour; recorded only (was fatal 0x908). */
 TRACE[14]=*(volatile u8 *)0x20100063;
 TRACE[15]=*(volatile u8 *)0x2010005f;
 if(TRACE[14]&1) finish(0x4641494c,0x90a);
 TRACE[1]=19;
 /* Force transport, not a warm MPR cache hit. */
 if(cd_find_root("PROBE.BIN;1",&f) || cd_read_at(&f,2043,p,23))
     finish(0x4641494c,0x90b);
 for(i=0;i<23;i++) {u32 o=2043+i;
  if(p[i]!=(u8)((o*37)^(o>>3)^0xa5)) finish(0x4641494c,0x90c);
 }
 if(cart_cd_cache_reset() || cart_cd_read(0x033b96ac,p,32))
     finish(0x4641494c,0x90d);
 if(cart_cache_stats.sector_reads!=1) finish(0x4641494c,0x90e);
 TRACE[19]=cd_pace_display_off;
 /* Depends on TVMD readback in cd_io pace(); recorded only (was fatal 0x90f). */
}
'''
        source=source.replace('static const struct',hardware+'\nstatic const struct')
        (out/'mpr_probe.c').write_text(source)
    if a.test_irq_dispatch or a.test_irq_guard:
        irq_code=r'''
static volatile u32 irq_count;
static const u8 irq_data[8]={1,3,5,7,9,11,13,15};
static void irq_callback(void) {
 u32 i;u8 *p=(u8 *)0x20204000;
 TRACE[12]=*(volatile u32 *)0x2021f010;
 if(TRACE[12]!=1) finish(0x4641494c,0x801);
 IRQ_COPY
 for(i=0;i<8;i++) if(p[i]!=irq_data[i]) finish(0x4641494c,0x802);
 irq_count++;TRACE[13]=irq_count;
}
static void irq_test(void) {
 u32 i;
 if(*(volatile u32 *)0x2021f010) finish(0x4641494c,0x803);
 *(volatile u32 *)0x26000a04=(u32)irq_callback; /* table[vector 0x41] */
 *(volatile u32 *)0x26000348=0xfffffffd;
 *(volatile u32 *)0x25fe00a0=0xfffffffd; /* only VBLANK-OUT */
 __asm__ volatile("mov #0,r0\n\tldc r0,sr":::"r0","memory");
 for(i=0;i<24000000 && irq_count<3;i++) __asm__ volatile("nop");
 __asm__ volatile("mov #15,r0\n\tshll2 r0\n\tshll2 r0\n\tldc r0,sr":::"r0","memory");
 *(volatile u32 *)0x25fe00a0=0xffffffff;
 *(volatile u32 *)0x26000348=0xffffffff;
 if(irq_count<3 || *(volatile u32 *)0x2021f010) finish(0x4641494c,0x804);
 TRACE[1]=17;
 ((void (*)(void))0x00210800)();
 if(*(volatile u32 *)0x2021f010) finish(0x4641494c,0x805);
}
'''
        copy='''if(((void *(*)(void *,const void *,u32))0x06053c98)(p,irq_data,8)!=p)
    finish(0x4641494c,0x806);'''
        if a.test_irq_guard:
            copy='''((void *(*)(void *,const void *,u32))0x06053c98)(p,(void *)0x033b96ac,8);
 finish(0x4641494c,0x807); /* MUST NOT return from rejected CD-in-IRQ call */'''
        source=source.replace('static const struct',irq_code.replace('IRQ_COPY',copy)+'\nstatic const struct')
        (out/'mpr_probe.c').write_text(source)
    if a.test_vdp_cache:
        start=0x13b96ac-0x400000
        expected_hash=2166136261
        for byte in image[start:start+42*32]:
            expected_hash=((expected_hash^byte)*16777619)&0xffffffff
        cache_test='''
 {
  u32 n,k,h=2166136261u;
  volatile u8 *v;
  if(cart_cd_cache_reset()) finish(0x4641494c,0x701);
  *(volatile u8 *)0x25c7eebf=0xa5;
  *(volatile u8 *)0x25c7f400=0x5a;
  for(n=0;n<42;n++) {
   v=(volatile u8 *)(0x25c7f3e0-n*32);
   if(((void *(*)(void *,const void *,u32))0x06053c98)((void *)v,
       (void *)(0x033b96ac+n*32),32)!=(void *)v) finish(0x4641494c,0x702);
   for(k=0;k<32;k++) h=(h^v[k])*16777619u;
  }
  TRACE[8]=h;TRACE[9]=cart_cache_stats.sector_reads;
  TRACE[10]=cart_cache_stats.hits;TRACE[11]=cart_cache_stats.misses;
  if(h!=EXPECTED_HASH || cart_cache_stats.sector_reads!=2 ||
      cart_cache_stats.misses!=2 || cart_cache_stats.hits!=41)
       finish(0x4641494c,0x703);
  if(*(volatile u8 *)0x25c7f400!=0x5a || *(volatile u8 *)0x25c7eebf!=0xa5)
      finish(0x4641494c,0x704);
  TRACE[1]=15;
  if(cart_cd_cache_reset()) finish(0x4641494c,0x705);
  if(((void *(*)(void *,const void *,u32))0x06053c98)((void *)0x25c7f3e0,
      (void *)0x033b96ac,32)!=(void *)0x25c7f3e0 ||
      cart_cache_stats.sector_reads!=1) finish(0x4641494c,0x706);
 }
 finish(0x50415353,16);
'''.replace('EXPECTED_HASH',hex(expected_hash)+'u')
        source=source.replace('finish(0x50415353,14);',cache_test)
        if a.test_irq_dispatch or a.test_irq_guard:
            if source.count('finish(0x50415353,16);')!=1:
                raise ValueError('IRQ test dispatch insertion failed')
            source=source.replace('finish(0x50415353,16);','irq_test();finish(0x50415353,18);')
        (out/'mpr_probe.c').write_text(source)
    if a.test_hardware_init:
        if source.count('finish(0x50415353,18);')!=1:
            raise ValueError('Hardware test insertion failed')
        source=source.replace('finish(0x50415353,18);','hardware_test();finish(0x50415353,20);')
        (out/'mpr_probe.c').write_text(source)
    if a.boot_trial:
        if source.count('hardware_test();finish(0x50415353,20);')!=1:
            raise ValueError('Boot trial insertion failed')
        source=source.replace('static const struct','extern void game_handoff(void);\nstatic const struct')
        source=source.replace('hardware_test();finish(0x50415353,20);','''hardware_test();
 *(volatile u16 *)0x2021f000=0xffff;
 *(volatile u16 *)0x2021f002=0xffff;
 *(volatile u16 *)0x2021f004=0xffff;
 /* Remove prior diagnostic bytes from the observed game resource targets. */
 for(i=0;i<1344;i++) ((volatile u8 *)0x25c7eec0)[i]=0xa5;
 for(i=20;i<28;i++) TRACE[i]=0;
 TRACE[0]=0x42545259;TRACE[1]=21; /* BOOT TRIAL, NOT PASS */
 *(volatile u16 *)0x25f80020=0;
 *(volatile u16 *)0x25e00000=0xfc1f;
 *(volatile u16 *)0x25f800ac=0;*(volatile u16 *)0x25f800ae=0;
 *(volatile u16 *)0x25f80000=0x8000;
 game_handoff();finish(0x4641494c,0xa01);''')
        extra_sources.append(runtime/'game_handoff.s')
        if a.test_game_video_init:
            source=source.replace('extern void game_handoff(void);','extern void game_handoff(void);\nextern void game_video_init(void);')
            source=source.replace('game_handoff();finish', '''TRACE[1]=22;
 /* Guard the exact original initializer entry before executing it. */
 if(*(volatile u32 *)0x0604b3c8!=0x4f22e300u ||
    *(volatile u32 *)0x0604b3cc!=0xd2142230u) finish(0x4641494c,0xa10);
 game_video_init();
 TRACE[28]=*(volatile u8 *)0x060d28b8;
 TRACE[29]=*(volatile u16 *)0x25f80000;
 TRACE[30]=*(volatile u16 *)0x060d28c8;
 TRACE[31]=*(volatile u16 *)0x060d4328;
 /* TRACE[29] (TVMD readback) is recorded only: not readable on hardware. */
 if(TRACE[28]!=0 || TRACE[30]==0xffff ||
    TRACE[31]!=TRACE[30]) finish(0x4641494c,0xa11);
 /* 0x060105fc reads ST-V system port 0x20400005 bit 7 (PAUSE, active low).
    Saturn has nothing there (Mednafen reads 0, hardware is open bus) and a
    0 toggles the pause flag 0x060831e0, freezing the scene loop. Point the
    literal at the FPR's own 0xffff alignment pad: pause always released. */
 if(*(volatile u32 *)0x06010624!=0x20400005u ||
    *(volatile u16 *)0x06010622!=0xffffu) finish(0x4641494c,0xa13);
 *(volatile u32 *)0x26010624=0x26010622u;
 /* Scene inits (0x0601009e/0x06010228/0x0601040c) set SCU ASR0/ASR1 to the
    ST-V ROM-board timing 0x14301430. On a Saturn with SAROO this makes A-bus
    CS0 reads return stale data (real hardware A-bus matrix, 2026-10-27:
    32/32 blocks bad, 0 after restoring the BIOS value). Keep BIOS timing. */
 if(*(volatile u32 *)0x06010148!=0x14301430u || *(volatile u32 *)0x060102ac!=0x14301430u ||
    *(volatile u32 *)0x06010490!=0x14301430u) finish(0x4641494c,0xa14);
 /* ASR sweep on hardware (2026-10-28): every CS0 timing down to 0x1110
    reads 0 errors by CPU and DMA when CS1 keeps the BIOS 0x1ff0; 0x1330 is
    ~17% faster than 0x1ff0. CS1 stays at the BIOS value. */
 *(volatile u32 *)0x26010148=0x13301ff0u;*(volatile u32 *)0x260102ac=0x13301ff0u;
 *(volatile u32 *)0x26010490=0x13301ff0u;
 *(volatile u32 *)0x25fe00b0=0x13301ff0u;*(volatile u32 *)0x25fe00b4=0x1ff01ff0u;
 *(volatile u32 *)0x25fe00b8=0x1fu;
 *(volatile u8 *)0xfffffe92=0x10;
 TRACE[1]=23;
 game_handoff();finish''')
            if os.environ.get('STV2SS_ABUS_MATRIX'):  # hardware diagnosis: A-bus read matrix, then halt
                source=source.replace(' *(volatile u32 *)0x26010624=0x26010622u;'+chr(10),' *(volatile u32 *)0x26010624=0x26010622u;'+chr(10)+' cart_cd_saroo_matrix();'+chr(10))
            if os.environ.get('STV2SS_FORCE_TCR2'):  # test-only: mimic real-hardware FRT /128
                source=source.replace(' *(volatile u32 *)0x26010624=0x26010622u;'+chr(10),' *(volatile u32 *)0x26010624=0x26010622u;'+chr(10)+' *(volatile u8 *)0xfffffe16=2;'+chr(10))
            extra_sources.append(runtime/'game_video_init.s')
            if a.test_game_startup_init:
                source=source.replace('0x0604b3c8!=0x4f22e300u','0x06033384!=0x4f227ffcu')
                source=source.replace('0x0604b3cc!=0xd2142230u','0x06033388!=0xd3192f32u')
                extra_sources[-1]=runtime/'game_startup_init.s'
                if info.get('cold_game_state'):
                    source=source.replace(' game_video_init();',
                        ' if(*(volatile u16 *)0x060550c4!=0) finish(0x4641494c,0xa12);\n game_video_init();')
                if a.prefetch_cold_palettes:
                    hashes=[]
                    for offset in (0x3f4724,0x3f4924):
                        value=2166136261
                        for byte in banks[3][offset:offset+512]:value=((value^byte)*16777619)&0xffffffff
                        hashes.append(value)
                    if os.environ.get('STV2SS_FORCE_A22'):hashes[0]^=1  # test-only: exercise the failure page
                    prefetch='''
 {
  u32 n,k,h;u8 *base=(u8 *)0x20231000;
  const u32 expected[2]={HASH0,HASH1};
  if(*(volatile u32 *)0x060282ac!=0x033f4724u ||
     *(volatile u32 *)0x060282b4!=0x033f4924u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xa20);
  *(volatile u8 *)0x20230fff=0xa5;*(volatile u8 *)0x20231400=0x5a;
  for(k=0;k<2;k++) {
   if(cart_cd_read(0x033f4724u+k*512,base+k*512,512)) finish(0x4641494c,0xa21);
   h=2166136261u;
   for(n=0;n<512;n++) h=(h^base[k*512+n])*16777619u;
   if(h!=expected[k]) finish(0x4641494c,0xa22+k);
   TRACE[26+k]=h;
  }
  if(*(volatile u8 *)0x20230fff!=0xa5 || *(volatile u8 *)0x20231400!=0x5a)
   finish(0x4641494c,0xa24);
  /* Publish both pointers only after both complete reads validate. */
  *(volatile u32 *)0x260282ac=0x20231000u;
  *(volatile u32 *)0x260282b4=0x20231200u;
  *(volatile u8 *)0xfffffe92=0x10; /* Purge cached original literals. */
 }
'''.replace('HASH0',hex(hashes[0])+'u').replace('HASH1',hex(hashes[1])+'u')
                    if a.saroo_native_rom:
                        # Real SAROO failed this check once (0xa22) after a clean
                        # verify: rescan / re-assert AA24 / reload, retry the read,
                        # and show the three scan words if it still fails.
                        old_fail='   if(h!=expected[k]) finish(0x4641494c,0xa22+k);'+chr(10)
                        if prefetch.count(old_fail)!=1:raise ValueError('Unexpected palette check')
                        prefetch=prefetch.replace(old_fail,'''   if(h!=expected[k] && cart_cd_saroo_resident()) {
    u32 diag[3];
    cart_cd_saroo_recheck(diag);
    if(cart_cd_read(0x033f4724u+k*512,base+k*512,512)) finish(0x4641494c,0xa21);
    h=2166136261u;
    for(n=0;n<512;n++) h=(h^base[k*512+n])*16777619u;
    if(h!=expected[k]) {
     u32 v[26];
     v[0]=0xa22+k;cart_cd_saroo_report(diag,v);
     TRACE[0]=0x4641494c;TRACE[1]=0xa22+k;
     __asm__ volatile("ldc %0,sr"::"r"(0xf0):"memory");
     diagnostic_grid(v,26);
     for(;;)__asm__ volatile("nop");
    }
   }
   if(h!=expected[k]) finish(0x4641494c,0xa22+k);
''')
                    if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected palette-prefetch insertion site')
                    source=source.replace(' TRACE[1]=23;',prefetch+' TRACE[1]=23;')
                if a.test_word_copy_hook:
                    source=source.replace('extern void game_handoff(void);',
                        'extern void game_handoff(void);\nextern int copy_word_install(void);')
                    word_hash=2166136261
                    for byte in banks[1][0x21470:0x21670]:word_hash=((word_hash^byte)*16777619)&0xffffffff
                    word_test='''
 {
  u32 n,h;u8 *p=(u8 *)0x20202000;
  *(volatile u8 *)0x2604afbc=0x66;
  if(!copy_word_install() || *(volatile u32 *)0x2604afbc!=0x6653a005u)
   finish(0x4641494c,0xa31);
  *(volatile u8 *)0x2604afbc=0x67;
  if(copy_word_install()) finish(0x4641494c,0xa30);
  p[0]=0xa5;p[514]=0x5a;
  ((void (*)(void *,const void *,u32))0x0604afbc)(p+2,(void *)0x02821470,256);
  h=2166136261u;for(n=0;n<512;n++) h=(h^p[n+2])*16777619u;
  if(h!=WORD_HASH || p[0]!=0xa5 || p[514]!=0x5a) finish(0x4641494c,0xa32);
  TRACE[2]=h;TRACE[3]=512;
 }
'''.replace('WORD_HASH',hex(word_hash)+'u')
                    source=source.replace(' TRACE[1]=23;',word_test+' TRACE[1]=23;')
                if a.test_alt_long_copy_hook:
                    source=source.replace('extern void game_handoff(void);',
                        'extern void game_handoff(void);\nextern int copy_alt_long_install(void);')
                    alt_hash=2166136261
                    for byte in banks[1][0x548:0x588]:alt_hash=((alt_hash^byte)*16777619)&0xffffffff
                    alt_test='''
 {
  u32 n,h;u8 *p=(u8 *)0x20202000;
  *(volatile u8 *)0x2604afec=0x66;
  if(!copy_alt_long_install() || *(volatile u32 *)0x2604afec!=0x6653a005u)
   finish(0x4641494c,0xa41);
  *(volatile u8 *)0x2604afec=0x67;
  if(copy_alt_long_install()) finish(0x4641494c,0xa40);
  p[0]=0xa5;p[68]=0x5a;for(n=0;n<64;n++) p[n+4]=0xa5;
  ((void (*)(void *,const void *,u32))0x0604afec)(p+4,(void *)0x02800548,16);
  h=2166136261u;for(n=0;n<64;n++) h=(h^p[n+4])*16777619u;
  if(h!=ALT_HASH || p[0]!=0xa5 || p[68]!=0x5a) finish(0x4641494c,0xa42);
  TRACE[28]=h;TRACE[29]=64;
 }
'''.replace('ALT_HASH',hex(alt_hash)+'u')
                    source=source.replace(' TRACE[1]=23;',alt_test+' TRACE[1]=23;')
                if a.prefetch_cold_vdp2_word:
                    if banks[1][0x14efdc:0x14efde]!=bytes.fromhex('8000'):
                        raise ValueError('Unexpected cold VDP2 word')
                    pinned='''
 {
  u8 *p=(u8 *)0x20231420;u32 h;
  if(*(volatile u32 *)0x06058200!=1u ||
     *(volatile u32 *)0x06058204!=0x0294efdcu ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xa50);
  *(volatile u8 *)0x2023141f=0xa5;p[2]=0x5a;
  if(cart_cd_read(0x0294efdcu,p,2)) finish(0x4641494c,0xa51);
  if(p[0]!=0x80 || p[1]!=0 || *(volatile u8 *)0x2023141f!=0xa5 || p[2]!=0x5a)
   finish(0x4641494c,0xa52);
  h=((2166136261u^p[0])*16777619u^p[1])*16777619u;
  TRACE[30]=h;TRACE[31]=2;
  /* Publish only the count-one descriptor; other mode literals remain original. */
  *(volatile u32 *)0x26058204=0x20231420u;
  *(volatile u8 *)0xfffffe92=0x10;
 }
'''
                    if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected VDP2 insertion site')
                    source=source.replace(' TRACE[1]=23;',pinned+' TRACE[1]=23;')
                if a.prefetch_cold_map:
                    map_data=banks[1][0x21668:0x21668+1058]
                    if len(map_data)!=1058 or map_data[:4]!=bytes.fromhex('001f0011'):
                        raise ValueError('Unexpected cold map dimensions')
                    map_hash=2166136261
                    for byte in map_data:map_hash=((map_hash^byte)*16777619)&0xffffffff
                    map_test='''
 {
  u32 n,h;u8 *p=(u8 *)0x20232000;
  if(*(volatile u32 *)0x0602843c!=0x02821668u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xa60);
  *(volatile u8 *)0x20231fff=0xa5;p[1058]=0x5a;
  if(cart_cd_read(0x02821668u,p,1058)) finish(0x4641494c,0xa61);
  h=2166136261u;for(n=0;n<1058;n++) h=(h^p[n])*16777619u;
  if(h!=MAP_HASH || p[0]!=0 || p[1]!=31 || p[2]!=0 || p[3]!=17 ||
     *(volatile u8 *)0x20231fff!=0xa5 || p[1058]!=0x5a) finish(0x4641494c,0xa62);
  *(volatile u32 *)0x2602843c=0x20232000u;
  *(volatile u8 *)0xfffffe92=0x10;
 }
'''.replace('MAP_HASH',hex(map_hash)+'u')
                    if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected map insertion site')
                    source=source.replace(' TRACE[1]=23;',map_test+' TRACE[1]=23;')
                if a.prefetch_cold_maps_rest:
                    rest_maps=[]
                    rest_test=''
                    map_specs=[
                        (0x02825898,0x06028474,0x20232800,34,17),
                        (0x0281a33c,0x06028480,0x20233000,35,8)]
                    if a.prefetch_cold_map_fourth:
                        map_specs.append((0x028172cc,0x060284ac,0x20233800,40,28))
                    for src,literal,ram,width,height in map_specs:
                        size=4+width*height*2
                        data=banks[1][src-0x02800000:src-0x02800000+size]
                        header=width.to_bytes(2,'big')+height.to_bytes(2,'big')
                        if len(data)!=size or data[:4]!=header:
                            raise ValueError('Unexpected remaining cold map dimensions')
                        h=2166136261
                        for byte in data:h=((h^byte)*16777619)&0xffffffff
                        rest_maps.append(dict(source=hex(src),literal=hex(literal),ram=hex(ram),
                            width=width,height=height,bytes=size,fnv1a=hex(h)))
                        rest_test+=f'''
 {{
  u32 n,h;u8 *p=(u8 *){hex(ram)};
  if(*(volatile u32 *){hex(literal)}!={hex(src)}u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xa70);
  *(volatile u8 *){hex(ram-1)}=0xa5;p[{size}]=0x5a;
  if(cart_cd_read({hex(src)}u,p,{size})) finish(0x4641494c,0xa71);
  h=2166136261u;for(n=0;n<{size};n++) h=(h^p[n])*16777619u;
  if(h!={hex(h)}u || p[0]!=0 || p[1]!={width} || p[2]!=0 || p[3]!={height} ||
     *(volatile u8 *){hex(ram-1)}!=0xa5 || p[{size}]!=0x5a) finish(0x4641494c,0xa72);
  *(volatile u32 *){hex(literal+0x20000000)}={hex(ram)}u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
                    if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected remaining-map insertion site')
                    source=source.replace(' TRACE[1]=23;',rest_test+' TRACE[1]=23;')
                if a.test_system_flag_slot:
                    flag_test='''
 {
  u32 a=*(volatile u32 *)0x26000820,b=*(volatile u32 *)0x26000824;
  u32 hi=*(volatile u32 *)0x26000828;u16 lo=*(volatile u16 *)0x2600081e;
  void (*fn)(u32)=(void (*)(u32))*(volatile u32 *)0x26000680;
  if((u32)fn!=0x00210ba0u) finish(0x4641494c,0xa80);
  *(volatile u32 *)0x26000820=0xa55a5aa5u;
  *(volatile u32 *)0x26000824=0xf13579bdu;
  fn(1);
  if(*(volatile u32 *)0x26000820!=0x00005aa5u ||
     *(volatile u32 *)0x26000824!=0xf13579bdu) finish(0x4641494c,0xa81);
  fn(0);
  if(*(volatile u32 *)0x26000820!=0x00005aa5u ||
     *(volatile u32 *)0x26000824!=0xf135799du) finish(0x4641494c,0xa82);
  fn(2);
  if(*(volatile u32 *)0x26000820!=0x00005aa5u ||
     *(volatile u32 *)0x26000824!=0xf135799du ||
     *(volatile u32 *)0x26000828!=hi || *(volatile u16 *)0x2600081e!=lo)
   finish(0x4641494c,0xa83);
  *(volatile u32 *)0x26000820=a;*(volatile u32 *)0x26000824=b;
 }
'''
                    if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected flag preflight site')
                    source=source.replace(' TRACE[1]=23;',flag_test+' TRACE[1]=23;')
                if a.prefetch_attract_vdp2_word:
                    attract='''
 if(*(volatile u32 *)0x060591ec!=1u ||
    *(volatile u32 *)0x060591f0!=0x0294efdcu ||
    *(volatile u16 *)0x20231420!=0x8000 ||
    *(volatile u8 *)0x2023141f!=0xa5 || *(volatile u8 *)0x20231422!=0x5a ||
    *(volatile u32 *)0x2021f010) finish(0x4641494c,0xa90);
 *(volatile u32 *)0x260591f0=0x20231420u;
 *(volatile u8 *)0xfffffe92=0x10;
'''
                    if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected attract pointer site')
                    source=source.replace(' TRACE[1]=23;',attract+' TRACE[1]=23;')
                if a.prefetch_attract_palette:
                    attract_palette_hash=2166136261
                    for byte in banks[3][0x3f2f24:0x3f3124]:
                        attract_palette_hash=((attract_palette_hash^byte)*16777619)&0xffffffff
                    palette='''
 {
  u32 n,h;u8 *p=(u8 *)0x20235000;
  if(*(volatile u32 *)0x06030d5c!=0x033f2f24u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xaa0);
  *(volatile u8 *)0x20234fff=0xa5;p[512]=0x5a;
  if(cart_cd_read(0x033f2f24u,p,512)) finish(0x4641494c,0xaa1);
  h=2166136261u;for(n=0;n<512;n++) h=(h^p[n])*16777619u;
  if(h!=PALETTE_HASH || *(volatile u8 *)0x20234fff!=0xa5 || p[512]!=0x5a)
   finish(0x4641494c,0xaa2);
  *(volatile u32 *)0x26030d5c=0x20235000u;
  *(volatile u8 *)0xfffffe92=0x10;
 }
'''.replace('PALETTE_HASH',hex(attract_palette_hash)+'u')
                    if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected attract palette site')
                    source=source.replace(' TRACE[1]=23;',palette+' TRACE[1]=23;')
                if a.prefetch_attract_patterns:
                    pattern_data=banks[1][0x54264:0x54264+13632]
                    if len(pattern_data)!=13632:raise ValueError('Incomplete attract pattern data')
                    pattern_hash=2166136261
                    for byte in pattern_data:pattern_hash=((pattern_hash^byte)*16777619)&0xffffffff
                    patterns='''
 {
  u32 n,h;u8 *p=(u8 *)0x20236000;
  if(*(volatile u32 *)0x06030d94!=0x02854264u ||
     *(volatile u16 *)0x06030d0e!=0x01aa ||
     *(volatile u16 *)0x06030d10!=0x016c ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xab0);
  *(volatile u8 *)0x20235fff=0xa5;p[13632]=0x5a;
  if(cart_cd_read(0x02854264u,p,13632)) finish(0x4641494c,0xab1);
  h=2166136261u;for(n=0;n<13632;n++) h=(h^p[n])*16777619u;
  if(h!=PATTERN_HASH || *(volatile u8 *)0x20235fff!=0xa5 || p[13632]!=0x5a)
   finish(0x4641494c,0xab2);
  *(volatile u32 *)0x26030d94=0x20236000u;
  *(volatile u8 *)0xfffffe92=0x10;
 }
'''.replace('PATTERN_HASH',hex(pattern_hash)+'u')
                    if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected pattern site')
                    source=source.replace(' TRACE[1]=23;',patterns+' TRACE[1]=23;')
                if a.prefetch_attract_map:
                    attract_map_data=banks[1][0x28b94:0x28b94+2244]
                    if len(attract_map_data)!=2244 or attract_map_data[:4]!=bytes.fromhex('0028001c'):
                        raise ValueError('Unexpected attract map dimensions')
                    attract_map_hash=2166136261
                    for byte in attract_map_data:attract_map_hash=((attract_map_hash^byte)*16777619)&0xffffffff
                    map_code='''
 {
  u32 n,h;u8 *p=(u8 *)0x2023a000;
  if(*(volatile u32 *)0x06030e94!=0x02828b94u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xac0);
  *(volatile u8 *)0x20239fff=0xa5;p[2244]=0x5a;
  if(cart_cd_read(0x02828b94u,p,2244)) finish(0x4641494c,0xac1);
  h=2166136261u;for(n=0;n<2244;n++) h=(h^p[n])*16777619u;
  if(h!=MAP_HASH || p[0]!=0 || p[1]!=40 || p[2]!=0 || p[3]!=28 ||
     *(volatile u8 *)0x20239fff!=0xa5 || p[2244]!=0x5a) finish(0x4641494c,0xac2);
  *(volatile u32 *)0x26030e94=0x2023a000u;
  *(volatile u8 *)0xfffffe92=0x10;
 }
'''.replace('MAP_HASH',hex(attract_map_hash)+'u')
                    if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected attract map site')
                    source=source.replace(' TRACE[1]=23;',map_code+' TRACE[1]=23;')
                if a.prefetch_story_table:
                    story_data=banks[1][0x15927c:0x15927c+240]
                    rows=[tuple(int.from_bytes(story_data[i+j:i+j+2],'big') for j in (0,2,4,6))
                          for i in range(0,len(story_data),8)]
                    if len(rows)!=30 or rows[0]!=(65535,0,0,0) or rows[-1]!=(0,0,0,65535) or any(r[3]==65535 for r in rows[:-1]):
                        raise ValueError('Unexpected story-table control extent')
                    story_hash=2166136261
                    for byte in story_data:story_hash=((story_hash^byte)*16777619)&0xffffffff
                    story='''
 {
  u32 n,h;u8 *p=(u8 *)0x2023b000;
  if(*(volatile u32 *)0x06031ac8!=0x0295927cu ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xad0);
  *(volatile u8 *)0x2023afff=0xa5;p[240]=0x5a;
  if(cart_cd_read(0x0295927cu,p,240)) finish(0x4641494c,0xad1);
  h=2166136261u;for(n=0;n<240;n++) h=(h^p[n])*16777619u;
  if(h!=STORY_HASH || *(volatile u8 *)0x2023afff!=0xa5 || p[240]!=0x5a)
   finish(0x4641494c,0xad2);
  *(volatile u32 *)0x26031ac8=0x2023b000u;
  *(volatile u8 *)0xfffffe92=0x10;
 }
'''.replace('STORY_HASH',hex(story_hash)+'u')
                    if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected story site')
                    source=source.replace(' TRACE[1]=23;',story+' TRACE[1]=23;')
        if a.prefetch_credit_ui_animation:
            expected=bytes.fromhex('028307440a000000028307640500000006057c90ff000000')
            if files['FPR.BIN'][0x47cb0:0x47cc8]!=expected:
                raise ValueError('Unexpected credit UI animation table')
            data=banks[1][0x30764:0x30784]
            animation_hash=2166136261
            for byte in data:animation_hash=((animation_hash^byte)*16777619)&0xffffffff
            first_hash=2166136261
            for byte in banks[1][0x30744:0x30764]:first_hash=((first_hash^byte)*16777619)&0xffffffff
            animation=f'''
 {{
  u32 n,h;u8 *p=(u8 *)0x2023c880;volatile u32 *t=(volatile u32 *)0x06057cb0;
  if(t[0]!=0x02830744u || t[1]!=0x0a000000u || t[2]!=0x02830764u ||
     t[3]!=0x05000000u || t[4]!=0x06057c90u || t[5]!=0xff000000u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xaf0);
  h=2166136261u;for(n=0;n<32;n++) h=(h^*(volatile u8 *)(0x2023c800+n))*16777619u;
  if(h!={hex(first_hash)}u || *(volatile u8 *)0x2023c7ff!=0xa5 ||
     *(volatile u8 *)0x2023c820!=0x5a) finish(0x4641494c,0xaf1);
  *(volatile u8 *)0x2023c87f=0xa5;p[32]=0x5a;
  if(cart_cd_read(0x02830764u,p,32)) finish(0x4641494c,0xaf2);
  h=2166136261u;for(n=0;n<32;n++) h=(h^p[n])*16777619u;
  if(h!={hex(animation_hash)}u || *(volatile u8 *)0x2023c87f!=0xa5 || p[32]!=0x5a)
   finish(0x4641494c,0xaf3);
  *(volatile u32 *)0x26057cb0=0x2023c800u;
  *(volatile u32 *)0x26057cb8=0x2023c880u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
            # UI-word prefetch must precede the reuse check, so insert later below.
        credit_ui_words=[]
        if a.prefetch_credit_ui_words:
            word_resources=[(0x02830744,0x06024e20,0x2023c800),
                            (0x02831220,0x06024e0c,0x2023c840)]
            if a.prefetch_credit_timeout_word:
                word_resources.append((0x028318fc,0x060254d0,0x2023c8c0))
            if a.prefetch_credit_timeout_last_word:
                word_resources.append((0x02832684,0x060254c4,0x2023c980))
            for address,literal,ram in word_resources:
                if files['FPR.BIN'][literal-0x06010000:literal-0x06010000+4]!=address.to_bytes(4,'big'):
                    raise ValueError('Unexpected credit UI word literal')
                data=banks[1][address-0x02800000:address-0x02800000+32]
                if len(data)!=32:raise ValueError('Truncated credit UI words')
                h=2166136261
                for byte in data:h=((h^byte)*16777619)&0xffffffff
                code=f'''
 {{
  u32 n,h;u8 *p=(u8 *){hex(ram)};
  if(*(volatile u32 *){hex(literal)}!={hex(address)}u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xae0);
  *(volatile u8 *){hex(ram-1)}=0xa5;p[32]=0x5a;
  if(cart_cd_read({hex(address)}u,p,32)) finish(0x4641494c,0xae1);
  h=2166136261u;for(n=0;n<32;n++) h=(h^p[n])*16777619u;
  if(h!={hex(h)}u || *(volatile u8 *){hex(ram-1)}!=0xa5 || p[32]!=0x5a)
   finish(0x4641494c,0xae2);
  *(volatile u32 *){hex(literal+0x20000000)}={hex(ram)}u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
                if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected credit UI site')
                source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
                credit_ui_words.append({'source':hex(address),'literal':hex(literal),
                    'ram':hex(ram),'bytes':32,'fnv1a':hex(h)})
        if a.prefetch_credit_ui_animation:
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected animation site')
            source=source.replace(' TRACE[1]=23;',animation+' TRACE[1]=23;')
        if a.prefetch_credit_timeout_animation:
            expected=bytes.fromhex('02831f600a00000002831f800500000006057c90ff000000')
            if files['FPR.BIN'][0x47cf8:0x47d10]!=expected:
                raise ValueError('Unexpected timeout animation table')
            timeout_animation_hash=2166136261
            for byte in banks[1][0x31f60:0x31fa0]:
                timeout_animation_hash=((timeout_animation_hash^byte)*16777619)&0xffffffff
            code=f'''
 {{
  u32 n,h;u8 *p=(u8 *)0x2023c900;volatile u32 *t=(volatile u32 *)0x06057cf8;
  if(t[0]!=0x02831f60u || t[1]!=0x0a000000u || t[2]!=0x02831f80u ||
     t[3]!=0x05000000u || t[4]!=0x06057c90u || t[5]!=0xff000000u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xb10);
  *(volatile u8 *)0x2023c8ff=0xa5;p[64]=0x5a;
  if(cart_cd_read(0x02831f60u,p,64)) finish(0x4641494c,0xb11);
  h=2166136261u;for(n=0;n<64;n++) h=(h^p[n])*16777619u;
  if(h!={hex(timeout_animation_hash)}u || *(volatile u8 *)0x2023c8ff!=0xa5 || p[64]!=0x5a)
   finish(0x4641494c,0xb12);
  *(volatile u32 *)0x26057cf8=0x2023c900u;
  *(volatile u32 *)0x26057d00=0x2023c920u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected timeout animation site')
            source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
        if a.reuse_title_maps:
            title_maps=[];code=''
            for literal,src,ram,size in ((0x06023db4,0x02821668,0x20232000,1058),
                    (0x06023dec,0x02825898,0x20232800,1160),
                    (0x06023df8,0x0281a33c,0x20233000,564),
                    (0x06023e24,0x028172cc,0x20233800,2244)):
                offset=literal-0x06010000
                if int.from_bytes(files['FPR.BIN'][offset:offset+4],'big')!=src:
                    raise ValueError('Unexpected title map literal')
                h=2166136261
                for byte in banks[1][src-0x02800000:src-0x02800000+size]:h=((h^byte)*16777619)&0xffffffff
                title_maps.append(dict(literal=hex(literal),source=hex(src),ram=hex(ram),bytes=size,fnv1a=hex(h)))
                code+=f'''
 {{
  u32 i,h;volatile u8 *p=(volatile u8 *){hex(ram)};
  if(*(volatile u32 *){hex(literal)}!={hex(src)}u || *(volatile u32 *)0x2021f010 ||
     p[-1]!=0xa5 || p[{size}]!=0x5a) finish(0x4641494c,0xcb1);
  h=2166136261u;for(i=0;i<{size};i++)h=(h^p[i])*16777619u;
  if(h!={hex(h)}u)finish(0x4641494c,0xcb2);
  *(volatile u32 *){hex(literal+0x20000000)}={hex(ram)}u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected title map reuse site')
            source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
        if a.reuse_title_palettes:
            for offset,original in ((0x13c48,0x033f4724),(0x13c50,0x033f4924)):
                if int.from_bytes(files['FPR.BIN'][offset:offset+4],'big')!=original:
                    raise ValueError('Unexpected title palette literal')
            code=f'''
 {{
  u32 i,k,h;const u32 expected[2]={{{hex(hashes[0])}u,{hex(hashes[1])}u}};
  if(*(volatile u32 *)0x06023c48!=0x033f4724u || *(volatile u32 *)0x06023c50!=0x033f4924u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xca1);
  for(k=0;k<2;k++){{
   volatile u8 *p=(volatile u8 *)(0x20231000u+k*512u);
   h=2166136261u;for(i=0;i<512;i++)h=(h^p[i])*16777619u;
   if(h!=expected[k])finish(0x4641494c,0xca2);
  }}
  *(volatile u32 *)0x26023c48=0x20231000u;
  *(volatile u32 *)0x26023c50=0x20231200u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected title palette reuse site')
            source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
        if a.reuse_title_vdp2_word:
            if files['FPR.BIN'][0x47c00:0x47c0c]!=bytes.fromhex('000000010294efdc06030000'):
                raise ValueError('Unexpected title VDP2 descriptor')
            code='''
 if(*(volatile u32 *)0x06057c00!=1u || *(volatile u32 *)0x06057c04!=0x0294efdcu ||
    *(volatile u32 *)0x06057c08!=0x06030000u || *(volatile u32 *)0x2021f010 ||
    *(volatile u16 *)0x20231420!=0x8000 || *(volatile u8 *)0x2023141f!=0xa5 ||
    *(volatile u8 *)0x20231422!=0x5a) finish(0x4641494c,0xc91);
 *(volatile u32 *)0x26057c04=0x20231420u;
 *(volatile u8 *)0xfffffe92=0x10;
'''
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected title reuse site')
            source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
        if a.reuse_post_difficulty_vdp2_word:
            if files['FPR.BIN'][0x4594c:0x45958]!=bytes.fromhex('000000010294efdc06030000'):
                raise ValueError('Unexpected post-difficulty VDP2 descriptor')
            code='''
 {
  if(*(volatile u32 *)0x0605594c!=1 || *(volatile u32 *)0x06055950!=0x0294efdcu ||
     *(volatile u32 *)0x06055954!=0x06030000u || *(volatile u32 *)0x2021f010 ||
     *(volatile u16 *)0x20231420!=0x8000 || *(volatile u8 *)0x2023141f!=0xa5 ||
     *(volatile u8 *)0x20231422!=0x5a) finish(0x4641494c,0xb30);
  *(volatile u32 *)0x26055950=0x20231420u;
  *(volatile u8 *)0xfffffe92=0x10;
 }
'''
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected post-difficulty word site')
            source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
        post_palettes=[]
        if a.prefetch_post_difficulty_palettes:
            for i,(address,literal) in enumerate(((0x033f2f24,0x060132dc),(0x033f3124,0x060132e4),
                    (0x033f3324,0x060132ec),(0x033f3724,0x060132f4),(0x033f3524,0x060132fc),
                    (0x033f4524,0x06013304),(0x033f6d24,0x0601330c))):
                ram=0x2023ca00+i*0x220
                if files['FPR.BIN'][literal-0x06010000:literal-0x06010000+4]!=address.to_bytes(4,'big'):
                    raise ValueError('Unexpected post-difficulty palette literal')
                data=banks[3][address-0x03000000:address-0x03000000+512]
                if len(data)!=512:raise ValueError('Truncated post-difficulty palette')
                h=2166136261
                for byte in data:h=((h^byte)*16777619)&0xffffffff
                code=f'''
 {{
  u32 n,h;u8 *p=(u8 *){hex(ram)};
  if(*(volatile u32 *){hex(literal)}!={hex(address)}u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xb40);
  *(volatile u8 *){hex(ram-1)}=0xa5;p[512]=0x5a;
  if(cart_cd_read({hex(address)}u,p,512)) finish(0x4641494c,0xb41);
  h=2166136261u;for(n=0;n<512;n++) h=(h^p[n])*16777619u;
  if(h!={hex(h)}u || *(volatile u8 *){hex(ram-1)}!=0xa5 || p[512]!=0x5a)
   finish(0x4641494c,0xb42);
  *(volatile u32 *){hex(literal+0x20000000)}={hex(ram)}u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
                if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected post palette site')
                source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
                post_palettes.append({'source':hex(address),'literal':hex(literal),
                    'ram':hex(ram),'bytes':512,'fnv1a':hex(h),'palette_index':i})
        if a.prefetch_post_difficulty_patterns:
            if files['FPR.BIN'][0x5ee28:0x5ee2c]!=bytes.fromhex('0287a78c') or files['FPR.BIN'][0x53852:0x53858]!=bytes.fromhex('0804020201ff'):
                raise ValueError('Unexpected scene pattern pointer or format table')
            # Format3 is 16-bit bitmap: 320 * 232 * 2 bytes plus two-long header.
            # Native row copier consumes 160 longs per row, not two longs per row.
            scene_bytes=8+320*232*2
            data=banks[1][0x7a78c:0x7a78c+scene_bytes]
            if len(data)!=scene_bytes or data[:8]!=bytes.fromhex('00000140000000e8'):
                raise ValueError('Unexpected scene pattern header')
            scene_pattern_hash=2166136261
            for byte in data:scene_pattern_hash=((scene_pattern_hash^byte)*16777619)&0xffffffff
            code=f'''
 {{
  u32 n,h;u8 *p=(u8 *)0x20280000;
  if(*(volatile u32 *)0x0606ee28!=0x0287a78cu || *(volatile u32 *)0x2021f010 ||
     *(volatile u16 *)0x06063852!=0x0804 || *(volatile u16 *)0x06063854!=0x0202 ||
     *(volatile u16 *)0x06063856!=0x01ff)
   finish(0x4641494c,0xb50);
  *(volatile u8 *)0x2027ffff=0xa5;p[{scene_bytes}]=0x5a;
  if(cart_cd_read(0x0287a78cu,p,{scene_bytes})) finish(0x4641494c,0xb51);
  h=2166136261u;for(n=0;n<{scene_bytes};n++) h=(h^p[n])*16777619u;
  if(h!={hex(scene_pattern_hash)}u || *(volatile u8 *)0x2027ffff!=0xa5 || p[{scene_bytes}]!=0x5a ||
     *(volatile u32 *)p!=0x140u || *(volatile u32 *)(p+4)!=232)
   finish(0x4641494c,0xb52);
  *(volatile u32 *)0x2606ee28=0x20280000u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected scene pattern site')
            source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
        if a.prefetch_post_difficulty_converted_patterns:
            if files['FPR.BIN'][0x5ee90:0x5ee94]!=bytes.fromhex('02843904') or files['FPR.BIN'][0x456fa:0x456fc]!=bytes.fromhex('00b2'):
                raise ValueError('Unexpected scene converter pointer or count')
            data=banks[1][0x43904:0x43904+5696]
            if len(data)!=5696:raise ValueError('Truncated scene converter resource')
            converted_pattern_hash=2166136261
            for byte in data:converted_pattern_hash=((converted_pattern_hash^byte)*16777619)&0xffffffff
            code=f'''
 {{
  u32 n,h;u8 *p=(u8 *)0x20251000;
  if(*(volatile u32 *)0x0606ee90!=0x02843904u || *(volatile u16 *)0x060556fa!=178 ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xb60);
  *(volatile u8 *)0x20250fff=0xa5;p[5696]=0x5a;
  if(cart_cd_read(0x02843904u,p,5696)) finish(0x4641494c,0xb61);
  h=2166136261u;for(n=0;n<5696;n++) h=(h^p[n])*16777619u;
  if(h!={hex(converted_pattern_hash)}u || *(volatile u8 *)0x20250fff!=0xa5 || p[5696]!=0x5a)
   finish(0x4641494c,0xb62);
  *(volatile u32 *)0x2606ee90=0x20251000u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected converted pattern site')
            source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
        if a.prefetch_post_difficulty_map:
            if files['FPR.BIN'][0x354c:0x3550]!=bytes.fromhex('02805928'):
                raise ValueError('Unexpected post-difficulty map literal')
            data=banks[1][0x5928:0x5928+436]
            if len(data)!=436 or data[:4]!=bytes.fromhex('000c0012'):
                raise ValueError('Unexpected post-difficulty map dimensions')
            post_map_hash=2166136261
            for byte in data:post_map_hash=((post_map_hash^byte)*16777619)&0xffffffff
            code=f'''
 {{
  u32 n,h;u8 *p=(u8 *)0x20252800;
  if(*(volatile u32 *)0x0601354c!=0x02805928u || *(volatile u32 *)0x2021f010)
   finish(0x4641494c,0xb70);
  *(volatile u8 *)0x202527ff=0xa5;p[436]=0x5a;
  if(cart_cd_read(0x02805928u,p,436)) finish(0x4641494c,0xb71);
  h=2166136261u;for(n=0;n<436;n++) h=(h^p[n])*16777619u;
  if(h!={hex(post_map_hash)}u || *(volatile u8 *)0x202527ff!=0xa5 || p[436]!=0x5a ||
     *(volatile u16 *)p!=12 || *(volatile u16 *)(p+2)!=18) finish(0x4641494c,0xb72);
  *(volatile u32 *)0x2601354c=0x20252800u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected scene map site')
            source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
        if a.prefetch_post_difficulty_map_second:
            if files['FPR.BIN'][0x3584:0x3588]!=bytes.fromhex('02805064'):
                raise ValueError('Unexpected second post-difficulty map literal')
            data=banks[1][0x5064:0x5064+2244]
            if len(data)!=2244 or data[:4]!=bytes.fromhex('0028001c'):
                raise ValueError('Unexpected second post-difficulty map dimensions')
            post_map_second_hash=2166136261
            for byte in data:post_map_second_hash=((post_map_second_hash^byte)*16777619)&0xffffffff
            code=f'''
 {{
  u32 n,h;u8 *p=(u8 *)0x20253000;
  if(*(volatile u32 *)0x06013584!=0x02805064u || *(volatile u32 *)0x2021f010)
   finish(0x4641494c,0xb80);
  *(volatile u8 *)0x20252fff=0xa5;p[2244]=0x5a;
  if(cart_cd_read(0x02805064u,p,2244)) finish(0x4641494c,0xb81);
  h=2166136261u;for(n=0;n<2244;n++) h=(h^p[n])*16777619u;
  if(h!={hex(post_map_second_hash)}u || *(volatile u8 *)0x20252fff!=0xa5 || p[2244]!=0x5a ||
     *(volatile u16 *)p!=40 || *(volatile u16 *)(p+2)!=28) finish(0x4641494c,0xb82);
  *(volatile u32 *)0x26013584=0x20253000u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected second scene map site')
            source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
        if a.prefetch_scene_character_palette:
            if files['FPR.BIN'][0x62b5c:0x62b60]!=bytes.fromhex('033f7524'):
                raise ValueError('Unexpected scene character palette entry')
            scene_character_palette_hash=2166136261
            for byte in banks[3][0x3f7524:0x3f7724]:
                scene_character_palette_hash=((scene_character_palette_hash^byte)*16777619)&0xffffffff
            code=f'''
 {{
  u32 n,h;u8 *p=(u8 *)0x20254000;
  if(*(volatile u32 *)0x06072b5c!=0x033f7524u || *(volatile u32 *)0x2021f010)
   finish(0x4641494c,0xb90);
  *(volatile u8 *)0x20253fff=0xa5;p[512]=0x5a;
  if(cart_cd_read(0x033f7524u,p,512)) finish(0x4641494c,0xb91);
  h=2166136261u;for(n=0;n<512;n++) h=(h^p[n])*16777619u;
  if(h!={hex(scene_character_palette_hash)}u || *(volatile u8 *)0x20253fff!=0xa5 || p[512]!=0x5a)
   finish(0x4641494c,0xb92);
  *(volatile u32 *)0x26072b5c=0x20254000u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected character palette site')
            source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
        difficulty_reuse=[]
        if a.reuse_difficulty_timeout_words:
            for address,literal,ram in ((0x028318fc,0x06025a94,0x2023c8c0),
                                       (0x02832684,0x06025a88,0x2023c980)):
                if files['FPR.BIN'][literal-0x06010000:literal-0x06010000+4]!=address.to_bytes(4,'big'):
                    raise ValueError('Unexpected difficulty timeout literal')
                h=2166136261
                for byte in banks[1][address-0x02800000:address-0x02800000+32]:
                    h=((h^byte)*16777619)&0xffffffff
                code=f'''
 {{
  u32 n,h;volatile u8 *p=(volatile u8 *){hex(ram)};
  if(*(volatile u32 *){hex(literal)}!={hex(address)}u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xb20);
  h=2166136261u;for(n=0;n<32;n++) h=(h^p[n])*16777619u;
  if(h!={hex(h)}u || *(volatile u8 *){hex(ram-1)}!=0xa5 || p[32]!=0x5a)
   finish(0x4641494c,0xb21);
  *(volatile u32 *){hex(literal+0x20000000)}={hex(ram)}u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
                if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected difficulty reuse site')
                source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
                difficulty_reuse.append({'literal':hex(literal),'source':hex(address),'ram':hex(ram),
                    'bytes':32,'fnv1a':hex(h)})
        credit_maps_rest=[]
        if a.prefetch_credit_maps_rest:
            for address,literal,ram,width,height in (
                    (0x0282fd50,0x06024958,0x2023c100,13,3),
                    (0x02830784,0x06024964,0x2023c200,13,7),
                    (0x02831260,0x06024970,0x2023c300,13,7),
                    (0x0283193c,0x06024980,0x2023c400,12,4),
                    (0x02831fa0,0x0602498c,0x2023c500,12,4),
                    (0x028326c4,0x06024998,0x2023c600,12,6)):
                size=4+width*height*2
                if files['FPR.BIN'][literal-0x06010000:literal-0x06010000+4]!=address.to_bytes(4,'big'):
                    raise ValueError('Unexpected additional credit map literal')
                data=banks[1][address-0x02800000:address-0x02800000+size]
                if len(data)!=size or data[:4]!=width.to_bytes(2,'big')+height.to_bytes(2,'big'):
                    raise ValueError('Unexpected additional credit map dimensions')
                h=2166136261
                for byte in data:h=((h^byte)*16777619)&0xffffffff
                code=f'''
 {{
  u32 n,h;u8 *p=(u8 *){hex(ram)};
  if(*(volatile u32 *){hex(literal)}!={hex(address)}u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xad0);
  *(volatile u8 *){hex(ram-1)}=0xa5;p[{size}]=0x5a;
  if(cart_cd_read({hex(address)}u,p,{size})) finish(0x4641494c,0xad1);
  h=2166136261u;for(n=0;n<{size};n++) h=(h^p[n])*16777619u;
  if(h!={hex(h)}u || *(volatile u8 *){hex(ram-1)}!=0xa5 || p[{size}]!=0x5a ||
     *(volatile u16 *)p!={width} || *(volatile u16 *)(p+2)!={height})
   finish(0x4641494c,0xad2);
  *(volatile u32 *){hex(literal+0x20000000)}={hex(ram)}u;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''
                if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected credit map rest site')
                source=source.replace(' TRACE[1]=23;',code+' TRACE[1]=23;')
                credit_maps_rest.append({'source':hex(address),'literal':hex(literal),
                    'ram':hex(ram),'bytes':size,'width':width,'height':height,'fnv1a':hex(h)})
        if a.prefetch_credit_map:
            if files['FPR.BIN'][0x14920:0x14924]!=bytes.fromhex('0282ebf0'):
                raise ValueError('Unexpected credit-selection map literal')
            data=banks[1][0x2ebf0:0x2ebf0+2244]
            if data[:4]!=bytes.fromhex('0028001c') or len(data)!=2244:
                raise ValueError('Unexpected credit-selection map dimensions')
            credit_map_hash=2166136261
            for byte in data:credit_map_hash=((credit_map_hash^byte)*16777619)&0xffffffff
            credit_map='''
 {
  u32 n,h;u8 *p=(u8 *)0x2023b800;
  if(*(volatile u32 *)0x06024920!=0x0282ebf0u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xac0);
  *(volatile u8 *)0x2023b7ff=0xa5;p[2244]=0x5a;
  if(cart_cd_read(0x0282ebf0u,p,2244)) finish(0x4641494c,0xac1);
  h=2166136261u;for(n=0;n<2244;n++) h=(h^p[n])*16777619u;
  if(h!=MAP_HASH || *(volatile u8 *)0x2023b7ff!=0xa5 || p[2244]!=0x5a ||
     *(volatile u16 *)p!=40 || *(volatile u16 *)(p+2)!=28)
   finish(0x4641494c,0xac2);
  *(volatile u32 *)0x26024920=0x2023b800u;
  *(volatile u8 *)0xfffffe92=0x10;
 }
'''.replace('MAP_HASH',hex(credit_map_hash)+'u')
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected credit map site')
            source=source.replace(' TRACE[1]=23;',credit_map+' TRACE[1]=23;')
        if a.prefetch_credit_palette:
            if files['FPR.BIN'][0x146e4:0x146e8]!=bytes.fromhex('033f2f24'):
                raise ValueError('Unexpected credit-transition palette literal')
            palette_reuse='''
 {
  u32 n,h;volatile u8 *p=(volatile u8 *)0x20235000;
  if(*(volatile u32 *)0x060246e4!=0x033f2f24u ||
     *(volatile u32 *)0x2021f010) finish(0x4641494c,0xab0);
  h=2166136261u;for(n=0;n<512;n++) h=(h^p[n])*16777619u;
  if(h!=PALETTE_HASH || *(volatile u8 *)0x20234fff!=0xa5 || p[512]!=0x5a)
   finish(0x4641494c,0xab1);
  *(volatile u32 *)0x260246e4=0x20235000u;
  *(volatile u8 *)0xfffffe92=0x10;
 }
'''.replace('PALETTE_HASH',hex(attract_palette_hash)+'u')
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected credit palette site')
            source=source.replace(' TRACE[1]=23;',palette_reuse+' TRACE[1]=23;')
        if a.prefetch_credit_vdp2_word:
            if files['FPR.BIN'][0x47e54:0x47e5c]!=bytes.fromhex('000000010294efdc'):
                raise ValueError('Unexpected credit-transition VDP2 descriptor')
            source=source.replace(' TRACE[1]=23;', '''
 if(*(volatile u32 *)0x06057e54!=1u || *(volatile u32 *)0x06057e58!=0x0294efdcu ||
    *(volatile u16 *)0x20231420!=0x8000 || *(volatile u8 *)0x2023141f!=0xa5 ||
    *(volatile u8 *)0x20231422!=0x5a || *(volatile u32 *)0x2021f010)finish(0x4641494c,0xc61);
 *(volatile u32 *)0x26057e58=0x20231420u;
 *(volatile u8 *)0xfffffe92=0x10;
 TRACE[1]=23;''')
        if info.get('resident_backup_callbacks'):
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected resident backup preflight site')
            source=source.replace(' TRACE[1]=23;', '''
 {u32 j;u8 saved[10];volatile u8 *p=(volatile u8 *)0x2022fef0;
  u32 (*access)(u32,u32,u32)=(void *)0x00212600;
  u8 dirty=*(volatile u8 *)0x06000653;
  for(j=0;j<10;j++){saved[j]=p[j];p[j]=0xa5;}
  access(2,0x2018fef0,0x1234);
  if(access(0,0x2018fef0,0)!=0x1234)finish(0x4641494c,0xc21);
  access(3,0x2018fef0,0x89abcdef);
  if(access(1,0x2018fef0,0)!=0x89abcdef)finish(0x4641494c,0xc22);
  if(access(1,0x2022fef0,0)!=0x89abcdef)finish(0x4641494c,0xc25);
  access(2,0x2022fef0,0x5678);
  if(access(0,0x2018fef0,0)!=0x5678 || access(0,0x2022fef0,0)!=0x5678)finish(0x4641494c,0xc26);
  for(j=0;j<10;j++)if((!(j&1) || j==9) && p[j]!=0xa5)finish(0x4641494c,0xc23);
  ((void (*)(void))0x00212800)();
  if(*(volatile u8 *)0x06000653!=1)finish(0x4641494c,0xc24);
  *(volatile u8 *)0x06000653=dirty;
  for(j=0;j<10;j++)p[j]=saved[j];
 }
 TRACE[1]=23;''')
        if info.get('resident_factory_config'):
            expected=','.join(hex(v) for v in bytes.fromhex(info['resident_factory_config']['bytes']))
            source=source.replace(' TRACE[1]=23;', '''
 {static const u8 expected[]={FACTORY_EXPECTED};volatile u8 *p=(volatile u8 *)0x0600078c;u32 j;
  for(j=0;j<16;j++)if(p[j]!=expected[j])finish(0x4641494c,0xc31);
  p[4]=2;((void (*)(void))0x00212e00)();
  if(p[4]!=2)finish(0x4641494c,0xc32);
  p[4]=expected[4];
  {static const u8 probe[]={0x12,0x34,0x56,0x78};u8 saved[4];
   volatile u8 *q=(volatile u8 *)0x06000828;
   u8 before=q[-1],after=q[4];
   for(j=0;j<4;j++)saved[j]=q[j];
   ((void (*)(const u8 *))0x00212f00)(probe);
   for(j=0;j<4;j++)if(q[j]!=probe[j])finish(0x4641494c,0xc33);
   if(q[-1]!=before || q[4]!=after)finish(0x4641494c,0xc34);
   for(j=0;j<4;j++)q[j]=saved[j];
  }
 }
 TRACE[1]=23;'''.replace('FACTORY_EXPECTED',expected))
        if info.get('coin_trial',{}).get('arm_before_native_handoff'):
            if info['coin_trial'].get('main_clock'):
                guard=bytes.fromhex('d32f03030009b1870009d22e')
                if files['FPR.BIN'][0x2e4:0x2f0]!=guard:raise ValueError('Unexpected native main entry')
                source=source.replace(' TRACE[1]=23;', '''
 {volatile u8 *p=(volatile u8 *)0x260102e4;
  static const u8 expected[]={0xd3,0x2f,0x03,0x03,0x00,0x09,0xb1,0x87,0x00,0x09,0xd2,0x2e};
  static const u8 patch[]={0xd3,0x01,0x43,0x2b,0x00,0x09,0x00,0x09,0x00,0x21,0x24,0x00};
  u32 j;for(j=0;j<12;j++)if(p[j]!=expected[j])finish(0x4641494c,0xc01);
  for(j=0;j<12;j++)p[j]=patch[j];
  *(volatile u32 *)0x2021f02c=0;
  *(volatile u8 *)0xfffffe92=0x10;
 }
 TRACE[1]=23;''')
            if source.count(' TRACE[1]=23;')!=1:raise ValueError('Unexpected coin arm site')
            source=source.replace(' TRACE[1]=23;',
                ' *(volatile u32 *)0x2021f020=0;\n *(volatile u32 *)0x2021f028=1;\n TRACE[1]=23;')
        (out/'mpr_probe.c').write_text(source)
    if a.test_nvram_shadow:
        source=source.replace('static const struct','extern u32 nv_channel_flags(void);\nstatic const struct')
        extra_sources.append(runtime/'nv_checks.s')
        nv_test='''
 {
  u32 n;u8 *v=(u8 *)0x20223d54;
  ((void (*)(u32,u32))0x00210330)(0x20223d54,0x12345678);
  TRACE[4]=((u32 (*)(u32))0x00210300)(0x20223d54);
  TRACE[5]=((u32 (*)(void))0x002101e0)();
  if(TRACE[4]!=0x12345678 || TRACE[5]!=0x20220100 ||
     v[1]!=0x12 || v[3]!=0x34 || v[5]!=0x56 || v[7]!=0x78)
      finish(0x4641494c,0xb02);
  for(n=0;n<8;n+=2) if(v[n]) finish(0x4641494c,0xb03);
  if(*(volatile u8 *)0x2021ffff!=0xa5 || *(volatile u8 *)0x20230000!=0x5a)
      finish(0x4641494c,0xb04);
  ((void (*)(u32,u32))0x00210330)(0x20223d54,0);
  TRACE[6]=2;
  TRACE[7]=nv_channel_flags();
  if(TRACE[7]!=1) finish(0x4641494c,0xb06);
 }
'''
        if a.test_nvram_guard:
            nv_test+='''
 *(volatile u8 *)0x26000650=9;
 ((u32 (*)(void))0x002101e0)();finish(0x4641494c,0xb05);
'''
        if source.count('hardware_test();')!=1:raise ValueError('NV test insertion failed')
        source=source.replace('hardware_test();','hardware_test();'+nv_test)
        (out/'mpr_probe.c').write_text(source)
    if a.irq_resource_cache:
        if not a.resident_hle:raise ValueError('IRQ resource cache requires resident HLE')
        seam=' if(cd_init() || cart_cd_init()) finish(0x4641494c,1);'
        if source.count(seam)!=1:raise ValueError('Unexpected cache preflight seam')
        block=image[0xff0000:0x1000000]
        h=2166136261
        for byte in block:h=((h^byte)*16777619)&0xffffffff
        source=source.replace(seam,seam+f'''
 if(cart_cd_irq_cache_load(0x033f0000))
     finish(0x4641494c,0x681);
 {{u32 k,n,h=2166136261u;for(k=0;k<CART_IRQ_CACHE_BYTES;k+=256){{
   if(cart_cd_irq_read(0x033f0000+k,p,256))finish(0x4641494c,0x681);
   for(n=0;n<256;n++)h=(h^p[n])*16777619u;}}
   if(h!=0x{h:08x}u)finish(0x4641494c,0x682);}}
''',1)
        (out/'mpr_probe.c').write_text(source)
    if a.prefetch_transition_word_table:
        if not (a.irq_resource_cache and a.boot_trial):raise ValueError('Transition table requires IRQ cache boot trial')
        from transition_word_table import extract_table
        table=extract_table(image[0x5512c4:0x551ac4])
        th=2166136261
        for byte in table:th=((th^byte)*16777619)&0xffffffff
        seam=' *(volatile u32 *)0x2021f028=1;'
        if source.count(seam)!=1:raise ValueError('Unexpected transition table handoff seam')
        source=source.replace(seam,f'''
 {{CdFile tf;u32 n,h=2166136261u;u8 *p=(u8 *)0x20271000;
  if(*(volatile u16 *)0x26041952!=0xd210 || *(volatile u32 *)0x26041994!=0x029512c4)
    finish(0x4641494c,0x691);
  *(volatile u8 *)0x20270fff=0xa5;p[{len(table)}]=0x5a;
  if(cd_find_root("MPR1.BIN;1",&tf) || cd_read_at(&tf,0x1512c4,p,{len(table)}))
    finish(0x4641494c,0x692);
  for(n=0;n<{len(table)};n++)h=(h^p[n])*16777619u;
  if(h!=0x{th:08x}u || *(volatile u8 *)0x20270fff!=0xa5 || p[{len(table)}]!=0x5a)
    finish(0x4641494c,0x693);
  *(volatile u32 *)0x26041994=0x20271000;
  *(volatile u8 *)0xfffffe92=0x10;
 }}
'''+seam,1)
        (out/'mpr_probe.c').write_text(source)
    if a.prefetch_idle_ui_table:
        if not a.boot_trial:raise ValueError('Idle UI table requires boot trial')
        idle_table=image[0x55992c:0x559934]
        if idle_table!=bytes.fromhex('ffff000000000000'):raise ValueError('Unexpected idle UI sentinel')
        seam=' *(volatile u32 *)0x2021f028=1;'
        if source.count(seam)!=1:raise ValueError('Unexpected idle UI handoff seam')
        source=source.replace(seam,'''
 {CdFile tf;u8 *p=(u8 *)0x20272000;
  if(*(volatile u16 *)0x26032182!=0xd213 || *(volatile u32 *)0x260321d0!=0x0295992c)
    finish(0x4641494c,0x6a1);
  *(volatile u8 *)0x20271fff=0xa5;p[8]=0x5a;
  if(cd_find_root("MPR1.BIN;1",&tf) || cd_read_at(&tf,0x15992c,p,8))
    finish(0x4641494c,0x6a2);
  if(*(volatile u32 *)p!=0xffff0000u || *(volatile u32 *)(p+4)!=0 ||
     *(volatile u8 *)0x20271fff!=0xa5 || p[8]!=0x5a)finish(0x4641494c,0x6a3);
  *(volatile u32 *)0x260321d0=0x20272000;
  *(volatile u8 *)0xfffffe92=0x10;
 }
'''+seam,1)
        (out/'mpr_probe.c').write_text(source)
    if a.experimental_sound_boot:
        seam=' game_handoff();finish'
        if source.count(seam)!=1:raise ValueError('Unexpected sound boot handoff seam')
        source='extern int sound_boot_start(void);\n'+source.replace(seam,
            ' {int sound_error=sound_boot_start();if(sound_error)finish(0x4641494c,(u32)sound_error);}\n'+seam,1)
        extra_sources.append(runtime/'sound_boot.c')
        if a.experimental_sound_align_pack:
            from inspect_sound_align_pack import validate_patch
            validate_patch(image[0x55a48c:0x55a48c+7342],
                           (runtime/'sound_align_pack.c').read_text())
            extra_sources.append(runtime/'sound_align_pack.c')
        (out/'mpr_probe.c').write_text(source)
    if a.experimental_sound_cd_dma:
        seam=' game_handoff();finish'
        if source.count(seam)!=1:raise ValueError('Unexpected sound DMA handoff seam')
        source='extern int sound_cd_dma_install(void);\n'+source.replace(seam,
            ' if(sound_cd_dma_install())finish(0x4641494c,0xb60);\n'+seam,1)
        extra_sources.extend((runtime/'sound_cd_dma.c',runtime/'sound_dma_native.s',runtime/'sound_dma_bounce.c'))
        (out/'mpr_probe.c').write_text(source)
    if a.experimental_sound_dma_prefetch:
        seam=' game_handoff();finish'
        source='extern int sound_cd_dma_prefetch(void);\n'+source.replace(seam,
            ' if(sound_cd_dma_prefetch())finish(0x4641494c,0xb68);\n'+seam,1)
        (out/'mpr_probe.c').write_text(source)
    if a.experimental_sound_stream_handoff:
        seam=' game_handoff();finish'
        if source.count(seam)!=1:raise ValueError('Unexpected stream handoff seam')
        source='extern int sound_stream_handoff_install(void);\n'+source.replace(seam,
            ' if(sound_stream_handoff_install())finish(0x4641494c,0xb70);\n'+seam,1)
        extra_sources.extend((runtime/'sound_stream_mailbox.c',runtime/'sound_stream_handoff.c',
                              runtime/'sound_stream_main_gate.s'))
        if a.experimental_sound_pad_yield:
            gate=(runtime/'sound_stream_main_gate.s').read_text()
            anchor='    mov #-16,r0'
            if gate.count(anchor)!=1:raise ValueError('Unexpected stream mask seam')
            gate=gate.replace(anchor,'    mov.l pad_yield_worker,r0\n    jsr @r0\n    nop\n'+anchor,1)
            gate+='\n    .align 2\npad_yield_worker: .long _sound_stream_pad_yield\n'
            generated=out/'sound_stream_main_gate_pad_yield.s';generated.write_text(gate)
            extra_sources.remove(runtime/'sound_stream_main_gate.s')
            extra_sources.extend((generated,runtime/'sound_pad_yield.c'))
        (out/'mpr_probe.c').write_text(source)
    if a.visible_boot_errors:
        anchor=' *(volatile u16 *)0x25f80000=0x8000;for(;;)__asm__ volatile("nop");'
        if source.count(anchor)!=1:raise ValueError('Unexpected fatal-display seam')
        source='#include "diagnostic_screen.h"\n'+source.replace(anchor,
            ' *(volatile u16 *)0x25f80000=0x8000;\n'
            ' if(state==0x4641494c){\n'
            '  __asm__ volatile("ldc %0,sr"::"r"(0xf0):"memory");\n'
            '  TRACE[6]=0;\n'
            '  diagnostic_screen(code,cd_error.code,cd_error.lba,cd_error.hirq);\n'
            '  TRACE[6]=0x44535059;\n'
            ' }\n'
            ' for(;;)__asm__ volatile("nop");',1)
        extra_sources.append(runtime/'diagnostic_screen.c')
        (out/'mpr_probe.c').write_text(source)
    if a.loading_screen:
        begin=' TRACE[0]=0x4d505244;TRACE[1]=0;\n'
        end=' irq_test();hardware_test();'
        if source.count(begin)!=1 or source.count(end)!=1:raise ValueError('Unexpected loading-screen seams')
        # Expected CD bytes before hardware_test: FPR + HLE (+ IRQ cache); cart_cd adds MPR0 when a cart is present.
        total=0xf0000+(a.resident_hle.stat().st_size if a.resident_hle else 0)+(0x10000 if a.irq_resource_cache else 0)
        source='#include "loading_screen.h"\n'+source.replace(begin,begin+f' loading_begin(0x{total:x}u);\n',1)
        source=source.replace(end,' loading_end();\n'+end,1)
        extra_sources.append(runtime/'loading_screen.c')
        (out/'mpr_probe.c').write_text(source)
    if a.saroo_native_rom:
        # Native SAROO MPR bypasses the CD sector cache, so the CD-path cache
        # statistic self-tests do not apply; the data checks stay mandatory.
        native=[(' if(cart_cache_stats.sector_reads!=1) finish(0x4641494c,0x90e);',
                 ' if(!cart_cd_saroo_resident() && cart_cache_stats.sector_reads!=1) finish(0x4641494c,0x90e);'),
                ('  if(h!=0xa574fdafu || cart_cache_stats.sector_reads!=2 ||@      cart_cache_stats.misses!=2 || cart_cache_stats.hits!=41)',
                 '  if(h!=0xa574fdafu || (!cart_cd_saroo_resident() && (cart_cache_stats.sector_reads!=2 ||@      cart_cache_stats.misses!=2 || cart_cache_stats.hits!=41)))'),
                ('      (void *)0x033b96ac,32)!=(void *)0x25c7f3e0 ||@      cart_cache_stats.sector_reads!=1) finish(0x4641494c,0x706);',
                 '      (void *)0x033b96ac,32)!=(void *)0x25c7f3e0 ||@      (!cart_cd_saroo_resident() && cart_cache_stats.sector_reads!=1)) finish(0x4641494c,0x706);')]
        for old,new in native:
            old=old.replace('@',chr(10));new=new.replace('@',chr(10))
            if source.count(old)>1:raise ValueError('Ambiguous cache self-test seam')
            source=source.replace(old,new)
        source='extern int cart_cd_saroo_resident(void);'+chr(10)+source
        (out/'mpr_probe.c').write_text(source)
    boot_args=['--sega-dir',str(a.sega_dir),'--output-dir',str(out),'--cd-read']
    if a.visible_boot_errors:boot_args.append('--visible-copy-errors')
    if a.resident_hle:
        boot_args.extend(['--fpr-rom-dir',str(a.rom_dir),'--hle-bin',str(a.resident_hle),
                          '--relocate-loader'])
    boot.main(boot_args,
        probe_source=out/'mpr_probe.c', extra_sources=extra_sources,
        extra_files=files, stack_address=0x20300000)
    disc_manifest=json.loads((out/'manifest.json').read_text())
    if a.loading_screen:
        disc_manifest['loading_screen']={'layer':'NBG0 512x256 RGB32768 bitmap','span':'probe start .. before hardware_test',
            'teardown':'BGON off, VRAM A bitmap cleared to 0; display off left to hardware_test resident init','post_video_init_loads':'not shown (display off)'}
    if a.saroo_native_rom:
        disc_manifest['saroo_native_rom']={'sd_file':'/SAROO/STV/BAKUMPR.BIN','sdram':'0x400000 (guest 0x02400000..0x033fffff)',
            'bakumpr_sha256':hashlib.sha256((out/'BAKUMPR.BIN').read_bytes()).hexdigest(),
            'stats_symbol':'_cart_saroo_stats','requires':'stv2ss mcuapp.bin (SSCMD 0x40/0x41), FPGA 06+ on HW1.3',
            'fallback':'CD','assume_emulator_cart':a.saroo_native_assume,'hardware_accepted':False}
    if a.experimental_mpr0_cart_ram:
        disc_manifest['experimental_mpr0_cart_ram']={'window':'0x02400000..0x027fffff','cart_id':'0x5c',
            'mpr0_fnv1a':f'{mpr0_cart_hash:08x}','stats_symbol':'_cart_mpr0_stats',
            'no_cart':'CD fallback','hash_mismatch':'fail-stop','hardware_accepted':False}
    if a.experimental_sound_pad_yield:
        disc_manifest['experimental_sound_pad_yield']={'budget':500000,'position':'before IRQ mask',
            'smpc_writes':False,'input_writes':False,'irq_mask_unchanged':True,'accepted':False}
    if a.experimental_sound_dma_prefetch:
        disc_manifest['experimental_sound_dma_prefetch']={'sources':['0x02a08000+36864','0x024b0000+65536','0x024c0000+65536','0x027305d4+4096','0x026ad070+32768','0x026b54c0+8192','0x02784358+8192','0x0279532c+8192','0x0251abc4+20480','0x0251ec30+32768'],
            'ram':['0x202c8000..0x202f8000','0x202b8000..0x202c7000','0x20256000..0x2025e000'],
            'fnv1a':['819c7f23','1d78cb8f','6885052b','3d9a738d','bde261dd','751e5471','2fd8a979','7d888654','8dda5cc8','22ae4c30'],
            'runtime_cd_fallback':False,'audible_accepted':False,'hardware_accepted':False}
    if a.experimental_sound_cd_dma:
        disc_manifest['experimental_sound_cd_dma']={'staging':'0x202b8000..0x202c8000 plus guards',
            'native_busy_completion_preserved':True,'irq_cd_reads_allowed':False,
            'audible_accepted':False,'hardware_accepted':False}
    if a.experimental_sound_boot:
        disc_manifest['experimental_sound_boot']={'staging':'0x202b0000..0x202b4058',
            'sequence':'SNDOFF/CD payloads/16-bit Sound RAM verification/SNDON/native OK',
            'old_async_sound_poll_enabled':False,'audible_accepted':False,'hardware_accepted':False}
    if a.visible_boot_errors:
        disc_manifest['visible_boot_errors']={'rows':['loader error','CD error','LBA','HIRQ'],
            'scope':'loader finish and copy-hook fatal; native HLE guard loops not intercepted',
            'display_complete_marker':'TRACE[6]=0x44535059 after drawing',
            'hardware_accepted':False}
    if a.prefetch_idle_ui_table:
        disc_manifest['idle_ui_table']={'source':'0x0295992c','ram':'0x20272000',
            'bytes':8,'data':'ffff000000000000','literal_patch':'0x060321d0',
            'instruction_guard':'0x06032182=d213','termination':'first word ffff'}
    if a.prefetch_transition_word_table:
        disc_manifest['transition_word_table']={'source':'0x029512c4',
            'ram':'0x20271000','bytes':len(table),'sha256':hashlib.sha256(table).hexdigest(),
            'fnv1a':hex(th),'literal_patch':'0x06041994','instruction_guard':'0x06041952=d210'}
    if a.irq_resource_cache:
        disc_manifest['irq_resource_cache']={'source':'0x033f0000..0x033fffff',
            'ram':'0x20260000..0x2026ffff',
            'bytes':65536,'sha256':hashlib.sha256(block).hexdigest(),
            'boot_fnv1a':hex(h),'irq_cd_io':False,'out_of_range':'fatal503'}
    disc_manifest['expected']='green after seven MPR windows and range/guard checks (8 groups)'
    if a.test_copy_hooks:
        disc_manifest.update(expected='green after 12 groups, including patched FPR copy entries',
                             heartbeat_address='0x0600e000',stack='0x20300000')
    if a.resident_hle:
        disc_manifest.update(expected='green after 14 groups with resident initialization and LWRAM hooks',
                             heartbeat_address='0x0021e000',loader_ram='0x00240000')
    if a.test_vdp_cache:
        disc_manifest['expected']='green after 16 groups; 42 VDP1 copies require two MPR sector reads'
    if a.test_irq_dispatch:
        disc_manifest['expected']='green after 18 groups including real VBLANK-OUT IRQ depth/RAM copy'
    if a.test_irq_guard:
        disc_manifest['expected']='intentional FAIL 0x503 when real IRQ attempts MPR copy'
    if a.test_hardware_init:
        disc_manifest['expected']='green after 20 groups including hardware baseline and forced post-init CD reads'
    if a.boot_trial:
        disc_manifest['expected']='execute original game entry with input/audio isolation; BOOT TRIAL not playable'
        disc_manifest.update(status='controlled-game-start-not-playable',heartbeat='0x42545259',
                             game_entry='0x06010808',game_stack_seed='0x060fffDC')
        disc_manifest['original_video_init_trial']=a.test_game_video_init
        disc_manifest['original_startup_init_trial']=a.test_game_startup_init
        if a.prefetch_story_table:
            disc_manifest['story_table_prefetch']={'source':'0x0295927c','bytes':240,
                'ram':'0x2023b000..0x2023b0ef','literal':'0x06031ac8','fnv1a':hex(story_hash),
                'records':30,'record_bytes':8,'terminal_record':29}
        if a.prefetch_attract_map:
            disc_manifest['attract_map_prefetch']={'source':'0x02828b94','bytes':2244,
                'ram':'0x2023a000..0x2023a8c3','literal':'0x06030e94',
                'width':40,'height':28,'fnv1a':hex(attract_map_hash)}
        if a.prefetch_attract_patterns:
            disc_manifest['attract_patterns_prefetch']={'source':'0x02854264','bytes':13632,
                'ram':'0x20236000..0x2023953f','literal':'0x06030d94','fnv1a':hex(pattern_hash),
                'groups':426,'longs_per_group':8,'original_parser':'0x0603858c'}
        if a.prefetch_attract_palette:
            disc_manifest['attract_palette_prefetch']={'source':'0x033f2f24','bytes':512,
                'ram':'0x20235000..0x202351ff','literal':'0x06030d5c','fnv1a':hex(attract_palette_hash)}
        if a.prefetch_attract_vdp2_word:
            disc_manifest['attract_vdp2_word']={'descriptor':'0x060591ec','literal':'0x060591f0',
                'source':'0x0294efdc','bytes':2,'ram':'0x20231420','reuses_verified_cold_word':True}
        if a.test_system_flag_slot:
            disc_manifest['system_flag_slot_test']='slot 06000680=00210BA0; operations 1/0/2, boundary guards and state restoration'
        if a.prefetch_cold_maps_rest:
            disc_manifest['remaining_cold_maps_prefetch']=rest_maps
        if a.prefetch_cold_map:
            disc_manifest['cold_map_prefetch']={'source':'0x02821668','width':31,'height':17,
                'bytes':1058,'fnv1a':hex(map_hash),'ram':'0x20232000..0x20232421',
                'literal':'0x0602843c'}
        if a.prefetch_cold_vdp2_word:
            disc_manifest['cold_vdp2_word_prefetch']={'source':'0x0294efdc','bytes':2,
                'ram':'0x20231420..0x20231421','literal':'0x06058204',
                'trace30':'prefetched FNV1a','trace31':'prefetched bytes'}
        if a.prefetch_cold_palettes:
            disc_manifest['cold_palette_prefetch']={'ram':'0x20231000..0x202313ff',
                'sources':['0x033f4724','0x033f4924'],'sizes':[512,512],
                'fnv1a':[hex(h) for h in hashes],
                'pointer_literals':['0x060282ac','0x060282b4'],
                'note':'Two known mode-0 palette sources only; IRQ CD guard unchanged'}
        if a.test_word_copy_hook:
            disc_manifest['word_copy_hook']={'entry':'0x0604afbc','original_bytes':'6753a0056543625375026175',
                'note':'Experimental word-count CD copy; native RAM loop retained; IRQ guard unchanged'}
        if a.test_alt_long_copy_hook:
            disc_manifest['alt_long_copy_hook']={'entry':'0x0604afec',
                'original_bytes':'6753a0056543625375046176','preflight_source':'0x02800548',
                'preflight_bytes':64,'preflight_fnv1a':hex(alt_hash),
                'trace28':'preflight hash','trace29':'preflight byte count'}
        disc_manifest['handoff_mask_shadow']={'address':'0x06000348','value':'0xffffe1fc'}
    for profile in ('resident_start_baseline','start_trial','resident_player_input','resident_game_ports','resident_system_config','resident_session_stats','confirm_trial','saturn_pad_input','manual_pad_profile','pad_frame_clock','pad_timed_poll','pad_hblank_worker'):
        if info.get(profile):disc_manifest[profile]=info[profile]
    if a.prefetch_scene_character_palette:
        disc_manifest['scene_character_palette']={'literal':'0x06072b5c','source':'0x033f7524',
            'ram':'0x20254000..0x202541ff','bytes':512,'fnv1a':hex(scene_character_palette_hash),
            'actual_caller_pr':'0x0603445a','palette_index':6}
    if a.prefetch_post_difficulty_map_second:
        disc_manifest['post_difficulty_map_second']={'literal':'0x06013584','source':'0x02805064',
            'ram':'0x20253000..0x202538c3','bytes':2244,'width':40,'height':28,
            'fnv1a':hex(post_map_second_hash),'actual_caller_pr':'0x060134ec','parser':'0x0604939c'}
    if a.prefetch_post_difficulty_map:
        disc_manifest['post_difficulty_map']={'literal':'0x0601354c','source':'0x02805928',
            'ram':'0x20252800..0x202529b3','bytes':436,'width':12,'height':18,'fnv1a':hex(post_map_hash),
            'actual_caller_pr':'0x0601349c','parser':'0x0604939c'}
    if a.prefetch_post_difficulty_converted_patterns:
        disc_manifest['post_difficulty_converted_patterns']={'literal':'0x0606ee90','source':'0x02843904',
            'ram':'0x20251000..0x2025263f','bytes':5696,'groups':178,'longs_per_group':8,
            'count_literal':'0x060556fa','fnv1a':hex(converted_pattern_hash),'parser':'0x0603858c',
            'runtime_region':'0x20240000..0x2024ffff (existing linker assertion includes BSS)'}
    if a.prefetch_post_difficulty_patterns:
        disc_manifest['post_difficulty_patterns']={'literal':'0x0606ee28','source':'0x0287a78c',
            'ram':'0x20280000..0x202a4407','bytes':scene_bytes,'fnv1a':hex(scene_pattern_hash),
            'groups':232,'observed_format':3,'observed_consumed_bytes':1864,
            'note':'Bounded maximum normal-format backing slice; no format/state changes'}
    if a.prefetch_post_difficulty_palettes:
        disc_manifest['post_difficulty_palettes']=post_palettes
    if a.reuse_title_vdp2_word:
        disc_manifest['title_vdp2_word']={'descriptor':'0x06057c00','literal':'0x06057c04',
            'source':'0x0294efdc','ram':'0x20231420','bytes':2,'queue_caller':'0x06023b72',
            'irq_cd_guard_retained':True}
    if a.reuse_title_palettes:
        disc_manifest['title_palettes']={'literals':['0x06023c48','0x06023c50'],
            'sources':['0x033f4724','0x033f4924'],'ram':['0x20231000','0x20231200'],
            'bytes_each':512,'fnv1a':[hex(h) for h in hashes],'irq_cd_guard_retained':True}
    if a.reuse_title_maps:
        disc_manifest['title_maps']=title_maps
    if a.reuse_post_difficulty_vdp2_word:
        disc_manifest['post_difficulty_vdp2_word']={'descriptor':'0x0605594c','literal':'0x06055950',
            'source':'0x0294efdc','ram':'0x20231420','bytes':2,'original_caller_pr':'0x0601322e'}
    if a.reuse_difficulty_timeout_words:
        disc_manifest['difficulty_timeout_reuse']=difficulty_reuse
    if a.prefetch_credit_timeout_animation:
        disc_manifest['credit_timeout_animation']={'table':'0x06057cf8','source':'0x02831f60',
            'ram':'0x2023c900..0x2023c93f','bytes':64,'fnv1a':hex(timeout_animation_hash),
            'timing_and_sentinel_unchanged':True}
    if a.prefetch_credit_ui_animation:
        disc_manifest['credit_ui_animation']={'table':'0x06057cb0','sources':['0x02830744','0x02830764'],
            'ram':['0x2023c800','0x2023c880'],'bytes_per_frame':32,'second_fnv1a':hex(animation_hash),
            'timing_and_sentinel_unchanged':True}
    if a.prefetch_credit_ui_words:
        disc_manifest['credit_ui_words']=credit_ui_words
    if a.prefetch_credit_maps_rest:
        disc_manifest['credit_maps_rest']=credit_maps_rest
    if a.prefetch_credit_map:
        disc_manifest['credit_map']={'literal':'0x06024920','source':'0x0282ebf0',
            'ram':'0x2023b800..0x2023c0c3','bytes':2244,'width':40,'height':28,
            'fnv1a':hex(credit_map_hash),'original_parser':'0x0604939c'}
    if a.prefetch_credit_palette:
        disc_manifest['credit_palette']={'literal':'0x060246e4','original':'0x033f2f24',
            'ram':'0x20235000','bytes':512,'fnv1a':hex(attract_palette_hash),
            'note':'Rechecks complete cached palette; IRQ CD guard retained'}
    if a.resident_hle and info.get('nvram_shadow'):
        disc_manifest['nvram_shadow']=info['nvram_shadow']
    if a.test_nvram_shadow:disc_manifest['nvram_shadow_test']=True
    if a.prefetch_credit_vdp2_word:
        disc_manifest['credit_vdp2_word']={'literal':'0x06057e58','original':'0x0294efdc',
            'ram':'0x20231420','bytes':2,'note':'Reuses independently verified cold word; IRQ CD guard retained'}
    if a.test_nvram_guard:disc_manifest['expected']='intentional FAIL 0xb01 for invalid NV channel 9'
    (out/'manifest.json').write_text(json.dumps(disc_manifest,indent=2)+'\n')
    manifest={'status':'MPR windows diagnostic, not a playable game',
       'mapping':'0x02400000..0x033fffff; word-swapped CD bytes',
       'banks':manifest,'windows':[{'address':hex(0x02400000+o),'size':s} for o,s in windows]}
    (out/'mpr-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__': main()
