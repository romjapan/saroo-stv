/* Introdon SAROO profile only. CPU payload, native DMA completion.
   Scratch/trace live in BIOS-owned HWRAM, never SAROO SDRAM or game LWRAM. */
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
#define W32(a) (*(volatile u32 *)(a))
#define TRACE ((volatile u32 *)0x2600a900)
#define SCRATCH 0x2600ae00u
extern void diagnostic_screen(u32,u32,u32,u32);
static int unsafe(u32 a) {
    a &= 0x1fffffffu;
    return (a>=0x02000000 && a<0x04000000) ||
           (a>=0x00200000 && a<0x00300000);
}
#define submitted(src) ((void)0)
static void halt(u32 code) {
    W32(0x2600a800)=0x4641494c; W32(0x2600a804)=code;
    __asm__ volatile("ldc %0,sr"::"r"(0xf0):"memory");
    diagnostic_screen(code,TRACE[0],TRACE[4],TRACE[5]);
    for(;;) __asm__ volatile("nop");
}
static void record(u32 site,u32 ch,u32 src,u32 dst,u32 n,u32 add,u32 mode) {
    u32 i=TRACE[0]++;
    u32 a=src&0x1fffffff;
    u32 cls=(a>=0x02000000 && a<0x04000000)?1:
            ((a>=0x00200000 && a<0x00300000)?2:0);
    volatile u32 *p=TRACE+8+(i%24)*8;
    volatile u32 *s=TRACE+208+(site*3+cls)*8;
    p[0]=site;p[1]=ch;p[2]=src;p[3]=dst;p[4]=n;p[5]=add;p[6]=mode;
    p[7]=unsafe(src);
    TRACE[1+site]++;
    if(unsafe(src)) TRACE[4]++;
    if(mode&0x1000000) TRACE[5]++;
    if(!s[0] || src<s[1]) s[1]=src;
    if(!s[0] || src>s[2]) s[2]=src;
    if(!s[0] || dst<s[3]) s[3]=dst;
    if(!s[0] || dst>s[4]) s[4]=dst;
    if(n>s[5]) s[5]=n;
    s[6]|=add;s[7]|=mode;s[0]++;
}
/* Only even, contiguous transfers have been established for this game.
   Reject other unsafe shapes instead of silently submitting corrupt DMA. */
static void copy(u32 src,u32 dst,u32 n,u32 add) {
    u32 i;
    volatile u16 *out=(volatile u16 *)((dst&0x1fffffff)|0x20000000);
    const volatile u8 *in=(const volatile u8 *)((src&0x1fffffff)|0x20000000);
    if(!n || (n&1) || (dst&1) || !(add&0x100) ||
       ((add&7)!=1 && (add&7)!=2)) halt(0xb51);
    if(!(src&1)) {
        const volatile u16 *words=(const volatile u16 *)in;
        for(i=0;i<n/2;i++) out[i]=words[i];
    } else for(i=0;i<n;i+=2) out[i/2]=(u16)((in[i]<<8)|in[i+1]);
}
static void tail(u32 ch,u32 *src,u32 *dst,u32 *n,u32 add) {
    u32 k=*n<4?*n:4, i;
    u32 scratch=SCRATCH+ch*8+((*src+*n-k)&3);
    volatile u8 *p=(volatile u8 *)scratch;
    const volatile u8 *in=(const volatile u8 *)((*src&0x1fffffff)|0x20000000);
    /* CPU copies the head; native tail generates the original IRQ. */
    if(*n>k) copy(*src,*dst,*n-k,add);
    if(!k || (k&1) || (*dst&1) || !(add&0x100) ||
       ((add&7)!=1 && (add&7)!=2)) halt(0xb51);
    for(i=0;i<k;i++) p[i]=in[*n-k+i];
    *src=scratch;*dst+=*n-k;*n=k;
}
void intro_dma_direct(u32 ch,u32 src,u32 dst,u32 n) {
    if(ch>2) halt(0xb52);
    record(0,ch,src,dst,n,0x101,0x10107);
    n &= ch?0xfff:0xfffff;
    if(!n) n=ch?0x1000:0x100000;
    if(unsafe(src)) tail(ch,&src,&dst,&n,0x101);
    submitted(src);
    ((void (*)(u32,u32,u32,u32))0x06034d10)(ch,src,dst,n);
}
void intro_dma_config(const u32 *p,u32 ch) {
    u32 q[10],i,src,dst,n,add,mode;
    volatile u32 *r=(volatile u32 *)(0x25fe0000+ch*32);
    if(ch>2) halt(0xb52);
    for(i=0;i<10;i++) q[i]=p[i];
    src=(q[9]&1)?q[0]:r[0];dst=(q[9]&2)?q[1]:r[1];
    n=q[2];add=q[3]|q[4];
    mode=q[5]|(q[6]<<16)|(q[7]<<8)|q[8];
    record(1,ch,src,dst,n,add,mode);
    if(mode&0x1000000) {
        /* Table triples: count,destination,source; source bit31=end.
           CPU walk also handles a table held in LWRAM/cart. No SCU table
           fetch is permitted there. Bound malformed/unterminated lists. */
        const volatile u32 *t=(const volatile u32 *)((dst&0x1fffffff)|0x20000000);
        if(!(add&0x100)) halt(0xb51);
        for(i=0;i<4096;i++,t+=3) {
            /* Indirect entries always have a 20-bit count, on all levels. */
            n=t[0]&0xfffff;dst=t[1];src=t[2];
            if(!n) n=0x100000;
            record(2,ch,src&0x7fffffff,dst,n,add,mode);
            if(src&0x80000000) break;
            copy(src,dst,n,add);
        }
        if(i==4096) halt(0xb53);
        src&=0x7fffffff;
        tail(ch,&src,&dst,&n,add);
        q[0]=src;q[1]=dst;q[2]=n;q[9]|=3;
        q[5]=mode&~0x1000000;q[6]=q[7]=q[8]=0;
    } else if(unsafe(src)) {
        n &= ch?0xfff:0xfffff;
        if(!n) n=ch?0x1000:0x100000;
        tail(ch,&src,&dst,&n,add);
        q[0]=src;q[1]=dst;q[2]=n;q[9]|=3;
    }
    submitted((q[9]&1)?q[0]:src);
    ((void (*)(const u32 *,u32))0x060cf944)(q,ch);
}
