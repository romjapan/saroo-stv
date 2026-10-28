/* Experimental boot-only loader. Caller must own SMPC and keep SH2 IRQs masked. */
#include "cart_cd.h"
#define R8(a) (*(volatile u8 *)(a))
#define R16(a) (*(volatile u16 *)(a))
#define SOUND_DRIVER_HASH 0xc682a227u
#define SOUND_BANK_HASH 0x0140f750u
/* Exclusive boot staging lifetime, published uncached to both SH2s. */
#define SOUND_BOOT_STAGE_RELEASED (*(volatile u32 *)0x2021e1f8)
extern int sound_align_pack_install(void) __attribute__((weak));
static int command(u8 c) {
    u32 n=4000000;
    while(R8(0x20100063)&1)if(!--n)return -1;
    R8(0x20100063)=1;R8(0x2010001f)=c;n=4000000;
    while(R8(0x20100063)&1)if(!--n)return -2;
    return R8(0x2010005f)==c ? 0 : -3;
}
static int payload(u32 src,u32 dst,u32 bytes,u32 expected) {
    u32 i,h=0x811c9dc5;u8 *p=(u8 *)0x202b0000;
    p[-1]=0xa5;p[bytes]=0x5a;
    if(cart_cd_read(src,p,bytes))return -1;
    for(i=0;i<bytes;i++)h=(h^p[i])*0x01000193;
    if(h!=expected || p[-1]!=0xa5 || p[bytes]!=0x5a)return -2;
    for(i=0;i<bytes/2;i++)((volatile u16 *)dst)[i]=((u16 *)p)[i];
    for(i=0;i<bytes/2;i++)if(((volatile u16 *)dst)[i]!=((u16 *)p)[i])return -3;
    return 0;
}
int sound_boot_start(void) {
    u32 i;
    SOUND_BOOT_STAGE_RELEASED=0;
    __asm__ volatile("ldc %0,sr"::"r"(0xf0):"memory");
    if(command(7))return 0xb10;
    for(i=0;i<0x80000/2;i++)((volatile u16 *)0x25a00000)[i]=0;
    if(payload(0x0295a48c,0x25a00000,7342,SOUND_DRIVER_HASH))return 0xb20;
    if(payload(0x0295c13a,0x25a03000,16472,SOUND_BANK_HASH))return 0xb30;
    if(sound_align_pack_install && sound_align_pack_install())return 0xb35;
    if(command(6))return 0xb40;
    i=4000000;
    while(R16(0x25a07dbc)!=0x4f4b)if(!--i)return 0xb50;
    __asm__ volatile("":::"memory");
    SOUND_BOOT_STAGE_RELEASED=1;
    return 0;
}
