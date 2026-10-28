/* SCU DMA cannot read Low Work RAM (0x00200000-0x002fffff): Mednafen and real
   hardware deliver wrong data, only Yabause copies it. Sound sources staged in
   LWRAM are therefore written to SCSP RAM by the CPU, and only the last (up to)
   four bytes go through the native DMA from a High Work RAM scratch so the
   game's own DMA-end bookkeeping still runs unchanged. */
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
extern void sound_dma_native(u32,u32,u32,u32,u32);
/* Only SAROO builds define it. */
extern int cart_cd_saroo_mapped(u32,u32) __attribute__((weak));
/* 0x06000bf0..bf7: unused BIOS work area (0x06000bfc is the HLE diag word). */
#define SCRATCH 0x26000bf0u
/* CPU copy only for contiguous transfers: read add +4 (bit 8) and write
   add 2 or 4 bytes (bits 2-0 = 1 or 2). */
static int contiguous(u32 dst,u32 bytes,u32 add) {
    return bytes>=2 && !(dst&1) && (add&0x100) && ((add&7)==1 || (add&7)==2);
}
static void bounce(u32 channel,u32 dst,u32 a,u32 bytes,u32 add) {
    u32 head,tail,j;
    const volatile u8 *in=(const volatile u8 *)(a|0x20000000);
    volatile u16 *out=(volatile u16 *)((dst&0x0fffffff)|0x20000000);   /* cache-through */
    volatile u8 *scratch;
    tail=bytes<4?bytes:4;head=bytes-tail;
    if(!(a&1)) {
        const volatile u16 *in16=(const volatile u16 *)in;
        for(j=0;j<head/2;j++) out[j]=in16[j];
    } else
        for(j=0;j<head/2;j++) out[j]=(u16)((in[2*j]<<8)|in[2*j+1]);
    /* Keep the native source alignment of the tail. */
    scratch=(volatile u8 *)(SCRATCH+((a+head)&3));
    for(j=0;j<tail;j++) scratch[j]=in[head+j];
    sound_dma_native(channel,dst+head,(u32)scratch,tail,add);
}
void sound_dma_lwram(u32 channel,u32 dst,u32 src,u32 bytes,u32 add) {
    u32 a=src&0x0fffffff;
    if(a<0x00200000 || a>=0x00300000 || !contiguous(dst,bytes,add)) {
        sound_dma_native(channel,dst,src,bytes,add);return;
    }
    bounce(channel,dst,a,bytes,add);
}
/* SAROO-resident cart (cart_cd.c): CS0 is plain memory, but SCU DMA from it
   returns wrong data on hardware, so the CPU copies it like LWRAM. Returns 0
   when the source is not mapped or the transfer is not contiguous. */
int sound_dma_cart(u32 channel,u32 dst,u32 src,u32 bytes,u32 add) {
    if(!cart_cd_saroo_mapped || !cart_cd_saroo_mapped(src,bytes) ||
       !contiguous(dst,bytes,add)) return 0;
    bounce(channel,dst,src&0x0fffffff,bytes,add);
    return 1;
}
