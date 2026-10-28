#ifndef CD_IO_H
#define CD_IO_H
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef struct { u32 lba, size; } CdFile;
typedef struct { u32 code, lba, hirq, response; } CdError;
extern CdError cd_error;
extern u32 cd_pace_display_off;
int cd_init(void);
int cd_find_root(const char *iso_name, CdFile *file);
int cd_read_at(const CdFile *file, u32 offset, void *destination, u32 size);
/* Loading progress: bytes delivered by the CD block, optional per-batch callback. */
extern u32 cd_progress_bytes, cd_progress_total;
extern void (*cd_progress)(void);
#endif
