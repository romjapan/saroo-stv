! Replays displaced BSRF and BSR through local return trampolines.
    .org 0x2400,0
cd_coin_main:
    mov.l r0,@-r15
    mov.l r1,@-r15
    stc.l sr,@-r15
    mov.l main_count,r0
    mov.l @r0,r1
    add #1,r1
    mov.l r1,@r0
    ldc.l @r15+,sr
    mov.l @r15+,r1
    mov.l main_mid_ptr,r3
    lds r3,pr
    mov.l main_cache,r3
    mov.l main_first_call,r0
    jmp @r0
    mov.l @r15+,r0
    .align 2
main_count: .long 0x2021f02c
main_return: .long cd_coin_main_return
main_cache: .long 0x00026abe
main_call: .long 0x060105fc
main_mid_ptr: .long cd_coin_main_mid
main_first_call: .long 0x06036da8
cd_coin_main_mid:
    mov.l r0,@-r15
    mov.l mid_return,r0
    lds r0,pr
    mov.l mid_call,r0
    jmp @r0
    mov.l @r15+,r0
    .align 2
mid_return: .long cd_coin_main_return
mid_call: .long 0x060105fc
cd_coin_main_return:
    mov.l r0,@-r15
    mov.l original_return,r0
    lds r0,pr
    mov.l original_r2,r2
    mov.l main_resume,r0
    jmp @r0
    mov.l @r15+,r0
    .align 2
original_return: .long 0x060102ee
original_r2: .long 0x060831e0
main_resume: .long 0x060102f0
