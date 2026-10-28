#ifndef SAROO_ROM_H
#define SAROO_ROM_H
#include "cd_io.h"
/* Poll budgets (each poll is one A-bus CS2 read, roughly 1 us). */
#define SAROO_SHORT_POLLS 3000000u
#define SAROO_LOAD_POLLS  60000000u
/* Optional: called every 2^20 polls while waiting for the MCU. */
extern void (*saroo_poll_hook)(u32 polls);
u32 saroo_id(void);
int saroo_present(void);
/* 0 ok, -1 timeout (MCU lacks the saroo-stv commands). ctrl = ST_CTRL[15:8]. */
int saroo_romctl(int aa24, u16 *ctrl);
/* Read SD file into SAROO SDRAM (CS0 offset). size 0 = rest of file.
   Returns 0 ok, negative FatFs error, -1000 timeout. */
int saroo_stvload(const char *name, u32 offset, u32 size, u32 sdram, u32 *loaded);
/* Write size bytes from SAROO SDRAM (bank 0 offset) to an SD file.
   offset -1 creates/truncates. Returns 0 ok, negative error, -1000 timeout. */
int saroo_filewr(const char *name,int offset,u32 size,u32 sdram);
#endif
