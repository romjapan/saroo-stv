#ifndef CART_CD_H
#define CART_CD_H
#include "cd_io.h"
#define CART_IRQ_CACHE_BYTES 65536u
int cart_cd_init(void);
typedef struct {u32 hits,misses,sector_reads;} CartCacheStats;
extern CartCacheStats cart_cache_stats;
int cart_cd_cache_reset(void);
/* Guest cart address, not a dereferenceable pointer. MPR range only. */
int cart_cd_read(u32 address, void *destination, u32 size);
int cart_cd_irq_cache_load(u32 address);
int cart_cd_irq_read(u32 address, void *destination, u32 size);
#ifdef CART_MPR0_RAM
/* state: 0 untried, 1 no 4 MiB cart (CD fallback), 2 resident, 3 CD error, 4 hash mismatch */
typedef struct {u32 state,id,hash,reads;} CartMpr0Stats;
extern CartMpr0Stats cart_mpr0_stats;
int cart_cd_mpr0_resident(void);
#endif
#ifdef CART_SAROO_ROM
/* state: 0 untried, 1 no SAROO, 2 MCU lacks saroo-stv commands, 3 load failed,
   4 AA24 not enabled, 5 resident, 6 verification failed after reloads */
typedef struct {u32 state,id,ctrl,err,reads,bad[3];} CartSarooStats;
extern CartSarooStats cart_saroo_stats;
int cart_cd_saroo_resident(void);
/* Safe on either CPU; -1 when not resident or out of the MPR range. */
int cart_cd_saroo_direct(u32 address,void *destination,u32 size);
/* Nonzero when [address,address+size) is readable straight from CS0. */
int cart_cd_saroo_mapped(u32 address,u32 size);
int cart_cd_saroo_recheck(u32 diag[3]);
void cart_cd_saroo_report(const u32 diag[3],u32 *v);
void cart_cd_saroo_matrix(void);
extern u32 cart_saroo_fail[2];
#endif
#endif
