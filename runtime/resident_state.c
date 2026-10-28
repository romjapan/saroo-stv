/* Resident060014fe publication; no credit award and no fabricated start. */
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
#ifndef L
#define L(a) (*(volatile u32 *)(a))
#define W(a) (*(volatile u16 *)(a))
#define B(a) (*(volatile u8 *)(a))
#endif
void cd_resident_state_publish(void) {
 u32 mode=W(0x0600079a)&3,config=B(0x06000795),i;
 u32 control=(config&1)?config&5:config&7;
 B(0x06000750)=(u8)((mode<<3)|control);
 B(0x06000751)=(control&2)?0x12:0x11;
 for(i=0;i<=mode;i++){
  u32 slot=(config&4)?i:0,credit=B(0x20223d05+2*slot),remainder=B(0x20223d5d+2*slot);
  u32 record=0x06000740+4*i,needed=1,status;
  if((config&4)||i==0){
   B(record)=(u8)credit;B(record+1)=(u8)remainder;B(record+2)=B(0x06000790);
  }
  if(config&1)status=2;
  else if(!(credit|remainder))status=0;
  else{
   if((config&2) && !B(0x06000828+i))needed++;
   status=credit>=needed?2:1;
  }
  B(record+3)=(u8)status;
 }
}
static void unsupported_start(void){
 L(0x2021e000)=0x4641494c;L(0x2021e004)=0xc41;
 for(;;){}
}
#ifdef RESIDENT_START_BASELINE
static u32 start_read32(u32 base){
 return ((u32)B(base+1)<<24)|((u32)B(base+3)<<16)|((u32)B(base+5)<<8)|B(base+7);
}
static void start_increment32(u32 base){
 u32 v=start_read32(base);if(v!=0xffffffffu)v++;
 B(base+1)=(u8)(v>>24);B(base+3)=(u8)(v>>16);B(base+5)=(u8)(v>>8);B(base+7)=(u8)v;
}
#endif
u32 cd_resident_start_consume(int player){
 cd_resident_state_publish();
 /* Original signed -1 probes resident073f; never an unchecked unsigned index. */
 if(player < -1 || player > 3)unsupported_start();
 if(B((u32)(0x06000740+4*player+3))!=2)return 0;
#ifdef RESIDENT_START_BASELINE
 /* Original060016b0, limited to verified default shared-credit profile. */
 if(player<0 || player>1 || (W(0x0600079a)&3)!=1 || B(0x06000795)!=0 ||
    B(0x06000791)!=0 || !B(0x20223d05))unsupported_start();
 start_increment32(0x20223d44);
 start_increment32(0x20223d80+32*(u32)B(0x06000650)+4);
 W(0x06000814)=0;W(0x06000816)=0;
 B(0x20223d05)--;
 if(B(0x06000828+(u32)player))
  start_increment32(0x20223d80+32*(u32)B(0x06000650)+12);
 B(0x06000653)=1;
 return 1;
#else
 /* Statistics/decrement branch not yet reconstructed: fail explicitly. */
 unsupported_start();return 0;
#endif
}
u32 cd_resident_notification(void){
 u32 read=B(0x0600075e),write=B(0x0600075f),event;
 if(read==write)return 0;
 if(read>=16 || write>=16)unsupported_start();
 B(0x0600075e)=(u8)((read+1)&15);
 event=B(0x06000770+read);
 return (u32)(int)(signed char)event;
}
