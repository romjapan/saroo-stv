#ifndef LOADING_SCREEN_H
#define LOADING_SCREEN_H
/* total: expected CD bytes before loading_end(); cart_cd adds 4 MiB when
   it copies MPR0 into a RAM cart. */
void loading_begin(unsigned int total);
void loading_end(void);
#endif
