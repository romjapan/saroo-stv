    .text
    .align 2
    .global _cd_word_hook
_cd_word_hook:
    mov.l r0,@-r15
    mov.l word_lower,r0
    cmp/hs r0,r5
    bf word_ram
    mov.l word_upper,r0
    cmp/hs r0,r5
    bf word_cart
    mov.l word_alias_lower,r0
    cmp/hs r0,r5
    bf word_ram
    mov.l word_alias_upper,r0
    cmp/hs r0,r5
    bt word_ram
word_cart:
    tst r6,r6
    bt word_ram
    stc.l sr,@-r15
    sts.l mach,@-r15
    sts.l macl,@-r15
    sts.l pr,@-r15
    mov.l r3,@-r15
    mov.l r4,@-r15
    mov.l r5,@-r15
    mov.l r6,@-r15
    mov.l word_helper,r0
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
    shll r6
    add r6,r7
    mov r4,r5
    add r6,r5
    mov r5,r2
    add #-2,r2
    mov.w @r2,r1
    mov #0,r6
    tst r6,r6
    mov.l @r15+,r0
    rts
    nop
word_ram:
    mov.l @r15+,r0
    mov r5,r7
    bra word_check
    mov r4,r5
word_loop:
    mov r5,r2
    add #2,r5
    mov.w @r7+,r1
    mov.w r1,@r2
    add #-1,r6
word_check:
    tst r6,r6
    bf word_loop
    rts
    nop
    .align 2
word_lower: .long 0x02000000
word_upper: .long 0x05000000
word_alias_lower: .long 0x22000000
word_alias_upper: .long 0x25000000
word_helper: .long _copy_cart_words
