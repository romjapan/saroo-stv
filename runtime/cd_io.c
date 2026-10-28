#include "cd_io.h"
#define R16(a) (*(volatile u16 *)(a))
#define R32(a) (*(volatile u32 *)(a))
#define HIRQ R16(0x25890008)
#define CR1 R16(0x25890018)
#define CR2 R16(0x2589001c)
#define CR3 R16(0x25890020)
#define CR4 R16(0x25890024)
#define CMOK 1
#define DRDY 2
#define CSCT 4
#define PEND 0x10
#define ESEL 0x40
#define EHST 0x80
/* Play command carries a 24-bit FAD; FAD = ISO LBA + 150. */
#define CD_MAX_LBA (0xffffffu-150u)
/* Sectors per play request. Each command still waits for pace(); batching
   cuts commands and seeks per sector (real CD timing, not Yabause's instant
   block). Well below the 200-sector CD buffer. */
#define CD_BATCH 32u
/* Outside FPR HWRAM and the loader: standalone diagnostic reservation only.
   Baku's actual LWRAM allocation remains to be established before game entry. */
static u8 *const scratch=(u8 *)0x20200000;
CdError cd_error;
u32 cd_pace_display_off;
u32 cd_progress_bytes,cd_progress_total;
void (*cd_progress)(void);
static int error(u32 code) {
    cd_error.code=code; cd_error.hirq=HIRQ; cd_error.response=CR1;
    return -1;
}
static int wait_flag(u16 flag,u32 code) {
    u32 i;
    for(i=0;i<12000000;i++) if((HIRQ&flag)==flag) return 0;
    return error(code);
}
static int pace(void) {
    u32 i,line;u16 mode=R16(0x25f80000);
    if(!(mode&0x8000)) {
        /* Existing Yabause forces TVSTAT.VBLANK=1 with DISP off. Do not
           wait for its falling edge. For normal TV modes, 313 full HBlank
           periods provide conservative command spacing without enabling DISP. */
        if((mode&7)>1) return error(0x903);
        for(line=0;line<313;line++) {
            for(i=0;i<12000000 && (R16(0x25f80004)&4);i++);
            if(i==12000000) return error(0x904);
            for(i=0;i<12000000 && !(R16(0x25f80004)&4);i++);
            if(i==12000000) return error(0x905);
        }
        cd_pace_display_off++;return 0;
    }
    for(i=0;i<12000000 && (R16(0x25f80004)&8);i++);
    if(i==12000000) return error(0x901);
    for(i=0;i<12000000 && !(R16(0x25f80004)&8);i++);
    return i==12000000 ? error(0x902):0;
}
static u16 last_r4;
static int cmd(u16 a,u16 b,u16 c,u16 d,u16 end) {
    u16 status,r2,r3,r4;
    if(pace() || wait_flag(CMOK,0x10000|a)) return -1;
    if(end && wait_flag(end,0x20000|a)) return -1;
    HIRQ=(u16)~(CMOK|end);
    CR1=a;CR2=b;CR3=c;CR4=d;
    if(wait_flag(CMOK,0x30000|a)) return -1;
    status=CR1>>8; r2=CR2; r3=CR3; r4=CR4;
    (void)r2;(void)r3;last_r4=r4;
    if(status==0xff || (status&0x80)) return error(0x40000|a);
    return end ? wait_flag(end,0x50000|a):0;
}
/* Read n consecutive sectors with one play request and one transfer.
   dst receives n*2048 bytes as aligned 32-bit stores (big-endian order). */
static int read_sectors(u32 lba,u32 n,u32 *dst) {
    u32 fad,i,polls;
    cd_error.lba=lba;
    if(lba>CD_MAX_LBA || !n || n>CD_BATCH || n-1>CD_MAX_LBA-lba) return error(0xc02);
    fad=lba+150;
    if(cmd(0x4800,0,0,0,ESEL)) return -1;
    HIRQ=(u16)~(CSCT|PEND);
    if(cmd(0x1080|(fad>>16),(u16)fad,0x0080,(u16)n,0)) return -1;
    /* Get Sector Number at the paced command rate, not a busy command loop. */
    for(polls=0;;polls++) {
        if(cmd(0x5100,0,0,0,0)) return -1;
        if(last_r4>=n) break;
        if(polls>=1200) return error(0x64000|last_r4);
    }
    if(last_r4!=n) return error(0x62000|last_r4);
    if(cmd(0x6300,0,0,(u16)n,0) || wait_flag(DRDY,0x70000)) return -1;
    HIRQ=(u16)~DRDY;
    for(i=0;i<n*512;i++) dst[i]=R32(0x25818000);
    if(cmd(0x0600,0,0,0,0) || wait_flag(EHST,0x80000)) return -1;
    cd_progress_bytes+=n<<11;
    if(cd_progress) cd_progress();
    return 0;
}
static int sector(u32 lba) {
    return read_sectors(lba,1,(u32 *)scratch);
}
static u32 le32(const u8 *p) {
    return p[0]|((u32)p[1]<<8)|((u32)p[2]<<16)|((u32)p[3]<<24);
}
int cd_init(void) {
    cd_error.code=0;
    cd_pace_display_off=0;
    if(cmd(0x3000,0,0,0,ESEL) || cmd(0x4400,0,0,0,ESEL) ||
       cmd(0x4603,0x00ff,0,0,ESEL) || cmd(0x6000,0,0,0,ESEL)) return -1;
    return 0;
}
int cd_find_root(const char *name,CdFile *file) {
    u32 root,bytes,pos,n=0,s;
    while(n<=255 && name[n]) n++;
    if(n>255 || !n) return error(0xa00);
    if(sector(16)) return -1;
    if(scratch[0]!=1 || scratch[1]!='C' || scratch[2]!='D' ||
       scratch[3]!='0' || scratch[4]!='0' || scratch[5]!='1') return error(0xa01);
    root=le32(scratch+158);bytes=le32(scratch+166);
    if(!root || !bytes || bytes>65536) return error(0xa02);
    for(s=0;s<(bytes+2047)/2048;s++) {
        u32 remaining=bytes-s*2048;
        if(sector(root+s)) return -1;
        for(pos=0;pos<2048 && pos<remaining && scratch[pos];pos+=scratch[pos]) {
            u8 *p=scratch+pos;u32 j;
            if(p[0]<34 || pos+p[0]>2048 || pos+p[0]>remaining ||
               p[32]>p[0]-33) return error(0xa03);
            if(p[32]!=n) continue;
            for(j=0;j<n && p[33+j]==(u8)name[j];j++);
            if(j!=n) continue;
            /* No directories, interleaved or multi-extent files in this reader. */
            if(p[25]&0x82 || p[26] || p[27]) return error(0xa05);
            file->lba=le32(p+2);file->size=le32(p+10);
            return 0;
        }
    }
    return error(0xa04);
}
int cd_read_at(const CdFile *file,u32 offset,void *destination,u32 size) {
    u8 *dst=(u8 *)destination;
    if(offset>file->size || size>file->size-offset) return error(0xc01);
    /* Validate the whole transfer before the first read or destination write.
       The size check above guarantees offset+size-1 cannot wrap for size>0. */
    if(size && (file->lba>CD_MAX_LBA ||
       ((offset+size-1)>>11)>CD_MAX_LBA-file->lba)) return error(0xc02);
    while(size) {
        u32 within=offset&2047,count=2048-within,i;
        if(!within && size>=2048 && !((unsigned long)dst&3)) {
            u32 n=size>>11;
            if(n>CD_BATCH) n=CD_BATCH;
            if(read_sectors(file->lba+(offset>>11),n,(u32 *)dst)) return -1;
            offset+=n<<11;dst+=n<<11;size-=n<<11;
            continue;
        }
        if(count>size) count=size;
        if(sector(file->lba+(offset>>11))) return -1;
        for(i=0;i<count;i++) dst[i]=scratch[within+i];
        offset+=count;dst+=count;size-=count;
    }
    return 0;
}
