/* SAROO SDRAM-backed ST-V ROM, for the saroo-stv MCU commands (mcuapp.bin with
   SSCMD_STVLOAD 0x40 / SSCMD_ROMCTL 0x41) on official FPGA 06+.
   Register addresses and the TMPBUFF little-endian parameter block follow
   SAROO v0.9 Firm_Saturn (read_file / LE32W). Every MCU wait is bounded:
   official mcuapp.bin never clears SS_CMD for unknown commands. */
#include "saroo_rom.h"
#define R16(a) (*(volatile u16 *)(a))
#define SS_ID  R16(0x25807000)
#define SS_VER R16(0x25807002)
#define SS_CMD R16(0x25897010)
#define SS_ARG R16(0x25897014)
#define TMPBUF ((volatile u8 *)0x220c7000)
#define SSCMD_FILEWR  0x0007
#define SSCMD_STVLOAD 0x0040
#define SSCMD_ROMCTL  0x0041
static void le32w(u32 off,u32 v) {
    TMPBUF[off]=(u8)v;TMPBUF[off+1]=(u8)(v>>8);TMPBUF[off+2]=(u8)(v>>16);TMPBUF[off+3]=(u8)(v>>24);
}
static u32 le32(u32 off) {
    return TMPBUF[off]|((u32)TMPBUF[off+1]<<8)|((u32)TMPBUF[off+2]<<16)|((u32)TMPBUF[off+3]<<24);
}
void (*saroo_poll_hook)(u32 polls);
static int command(u16 cmd,u16 arg,u32 polls,u16 *result) {
    u32 i;
    SS_ARG=arg;SS_CMD=cmd;
    for(i=0;i<polls;i++) {
        if(!SS_CMD) {*result=SS_ARG;return 0;}
        if(saroo_poll_hook && !(i&0xfffff)) saroo_poll_hook(i);
    }
    return -1;
}
u32 saroo_id(void) {return ((u32)SS_ID<<16)|SS_VER;}
int saroo_present(void) {return SS_ID==0x5253;}
int saroo_romctl(int aa24,u16 *ctrl) {
    return command(SSCMD_ROMCTL,aa24?1:0,SAROO_SHORT_POLLS,ctrl);
}
int saroo_stvload(const char *name,u32 offset,u32 size,u32 sdram,u32 *loaded) {
    u32 i;u16 status;
    le32w(0x00,offset);le32w(0x04,size);le32w(0x08,sdram);
    for(i=0;name[i] && i<0xef;i++) TMPBUF[0x10+i]=(u8)name[i];
    TMPBUF[0x10+i]=0;
    if(command(SSCMD_STVLOAD,0,SAROO_LOAD_POLLS,&status)) return -1000;
    *loaded=le32(0x04);
    return (short)status;
}
int saroo_filewr(const char *name,int offset,u32 size,u32 sdram) {
    u32 i;u16 status;
    le32w(0x00,(u32)offset);le32w(0x04,size);le32w(0x08,sdram);
    for(i=0;name[i] && i<0xef;i++) TMPBUF[0x10+i]=(u8)name[i];
    TMPBUF[0x10+i]=0;
    if(command(SSCMD_FILEWR,0,SAROO_SHORT_POLLS,&status)) return -1000;
    return (short)status;
}
