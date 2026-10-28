/* Fatal diagnostic only: replaces VRAM with four readable hexadecimal rows. */
#include "diagnostic_screen.h"
#ifndef D16
#define D16(a) (*(volatile unsigned short *)(a))
#endif
static const unsigned short glyph[16]={
 0x7b6f,0x2492,0x73e7,0x73cf,0x5bc9,0x79cf,0x79ef,0x7249,
 0x7bef,0x7bcf,0x7bed,0x6bae,0x7927,0x6b6e,0x79e7,0x79e4
};
static void row(unsigned int value,unsigned int y){
 unsigned int d,x,gy,gx,sy,sx,bits,mask;
 for(d=0;d<8;d++){
  bits=glyph[value>>28];value<<=4;x=32+d*16;mask=0x4000;
  for(gy=0;gy<5;gy++)for(gx=0;gx<3;gx++)
   {if(bits&mask)
    for(sy=0;sy<4;sy++)for(sx=0;sx<4;sx++)
     D16(0x25e00000+((y+gy*4+sy)*512+x+gx*4+sx)*2)=0xffff;
    mask>>=1;}
 }
}
void diagnostic_screen(unsigned int code,unsigned int cdcode,unsigned int lba,unsigned int hirq){
 unsigned int i;
 D16(0x25f80000)=0;D16(0x25f80020)=0;
 for(i=0;i<512*256;i++)D16(0x25e00000+i*2)=0x8000;
 /* ST-058: NBG0 512x256 RGB32768 bitmap, unit scale, no windows/effects. */
 D16(0x25f8000e)=0;D16(0x25f80010)=0x4444;D16(0x25f80012)=0xffff;
 D16(0x25f80014)=0x4444;D16(0x25f80016)=0xffff;
 D16(0x25f80028)=0x0032;D16(0x25f8002c)=0;D16(0x25f8003c)=0;
 for(i=0x70;i<=0x7e;i+=2)D16(0x25f80000+i)=0;
 D16(0x25f80078)=1;D16(0x25f8007c)=1;
 D16(0x25f8009a)=0;D16(0x25f800d0)=0;
 D16(0x25f800ec)=0;D16(0x25f80110)=0;D16(0x25f800f8)=7;
 row(code,32);row(cdcode,72);row(lba,112);row(hirq,152);
 D16(0x25f80020)=1;D16(0x25f80000)=0x8000;
}

/* Denser fatal page: up to 26 values, two columns of 13 rows, 3x3-pixel
   glyph cells. Row r column c shows v[r*2+c]. */
static void cell(unsigned int value,unsigned int x0,unsigned int y){
 unsigned int d,x,gy,gx,sy,sx,bits,mask;
 for(d=0;d<8;d++){
  bits=glyph[value>>28];value<<=4;x=x0+d*12;mask=0x4000;
  for(gy=0;gy<5;gy++)for(gx=0;gx<3;gx++)
   {if(bits&mask)
    for(sy=0;sy<3;sy++)for(sx=0;sx<3;sx++)
     D16(0x25e00000+((y+gy*3+sy)*512+x+gx*3+sx)*2)=0xffff;
    mask>>=1;}
 }
}
void diagnostic_grid(const unsigned int *v,unsigned int n){
 unsigned int i;
 diagnostic_screen(0,0,0,0);
 D16(0x25f80000)=0;
 for(i=0;i<512*256;i++)D16(0x25e00000+i*2)=0x8000;
 for(i=0;i<n && i<26;i++) cell(v[i],(i&1)?176:24,4+(i>>1)*19);
 D16(0x25f80000)=0x8000;
}
