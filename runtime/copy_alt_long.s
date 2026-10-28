    .text
    .align 2
    .global _cd_alt_long_hook
_cd_alt_long_hook:
    mov.l r0,@-r15
    mov.l alt_lower,r0
    cmp/hs r0,r5
    bf alt_ram
    mov.l alt_upper,r0
    cmp/hs r0,r5
    bf alt_cart
    mov.l alt_alias_lower,r0
    cmp/hs r0,r5
    bf alt_ram
    mov.l alt_alias_upper,r0
    cmp/hs r0,r5
    bt alt_ram
alt_cart:
    tst r6,r6
    bt alt_ram
    stc.l sr,@-r15
    sts.l mach,@-r15
    sts.l macl,@-r15
    sts.l pr,@-r15
    mov.l r3,@-r15
    mov.l r4,@-r15
    mov.l r5,@-r15
    mov.l r6,@-r15
    mov.l alt_helper,r0
    jsr @r0
    nop
    mov.l @r15+,r6
    mov.l @r15+,r7
    mov.l @r15+,r4
    mov.l @r15+,r3
    lds.l @r15+,pr
    lds.l @r15+,macl
    lds.l @r15+,mach
    ldc.l @r15+,sr
    shll2 r6
    add r6,r7
    mov r4,r5
    add r6,r5
    mov r5,r2
    add #-4,r2
    mov.l @r2,r1
    mov #0,r6
    tst r6,r6
    mov.l @r15+,r0
    rts
    nop
alt_ram:
    mov.l @r15+,r0
    mov r5,r7
    bra alt_check
    mov r4,r5
alt_loop:
    mov r5,r2
    add #4,r5
    mov.l @r7+,r1
    mov.l r1,@r2
    add #-1,r6
alt_check:
    tst r6,r6
    bf alt_loop
    rts
    nop
    .align 2
alt_lower: .long 0x02000000
alt_upper: .long 0x05000000
alt_alias_lower: .long 0x22000000
alt_alias_upper: .long 0x25000000
alt_helper: .long _copy_cart_longs
