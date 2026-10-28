/* Opt-in original resident mapper/release queue, no credit-field writes. */
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
#ifndef L
#define L(a) (*(volatile u32 *)(a))
#define W(a) (*(volatile u16 *)(a))
#define B(a) (*(volatile u8 *)(a))
#endif
#ifdef RESIDENT_CREDIT_BASELINE
extern void cd_resident_credit_tick(void);
#endif
#ifdef RESIDENT_STATE_PUBLISH
extern void cd_resident_state_publish(void);
#endif
 #ifdef RESIDENT_PLAYER_INPUT
 extern void cd_resident_player_input(void);
 #endif
void cd_resident_input_edges(void) {
#ifdef RESIDENT_GAME_PORTS
 extern void cd_resident_game_ports(void);
 extern int cd_resident_game_ports_install(void);
 /* FPR guard must run after native handoff, not early SCU installation. */
 if(L(0x2021f028)){
  if(L(0x2021f050)!=0x504f5254){cd_resident_game_ports_install();L(0x2021f050)=0x504f5254;}
  cd_resident_game_ports();
 }
#endif
 u32 mode=L(0x06000798),config=B(0x06000795),m=mode&3;
 u32 players=m==0?1:m==1?3:m==2?7:15;
 u32 a=L(0x06002864),b=L(0x06002868),c=L(0x0600286c);
 #ifdef RESIDENT_PLAYER_INPUT
 /* Unsupported mapper profiles stop rather than silently publishing wrong records. */
 if(m!=1 || config!=0){L(0x2021e000)=0x4641494c;L(0x2021e004)=0xc61;for(;;){}}
 cd_resident_player_input();
 #endif
 u32 e=L(0x06002870),f=L(0x06002874),aux=L(0x06002878);
 u32 value=((aux<<8)&0x600)|((c<<7)&0x4000)|(c&12);
 u16 old=W(0x06000728),current,released;
 if(mode&4)value|=(c<<7)&0x2000;
 if(!(config&4)){
  value|=c&3;
  if(players&1)value|=c&16;
  if(players&2)value|=c&32;
 }else{
  if(players&1)value|=c&17;
  if(players&2)value|=c&34;
 }
 if(players&4){value|=(e<<3)&64;if(config&4)value|=(a<<8)&0x800;}
 if(players&8){value|=(f<<4)&128;if(config&4)value|=(b<<9)&0x1000;}
 current=(u16)value;released=(u16)(old&~current);
 W(0x0600072a)=old;W(0x06000728)=current;
 W(0x0600072c)=(u16)(~old&current);W(0x0600072e)=released;
 if(released&1)B(0x06000754)++;
 if(!(config&4)){
  if(released&2)B(0x06000755)++;
  B(0x06000756)=0;B(0x06000757)=0;
 }else{
  if(m && (released&2))B(0x06000755)++;
  if(!m)B(0x06000755)=0;
  if(m>=2){if(released&0x800)B(0x06000756)++;}else B(0x06000756)=0;
  if(m>=3){if(released&0x1000)B(0x06000757)++;}else B(0x06000757)=0;
 }
#ifdef RESIDENT_CREDIT_BASELINE
 cd_resident_credit_tick();
#endif
#ifdef RESIDENT_STATE_PUBLISH
 cd_resident_state_publish();
#endif
}
