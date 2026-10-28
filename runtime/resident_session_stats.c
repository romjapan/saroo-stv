/* ROM00003842: snapshots and verified command1/32 elapsed-time ledgers. */
typedef unsigned int u32;
typedef unsigned char u8;
#ifndef L
#define L(a) (*(volatile u32 *)(a))
#define B(a) (*(volatile u8 *)(a))
#endif
static u32 nv_read(u32 address){
 u32 n,value=0;
 for(n=1;n<8;n+=2)value=(value<<8)|B(address+n);
 return value;
}
static void nv_write(u32 address,u32 value){
 u32 n;
 for(n=7;n;n-=2){B(address+n)=(u8)value;value>>=8;if(n==1)break;}
}
/* BIOS0ECC: unsigned wrap, except negative old crossing to nonnegative ->-1. */
static u32 accumulated(u32 old,u32 delta){
 u32 sum=old+delta;
 return (old&0x80000000u) && !(sum&0x80000000u)?0xffffffffu:sum;
}
int cd_resident_session_stats(u32 command){
 if(command!=0 && command!=1 && command!=16 && command!=32){
  L(0x2021e000)=0x4641494c;L(0x2021e004)=0xcc1;
  L(0x2021e008)=command;
#ifdef HOST_TEST
  return 1;
#else
  for(;;){}
#endif
 }
 /* Slot640/644 read long from odd bytes+1,+3,+5,+7, not contiguous L. */
 if(command==1){
  u32 delta=nv_read(0x20220000)-L(0x06000840);
  u32 channel=0x20223dacu+((u32)B(0x06000650)<<6);
  nv_write(0x20223d54,accumulated(nv_read(0x20223d54),delta));
  nv_write(channel,accumulated(nv_read(channel),delta));
 }else if(command==32){
  u32 delta=nv_read(0x20220000)-L(0x06000830);
  u32 channel=0x20223d80u+((u32)B(0x06000650)<<6);
  u32 minimum=nv_read(channel+28);
  nv_write(channel+36,accumulated(nv_read(channel+36),delta));
  if(nv_read(channel+20)<delta)nv_write(channel+20,delta);
  if(!minimum || minimum>delta)nv_write(channel+28,delta);
 }else L(command==0?0x06000840:0x06000830)=nv_read(0x20220000);
 B(0x06000653)=1; /* Original tail calls slot648 dirty notifier. */
 return 0;
}
