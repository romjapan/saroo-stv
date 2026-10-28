#ifndef SOUND_STREAM_MAILBOX_H
#define SOUND_STREAM_MAILBOX_H
#include "cart_cd.h"
enum { SOUND_STREAM_IDLE=0,SOUND_STREAM_REQUESTED=1,SOUND_STREAM_BUSY=2,
       SOUND_STREAM_DONE=3,SOUND_STREAM_FAILED=4,SOUND_STREAM_BORROWED=5 };
/* Boot-only reset; never reset while either CPU owns a request. */
void sound_stream_reset(void);
int sound_stream_submit(u32 source,u32 bytes);
int sound_stream_collect(void *destination,u32 bytes);
int sound_stream_borrow(void **buffer,u32 bytes);
int sound_stream_release(void);
void sound_stream_timeout(void);
u32 sound_stream_state(void);
/* Caller must be master main-loop context with interrupts masked. This
   protocol does not install the main hook or mask/restore SR itself. */
int sound_stream_service(int (*read_block)(u32,void *,u32),u32 irq_depth);
#endif
