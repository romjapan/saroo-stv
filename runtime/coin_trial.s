! Diagnostic only: count native input polls, never wall-clock time.
    .org 0x2200,0
cd_coin_tick:
    mov.l r1,@-r15
    mov.l r2,@-r15
    stc.l sr,@-r15
    mov.l coin_arm,r1
    mov.l @r1,r0
    tst r0,r0
    bt coin_idle
    mov.l coin_count,r1
    mov.l @r1,r2
    add #1,r2
    mov.l r2,@r1
    mov.w coin_begin,r0
    cmp/hs r0,r2
    bf coin_idle
    mov.w coin_end,r0
    cmp/hs r0,r2
    bt coin_idle
    mov.w coin_pressed,r0
    bra coin_publish
    nop
coin_idle:
    mov #-1,r0
coin_publish:
    mov.l coin_shadow,r1
    mov.w r0,@r1
    ldc.l @r15+,sr
    mov.l @r15+,r2
    mov.l @r15+,r1
    rts
    nop
    .align 2
coin_count: .long 0x2021f020
coin_arm: .long 0x2021f028
coin_shadow: .long 0x2021f002
coin_begin: .word 1200
coin_end: .word 1208
coin_pressed: .word 0xfeff
