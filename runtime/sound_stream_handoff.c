/* Narrow CPU-refill fallback; original cached DMA route stays unchanged. */
#include "sound_stream_mailbox.h"
#include "diagnostic_screen.h"
/* Only SAROO builds define them. */
extern void cart_cd_diag_tick(void) __attribute__((weak));
extern int cart_cd_saroo_direct(u32,void *,u32) __attribute__((weak));
/* Slave-only staging for direct SAROO refills (Low Work RAM, as
   sound_dma_lwram requires). Mailbox untouched on this path. */
static u8 direct_data[520] __attribute__((aligned(4)));
/* Reads the 512 logical bytes at src into direct_data[0..511] with a
   four-aligned start. Returns 0 when the mailbox must be used instead. */
static int direct_fill(u32 src) {
    u32 i,delta=src&3;
    volatile u8 *p=(volatile u8 *)((u32)direct_data|0x20000000u);
    if(!cart_cd_saroo_direct ||
       cart_cd_saroo_direct(src-delta,direct_data,(512+delta+3)&~3u))return 0;
    if(delta)for(i=0;i<512;i++)p[i]=p[i+delta];
    return 1;
}
extern void sound_stream_main_gate(void);
extern void sound_dma_lwram(u32,u32,u32,u32,u32);
static u32 vbr(void) { u32 value;__asm__ volatile("stc vbr,%0":"=r"(value));return value; }
static void fail(u32 code) {
    volatile u32 *trace=(volatile u32 *)0x2021e000;
    __asm__ volatile("ldc %0,sr"::"r"(0xf0):"memory");
    trace[0]=0x4641494c;trace[1]=code;trace[6]=0;
    diagnostic_screen(code,cd_error.code,cd_error.lba,cd_error.hirq);
    trace[6]=0x44535059;for(;;)__asm__ volatile("nop");
}
void sound_stream_master_tick(void) {
    if(vbr()!=0x06000000)fail(0xb76);
    sound_stream_service(cart_cd_read,*(volatile u32 *)0x2021f010);
    if(cart_cd_diag_tick) cart_cd_diag_tick();
}
int sound_stream_refill(u32 dst,u32 src,u32 bytes) {
    u32 n=40000000;
    int result;
    if(vbr()!=0)fail(0xb71); /* Never wait for ourselves on master. */
    if(dst<0x25a00000 || bytes!=512 || dst>0x25a80000-bytes || (dst&1))fail(0xb72);
    if(direct_fill(src)) {
        const volatile u8 *in=(const volatile u8 *)((u32)direct_data|0x20000000u);
        u32 i;
        for(i=0;i<512;i++)((volatile u8 *)dst)[i]=in[i];
        return 1;
    }
    if(sound_stream_submit(src,bytes))fail(0xb73);
    for(;;) {
        result=sound_stream_collect((void *)dst,bytes);
        if(result==1)return 1;
        if(result<0)fail(0xb74);
        if(!--n){sound_stream_timeout();fail(0xb75);}
    }
}
static void wait_native_completion(u32 channel) {
    int (*status)(u32)=(int (*)(u32))0x06048430;
    u32 n=40000000;
    /* Native status returns0 for completion, nonzero while not complete.
       Retains original DMA-end bookkeeping/callback, not just DSTA bits. */
    while(status(channel))if(!--n){sound_stream_timeout();fail(0xb77);}
}
int sound_stream_dma_refill(u32 channel,u32 dst,u32 src,u32 bytes,u32 add) {
    void *buffer=0;
    u32 n=40000000;
    int result;
    if(bytes!=512)return 0; /* Bulk misses remain explicit, unsupported. */
    if(vbr()!=0)fail(0xb71);
    if(channel!=0 || dst<0x25a00000 || dst>0x25a80000-bytes ||
       (dst&1) || add!=0x101)fail(0xb72);
    wait_native_completion(channel);
    if(direct_fill(src)) {
        sound_dma_lwram(channel,dst,(u32)direct_data|0x20000000u,bytes,add);
        wait_native_completion(channel);
        return 1;
    }
    if(sound_stream_submit(src,bytes))fail(0xb73);
    for(;;) {
        result=sound_stream_borrow(&buffer,bytes);
        if(result==1)break;
        if(result<0)fail(0xb74);
        if(!--n){sound_stream_timeout();fail(0xb75);}
    }
    sound_dma_lwram(channel,dst,(u32)buffer,bytes,add);
    wait_native_completion(channel);
    if(sound_stream_release())fail(0xb78);
    return 1;
}
int sound_stream_handoff_install(void) {
    static const u8 expected[12]={0xd3,0x01,0x43,0x2b,0x00,0x09,
                                0x00,0x09,0x00,0x21,0x24,0x00};
    volatile u32 *site=(volatile u32 *)0x260102e4;
    u32 i;
    static const u8 status_guard[8]={0x2f,0xe6,0x4f,0x22,0x7f,0xf8,0x2f,0x42};
    for(i=0;i<8;i++)if(((volatile u8 *)0x26048430)[i]!=status_guard[i])return -3;
    for(i=0;i<12;i++)if(((volatile u8 *)site)[i]!=expected[i])return -1;
    sound_stream_reset();
    /* Guarded wrapper around existing immutable00212400 coin_main hook. */
    site[2]=(u32)sound_stream_main_gate;
    if(site[2]!=(u32)sound_stream_main_gate)return -2;
    *(volatile u8 *)0xfffffe92=(u8)((*(volatile u8 *)0xfffffe92&0x0f)|0x10);
    return 0;
}
