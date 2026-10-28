/* ROM0305a4/03069c/0306dc: two-player record subset. */
typedef unsigned int u32;
typedef unsigned short u16;
#ifndef L
#define L(a) (*(volatile u32 *)(a))
#define W(a) (*(volatile u16 *)(a))
#endif
void cd_resident_player_input(void) {
 u32 i,c=L(0x0600286c),aux=L(0x06002874);
 for(i=0;i<2;i++) {
  u32 port=L(0x06002864+4*i),record=0x06000708+8*i;
  u16 old=W(record);
  u16 now=(u16)((port&7)|((port<<2)&0x3c0)|((c<<(i?5:6))&0x400)|((i?aux>>1:aux<<3)&0x38));
  W(record+2)=old;W(record)=now;
  W(record+4)=(u16)(~old&now);
  W(record+6)=(u16)(old&~now);
 }
 for(i=0;i<8;i++)W(0x06000718+2*i)=0;
}
