! Experimental FRT gate (/8, /32 or /128; elapsed scaled to /8 units). No waits and no FRT register writes.
    .text
    .org 0x4b00,0
cd_pad_timed_poll:
    sts.l pr,@-r15
    stc.l sr,@-r15
    stc sr,r0
    or #0xf0,r0
    ldc r0,sr
    ! Diagnostic counters (0x2021f400): r5 = outcome, r6 = FRC elapsed.
    mov #-1,r6
    mov.l timed_pad_state,r1
    mov.b @r1,r0
    mov #8,r5
    tst r0,r0
    bf timed_poll_call
    mov.l timed_clock,r1
    mov.l @(12,r1),r0
    mov #1,r5
    tst r0,r0
    bt timed_poll_return
    mov.l timed_tvstat,r2
    mov.w @r2,r0
    mov #2,r5
    tst #8,r0
    bt timed_poll_return
    ! FRT clock select at the VBlank stamp. Real hardware (SAROO boot) runs
    ! TCR=2 (/128) while emulators show /8; scale elapsed to /8 units.
    mov.l @(4,r1),r0
    and #3,r0
    mov r0,r7
    mov #3,r5
    cmp/eq #3,r0
    bt timed_poll_return
    mov.l timed_frc,r2
    mov.b @r2,r0
    extu.b r0,r0
    shll8 r0
    add #1,r2
    mov.b @r2,r3
    extu.b r3,r3
    or r3,r0
    mov.l @r1,r3
    sub r3,r0
    extu.w r0,r0
    mov r7,r4
    tst r4,r4
    bt timed_scaled
timed_scale:
    shll2 r0
    dt r4
    bf timed_scale
timed_scaled:
    mov r0,r6
    add #3,r2
    mov.b @r2,r3
    mov #3,r4
    and r4,r3
    mov #4,r5
    cmp/eq r7,r3
    bf timed_poll_return
    add #-5,r2
    mov.b @r2,r3
    mov #1,r4
    and r4,r3
    mov #5,r5
    tst r3,r3
    bf timed_poll_return
    mov.w timed_min,r3
    mov #6,r5
    cmp/hs r3,r0
    bf timed_poll_return
    mov.w timed_max,r3
    mov #7,r5
    cmp/hs r3,r0
    bt timed_poll_return
    mov #0,r5
timed_poll_call:
    mov.l r5,@-r15
    mov.l r6,@-r15
    mov.l timed_real_poll,r0
    jsr @r0
    nop
    mov.l @r15+,r6
    mov.l @r15+,r5
timed_poll_return:
    ! A timing rejection defers acquisition, not the held-button state.
    ! The input caller just cleared raw ports; replay the cached packet.
    ! The callees clobber r4-r7: keep the diagnostic outcome/elapsed.
    mov.l r5,@-r15
    mov.l r6,@-r15
    mov.l timed_replay,r0
    jsr @r0
    nop
    mov.l @r15+,r6
    mov.l @r15+,r5
    mov.l timed_diag,r1
    shll2 r5
    mov r1,r2
    add r5,r2
    mov.l @r2,r0
    add #1,r0
    mov.l r0,@r2
    mov.w timed_none,r3
    cmp/eq r3,r6
    bt timed_diag_cache
    mov.l r6,@(0x38,r1)
    mov.l @(0x30,r1),r0
    tst r0,r0
    bt timed_diag_min
    cmp/hs r0,r6
    bt timed_diag_max
timed_diag_min:
    mov r6,r0
    add #1,r0
    mov.l r0,@(0x30,r1)
timed_diag_max:
    mov.l @(0x34,r1),r0
    cmp/hs r6,r0
    bt timed_diag_cache
    mov.l r6,@(0x34,r1)
timed_diag_cache:
    mov.l timed_cache,r2
    mov.l @(4,r2),r0
    tst #1,r0
    bt timed_diag_no_l
    mov.l @(0x24,r1),r3
    add #1,r3
    mov.l r3,@(0x24,r1)
timed_diag_no_l:
    tst #0x10,r0
    bt timed_diag_no_start
    mov.l @(0x28,r1),r3
    add #1,r3
    mov.l r3,@(0x28,r1)
timed_diag_no_start:
    mov.l @(0x2c,r1),r3
    add #1,r3
    mov.l r3,@(0x2c,r1)
    ldc.l @r15+,sr
    lds.l @r15+,pr
    rts
    nop
    .align 2
timed_min: .word 1200
timed_max: .word 12000
timed_none: .word 0xffff
    .align 2
timed_clock: .long 0x2021f060
timed_frc: .long 0xfffffe12
timed_tvstat: .long 0x25f80004
timed_pad_state: .long 0x06000be0
timed_real_poll: .long stv_smpc_pad_poll
timed_replay: .long stv_cd_pad_replay
timed_diag: .long 0x2021f400
timed_cache: .long 0x06000be8

cd_pad_main_worker:
    mov.l r0,@-r15
    mov.l r1,@-r15
    mov.l r2,@-r15
    mov.l r3,@-r15
    mov.l r4,@-r15
    mov.l r5,@-r15
    mov.l r6,@-r15
    mov.l r7,@-r15
    sts.l pr,@-r15
    stc.l sr,@-r15
    mov.l timed_worker_state,r1
    mov.b @r1,r0
    tst r0,r0
    bf timed_worker_done
    bsr cd_pad_timed_poll
    nop
timed_worker_done:
    ldc.l @r15+,sr
    lds.l @r15+,pr
    mov.l @r15+,r7
    mov.l @r15+,r6
    mov.l @r15+,r5
    mov.l @r15+,r4
    mov.l @r15+,r3
    mov.l @r15+,r2
    mov.l @r15+,r1
    mov.l @r15+,r0
    rts
    nop
    .align 2
timed_worker_state: .long 0x06000be0
