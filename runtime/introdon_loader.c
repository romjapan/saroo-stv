/* Introdon loader. Never load over SAROO's SDRAM menu/TMPBUFF. */
#include "cd_io.h"
#include "saroo_rom.h"
#include "diagnostic_screen.h"
#if INTRO_PROGRESS
#include "load_progress.h"
static u32 cd_seen;
static void cd_tick(void) {
    u32 now=cd_progress_bytes;
    load_progress_advance(now-cd_seen);cd_seen=now;
}
#define STAGE(s) load_progress_stage(s)
#define ADVANCE(n) load_progress_advance(n)
#else
#define STAGE(s) ((void)0)
#define ADVANCE(n) ((void)0)
#endif
#define W32(a) (*(volatile u32 *)(a))
#define W8(a) (*(volatile u8 *)(a))
#define W16(a) (*(volatile u16 *)(a))
#define TRACE ((volatile u32 *)0x2600a800)
extern void game_handoff(void);
/* BIOS ba34..ba60: do not inherit Saturn menu framebuffer mode/window.
   All VDP1 register accesses are 16-bit. ENDR is a command, not a shadow. */
static void vdp1_swap(void) {
    W16(0x25d00002)=3;
    /* Manual change takes effect at VBlank end. No drawing is active. */
    while(W16(0x25f80004)&8) {}
    while(!(W16(0x25f80004)&8)) {}
    while(W16(0x25f80004)&8) {}
}
static void cold_vdp1(int empty_memory) {
    u32 i;
    W16(0x25d00004)=0;
    W16(0x25d0000c)=0;
    W16(0x25d00000)=0;
    if(empty_memory) {
        /* TVSTAT reports VBlank continuously with display disabled. Enable
           scanout with every layer hidden while waiting for manual swaps. */
        W16(0x25f80020)=0;
        for(i=0xf0;i<=0xf6;i+=2)W16(0x25f80000+i)=0;
        W16(0x25f80000)=0x8001;
        /* Match the observed blank BIOS draw buffer; use an empty END
           instead of copying its obsolete menu commands or graphics. */
        for(i=0;i<0x80000;i+=2)W16(0x25c00000+i)=0;
        vdp1_swap();
        for(i=0;i<0x40000;i+=2)W16(0x25c80000+i)=0;
        vdp1_swap();
        for(i=0;i<0x40000;i+=2)W16(0x25c80000+i)=0;
        W16(0x25f80000)=1;W16(0x25f80020)=8;
        for(i=0xf0;i<=0xf6;i+=2)W16(0x25f80000+i)=0x0606;
    }
    W16(0x25d00002)=0;
    W16(0x25d00006)=0;
    W16(0x25d00008)=0;
    W16(0x25d0000a)=0x58e0;
    W16(0x25c00000)=0x8000;
    W16(0x25d00004)=2;
}
/* Independently expressed register effects of BIOS 1c892/1c9e4. Do not
   inherit the boot UI, Saturn menu, or Baku's measured in-game cycle slots.
   Read-only TVSTAT/HCNT/VCNT are skipped as in the BIOS register uploader. */
static void cold_video(void) {
    u32 i;
    W16(0x25f80000)=0;
    W16(0x25f80002)=0;W16(0x25f80006)=0;
    for(i=0x0c;i<0x120;i+=2) W16(0x25f80000+i)=0;
    W16(0x25f8000e)=0x1300;
    for(i=0x10;i<0x20;i+=2) W16(0x25f80000+i)=0xffff;
    W16(0x25f80078)=1;W16(0x25f8007c)=1;
    W16(0x25f80088)=1;W16(0x25f8008c)=1;
    W16(0x25f800bc)=0x12f1;W16(0x25f800e0)=0x20;
    /* BIOS game-entry state after its menu, not merely 1c892's cold
       defaults. In particular TVMD bit 0 is preserved by video uploaders. */
    W16(0x25f80014)=0x4455;
    W16(0x25f8001c)=0x0031;W16(0x25f8001e)=0x1ff7;
    W16(0x25f80020)=8;W16(0x25f80036)=0xc00c;
    W16(0x25f8004c)=0x3131;W16(0x25f8004e)=0x3131;
    W16(0x25f800e4)=0x4000;
    for(i=0xf0;i<=0xf6;i+=2)W16(0x25f80000+i)=0x0606;
    W16(0x25f800fa)=0x0700;W16(0x25f80110)=0x48;
    for(i=0;i<0x80000;i+=2) W16(0x25e00000+i)=0;
    for(i=0;i<0x1000;i+=2) W16(0x25f00000+i)=0;
    W16(0x25f80000)=1;
}
static void fail(u32 code) {
    TRACE[0]=0x4641494c;TRACE[1]=code;
    diagnostic_screen(code,cd_error.code,cd_error.lba,0);
    for(;;) __asm__ volatile("nop");
}
void probe_main(void) {
    u32 i,b,h,loaded;u16 ctrl;CdFile f;
    u32 saturn_bup_init=W32(0x26000358);
    u32 saturn_bup_source=W32(0x2600035c);
    TRACE[0]=0x494e5452;TRACE[1]=1;
#if INTRO_PROGRESS
    load_progress_begin(INTRO_ROM_SIZE*2+0xe0000+INTRO_CD_WORK);
    STAGE(LOAD_CD);cd_seen=cd_progress_bytes;cd_progress=cd_tick;
#endif
    if(cd_init()) fail(0xb01);
    if(cd_find_root("HLE.BIN;1",&f) || f.size>0x6000 ||
       cd_read_at(&f,0,(void *)0x26004000,f.size)) fail(0xb02);
    for(i=0;i<0x5000;i++) W8(0x2600a000+i)=0;
    if(cd_find_root("PANEL.BIN;1",&f) || f.size>0x200 ||
       cd_read_at(&f,0,(void *)0x2600fe00,f.size)) fail(0xb63);
    W8(0x2600a0d8)=6;
    for(i=0;i<64;i++)W32(0x2600d400+i*4)=W32(0x26000300+i*4);
    if(cd_find_root("PERSIST.BIN;1",&f) || f.size>0x1400 ||
       cd_read_at(&f,0,(void *)0x2600bc00,f.size)) fail(0xb64);
#if INTRO_PROGRESS
    cd_progress=0;
    saroo_poll_hook=load_progress_pulse;
#endif
    /* Software I/O shadow uses active-low bytes, unlike raw BIOS ports. */
    for(i=0;i<6;i++) W8(0x2600a000+i)=0xff;
    W32(0x2600a084)=0xffffffffu; /* No native answer selected yet. */
    TRACE[0]=0x494e5452;TRACE[1]=1;
    W8(0xfffffe92)=0x10;
    ((void (*)(void))0x06004800)();
    TRACE[1]=2;
    ((int (*)(void))0x06005400)();
    ((void (*)(void))0x06005200)(); /* resident Saturn INTBACK pad setup */
    ((void (*)(u32,u32))0x0600bc10)(saturn_bup_init,saturn_bup_source);
    /* BIOS cold video init (ba4a..ba4e, ba86..): a real empty draw.
       Introdon's first frame waits for this VDP1 completion in IST. */
    cold_vdp1(0);
    STAGE(LOAD_SAROO);
#if !INTRO_ASSUME
    /* Establish SAROO timing before any mapped cart reads, as well as at
       handoff below. Native reinit keeps these same values thereafter. */
    W32(0x25fe00b0)=0x1ff01ff0;W32(0x25fe00b4)=0x1ff01ff0;
    W32(0x25fe00b8)=0x1f;
    if(!saroo_present()) fail(0xb03);
    if(saroo_romctl(0,&ctrl)) fail(0xb04);
    if(saroo_stvload(INTRO_SD_FILE,0,INTRO_ROM_SIZE,INTRO_SDRAM,&loaded) ||
       loaded!=INTRO_ROM_SIZE) fail(0xb05);
    if(saroo_romctl(1,&ctrl) || !(ctrl&0x10)) fail(0xb06);
#endif
    ADVANCE(INTRO_ROM_SIZE);
#if INTRO_PROGRESS
    saroo_poll_hook=0;
#endif
    STAGE(LOAD_VERIFY);
    for(b=0;b<INTRO_ROM_SIZE/0x10000;b++) {
        h=2166136261u;
        for(i=0;i<0x10000;i+=4)
            h=(h^W32((INTRO_ROM_BASE|0x20000000)+(b<<16)+i))*16777619u;
        if(h!=intro_hash[b]) {TRACE[2]=b;TRACE[3]=h;fail(0xb07);}
        TRACE[2]=b+1;
        ADVANCE(0x10000);
    }
    STAGE(LOAD_COPY);
    for(b=0;b<0xe0000;b+=0x1000) {
        for(i=b;i<b+0x1000;i+=4) W32(0x26010000+i)=W32(0x22200000+i);
        ADVANCE(0x1000);
    }
    for(i=0;i<sizeof(intro_patches)/sizeof(intro_patches[0]);i++) {
        u32 a=intro_patches[i][0]|0x20000000;
        if(W32(a)!=intro_patches[i][1]) fail(0xb0a);
        W32(a)=intro_patches[i][2];
    }
    TRACE[1]=3;
    W32(0x25fe00b0)=0x1ff01ff0;W32(0x25fe00b4)=0x1ff01ff0;
    W32(0x25fe00b8)=0x1f;
    /* First call at 0601004e is through this BIOS service. Fail explicitly
       instead of executing address zero and hiding the missing HLE service. */
    TRACE[4]=W32(0x26000628);TRACE[5]=W32(0x26000630);
    TRACE[6]=W32(0x26000634);TRACE[7]=W32(0x26000344);
    if(!TRACE[4]) fail(0xb09);
    /* Cold ST-V entry uses BIOS vectors; do not seed Baku's private state. */
#if INTRO_FORCE_TCR2
    W8(0xfffffe16)=2;
#endif
#if INTRO_PROGRESS
    load_progress_end();
#endif
    cold_video();
    cold_vdp1(1);
    game_handoff();
    fail(0xb08);
}
