/* Opt-in port-side sample packing. Original DMA helper/completion unchanged. */
#include "cart_cd.h"
int sound_align_pack_install(void) {
    static const u16 original[3]={0xd086,0x51cf,0xffbe};
    /* 1e00: add.l d6,d0; addq.l #1,d0; andi.l #fffffffe,d0;
       dbra d7,1218; jmp125c. DBRA displacement is relative to1e0c. */
    static const u16 stub[10]={0xd086,0x5280,0x0280,0xffff,0xfffe,
                              0x51cf,0xf40c,0x4ef9,0x0000,0x125c};
    static const u16 jump[3]={0x4ef9,0x0000,0x1e00};
    volatile u16 *site=(volatile u16 *)0x25a01256;
    volatile u16 *target=(volatile u16 *)0x25a01e00;
    u32 i;
    for(i=0;i<3;i++)if(site[i]!=original[i])return -1;
    for(i=0;i<10;i++)if(target[i])return -2;
    for(i=0;i<10;i++)target[i]=stub[i];
    for(i=0;i<10;i++)if(target[i]!=stub[i])return -3;
    for(i=0;i<3;i++)site[i]=jump[i];
    for(i=0;i<3;i++)if(site[i]!=jump[i])return -4;
    return 0;
}
