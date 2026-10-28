/* Opt-in diagnostic adapter. Original SCU helper still owns DMA completion. */
#include "cart_cd.h"
#include "diagnostic_screen.h"
extern void sound_dma_native(u32,u32,u32,u32,u32);
extern void sound_dma_lwram(u32,u32,u32,u32,u32);
extern int sound_dma_cart(u32,u32,u32,u32,u32);
/* Only SAROO builds define it. */
extern int cart_cd_saroo_mapped(u32,u32) __attribute__((weak));
extern int sound_stream_refill(u32,u32,u32) __attribute__((weak));
extern int sound_stream_dma_refill(u32,u32,u32,u32,u32) __attribute__((weak));
/* Both SH2s enter this adapter. Never publish readiness through a cached
   loader BSS address: the slave can retain a stale zero. */
#define PREFETCH_READY (*(volatile u32 *)0x2021e1f0)
#define PREFETCH_REQUESTED (*(volatile u32 *)0x2021e1f4)
#define SOUND_BOOT_STAGE_RELEASED (*(volatile u32 *)0x2021e1f8)
static const u32 cache_src[16]={0x02a08000,0x024b1b40,0x027305d4,0x026ad070,0x026b54c0,0x02784358,0x0279532c,0x0251abc4,0x0251ec30,0x02525a88,0x025292ac,0x027203b0,0x02781a4c,0x025c15a0,0x0271bb00,0x025d0b08};
/* Small extents reuse the otherwise idle legacy DMA staging reservation. */
/* 20274000..2027fc40: explicit gap above idle/transition tables, below
   scene-pattern guard at 2027ffff. No dynamic CD reads or cache eviction. */
/* Repacked small extents share released boot staging and legacy sound pool.
   Trimmed sizes cover full native refill spans, not only observed512B reads. */
/* Sample138 full loop/refill span, above scene tail202a4408. */
/* Six complete early sample refill spans are merged into109812 bytes.
   Combined PCM, trimmed bulk and sample140 fit202d1000..202f7ba4. */
static const u32 cache_ram[16]={0x202c8000,0x202d1000,0x202b5dcc,0x202b6bcc,0x202bebcc,0x202c05cc,0x202c19cc,0x202ebcf4,0x20256000,0x20274000,0x20277824,0x202b0000,0x202b4cd8,0x202a5000,0x202c29cc,0x202efd60};
static const u32 cache_size[16]={36864,109812,3584,32768,6656,5120,4096,16492,32768,14372,33820,19672,4340,30028,18604,32324};
int sound_cd_dma_prefetch(void) {
    static const u32 expected[16]={0x819c7f23,0xf35b4a81,0xa51b954b,0xbde261dd,0xcf45b191,0x0fcf20e3,0x62a20b31,0xf5bc834b,0x22ae4c30,0x8ae88d02,0x1d59e0dd,0xca4599d2,0x13d33700,0xb3b0b3a4,0x35fd1152,0xda661431};
    u32 i,j,h;
    PREFETCH_READY=0;
    PREFETCH_REQUESTED=1;
    if(SOUND_BOOT_STAGE_RELEASED!=1)return -3;
    for(i=0;i<16;i++) {
        u8 *p=(u8 *)cache_ram[i];
        if(cart_cd_read(cache_src[i],p,cache_size[i]))return -1;
        h=0x811c9dc5;
        for(j=0;j<cache_size[i];j++)h=(h^p[j])*0x01000193;
        if(h!=expected[i])return -2;
    }
    __asm__ volatile("":::"memory");
    PREFETCH_READY=1;return 0;
}
static void sound_dma_fail(u32 code) {
    volatile u32 *t=(volatile u32 *)0x2021e000;
    __asm__ volatile("ldc %0,sr"::"r"(0xf0):"memory");
    t[0]=0x4641494c;t[1]=code;t[6]=0;
    diagnostic_screen(code,cd_error.code,cd_error.lba,cd_error.hirq);
    t[6]=0x44535059;
    for(;;)__asm__ volatile("nop");
}
/* Native stream refill has a second, CPU-copy path (06033ad0).
   Return zero only when the cache mode was not requested. */
int sound_cd_cached_copy(u32 dst,u32 src,u32 bytes) {
    u32 i,j;
    if(!PREFETCH_READY) {
        if(PREFETCH_REQUESTED)sound_dma_fail(0xb6a);
        return 0;
    }
    if(dst<0x25a00000 || dst>=0x25a80000 || bytes>0x25a80000-dst ||
       ((dst|src|bytes)&1))sound_dma_fail(0xb69);
    for(i=0;i<16;i++)if(src>=cache_src[i] && src-cache_src[i]<cache_size[i] &&
        bytes<=cache_size[i]-(src-cache_src[i])) {
        volatile u16 *out=(volatile u16 *)dst;
        const u16 *in=(const u16 *)(cache_ram[i]+src-cache_src[i]);
        for(j=0;j<bytes/2;j++)out[j]=in[j];
        return 1;
    }
    if(bytes!=512 && cart_cd_saroo_mapped && cart_cd_saroo_mapped(src,bytes)) {
        volatile u16 *out=(volatile u16 *)dst;
        const volatile u16 *in=(const volatile u16 *)(src|0x20000000);
        for(j=0;j<bytes/2;j++)out[j]=in[j];
        return 1;
    }
    if(sound_stream_refill)return sound_stream_refill(dst,src,bytes);
    ((volatile u32 *)0x2021e200)[0]=dst;
    ((volatile u32 *)0x2021e200)[1]=src;
    ((volatile u32 *)0x2021e200)[2]=bytes;
    ((volatile u32 *)0x2021e200)[3]=1;
    sound_dma_fail(0xb67);return -1;
}
void sound_dma_cd(u32 channel,u32 dst,u32 src,u32 bytes,u32 add) {
    u32 n,aligned,span,delta;
    u8 *stage=(u8 *)0x202b8000;
    int (*busy)(u32)=(int (*)(u32))0x06048430;
    if(src<0x02400000 || src>=0x03400000) {
        /* Also VDP/WRAM transfers from LWRAM resource caches: SCU DMA cannot
           read Low Work RAM on hardware (Mednafen too) -> sprite corruption. */
        sound_dma_lwram(channel,dst,src,bytes,add);return;
    }
    {
        volatile u32 *t=(volatile u32 *)0x2021e100;
        u32 slot=t[0]&7,base=1+slot*7;
        t[base]=channel;t[base+1]=dst;t[base+2]=src;
        t[base+3]=bytes;t[base+4]=add;
        t[base+5]=*(volatile u32 *)0x2021f010;
        __asm__ volatile("stc sr,%0":"=r"(t[base+6]));
        t[0]++;
    }
    /* Deliberately narrow first candidate, not a general DMA substitute. */
    if(channel!=0 || dst<0x25a00000 || dst>=0x25a80000 ||
       bytes==0 || bytes>65528 || bytes>0x25a80000-dst || add!=0x101)
        sound_dma_fail(0xb61);
    if(PREFETCH_READY) {
        u32 i;
        /* Odd ROM offsets may arise after native loop wrapping. Even a cache
           hit would expose an odd T2 word source; use aligned handoff instead. */
        if((src&1) && sound_stream_dma_refill &&
           sound_stream_dma_refill(channel,dst,src,bytes,add))return;
        for(i=0;i<16;i++)if(src>=cache_src[i] && src-cache_src[i]<cache_size[i] &&
            bytes<=cache_size[i]-(src-cache_src[i])) {
            sound_dma_lwram(channel,dst,cache_ram[i]+src-cache_src[i],bytes,add);
            return;
        }
        if(sound_stream_dma_refill && sound_stream_dma_refill(channel,dst,src,bytes,add))return;
        /* SAROO-resident cart: bulk loads outside the prefetch set (hardware
           2026-10-29, 0xb67 at dst 25a08000 on a later opponent). */
        if(sound_dma_cart(channel,dst,src,bytes,add))return;
        ((volatile u32 *)0x2021e200)[0]=dst;
        ((volatile u32 *)0x2021e200)[1]=src;
        ((volatile u32 *)0x2021e200)[2]=bytes;
        ((volatile u32 *)0x2021e200)[3]=2;
        sound_dma_fail(0xb67); /* no runtime CD fallback in prefetch mode */
    }
    if(PREFETCH_REQUESTED)sound_dma_fail(0xb6a);
    if(*(volatile u32 *)0x2021f010)sound_dma_fail(0xb62); /* never CD I/O in IRQ */
    n=4000000;
    while(busy(channel))if(!--n)sound_dma_fail(0xb63);
    /* Preserve source address low bits and surrounding bytes for native
       DMA access widths. Do not reinterpret odd-address transfer semantics. */
    delta=src&3;aligned=src-delta;span=(delta+bytes+3)&~3u;
    if(span>65536 || span>0x03400000-aligned)sound_dma_fail(0xb64);
    stage[-1]=0xa5;stage[span]=0x5a;
    if(cart_cd_read(aligned,stage,span))sound_dma_fail(0xb65);
    if(stage[-1]!=0xa5 || stage[span]!=0x5a)sound_dma_fail(0xb66);
    sound_dma_lwram(channel,dst,(u32)stage+delta,bytes,add);
}
int sound_cd_dma_install(void) {
    static const u8 original[12]={0x2f,0xe6,0x2f,0xd6,0x4f,0x22,
                                0x6d,0x43,0x7f,0xf4,0x6e,0xd3};
    volatile u32 *entry=(volatile u32 *)0x260483c0;
    u32 i;
    for(i=0;i<12;i++)if(((volatile u8 *)entry)[i]!=original[i])return -1;
    for(i=0;i<57;i++)((volatile u32 *)0x2021e100)[i]=0;
    PREFETCH_READY=0;
    PREFETCH_REQUESTED=0;
    for(i=0;i<4;i++)((volatile u32 *)0x2021e200)[i]=0;
    /* Tail-jump: preserves native fifth stack argument and caller PR. */
    entry[0]=0xd001402b;entry[1]=0x00090009;entry[2]=(u32)sound_dma_cd;
    *(volatile u32 *)0x2609b30c=0x02a00000;
    *(volatile u32 *)0x2609b310=0x02400000;
    *(volatile u8 *)0xfffffe92=(u8)((*(volatile u8 *)0xfffffe92&0x0f)|0x10);
    return 0;
}
