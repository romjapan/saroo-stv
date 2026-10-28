#ifndef DIAGNOSTIC_SCREEN_H
#define DIAGNOSTIC_SCREEN_H
void diagnostic_screen(unsigned int code,unsigned int cdcode,unsigned int lba,unsigned int hirq);
void diagnostic_grid(const unsigned int *v,unsigned int n);
#endif
