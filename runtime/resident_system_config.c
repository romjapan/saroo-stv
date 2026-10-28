/* Opt-in initial publication derived from ROM0304f4..03054a, not full dispatcher. */
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
#ifndef L
#define L(a) (*(volatile u32 *)(a))
#define W(a) (*(volatile u16 *)(a))
#define B(a) (*(volatile u8 *)(a))
#endif
extern const u8 cd_system_policy[4];
int cd_resident_system_config_init(void){
 u16 config=W(0x0600079a);u32 index=(config>>10)&3;
 if(config!=0x08fd || B(0x06000795)!=0 || W(0x06000654)!=0 || W(0x0600073e)!=0){
  L(0x2021e000)=0x4641494c;L(0x2021e004)=0xc81;
#ifdef HOST_TEST
  return 1;
#else
  for(;;){}
#endif
 }
 W(0x06000654)=(u16)(W(0x0600073e)|(index?0x100:0)|((config<<7)&0x200)|cd_system_policy[index]);
 return 0;
}
