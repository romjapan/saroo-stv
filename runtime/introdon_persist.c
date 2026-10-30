/* Internal backup device 0, always through the running Saturn BIOS library.
 * Library/workspace use temporary high RAM above the native image and below
 * the guarded live stack. Never format
 * a device, delete a file, or issue an operation for a different filename. */
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
#define L(a) (*(volatile u32 *)(a))
#define B(a) (*(volatile u8 *)(a))
typedef struct {u8 name[12],comment[11],language;u32 date,size;u16 blocks;} Dir;
typedef struct {u32 total,blocks,blocksize,free,freeblocks,count;} Stat;
typedef struct {u32 init,ready,last_frame,stable,hash,saved_hash,status,writes,compressed,serviceheld;} State;
#define S ((volatile State *)0x2600d300)
#define SNAP ((u8 *)0x2600d000)
#define BYTES 460
#define TOTAL (BYTES+16)
static const u8 name[12]="INTRODONP12";
extern int intro_persist_command(u32 command);
static void pack(u8 *p,int restore) {
 u32 i,j=16,a;
 /* Odd lanes: native channel-0 data 0x100..0x217; BIOS header+records
    0x3d00..0x3e7f. Its mirror is reconstructed, never stored twice. */
 for(i=0;i<332;i++) {
  a=i<140?0x2600b101+i*2:0x2600ed01+(i-140)*2;
  if(restore)B(a)=p[j++];else p[j++]=B(a);
 }
 for(i=0;i<128;i++) {
  a=0x26000780+i;
  if(restore)B(a)=p[j++];else p[j++]=B(a);
 }
 if(restore)for(i=0;i<384;i++)B(0x2600ee80+i)=B(0x2600ed00+i);
}
static u32 hash(const u8 *p) {
 u32 h=2166136261u,i;
 for(i=16;i<TOTAL;i++)h=(h^p[i])*16777619u;
 return h;
}
/* mode0 load, mode1 store. No library call is made from an interrupt. */
static int access(int mode) {
 u32 *lib=(u32 *)0x060f2000,*work=(u32 *)0x060f6000;
 u32 conf[3],old_table[64],old_ims=L(0x25fe00a0),i;
 Dir d;Stat stat;u32 *v;int ret=-1,n;
 if(!S->init || S->init>=0x80000)return -10;
 if(intro_persist_command(0x1a))return -11;
 /* The BIOS decompressor calls arithmetic helpers through its API table.
    HLE owns that table during play; restore Saturn's table only while IRQs
    and panel reset are disabled, then put every HLE slot back. */
 for(i=0;i<64;i++){old_table[i]=L(0x26000300+i*4);L(0x26000300+i*4)=L(0x2600d400+i*4);}
 L(0x26000348)=old_ims; /* BUP uses the Saturn BIOS SCU-mask shadow. */
 B(0xfffffe92)=0x11; /* BIOS helpers read the cached API-table alias. */
 ((void (*)(u32 *,u32 *,u32 *))S->init)(lib,work,conf);
 /* BUP_Init publishes its dispatch table in BIOS work RAM. */
 B(0xfffffe92)=0x11;
 v=(u32 *)L(0x26000354);
 if(v!=work)goto done;
 for(i=0;i<11;i++)if(v[i]<(u32)lib || v[i]>=(u32)(lib+4096))goto done;
 for(i=0;i<sizeof(d);i++)((u8 *)&d)[i]=0;
 for(i=0;i<12;i++)d.name[i]=name[i];
 n=((int (*)(u32,const u8 *,u16,Dir *))v[7])(0,name,1,&d);
 if(n!=0 && (n!=1 || d.size!=TOTAL)) {ret=-12;goto done;}
 if(!mode) {
  if(n!=1){ret=-13;goto done;}
  ret=((int (*)(u32,const u8 *,u8 *))v[5])(0,name,SNAP);
  if(!ret && (((u32 *)SNAP)[0]!=0x494e5431 || ((u32 *)SNAP)[1]!=1 ||
       ((u32 *)SNAP)[2]!=BYTES || ((u32 *)SNAP)[3]!=hash(SNAP)))ret=-14;
  if(!ret)pack(SNAP,1);
 } else {
  ret=((int (*)(u32,u32,Stat *))v[3])(0,TOTAL,&stat);
  if(ret || stat.blocksize!=64 || stat.freeblocks+(n?d.blocks:0)<9){if(!ret)ret=-15;goto done;}
  for(i=0;i<12;i++)d.name[i]=name[i];
  for(i=0;i<11;i++)d.comment[i]=i<8?(u8)"INTRODON!"[i]:0;
  d.language=1;d.size=TOTAL;
  ret=((int (*)(u32,Dir *,u8 *,u8))v[4])(0,&d,SNAP,0);
  if(!ret)ret=((int (*)(u32,const u8 *,u8 *))v[8])(0,name,SNAP);
 }
done:
 for(i=0;i<64;i++)L(0x26000300+i*4)=old_table[i];
 B(0xfffffe92)=0x11; /* Game/HLE callers must see restored slots as well. */
 L(0x25fe00a0)=old_ims;
 intro_persist_command(0x19);
 return ret;
}
void intro_persist_init(u32 init,u32 compressed) {
 S->init=init;S->compressed=compressed;S->ready=0;S->writes=0;
 S->status=(u32)access(0);
 pack(SNAP,0);S->hash=S->saved_hash=hash(SNAP);
 S->last_frame=0;S->stable=0;S->ready=1;
}
void intro_persist_tick(void) {
 u32 frame=L(0x2600a0b4),h,sp,c=L(0x26000bec),exit=L(0x2600a0e0);
 if(S->ready && S->serviceheld && !(c&8) && L(0x2609eacc)!=1) {
  /* Service credit does not advance either physical coin audit. */
  if(B(0x2600ed05)<9)B(0x2600ed05)++;
  B(0x26000653)=1;
 }
 S->serviceheld=c&8;
 __asm__ volatile("mov r15,%0":"=r"(sp));
 L(0x2600a0ec)=sp;
 /* INTBACK owns the SMPC until its BREAK has completed. */
 if(B(0x26000be0) || (B(0x20100063)&1) || sp<0x060f9000)return;
 if(!S->ready || (frame==S->last_frame && !exit))return;
 S->last_frame=frame;
 if(!exit && (L(0x2609ea20)||L(0x2609ea24))){S->stable=0;return;}
 pack(SNAP,0);h=hash(SNAP);
 if(h!=S->hash){S->hash=h;S->stable=0;if(!exit)return;}
 if(h==S->saved_hash){if(exit)intro_persist_command(13);return;}
 if(!exit && ++S->stable<120)return;
 ((u32 *)SNAP)[0]=0x494e5431;((u32 *)SNAP)[1]=1;
 ((u32 *)SNAP)[2]=BYTES;((u32 *)SNAP)[3]=h;
 S->status=(u32)access(1);
 if(!S->status){S->saved_hash=h;S->writes++;}
 /* Full/unformatted memory stays nonintrusive; retry after another change. */
 else S->saved_hash=h;
 S->stable=0;
 if(exit)intro_persist_command(13);
}
