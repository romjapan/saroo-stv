#include "cart_cd.h"
#ifdef VISIBLE_COPY_ERRORS
#include "diagnostic_screen.h"
#endif
extern void cd_long_hook(void);
extern void cd_word_hook(void);
extern void cd_alt_long_hook(void);
/* Optional sound experiment; absent in all existing non-sound builds. */
extern int sound_cd_cached_copy(u32,u32,u32) __attribute__((weak));
static void record(u32 source,u32 destination,u32 bytes,u32 kind) {
#ifdef TEST_RESIDENT_INIT
    volatile u32 *p=(volatile u32 *)0x2021e000;
    p[20]++;p[21]=source;p[22]=destination;p[23]=bytes;p[24]=kind;
    p[25]=*(volatile u32 *)0x2021f010;
#endif
}
/* Diagnostic-only fail-stop: never silently return partial resource data. */
static void fatal(u32 code) {
#ifdef TEST_RESIDENT_INIT
    volatile u32 *trace=(volatile u32 *)0x2021e000;
#else
    volatile u32 *trace=(volatile u32 *)0x0600e000;
#endif
    trace[0]=0x4641494c;trace[1]=code;trace[2]=cd_error.code;
    trace[3]=cd_error.lba;
#ifdef VISIBLE_COPY_ERRORS
    /* Fatal path never resumes. Mask IRQs before taking over display RAM. */
    __asm__ volatile("ldc %0,sr"::"r"(0xf0):"memory");
    trace[6]=0;
    diagnostic_screen(code,cd_error.code,cd_error.lba,cd_error.hirq);
    trace[6]=0x44535059; /* DSPY: fatal display drawing complete. */
#endif
    for(;;)__asm__ volatile("nop");
}
void copy_cart_longs(void *dst,u32 src,u32 count) {
    record(src,(u32)dst,count<<2,0x4c4f4e47);
    if(sound_cd_cached_copy && (u32)dst>=0x25a00000 && (u32)dst<0x25a80000) {
        if(count>0x3fffffff)fatal(0x501);
        if(sound_cd_cached_copy((u32)dst,src,count<<2))return;
    }
#ifdef TEST_RESIDENT_INIT
    if(*(volatile u32 *)0x2021f010) {
        if(count>0x3fffffff || cart_cd_irq_read(src,dst,count<<2)) fatal(0x503);
        return;
    }
#endif
    if(count>0x3fffffff || cart_cd_read(src,dst,count<<2)) fatal(0x501);
}
void copy_cart_words(void *dst,u32 src,u32 count) {
    record(src,(u32)dst,count<<1,0x574f5244);
    if(sound_cd_cached_copy && (u32)dst>=0x25a00000 && (u32)dst<0x25a80000) {
        if(count>0x7fffffff)fatal(0x501);
        if(sound_cd_cached_copy((u32)dst,src,count<<1))return;
    }
#ifdef TEST_RESIDENT_INIT
    if(*(volatile u32 *)0x2021f010) {
        if(count>0x7fffffff || cart_cd_irq_read(src,dst,count<<1)) fatal(0x503);
        return;
    }
#endif
    if(count>0x7fffffff || cart_cd_read(src,dst,count<<1)) fatal(0x501);
}
int copy_word_install(void) {
    static const u8 original[12]={0x67,0x53,0xa0,0x05,0x65,0x43,
                                  0x62,0x53,0x75,0x02,0x61,0x75};
    volatile u32 *p=(volatile u32 *)0x2604afbc;u32 i;
    for(i=0;i<12;i++) if(((volatile u8 *)p)[i]!=original[i]) return -1;
    /* R7 is overwritten by the original loop; avoid clobbering caller R0. */
    p[0]=0xd701472b;p[1]=0x00090009;p[2]=(u32)cd_word_hook;
    *(volatile u8 *)0xfffffe92=(u8)((*(volatile u8 *)0xfffffe92&0x0f)|0x10);return 0;
}
int copy_alt_long_install(void) {
    static const u8 original[12]={0x67,0x53,0xa0,0x05,0x65,0x43,
                                  0x62,0x53,0x75,0x04,0x61,0x76};
    volatile u32 *p=(volatile u32 *)0x2604afec;u32 i;
    for(i=0;i<12;i++) if(((volatile u8 *)p)[i]!=original[i]) return -1;
    p[0]=0xd701472b;p[1]=0x00090009;p[2]=(u32)cd_alt_long_hook;
    *(volatile u8 *)0xfffffe92=(u8)((*(volatile u8 *)0xfffffe92&0x0f)|0x10);return 0;
}
void *cd_mem_hook(void *dst,const void *source,u32 size) {
    u8 *d=(u8 *)dst;const u8 *s=(const u8 *)source;u32 address=(u32)source,i;
    record(address,(u32)dst,size,0x4d4f5645);
    if((address>=0x02000000 && address<0x05000000) ||
       (address>=0x22000000 && address<0x25000000)) {
#ifdef TEST_RESIDENT_INIT
        if(*(volatile u32 *)0x2021f010) {
            if(cart_cd_irq_read(address,dst,size)) fatal(0x503);
            return dst;
        }
#endif
        if(cart_cd_read(address,dst,size)) fatal(0x502);
    } else if(d!=s) {
        if((u32)d<(u32)s) for(i=0;i<size;i++) d[i]=s[i];
        else for(i=size;i;i--) d[i-1]=s[i-1];
    }
    return dst;
}
int copy_hooks_install(void) {
    static const u8 original[2][12]={
        {0x67,0x53,0xa0,0x05,0x65,0x43,0x62,0x53,0x75,0x04,0x61,0x76},
        {0x2f,0xd6,0x34,0x50,0x89,0x1d,0x34,0x52,0x8d,0x0e,0xe7,0x00}};
    u32 addresses[2]={0x2604afd4,0x26053c98};
    u32 targets[2]={(u32)cd_long_hook,(u32)cd_mem_hook};u32 i,j;
    /* Validate BOTH original sites before modifying either. */
    for(i=0;i<2;i++) for(j=0;j<12;j++)
        if(((volatile u8 *)addresses[i])[j]!=original[i][j]) return -1;
    for(i=0;i<2;i++) {
        volatile u32 *p=(volatile u32 *)addresses[i];
        p[0]=0xd001402b;p[1]=0x00090009;p[2]=targets[i];
    }
    *(volatile u8 *)0xfffffe92=(u8)((*(volatile u8 *)0xfffffe92&0x0f)|0x10);return 0;
}
