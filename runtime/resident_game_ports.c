/* Raw active-low ST-V odd-byte port mirror; no game input/credit writes. */
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
#ifndef L
#define L(a) (*(volatile u32 *)(a))
#define W(a) (*(volatile u16 *)(a))
#define B(a) (*(volatile u8 *)(a))
#endif
void cd_resident_game_ports(void){
#ifdef INTRODON_INPUT
 u32 a=L(0x26000be8),c=L(0x26000bec);
 if(L(0x2600a0d0))c|=4;
 /* Native input routine also reads ST-V PDR2 bits1/2 (TEST/SERVICE).
    Never read Saturn's peripheral electrical pins as cabinet switches. */
 B(0x2600a0d8)=(u8)(6&~((c&12)>>1));
 L(0x0600286c)|=c&12;
 /* Acquisition owns the answer latch. Publication only replays that packet;
    it must not recompute edges or mix cached and uncached packet aliases. */
 /* Native quiz: any A/B/C confirms the current menu row. X also confirms;
    intro_answer_query supplies its direct row at the guarded menu call. */
 a=(a&~8u)|((a&8)?1u:0u);
 B(0x2021f041)=(u8)~a;
 B(0x2021f043)=0xff;
 B(0x2021f045)=(u8)(~c|0x80);
 return;
#endif
#ifdef SATURN_PAD_INPUT
 B(0x2021f041)=(u8)~L(0x06002864);
 B(0x2021f043)=(u8)~L(0x06002868);
 B(0x2021f045)=(u8)~L(0x0600286c);
#else
 u16 ab=W(0x2021f000),ce=W(0x2021f002);
 B(0x2021f041)=(u8)(ab>>8);
 B(0x2021f043)=(u8)ab;
 B(0x2021f045)=(u8)(ce>>8);
#endif
}
int cd_resident_game_ports_install(void){
 if(L(0x06037014)!=0x20400001 || W(0x06036ff0)!=0xd308){
  L(0x2021e000)=0x4641494c;L(0x2021e004)=0xc71;
#ifdef HOST_TEST
  return 1;
#else
  for(;;){}
#endif
 }
 cd_resident_game_ports();
 L(0x26037014)=0x2021f041;
 B(0xfffffe92)=(u8)(B(0xfffffe92)|0x10);
 return 0;
}
