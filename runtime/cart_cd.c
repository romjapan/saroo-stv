#include "cart_cd.h"
#include "diagnostic_screen.h"
static CdFile banks[4];
static int ready;
static u8 cache[2048];
static u32 cached_sector;
static int valid;
static volatile u8 busy;
/* Dedicated immutable-after-load buffer: IRQ reads never touch CD/sector lock. */
#ifdef CART_HOST_TEST
static u8 irq_cache[CART_IRQ_CACHE_BYTES];
#else
/* Reserved LWRAM 00260000..0026ffff; outside loader and existing art buffers. */
static u8 *const irq_cache=(u8 *)0x20260000;
#endif
static u32 irq_base;
static volatile u8 irq_valid;
CartCacheStats cart_cache_stats;
#ifdef CART_MPR0_RAM
/* Opt-in: MPR0 copied once into a 4 MiB RAM cart. Its A-bus window
   0x02400000..0x027fffff is MPR0's own guest range (identity mapping).
   Immutable after verification, so reads need no lock and are IRQ-safe. */
#ifdef CART_HOST_TEST
u8 cart_host_ram[0x400000] __attribute__((aligned(4)));u8 cart_host_id;u16 cart_host_init;
#define MPR0_RAM ((const u8 *)cart_host_ram)
#define MPR0_WRITE ((void *)cart_host_ram)
#define CART_ID cart_host_id
#define CART_INIT cart_host_init
static void purge(void){}
#else
#define MPR0_RAM ((const volatile u8 *)0x02400000)
#define CART_ID (*(volatile u8 *)0x24ffffff)
#define CART_INIT (*(volatile u16 *)0x257efffe)
/* Cache-through 32-bit CPU stores via cd_read_at (ST-TECH-47: no SCU DMA writes). */
#define MPR0_WRITE ((void *)0x22400000)
static void purge(void){*(volatile u8 *)0xfffffe92=(u8)((*(volatile u8 *)0xfffffe92&0x0f)|0x10);}
#endif
static volatile u8 mpr0_ram;
CartMpr0Stats cart_mpr0_stats;
/* Returns 1 when no 4 MiB cart is present (CD fallback), 0 loaded, -1 failure. */
static int mpr0_load(void) {
    u32 offset,i,h=2166136261u;
    mpr0_ram=0;cart_mpr0_stats.id=CART_ID;
    if(cart_mpr0_stats.id!=0x5c) {cart_mpr0_stats.state=1;return 1;}
    CART_INIT=1;
    cd_progress_total+=0x400000;
    /* Sector-aligned 64 KiB requests take cd_io's batched direct-store path. */
    for(offset=0;offset<0x400000;offset+=0x10000)
        if(cd_read_at(&banks[0],offset,(u8 *)MPR0_WRITE+offset,0x10000)) {cart_mpr0_stats.state=3;return -1;}
    purge();
    for(i=0;i<0x400000;i++) h=(h^MPR0_RAM[i])*16777619u;
    cart_mpr0_stats.hash=h;
#ifdef CART_MPR0_HASH
    if(h!=CART_MPR0_HASH) {cart_mpr0_stats.state=4;return -1;}
#endif
    cart_mpr0_stats.state=2;
    __asm__ volatile("":::"memory");
    mpr0_ram=1;return 0;
}
static void mpr0_copy(u32 offset,u8 *out,u32 size) {
    u32 i;for(i=0;i<size;i++) out[i]=MPR0_RAM[offset+i];
}
int cart_cd_mpr0_resident(void) {return mpr0_ram;}
#endif
#ifdef CART_SAROO_ROM
/* Opt-in: SAROO (stv2ss mcuapp.bin + FPGA 06 AA24 bit) holds all four MPR
   banks in SDRAM at their own guest addresses 0x02400000..0x033fffff.
   Verified per 64 KiB block with a word FNV; bad blocks are reloaded, and
   anything short of a clean pass falls back to CD with AA24 switched off.
   CART_SAROO_ASSUME (emulator tests only) skips the SAROO commands and
   checks a ROM the emulator already maps there. */
#include "saroo_rom.h"
#include "cart_saroo_expect.h"
#ifndef CART_SAROO_FILE
#define CART_SAROO_FILE "/SAROO/STV/BAKUMPR.BIN"
#endif
#ifdef CART_HOST_TEST
u8 cart_host_rom[0x1000000] __attribute__((aligned(4)));
#define SAROO_PTR(a) ((const u8 *)cart_host_rom+((a)-0x02400000))
static u32 saroo_word(u32 a) {
    const u8 *p=SAROO_PTR(a);return ((u32)p[0]<<24)|((u32)p[1]<<16)|((u32)p[2]<<8)|p[3];
}
static void saroo_purge(void){}
#else
#define SAROO_PTR(a) ((const volatile u8 *)(a))
/* Verification reads bypass the cache; runtime reads use the cached alias. */
static u32 saroo_word(u32 a) {return *(const volatile u32 *)(a|0x20000000);}
static void saroo_purge(void){*(volatile u8 *)0xfffffe92=(u8)((*(volatile u8 *)0xfffffe92&0x0f)|0x10);}
#endif
static volatile u8 saroo_rom;
CartSarooStats cart_saroo_stats;
static u32 saroo_block(u32 a) {
    u32 h=2166136261u,i;
    for(i=0;i<0x10000;i+=4) h=(h^saroo_word(a+i))*16777619u;
    return h;
}
/* Returns 0 resident, 1 not used (CD fallback). */
static int saroo_load(void) {
    u32 b,pass,bad,loaded=0;u16 ctrl=0;int r;
    saroo_rom=0;cart_saroo_stats.id=saroo_id();
#ifndef CART_SAROO_ASSUME
    if(!saroo_present()) {cart_saroo_stats.state=1;return 1;}
    if(saroo_romctl(0,&ctrl)) {cart_saroo_stats.state=2;return 1;}
    r=saroo_stvload(CART_SAROO_FILE,0,0x1000000,0x400000,&loaded);
    cart_saroo_stats.err=(u32)r;
    if(r || loaded!=0x1000000) {cart_saroo_stats.state=3;return 1;}
    if(saroo_romctl(1,&ctrl) || !(ctrl&0x10)) {
        cart_saroo_stats.state=4;saroo_romctl(0,&ctrl);return 1;
    }
#endif
    cart_saroo_stats.ctrl=ctrl;
    cd_progress_total+=0x1000000;
    for(pass=0;pass<3;pass++) {
        bad=0;
        for(b=0;b<256;b++) {
            if(saroo_block(0x02400000+(b<<16))!=cart_saroo_expect[b]) {
                bad++;
#ifndef CART_SAROO_ASSUME
                saroo_stvload(CART_SAROO_FILE,b<<16,0x10000,0x400000+(b<<16),&loaded);
#endif
            }
            if(!pass) {cd_progress_bytes+=0x10000;if(cd_progress) cd_progress();}
        }
        cart_saroo_stats.bad[pass]=bad;
        if(!bad) {
            saroo_purge();cart_saroo_stats.state=5;
            __asm__ volatile("":::"memory");
            saroo_rom=1;return 0;
        }
    }
    cart_saroo_stats.state=6;
#ifndef CART_SAROO_ASSUME
    saroo_romctl(0,&ctrl);
#endif
    return 1;
}
/* Same access as the verifier: uncached aligned 32-bit reads. The first
   hardware run with cached byte reads failed the 0x033f4724 palette check
   (0xa22) although every block had verified. */
/* Real SAROO, second run (photo 2026-10-27): after boot some reads return
   the previous access's data. Accept a word only once two consecutive
   reads agree. */
static u32 saroo_stable(u32 a) {
    u32 x=saroo_word(a),y,i;
    for(i=0;i<8;i++) {y=saroo_word(a);if(y==x) return y;x=y;}
    return x;
}
/* With the BIOS A-bus timing restored (ASR0 0x1ff01ff0) single reads are
   exact on hardware (A-bus matrix: 0 unstable words), so read once. */
static void saroo_copy(u32 address,u8 *out,u32 size) {
    u32 w;
    while(size) {
        w=saroo_word(address&~3u);
        if(!(address&3) && size>=4 && !((unsigned long)out&3)) {
#ifdef CART_HOST_TEST
            out[0]=(u8)(w>>24);out[1]=(u8)(w>>16);out[2]=(u8)(w>>8);out[3]=(u8)w;
#else
            *(u32 *)out=w;
#endif
            out+=4;address+=4;size-=4;continue;
        }
        if(!(address&2)) w>>=16;   /* no variable shifts on SH-2 without libgcc */
        if(!(address&1)) w>>=8;
        *out++=(u8)w;address++;size--;
    }
}
int cart_cd_saroo_resident(void) {return saroo_rom;}
/* Either CPU: copy straight from resident SAROO SDRAM. Only touches CS0, no
   CD or cache state, so the slave sound refill need not wait for the master
   main loop (hardware 2026-10-28: one mailbox service per main pass held the
   game at ~0.18 main passes per VBlank). The flag is read cache-through: the
   slave may hold a stale cached zero, which only means the mailbox path. */
int cart_cd_saroo_mapped(u32 address,u32 size) {
#ifdef CART_HOST_TEST
    if(!saroo_rom) return 0;
#else
    if(!*(volatile u8 *)((u32)&saroo_rom|0x20000000u)) return 0;
#endif
    return address>=0x02400000 && address<0x03400000 && size<=0x03400000-address;
}
int cart_cd_saroo_direct(u32 address,void *destination,u32 size) {
    if(!cart_cd_saroo_mapped(address,size)) return -1;
    saroo_copy(address,(u8 *)destination,size);return 0;
}
#if defined(CART_SAROO_DIAG) && !defined(CART_SAROO_ASSUME) && !defined(CART_HOST_TEST)
/* Hardware pad diagnosis: every 600 main iterations append a 256-byte
   record (big-endian words) to /SAROO/STV/PADDIAG.BIN via SAROO SDRAM
   0x3f0000. Counters come from pad_timed_poll.s (0x2021f400). */
/* Master PC profile, sampled at VBlank-IN. The wrapper saves the C scratch
   registers, passes the interrupted PC, then chains to the game's handler.
   u16 counters live in SAROO SDRAM 0x3f1000 (CS0 0x223f1000), 256-byte
   buckets: HWRAM 0x06000000.. [4096], LWRAM 0x00200000.. [4096], then
   other count, last other PC, total samples (u32). /SAROO/STV/PROFILE.BIN. */
#define PROF_HW ((volatile u16 *)0x223f1000)
#define PROF_LW ((volatile u16 *)0x223f3000)
#define PROF_MISC ((volatile u32 *)0x223f5000)
#define PROF_BYTES 0x4010u
#define TRACE_RING ((volatile u32 *)0x223f6000)
#define TRACE_BYTES 0x8000u
#define PROF_VECTOR (*(volatile u32 *)0x06000100)
extern void prof_vbl_entry(void);
u32 prof_orig_vector;
static u8 prof_ready;
__asm__(
"    .text\n    .align 2\n_prof_vbl_entry:\n"
"    mov.l r0,@-r15\n    mov.l r1,@-r15\n    mov.l r2,@-r15\n    mov.l r3,@-r15\n"
"    mov.l r4,@-r15\n    mov.l r5,@-r15\n    mov.l r6,@-r15\n    mov.l r7,@-r15\n"
"    sts.l pr,@-r15\n    sts.l mach,@-r15\n    sts.l macl,@-r15\n"
"    mov r15,r0\n    add #44,r0\n    mov.l @r0,r4\n"
"    mov.l 1f,r0\n    jsr @r0\n    nop\n"
"    lds.l @r15+,macl\n    lds.l @r15+,mach\n    lds.l @r15+,pr\n"
"    mov.l @r15+,r7\n    mov.l @r15+,r6\n    mov.l @r15+,r5\n    mov.l @r15+,r4\n"
"    mov.l @r15+,r3\n    mov.l @r15+,r2\n    mov.l @r15+,r1\n"
"    mov.l 2f,r0\n    mov.l @r0,r0\n    jmp @r0\n    mov.l @r15+,r0\n"
"    .align 2\n1:  .long _prof_sample\n2:  .long _prof_orig_vector\n");
void prof_sample(u32 pc) {
    u32 r=pc&0x0ff00000u;
    if(r==0x06000000u) PROF_HW[(pc>>8)&0xfff]++;
    else if(r==0x00200000u) PROF_LW[(pc>>8)&0xfff]++;
    else {PROF_MISC[0]++;PROF_MISC[1]=pc;}
    PROF_MISC[2]++;
    /* Input trace (hardware-only in-match pad loss, 2026-10-29): every 4th
       VBlank, 8 words into a 1024-entry ring at SDRAM 0x3f6000; PROF_MISC[3]
       is the next entry. /SAROO/STV/TRACE.BIN. */
    if(!(PROF_MISC[2]&3)) {
        u32 n=PROF_MISC[3];
        volatile u32 *e=TRACE_RING+(n&1023)*8;
        e[0]=(*(volatile u32 *)0x2021f070<<16)|(*(volatile u32 *)0x2021f02c&0xffff);
        e[1]=*(volatile u32 *)0x06002864;e[2]=*(volatile u32 *)0x06002868;
        e[3]=*(volatile u32 *)0x0600286c;
        e[4]=((u32)*(volatile u16 *)0x06000708<<16)|*(volatile u16 *)0x0600070c;
        e[5]=*(volatile u32 *)0x2021f040;
        e[6]=((u32)*(volatile u16 *)0x060874d2<<16)|*(volatile u16 *)0x060874d6;
        e[7]=*(volatile u32 *)0x06083238;
        PROF_MISC[3]=n+1;
    }
}
/* Main-gate context (SR masked). Re-wraps if the game replaced the vector. */
static void prof_arm(void) {
    u32 i;
    if(PROF_VECTOR==(u32)prof_vbl_entry) return;
    if(!prof_ready) {
        for(i=0;i<PROF_BYTES/4;i++) ((volatile u32 *)0x223f1000)[i]=0;
        for(i=0;i<TRACE_BYTES/4;i++) TRACE_RING[i]=0;
        prof_ready=1;
    }
    prof_orig_vector=PROF_VECTOR;
    PROF_VECTOR=(u32)prof_vbl_entry;
}
static u32 pad_diag_last;
static void pad_diag(void) {
    volatile u32 *dst=(volatile u32 *)0x223f0000;
    u32 rec[64];
    u32 i,k,f,main=*(volatile u32 *)0x2021f02c,vbl=*(volatile u32 *)0x2021f070;
    prof_arm();
    /* Time based (VBlank-in count), so a slow game still gets records. */
    k=0;while(k<32 && (k+1)*600<=vbl) k++;
    if(!k || k<=pad_diag_last) return;
    pad_diag_last=k;
    for(i=0;i<64;i++) rec[i]=0;
    rec[0]=0x50414447;rec[1]=main;rec[2]=cart_saroo_stats.reads;rec[3]=k;
    for(i=0;i<16;i++) rec[4+i]=((volatile u32 *)0x2021f400)[i];
    rec[19]=vbl;                                  /* VBlank-in count: main/VBlank = speed */
    for(i=0;i<4;i++) rec[20+i]=((volatile u32 *)0x2021f060)[i];
    for(i=0;i<4;i++) rec[24+i]=((volatile u32 *)0x06000be0)[i];
    rec[28]=*(volatile u32 *)0x06002864;rec[29]=*(volatile u32 *)0x06002868;
    rec[30]=*(volatile u32 *)0x0600286c;rec[31]=*(volatile u32 *)0x06000730;
    for(i=0;i<8;i++)
        rec[32+i]=((u32)*(volatile u8 *)(0x20100021+i*8)<<24)|((u32)*(volatile u8 *)(0x20100023+i*8)<<16)|
                  ((u32)*(volatile u8 *)(0x20100025+i*8)<<8)|*(volatile u8 *)(0x20100027+i*8);
    rec[40]=((u32)*(volatile u8 *)0x20100061<<8)|*(volatile u8 *)0x20100063;
    for(i=0;i<8;i++) rec[41+i]=((volatile u32 *)0x2021f000)[i];
    for(i=0;i<8;i++) {       /* FRT is an 8-bit module: byte reads only */
        f=*(volatile u8 *)(0xfffffe10+i);
        if(i<4) rec[49]=(rec[49]<<8)|f; else rec[50]=(rec[50]<<8)|f;
    }
    rec[51]=*(volatile u32 *)0x06083238;rec[52]=*(volatile u32 *)0x060831e0;
    rec[53]=*(volatile u32 *)0x06000be8;rec[54]=*(volatile u32 *)0x06000bec;
    /* Sound: driver mailbox and OK word, adapter state (sound_cd_dma.c,
       sound_stream_mailbox.c). */
    rec[55]=*(volatile u32 *)0x25a07d84;rec[56]=*(volatile u32 *)0x25a07d88;
    rec[57]=*(volatile u32 *)0x25a07dbc;
    rec[58]=*(volatile u32 *)0x2021e1f0;rec[59]=*(volatile u32 *)0x2021e1f4;
    rec[60]=*(volatile u32 *)0x2021e1f8;rec[61]=*(volatile u32 *)0x2021e100;
    rec[62]=*(volatile u32 *)0x2021e300;rec[63]=*(volatile u32 *)0x2021e200;
    for(i=0;i<64;i++) dst[i]=rec[i];
    saroo_filewr("/SAROO/STV/PADDIAG.BIN",k==1?-1:(int)((k-1)*256),256,0x3f0000);
    saroo_filewr("/SAROO/STV/PROFILE.BIN",-1,PROF_BYTES,0x3f1000);
    saroo_filewr("/SAROO/STV/TRACE.BIN",-1,TRACE_BYTES,0x3f6000);
    /* Fail trace + sound DMA log (0x2021e000..e1ff, sound_cd_dma.c): a
       slave fatal draws over VRAM while the master game keeps running. */
    for(i=0;i<128;i++) ((volatile u32 *)0x223fe000)[i]=((volatile u32 *)0x2021e000)[i];
    saroo_filewr("/SAROO/STV/FAIL.BIN",-1,512,0x3fe000);
}
void cart_cd_diag_tick(void) {if(saroo_rom) pad_diag();}
#else
static void pad_diag(void) {}
void cart_cd_diag_tick(void) {}
#endif
/* First resident read (sampled every 16th) at which block 0 no longer
   verifies: [0] read number (1-based, 0 never), [1] guest address. */
u32 cart_saroo_fail[2];
static void saroo_spot(u32 address) {
    if(cart_saroo_fail[0] || (cart_saroo_stats.reads&15) || cart_saroo_stats.reads>=2048) return;
    if(saroo_block(0x02400000)!=cart_saroo_expect[0]) {
        cart_saroo_fail[0]=cart_saroo_stats.reads+1;cart_saroo_fail[1]=address;
    }
}
/* Hardware diagnosis after a failed resident read: rescan all 256 blocks
   (a), re-assert AA24 and rescan (b), reload bad blocks and rescan (c).
   Each word: ctrl<<24 | bad count<<8 | first bad block (0xff none).
   Returns 0 when the image is clean again. */
static u32 saroo_scan(void) {
    u32 b,bad=0,first=0xff;
    for(b=0;b<256;b++)
        if(saroo_block(0x02400000+(b<<16))!=cart_saroo_expect[b]) {if(!bad) first=b;bad++;}
    return (bad<<8)|first;
}
static u32 saroo_scan_stable(void) {
    u32 b,i,h,bad=0,first=0xff;
    for(b=0;b<256;b++) {
        h=2166136261u;
        for(i=0;i<0x10000;i+=4) h=(h^saroo_stable(0x02400000+(b<<16)+i))*16777619u;
        if(h!=cart_saroo_expect[b]) {if(!bad) first=b;bad++;}
    }
    return (bad<<8)|first;
}
#ifdef CART_HOST_TEST
static u32 sr_get(void) {return 0;}
static void sr_set(u32 v) {(void)v;}
#else
static u32 sr_get(void) {u32 v;__asm__ volatile("stc sr,%0":"=r"(v));return v;}
static void sr_set(u32 v) {__asm__ volatile("ldc %0,sr"::"r"(v):"memory");}
#endif
#ifdef CART_SAROO_PROBE_WORDS
#define PROBE(i) cart_saroo_probe[i]
#else
#define PROBE(i) 0u
#endif
/* Alternate between 0x033f4724 and 0x02400000 (mode 0 plain, 1 stable);
   or (mode 2) re-read 0x033f4724 only. Returns wrong reads out of 2000. */
static u32 saroo_alternate(int mode) {
    u32 i,bad=0;
    for(i=0;i<1000;i++) {
        if(mode==2) {
            if(saroo_word(0x033f4724)!=PROBE(2)) bad++;
            if(saroo_word(0x033f4724)!=PROBE(2)) bad++;
        } else if(mode==1) {
            if(saroo_stable(0x033f4724)!=PROBE(2)) bad++;
            if(saroo_stable(0x02400000)!=PROBE(0)) bad++;
        } else {
            if(saroo_word(0x033f4724)!=PROBE(2)) bad++;
            if(saroo_word(0x02400000)!=PROBE(0)) bad++;
        }
    }
    return bad;
}
/* Fill v[1..25] for diagnostic_grid (v[0] is the caller's code).
   Runs with interrupts as found except where noted. */
static u32 cap8(u32 x) {return x>255?255:x;}
void cart_cd_saroo_report(const u32 diag[3],u32 *v) {
    u32 sr=sr_get();
    v[1]=saroo_id();
#ifdef CART_HOST_TEST
    v[2]=0;v[7]=0;
#else
    v[2]=((u32)*(volatile u16 *)0x25807004<<16)|*(volatile u16 *)0x25807006;
    v[7]=*(volatile u32 *)0x25fe007c;     /* SCU DMA status DSTA */
#endif
    v[3]=(cart_saroo_stats.state<<24)|(cap8(cart_saroo_stats.bad[0])<<16)|
         (cap8(cart_saroo_stats.bad[1])<<8)|cap8(cart_saroo_stats.bad[2]);
    v[4]=diag[0];v[5]=diag[1];v[6]=diag[2];
    v[8]=sr;
    v[12]=saroo_alternate(0);             /* interrupts as found */
    v[13]=saroo_alternate(1);
    v[14]=saroo_alternate(2);
    v[10]=saroo_scan_stable();
    sr_set(sr|0xf0);                      /* interrupts off */
    v[9]=saroo_scan();
    v[11]=saroo_scan_stable();
    v[15]=saroo_alternate(0);
    v[16]=saroo_alternate(2);
    sr_set(sr);
    v[17]=saroo_word(0x033f4724);v[18]=saroo_word(0x033f4728);
    v[19]=PROBE(2);v[20]=PROBE(3);
#ifdef CART_HOST_TEST
    v[21]=0;
#else
    v[21]=((u32)*(volatile u16 *)0x22400000<<16)|*(volatile u16 *)0x22400002;
#endif
    v[22]=cart_saroo_fail[0];v[23]=cart_saroo_fail[1];
    v[24]=saroo_stable(0x033f4724);v[25]=saroo_stable(0x033f4728);
}
#if !defined(CART_HOST_TEST)
/* A-bus read matrix (hardware diagnosis, halts afterwards). Blocks 0..31
   (0x02400000..0x025fffff) are hashed from the first of two consecutive
   reads per word; "unstable" counts words whose two reads differ.
   Result word: bad blocks<<16 | unstable words (capped 0xffff). */
static u32 matrix_scan(void) {
    u32 b,i,h,x,y,bad=0,unstable=0;
    for(b=0;b<32;b++) {
        h=2166136261u;
        for(i=0;i<0x10000;i+=4) {
            x=saroo_word(0x02400000+(b<<16)+i);
            y=saroo_word(0x02400000+(b<<16)+i);
            if(x!=y && unstable<0xffff) unstable++;
            h=(h^x)*16777619u;
        }
        if(h!=cart_saroo_expect[b]) bad++;
    }
    return (bad<<16)|unstable;
}
static void smpc(u8 c) {
    u32 n=4000000;
    while(*(volatile u8 *)0x20100063&1) if(!--n) return;
    *(volatile u8 *)0x20100063=1;*(volatile u8 *)0x2010001f=c;n=4000000;
    while(*(volatile u8 *)0x20100063&1) if(!--n) return;
}
#define SCU(o) (*(volatile u32 *)(0x25fe0000+(o)))
static u32 matrix_dma(void) {
    volatile u32 *dst=(volatile u32 *)0x260c0000;
    u32 i,bad=0,n;
    for(i=0;i<0x4000;i++) dst[i]=0xdeadbeef;
    SCU(0x10)=0;                                   /* D0EN off */
    SCU(0x00)=0x02400000;SCU(0x04)=0x060c0000;SCU(0x08)=0x10000;
    SCU(0x0c)=0x102;SCU(0x14)=0x07;                /* read +4, write +4; start: immediate */
    SCU(0x10)=0x101;                               /* enable + start */
    n=40000000;
    while((SCU(0x7c)&0x10) && --n) ;               /* D0MV: level 0 busy */
    if(!n) return 0xffffffff;
    for(i=0;i<0x4000;i++) if(dst[i]!=saroo_stable(0x02400000+i*4) && bad<0xffff) bad++;
    return bad;
}
void cart_cd_saroo_matrix(void) {
    u32 v[26],i,sr=sr_get();
    for(i=0;i<26;i++) v[i]=0;
    v[0]=0x4d545258;                               /* "MTRX" */
    v[1]=saroo_id();
    v[2]=((u32)*(volatile u16 *)0x25807004<<16)|*(volatile u16 *)0x25807006;
    v[3]=(cart_saroo_stats.state<<24)|saroo_rom;
    v[4]=sr;
    v[5]=*(volatile u32 *)0x25fe007c;              /* DSTA */
    v[6]=matrix_scan();                            /* as found */
    sr_set(sr|0xf0);
    v[7]=matrix_scan();                            /* IRQ off */
    SCU(0xb0)=0x1ff01ff0;SCU(0xb8)=0x1f;           /* BIOS ASR0 / AREF */
    v[8]=matrix_scan();
    SCU(0xb0)=0x0ff01ff0;v[9]=matrix_scan();       /* external wait off */
    SCU(0xb0)=0x3ff01ff0;v[10]=matrix_scan();      /* + read precharge */
    SCU(0xb0)=0x9ff01ff0;v[11]=matrix_scan();      /* + A0PRD */
    SCU(0xb0)=0x1ff01ff0;
    smpc(0x03);                                    /* SSHOFF: stop slave SH-2 */
    for(i=0;i<2000000;i++) __asm__ volatile("nop");
    v[12]=matrix_scan();                           /* slave off, IRQ off */
    v[13]=matrix_scan();
    v[14]=matrix_dma();                            /* SCU DMA CS0 -> HWRAM */
    v[15]=matrix_dma();
    v[16]=saroo_word(0x02400000);v[17]=saroo_word(0x02400004);
    v[18]=cart_saroo_expect[0];v[19]=cart_saroo_expect[1];
    v[20]=cart_saroo_stats.reads;
    v[21]=*(volatile u32 *)0x2021f02c;
    diagnostic_grid(v,26);
    for(;;) __asm__ volatile("nop");
}
#endif
int cart_cd_saroo_recheck(u32 diag[3]) {
    u32 b,loaded;u16 ctrl=0;
    diag[0]=saroo_scan();diag[1]=diag[2]=0;
    if(!(diag[0]>>8)) return 0;
#ifndef CART_SAROO_ASSUME
    saroo_romctl(1,&ctrl);
#endif
    diag[1]=((u32)(ctrl&0xff)<<24)|saroo_scan();
    if(!((diag[1]>>8)&0xffff)) {saroo_purge();return 0;}
    for(b=0;b<256;b++)
        if(saroo_block(0x02400000+(b<<16))!=cart_saroo_expect[b]) {
#ifndef CART_SAROO_ASSUME
            saroo_stvload(CART_SAROO_FILE,b<<16,0x10000,0x400000+(b<<16),&loaded);
#endif
        }
    (void)loaded;
    diag[2]=saroo_scan();saroo_purge();
    return (diag[2]>>8)?1:0;
}
#endif
static int acquire(void) {
    int free;
#ifdef CART_HOST_TEST
    free=!__atomic_test_and_set(&busy,__ATOMIC_ACQUIRE);
#else
    __asm__ volatile("tas.b @%1\n\tmovt %0":"=r"(free):"r"(&busy):"memory");
#endif
    return free;
}
static void release(void) {
#ifdef CART_HOST_TEST
    __atomic_clear(&busy,__ATOMIC_RELEASE);
#else
    __asm__ volatile("":::"memory");busy=0;
#endif
}
int cart_cd_cache_reset(void) {
    if(!acquire()) return -2;
    valid=0;cart_cache_stats.hits=0;cart_cache_stats.misses=0;
    cart_cache_stats.sector_reads=0;release();return 0;
}
int cart_cd_init(void) {
    static const char *names[4]={"MPR0.BIN;1","MPR1.BIN;1","MPR2.BIN;1","MPR3.BIN;1"};
    u32 i;
    if(!acquire()) return -2;
    ready=0;valid=0;irq_valid=0;
    for(i=0;i<4;i++)
        if(cd_find_root(names[i],&banks[i]) || banks[i].size!=0x400000) {
            release();return -1;
        }
#ifdef CART_SAROO_ROM
    if(!saroo_load()) {ready=1;release();return 0;}
#endif
#ifdef CART_MPR0_RAM
    if(mpr0_load()<0) {release();return -1;}
#endif
    ready=1;release();return 0;
}
int cart_cd_read(u32 address,void *destination,u32 size) {
    u32 offset,bank,within,count,sector,i;
    u8 *out=(u8 *)destination;
    /* No masking: reject CS1/relocated/uncached aliases until independently verified. */
    if(!ready || address<0x02400000 || address>0x03400000) return -1;
    offset=address-0x02400000;
    if(size>0x1000000-offset) return -1;
#ifdef CART_SAROO_ROM
    if(saroo_rom) {saroo_spot(address);pad_diag();saroo_copy(address,out,size);cart_saroo_stats.reads++;return 0;}
#endif
#ifdef CART_MPR0_RAM
    if(mpr0_ram && size && offset<0x400000) {
        u32 n=0x400000-offset;if(n>size) n=size;
        mpr0_copy(offset,out,n);cart_mpr0_stats.reads++;
        offset+=n;out+=n;size-=n;
        if(!size) return 0;
    }
#endif
    if(!acquire()) return -2;
    while(size) {
        bank=offset>>22;within=offset&0x3fffff;
        sector=offset>>11;
        if(!(within&2047) && size>=2048 && !((unsigned long)out&3)) {
            /* Whole aligned sectors bypass the 2 KiB cache: batched CD reads. */
            count=size&~2047u;
            if(count>0x400000-within) count=0x400000-within;
            if(cd_read_at(&banks[bank],within,out,count)) {release();return -1;}
            cart_cache_stats.sector_reads+=count>>11;
            offset+=count;out+=count;size-=count;
            continue;
        }
        if(!valid || cached_sector!=sector) {
            valid=0;cart_cache_stats.misses++;
            if(cd_read_at(&banks[bank],within&~2047u,cache,2048)) {
                release();return -1;
            }
            cached_sector=sector;valid=1;cart_cache_stats.sector_reads++;
        } else cart_cache_stats.hits++;
        count=2048-(within&2047);if(count>size) count=size;
        for(i=0;i<count;i++) out[i]=cache[(within&2047)+i];
        offset+=count;out+=count;size-=count;
    }
    release();return 0;
}
int cart_cd_irq_cache_load(u32 address) {
    irq_valid=0;
    if((address&2047u) || cart_cd_read(address,irq_cache,CART_IRQ_CACHE_BYTES)) return -1;
    irq_base=address;
    __asm__ volatile("":::"memory");
    irq_valid=1;
    return 0;
}
int cart_cd_irq_read(u32 address,void *destination,u32 size) {
    u32 offset,i;u8 *out=(u8 *)destination;
#ifdef CART_SAROO_ROM
    if(saroo_rom && address>=0x02400000 && address<0x03400000 &&
       size<=0x03400000-address) {
        saroo_copy(address,out,size);return 0;
    }
#endif
#ifdef CART_MPR0_RAM
    if(mpr0_ram && address>=0x02400000 && address<0x02800000 &&
       size<=0x02800000-address) {
        mpr0_copy(address-0x02400000,out,size);return 0;
    }
#endif
    if(!irq_valid || address<irq_base) return -1;
    offset=address-irq_base;
    if(offset>CART_IRQ_CACHE_BYTES || size>CART_IRQ_CACHE_BYTES-offset) return -1;
    for(i=0;i<size;i++) out[i]=irq_cache[offset+i];
    return 0;
}
