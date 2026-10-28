/* Guarded shared-credit/non-bonus branch of resident01988 -> 01ad0/01bae. */
typedef unsigned int u32;
typedef unsigned char u8;
#ifndef L
#define L(a) (*(volatile u32 *)(a))
#define B(a) (*(volatile u8 *)(a))
#endif
extern const u32 cd_credit_limits[16];
static u32 read32(u32 a){return ((u32)B(a+1)<<24)|((u32)B(a+3)<<16)|((u32)B(a+5)<<8)|B(a+7);}
static void write32(u32 a,u32 v){B(a+7)=(u8)v;B(a+5)=(u8)(v>>8);B(a+3)=(u8)(v>>16);B(a+1)=(u8)(v>>24);}
static void add32(u32 a,u32 v){write32(a,read32(a)+v);}
static void ring(u32 read,u32 write,u32 base,u32 event){
 u32 r=B(read),w=B(write),next;
 if(r>=16 || w>=16){L(0x2021e000)=0x4641494c;L(0x2021e004)=0xc51;for(;;){}}
 next=(w+1)&15;
 if(next!=r){B(base+w)=(u8)event;B(write)=(u8)next;}
}
void cd_resident_credit_tick(void){
 u32 slot,processed=0,awards=0;
 if(!(B(0x06000754)|B(0x06000755)|B(0x06000756)|B(0x06000757)))return;
 /* No guessed support for free play, individual-credit or bonus configurations. */
 if(B(0x06000795)!=0 || B(0x06000791)!=0 || B(0x06000756) || B(0x06000757))goto bad;
 for(slot=0;slot<2;slot++){
  u32 pending=0x06000754+slot,den=B(0x06000790),units=B(0x06000792+slot);
  u32 limit=cd_credit_limits[(L(0x06000248)>>12)&15];
  u32 credit=B(0x20223d05),remainder=B(0x20223d5d),awarded=0;
  if(!B(pending))continue;
  if(!den || den>127 || !units || units>127 || !limit || limit>127 || credit>limit || remainder>=den)goto bad;
  B(pending)--;ring(0x0600075c,0x0600075d,0x06000760,slot);
  processed++;
  if(credit<limit){
   remainder+=units;
   while(remainder>=den && credit<limit){remainder-=den;credit++;awarded++;}
   if(credit==limit)remainder=0;
   B(0x20223d05)=(u8)credit;B(0x20223d5d)=(u8)remainder;
   ring(0x0600075e,0x0600075f,0x06000770,awarded?2:1);
  }
  /* Native physical-coin audits advance even when already at the credit cap. */
  add32(0x20223d2c,1);add32(0x20223d0c,1);
  B(0x0600081c)++;B(0x06000653)=1;awards+=awarded;
 }
 add32(0x20223d34,processed);add32(0x20223d3c,awards);
 return;
bad:
 L(0x2021e000)=0x4641494c;L(0x2021e004)=0xc51;
 for(;;){}
}
