    .section .text
    .align 2
    .global _cd_long_hook
_cd_long_hook:
    mov.l lower,r0
    cmp/hs r0,r5
    bf ram_copy
    mov.l upper,r0
    cmp/hs r0,r5
    bf cart_copy
    mov.l alias_lower,r0
    cmp/hs r0,r5
    bf ram_copy
    mov.l alias_upper,r0
    cmp/hs r0,r5
    bt ram_copy
cart_copy:
    tst r6,r6
    bt ram_copy
    sts.l pr,@-r15
    mov.l r4,@-r15
    mov.l r5,@-r15
    mov.l r6,@-r15
    mov.l helper,r0
    jsr @r0
    nop
    mov.l @r15+,r6
    mov.l @r15+,r7
    mov.l @r15+,r4
    lds.l @r15+,pr
    shll2 r6
    add r6,r7
    mov r4,r5
    add r6,r5
    mov r5,r2
    add #-4,r2
    mov.l @r2,r1
    mov #0,r6
    tst r6,r6
    rts
    nop
ram_copy:
    mov r5,r7
    bra check
    mov r4,r5
loop:
    mov r5,r2
    add #4,r5
    mov.l @r7+,r1
    mov.l r1,@r2
    add #-1,r6
check:
    tst r6,r6
    bf loop
    rts
    nop
    .align 2
lower: .long 0x02000000
upper: .long 0x05000000
alias_lower: .long 0x22000000
alias_upper: .long 0x25000000
helper: .long _copy_cart_longs

! Diagnostic harness: invoke the patched original game entry and record its
! volatile postconditions. PR and all callee-saved registers remain intact.
    .align 2
    .global _test_long_registers
_test_long_registers:
    sts.l pr,@-r15
    mov #0x11,r1
    mov #0x22,r2
    mov.l game_entry,r0
    jsr @r0
    nop
    mov.l result_ptr,r0
    mov.l r4,@r0
    add #4,r0
    mov.l r5,@r0
    add #4,r0
    mov.l r6,@r0
    add #4,r0
    mov.l r7,@r0
    add #4,r0
    mov.l r2,@r0
    add #4,r0
    mov.l r1,@r0
    lds.l @r15+,pr
    rts
    nop
    .align 2
game_entry: .long 0x0604afd4
result_ptr: .long 0x20202200
