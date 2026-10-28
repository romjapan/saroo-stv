    .text
    .align 2
    .global _nv_channel_flags
_nv_channel_flags:
    sts.l pr,@-r15
    sett
    mov.l channel_leaf,r0
    jsr @r0
    nop
    movt r0
    lds.l @r15+,pr
    rts
    nop
    .align 2
channel_leaf: .long 0x002101e0
