/* Experimental master/slave sound stream handoff. */
#include "sound_stream_mailbox.h"
#define GUARD 0x73544d42u
typedef struct {
    u32 state,source,bytes,result,generation,services,timeouts,hash;
    u32 before;
    u8 data[520];
    u32 after;
} StreamMailbox;
#ifdef SOUND_STREAM_HOST_TEST
static volatile StreamMailbox backing;
#define BOX (&backing)
void sound_stream_test_corrupt_tail(void) { BOX->after=0; }
#else
/* Shared uncached reservation2021e300..2021e530. Four-aligned data;
   retain surrounding bytes and source low bits for native DMA widths. */
#define BOX ((volatile StreamMailbox *)0x2021e300)
#endif
typedef char mailbox_size_check[(sizeof(StreamMailbox)==560)?1:-1];
static void barrier(void) { __asm__ volatile("":::"memory"); }
static u32 hash(void) {
    u32 i,h=0x811c9dc5;
    for(i=0;i<520;i++)h=(h^BOX->data[i])*0x01000193;
    return h;
}
void sound_stream_reset(void) {
    BOX->state=SOUND_STREAM_IDLE;BOX->source=0;BOX->bytes=0;
    BOX->result=0;BOX->generation=0;BOX->services=0;BOX->timeouts=0;
    BOX->hash=0;BOX->before=GUARD;BOX->after=GUARD;barrier();
}
u32 sound_stream_state(void) { return BOX->state; }
int sound_stream_submit(u32 source,u32 bytes) {
    u32 i;
    if(bytes!=512 || source<0x02400000 || source>0x03400000-512)
        return -1;
    if(BOX->state!=SOUND_STREAM_IDLE)return -2;
    BOX->source=source;BOX->bytes=bytes;BOX->result=0;BOX->generation++;
    for(i=0;i<520;i++)BOX->data[i]=0;
    BOX->before=GUARD;BOX->after=GUARD;barrier();
    BOX->state=SOUND_STREAM_REQUESTED;return 0;
}
int sound_stream_service(int (*read_block)(u32,void *,u32),u32 irq_depth) {
    int result;
    if(irq_depth || !read_block)return -1;
    if(BOX->state!=SOUND_STREAM_REQUESTED)return 0;
    BOX->state=SOUND_STREAM_BUSY;barrier();
    result=read_block(BOX->source&~3u,(void *)BOX->data,
                      (512+(BOX->source&3)+3)&~3u);
    /* A timed-out slave must not receive a late success or new request. */
    if(BOX->state!=SOUND_STREAM_BUSY)return -2;
    BOX->result=(u32)result;BOX->services++;
    if(result || BOX->before!=GUARD || BOX->after!=GUARD) {
        barrier();BOX->state=SOUND_STREAM_FAILED;return -3;
    }
    BOX->hash=hash();barrier();BOX->state=SOUND_STREAM_DONE;return 1;
}
int sound_stream_collect(void *destination,u32 bytes) {
    u32 i;
    if(!destination || bytes!=512)return -1;
    if(BOX->state==SOUND_STREAM_FAILED)return -2;
    if(BOX->state!=SOUND_STREAM_DONE)return 0;
    if(BOX->before!=GUARD || BOX->after!=GUARD || hash()!=BOX->hash) {
        BOX->state=SOUND_STREAM_FAILED;return -3;
    }
    for(i=0;i<512;i++)((volatile u8 *)destination)[i]=BOX->data[i+(BOX->source&3)];
    barrier();BOX->state=SOUND_STREAM_IDLE;return 1;
}
int sound_stream_borrow(void **buffer,u32 bytes) {
    u32 i,delta;
    if(!buffer || bytes!=512)return -1;
    if(BOX->state==SOUND_STREAM_FAILED)return -2;
    if(BOX->state!=SOUND_STREAM_DONE)return 0;
    if(BOX->before!=GUARD || BOX->after!=GUARD || hash()!=BOX->hash) {
        BOX->state=SOUND_STREAM_FAILED;return -3;
    }
    /* DONE gives this slave exclusive ownership. Normalize logical bytes to
       a four-aligned DMA source; never depend on odd native word accesses. */
    delta=BOX->source&3;
    if(delta) {
        for(i=0;i<512;i++)BOX->data[i]=BOX->data[i+delta];
        for(i=512;i<520;i++)BOX->data[i]=0;
        BOX->hash=hash();
    }
    *buffer=(void *)BOX->data;barrier();BOX->state=SOUND_STREAM_BORROWED;return 1;
}
int sound_stream_release(void) {
    if(BOX->state!=SOUND_STREAM_BORROWED)return -1;
    if(BOX->before!=GUARD || BOX->after!=GUARD || hash()!=BOX->hash) {
        BOX->state=SOUND_STREAM_FAILED;return -2;
    }
    barrier();BOX->state=SOUND_STREAM_IDLE;return 0;
}
void sound_stream_timeout(void) {
    if(BOX->state==SOUND_STREAM_REQUESTED || BOX->state==SOUND_STREAM_BUSY ||
       BOX->state==SOUND_STREAM_BORROWED) {
        BOX->timeouts++;barrier();BOX->state=SOUND_STREAM_FAILED;
    }
}
