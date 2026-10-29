/* Shared boot-only NBG0 512x256 RGB32768 renderer. Explicit caller work
   drives progress. end clears the bitmap and disables display before the
   game's video initialization. The accepted legacy Baku renderer is frozen. */
#include "cd_io.h"
#include "load_progress.h"
#ifndef D16
#define D16(a) (*(volatile u16 *)(a))
#endif
#define VRAM 0x25e00000u
#define WHITE 0xffffu
#define DARK 0x8c63u
#define FILL 0x83ffu
#define BAR_X 48u
#define BAR_Y 132u
#define BAR_W 224u
#define BAR_H 12u
/* 5x7 glyphs, one row per byte (bit4 = leftmost column). */
static const u8 font[][7]={
 {0x11,0x19,0x15,0x13,0x11,0x11,0x11}, /* N */
 {0x0e,0x11,0x11,0x11,0x11,0x11,0x0e}, /* O */
 {0x11,0x11,0x11,0x15,0x15,0x1b,0x11}, /* W */
 {0x10,0x10,0x10,0x10,0x10,0x10,0x1f}, /* L */
 {0x0e,0x11,0x11,0x1f,0x11,0x11,0x11}, /* A */
 {0x1e,0x11,0x11,0x11,0x11,0x11,0x1e}, /* D */
 {0x0e,0x04,0x04,0x04,0x04,0x04,0x0e}, /* I */
 {0x0e,0x11,0x10,0x17,0x11,0x11,0x0f}, /* G */
 {0x18,0x19,0x02,0x04,0x08,0x13,0x03}, /* % */
 {0x0e,0x11,0x13,0x15,0x19,0x11,0x0e}, /* 0 */
 {0x04,0x0c,0x04,0x04,0x04,0x04,0x0e},
 {0x0e,0x11,0x01,0x02,0x04,0x08,0x1f},
 {0x1f,0x02,0x04,0x02,0x01,0x11,0x0e},
 {0x02,0x06,0x0a,0x12,0x1f,0x02,0x02},
 {0x1f,0x10,0x1e,0x01,0x01,0x11,0x0e},
 {0x06,0x08,0x10,0x1e,0x11,0x11,0x0e},
 {0x1f,0x01,0x02,0x04,0x08,0x08,0x08},
 {0x0e,0x11,0x11,0x0e,0x11,0x11,0x0e},
 {0x0e,0x11,0x11,0x0f,0x01,0x02,0x0c}, /* 9 */
 {0x11,0x11,0x11,0x11,0x11,0x0a,0x04}, /* V */
 {0x1f,0x10,0x10,0x1e,0x10,0x10,0x1f}, /* E */
 {0x1e,0x11,0x11,0x1e,0x14,0x12,0x11}, /* R */
 {0x1f,0x10,0x10,0x1e,0x10,0x10,0x10}, /* F */
 {0x11,0x11,0x0a,0x04,0x04,0x04,0x04}, /* Y */
 {0x0e,0x11,0x10,0x10,0x10,0x11,0x0e}, /* C */
 {0x1e,0x11,0x11,0x1e,0x10,0x10,0x10}, /* P */
 {0x0f,0x10,0x10,0x0e,0x01,0x01,0x1e} /* S */
};
enum {G_N,G_O,G_W,G_L,G_A,G_D,G_I,G_G,G_PCT,G_0,G_V=19,G_E,G_R,G_F,G_Y,G_C,G_P,G_S};
static u32 work_done,work_total,drawn,shown_pct;
/* Linked without libgcc: shift-subtract unsigned division. */
static u32 udiv(u32 n,u32 d){
 u32 q=0,bit=1;
 if(!d)return 0;
 while(d<n && !(d&0x80000000u)){d<<=1;bit<<=1;}
 while(bit){if(n>=d){n-=d;q|=bit;}d>>=1;bit>>=1;}
 return q;
}
static void rect(u32 x,u32 y,u32 w,u32 h,u16 c){
 u32 i,j;for(j=0;j<h;j++)for(i=0;i<w;i++)D16(VRAM+((y+j)*512+x+i)*2)=c;
}
static void glyph(u32 g,u32 x,u32 y,u32 s,u16 c){
 u32 r,b,m;for(r=0;r<7;r++)for(b=0,m=0x10;b<5;b++,m>>=1)
  rect(x+b*s,y+r*s,s,s,(font[g][r]&m)?c:0x8000);
}
static void percent(u32 pct){
 u32 x=136,tens=udiv(pct,10),ones=pct-tens*10;
 rect(x,152,48,14,0x8000);
 if(pct>=100){glyph(G_0+1,x,152,2,WHITE);x+=12;tens-=10;}
 if(pct>=10){glyph(G_0+tens,x,152,2,WHITE);x+=12;}
 glyph(G_0+ones,x,152,2,WHITE);x+=12;
 glyph(G_PCT,x,152,2,WHITE);
}
static void update(void){
 u32 done=work_done,total=work_total,w,pct;
 if(!total)return;
 if(done>total)done=total;
 /* Bound multiplication while retaining small caller-defined totals. */
 while(total>0x00ffffffu){total=(total+1)>>1;done>>=1;}
 w=udiv((BAR_W-4)*done,total);
 if(w>BAR_W-4)w=BAR_W-4;
 if(w>drawn){rect(BAR_X+2+drawn,BAR_Y+2,w-drawn,BAR_H-4,FILL);drawn=w;}
 pct=udiv(100*done,total);
 if(pct>100)pct=100;
 if(pct!=shown_pct){percent(pct);shown_pct=pct;}
}
/* Resident construction overwrites RAMCTL and all eight cycle words. Restore
   the complete proven loading layout before drawing another stage, not just
   TVMD/BGON. Keep Baku's accepted legacy implementation untouched. */
static void video_setup(void){
 u32 i;
 D16(0x25f80000)=0;
 /* ST-058: NBG0 512x256 RGB32768 bitmap, unit scale, no windows/effects. */
 D16(0x25f8000e)=0;D16(0x25f80010)=0x4444;D16(0x25f80012)=0xffff;
 D16(0x25f80014)=0x4444;D16(0x25f80016)=0xffff;
 D16(0x25f80028)=0x0032;D16(0x25f8002c)=0;D16(0x25f8003c)=0;
 for(i=0x70;i<=0x7e;i+=2)D16(0x25f80000+i)=0;
 D16(0x25f80078)=1;D16(0x25f8007c)=1;
 D16(0x25f8009a)=0;D16(0x25f800d0)=0;
 D16(0x25f800ec)=0;D16(0x25f80110)=0;D16(0x25f800f8)=7;
}
void load_progress_begin(u32 total){
 static const u8 title[]={G_N,G_O,G_W,0xff,G_L,G_O,G_A,G_D,G_I,G_N,G_G};
 u32 i,x;
 video_setup();
 for(i=0;i<512*256;i++)D16(VRAM+i*2)=0x8000;
 for(i=0,x=94;i<sizeof title;i++,x+=12) if(title[i]!=0xff) glyph(title[i],x,96,2,WHITE);
 rect(BAR_X,BAR_Y,BAR_W,BAR_H,WHITE);
 rect(BAR_X+1,BAR_Y+1,BAR_W-2,BAR_H-2,0x8000);
 rect(BAR_X+2,BAR_Y+2,BAR_W-4,BAR_H-4,DARK);
 work_done=0;work_total=total;drawn=0;shown_pct=~0u;
 update();
 D16(0x25f80020)=1;D16(0x25f80000)=0x8000;

}

void load_progress_stage(u32 stage){
 static const u8 labels[][11]={
  {G_L,G_O,G_A,G_D,G_I,G_N,G_G,255,255,255,255},
  {G_N,G_O,G_W,255,G_L,G_O,G_A,G_D,G_I,G_N,G_G},
  {G_V,G_E,G_R,G_I,G_F,G_Y,G_I,G_N,G_G,255,255},
  {G_C,G_O,G_P,G_Y,G_I,G_N,G_G,255,255,255,255}
 };
 u32 i;if(stage>LOAD_COPY)stage=LOAD_CD;
 video_setup();
 rect(80,96,180,14,0x8000);
 for(i=0;i<11;i++)if(labels[stage][i]!=255)glyph(labels[stage][i],80+i*12,96,2,WHITE);
 glyph(G_0+stage+1,244,96,2,WHITE);
 /* A resident BIOS setup may disable display between loader phases. */
 D16(0x25f80020)=1;D16(0x25f80000)=0x8000;
}
void load_progress_advance(u32 work){
 if(work>work_total-work_done)work=work_total-work_done;
 work_done+=work;update();
}
void load_progress_pulse(u32 polls){
 rect(48,176,224,4,0x8000);
 rect(48+((polls>>20)&15)*14,176,14,4,FILL);
}
void load_progress_end(void){
 u32 i;load_progress_advance(work_total-work_done);
 D16(0x25f80000)=0;D16(0x25f80020)=0;
 for(i=0;i<512*256;i++)D16(VRAM+i*2)=0;
 D16(0x25f8000e)=0;
 for(i=0x10;i<=0x16;i+=2)D16(0x25f80000+i)=0;
 D16(0x25f80028)=0;D16(0x25f8002c)=0;D16(0x25f8003c)=0;
 for(i=0x70;i<=0x7e;i+=2)D16(0x25f80000+i)=0;
 D16(0x25f8009a)=0;D16(0x25f800d0)=0;D16(0x25f800ec)=0;
 D16(0x25f80110)=0;D16(0x25f800f8)=0;
}
