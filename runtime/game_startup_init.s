    .text
    .align 2
    .global _game_video_init
_game_video_init:
    sts.l pr,@-r15
    stc.l gbr,@-r15
    stc.l sr,@-r15
    mov #15,r0
    shll2 r0
    shll2 r0
    ldc r0,sr
    mov.l original_startup,r0
    jsr @r0
    nop
    ldc.l @r15+,sr
    ldc.l @r15+,gbr
    lds.l @r15+,pr
    rts
    nop
    .align 2
original_startup: .long 0x06033384
