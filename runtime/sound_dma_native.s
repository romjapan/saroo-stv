    .text
    .align 2
    .global _sound_dma_native
_sound_dma_native:
    /* Replay only the verified displaced native prologue. */
    mov.l r14,@-r15
    mov.l r13,@-r15
    sts.l pr,@-r15
    mov r4,r13
    add #-12,r15
    mov r13,r14
    mov.l .Lresume,r0
    jmp @r0
    nop
    .align 2
.Lresume:
    .long 0x060483cc
