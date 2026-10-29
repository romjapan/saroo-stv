#ifndef LOAD_PROGRESS_H
#define LOAD_PROGRESS_H
#include "cd_io.h"
/* Boot-only ownership of VDP2 bitmap A. Units are caller defined (total <= 2Gi).
   end clears VRAM and touched registers before the game's video init. */
enum { LOAD_CD, LOAD_SAROO, LOAD_VERIFY, LOAD_COPY };
void load_progress_begin(u32 total);
void load_progress_stage(u32 stage);
void load_progress_advance(u32 work);
void load_progress_pulse(u32 polls);
void load_progress_end(void);
#endif
