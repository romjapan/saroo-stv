! Guarded 06001412-compatible callback. Only NV shadow is touched.
    .org 0x2600,0
cd_backup_access:
    mov.l r7,@-r15
    mov.l r8,@-r15
    stc.l sr,@-r15
    mov #3,r0
    cmp/hi r0,r4
    bt cd_backup_bad
    mov.l backup_shadow_base,r7
    cmp/hs r7,r5
    bt backup_shadow_domain
    mov.l backup_base,r7
    cmp/hs r7,r5
    bf cd_backup_bad
    mov r4,r0
    and #1,r0
    tst r0,r0
    bt backup_word_bound
    mov.l backup_long_end,r8
    bra backup_bound
    nop
backup_word_bound:
    mov.l backup_word_end,r8
backup_bound:
    cmp/hi r8,r5
    bt cd_backup_bad
    mov.l backup_delta,r7
    bra backup_alignment
    nop
backup_shadow_domain:
    mov r4,r0
    and #1,r0
    tst r0,r0
    bt backup_shadow_word
    mov.l backup_shadow_long_end,r8
    bra backup_shadow_bound
    nop
backup_shadow_word:
    mov.l backup_shadow_word_end,r8
backup_shadow_bound:
    cmp/hi r8,r5
    bt cd_backup_bad
    mov #0,r7
backup_alignment:
    mov r5,r0
    and #1,r0
    tst r0,r0
    bf cd_backup_bad
    add r7,r5
    ldc.l @r15+,sr
    mov r4,r8
    shll2 r4
    mov r8,r0
    cmp/eq #0,r0
    bt backup_read_word
    cmp/eq #1,r0
    bt backup_read_long
    cmp/eq #2,r0
    bt backup_write_word
backup_write_long:
    mov #3,r0
    add #7,r5
backup_write_loop:
    mov.b r6,@r5
    shlr8 r6
    add #-2,r5
    dt r0
    bf/s backup_write_loop
    mov.b r6,@r5
    bra backup_return
    nop
backup_write_word:
    clrt
    add #3,r5
    mov.b r6,@r5
    shlr8 r6
    add #-2,r5
    mov.b r6,@r5
    bra backup_return
    nop
backup_read_long:
    mov #3,r2
    add #1,r5
    mov.b @r5,r0
    extu.b r0,r0
backup_read_loop:
    shll8 r0
    add #2,r5
    mov.b @r5,r1
    extu.b r1,r1
    dt r2
    bf/s backup_read_loop
    or r1,r0
    bra backup_return
    nop
backup_read_word:
    clrt
    add #1,r5
    mov.b @r5,r0
    extu.b r0,r0
    shll8 r0
    add #2,r5
    mov.b @r5,r1
    extu.b r1,r1
    or r1,r0
backup_return:
    sub r7,r5
    mov.l @r15+,r8
    mov.l @r15+,r7
    rts
    nop
cd_backup_bad:
    mov.l backup_trace,r1
    mov.l backup_fail,r0
    mov.l r0,@r1
    mov.l backup_code,r0
    mov.l r0,@(4,r1)
backup_bad_spin:
    bra backup_bad_spin
    nop
    .align 2
backup_base: .long 0x20180000
backup_word_end: .long 0x2018fffc
backup_long_end: .long 0x2018fff8
backup_delta: .long 0x000a0000
backup_shadow_base: .long 0x20220000
backup_shadow_word_end: .long 0x2022fffc
backup_shadow_long_end: .long 0x2022fff8
backup_trace: .long 0x2021e000
backup_fail: .long 0x4641494c
backup_code: .long 0xc11
    .org 0x2800,0
cd_backup_mark:
    mov.l backup_dirty,r1
    mov #1,r0
    mov.b r0,@r1
    rts
    nop
    .align 2
backup_dirty: .long 0x06000653
