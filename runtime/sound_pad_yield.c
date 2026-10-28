/* Experimental main-only yield BEFORE entering the masked CD section.
   Never issues SMPC commands or writes pad/game state. IRQ handlers retain
   ownership of the existing guarded acquisition window. */
#include "sound_stream_mailbox.h"
#ifdef SOUND_PAD_YIELD_HOST_TEST
extern u32 yield_test_sr(void),yield_test_vbr(void),yield_test_depth(void);
extern u32 yield_test_stream(void),yield_test_pad(void);
#define SR() yield_test_sr()
#define VBR() yield_test_vbr()
#define DEPTH() yield_test_depth()
#define STREAM() yield_test_stream()
#define PAD() yield_test_pad()
#else
static u32 read_sr(void) { u32 x;__asm__ volatile("stc sr,%0":"=r"(x));return x; }
static u32 read_vbr(void) { u32 x;__asm__ volatile("stc vbr,%0":"=r"(x));return x; }
#define SR() read_sr()
#define VBR() read_vbr()
#define DEPTH() (*(volatile u32 *)0x2021f010)
#define STREAM() sound_stream_state()
#define PAD() (*(volatile u8 *)0x06000be0)
#endif

int sound_pad_wait_for_issue(u32 budget) {
    u32 old_pending;
    if((SR()&0xf0) || VBR()!=0x06000000 || DEPTH())return 0;
    if(STREAM()!=SOUND_STREAM_REQUESTED)return 0;
    old_pending=PAD()!=0;
    while(budget--) {
        u32 pending=PAD()!=0;
        if(old_pending) {
            if(!pending)old_pending=0;
        } else if(pending)return 1;
    }
    return -1; /* Bounded failure to yield; caller still services the request. */
}
int sound_stream_pad_yield(void) { return sound_pad_wait_for_issue(500000); }
