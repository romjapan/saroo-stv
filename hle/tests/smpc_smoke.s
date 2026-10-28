    .section .text, "ax"
    .global _start
_start:
    mov.l   smoke_stack, r15
    mov     #0, r0
    mov.l   port_a_ptr, r1
    mov.l   r0, @r1
    mov.l   port_b_ptr, r1
    mov.l   r0, @r1
    mov.l   port_c_ptr, r1
    mov.l   r0, @r1
    mov.l   system_ptr, r1
    mov.b   r0, @r1

    mov.l   hardware_init_ptr, r0
    jsr     @r0
    nop
    mov.l   pad_init_ptr, r0
    jsr     @r0
    nop
    mov     #120, r8
smoke_poll_loop:
    mov.l   pad_poll_ptr, r0
    jsr     @r0
    nop
    mov.l   system_ptr, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    .ifdef EXPECT_PRESSED
    add     #6, r0
    bra     smoke_poll_compare
    nop
    .endif
    add     #1, r0
smoke_poll_compare:
    extu.b  r0, r0
    tst     r0, r0
    bt      smoke_check_result
    mov.l   delay_count, r9
smoke_delay:
    dt      r9
    bf      smoke_delay
    dt      r8
    bf      smoke_poll_loop
    bra     smoke_fail
    nop

smoke_check_result:
    mov.l   port_a_ptr, r1
    mov.l   @r1, r0
    .ifdef EXPECT_PRESSED
    mov     #0xAF, r1
    extu.b  r1, r1
    cmp/eq  r1, r0
    bf      smoke_fail_a
    bra     smoke_check_c
    nop
    .endif
    tst     r0, r0
    bf      smoke_fail
smoke_check_c:
    mov.l   port_c_ptr, r1
    mov.l   @r1, r0
    .ifdef EXPECT_PRESSED
    cmp/eq  #0x11, r0
    bf      smoke_fail_c
    bra     smoke_check_system
    nop
    .endif
    tst     r0, r0
    bf      smoke_fail_system
smoke_check_system:
    mov.l   system_ptr, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    .ifdef EXPECT_PRESSED
    add     #6, r0
    extu.b  r0, r0
    tst     r0, r0
    bf      smoke_fail_system
    bra     smoke_success
    nop
    .endif
    add     #1, r0
    extu.b  r0, r0
    tst     r0, r0
    bf      smoke_fail_system

smoke_success:
    mov.l   sound_vector_ptr, r1
    mov.l   sound_vector_value, r0
    mov.l   r0, @r1
    mov     #120, r8
smoke_sound_loop:
    mov.l   sound_poll_ptr, r0
    jsr     @r0
    nop
    mov.l   sound_state_ptr, r1
    mov.b   @r1, r0
    tst     r0, r0
    bf      smoke_sound_wait
    mov.l   sound_last_ptr, r1
    mov.l   @r1, r0
    mov.w   sound_vector_expected, r1
    cmp/eq  r1, r0
    bt      smoke_sound_done
smoke_sound_wait:
    mov.l   delay_count, r9
smoke_sound_delay:
    dt      r9
    bf      smoke_sound_delay
    dt      r8
    bf      smoke_sound_loop
    bra     smoke_fail
    nop
smoke_sound_done:
    mov.l   result_ptr, r1
    mov.l   success_value, r0
    mov.l   r0, @r1
    mov.l   comreg_ptr, r1
    mov     #0x17, r0
    mov.b   r0, @r1
smoke_pass:
    bra     smoke_pass
    nop

smoke_fail:
    mov.l   result_ptr, r1
    mov.l   failure_value, r0
    mov.l   r0, @r1
    mov.l   comreg_ptr, r1
    mov     #0x18, r0
    mov.b   r0, @r1
    .word   0xffff
    bra     smoke_fail
    nop

smoke_fail_a:
    mov.l   comreg_ptr, r1
    mov.b   r0, @r1
    .word   0xffff
    bra     smoke_fail_a
    nop

smoke_fail_c:
    mov.l   result_ptr, r1
    mov.l   failure_value, r0
    mov.l   r0, @r1
    mov.l   comreg_ptr, r1
    mov     #0x19, r0
    mov.b   r0, @r1
    .word   0xffff
    bra     smoke_fail_c
    nop

smoke_fail_system:
    mov.l   result_ptr, r1
    mov.l   failure_value, r0
    mov.l   r0, @r1
    mov.l   comreg_ptr, r1
    mov     #0x1A, r0
    mov.b   r0, @r1
    .word   0xffff
    bra     smoke_fail_system
    nop

    .align 2
smoke_stack:    .long 0x060FF000
port_a_ptr:     .long 0x06002864
port_b_ptr:     .long 0x06002868
port_c_ptr:     .long 0x0600286C
system_ptr:     .long 0x06000730
result_ptr:     .long 0x06000BF0
comreg_ptr:     .long 0x2010001F
success_value:  .long 0x50414431
failure_value:  .long 0xDEAD1200
pad_init_ptr:   .long 0x06009200
pad_poll_ptr:   .long 0x06009280
hardware_init_ptr: .long 0x06009400
sound_poll_ptr:  .long 0x06009600
sound_state_ptr: .long 0x06000BE2
sound_last_ptr:  .long 0x06000BE4
sound_vector_ptr:.long 0x25A00004
sound_vector_value:.long 0x00000120
delay_count:    .long 0x00010000
sound_vector_expected:.word 0x0120
    .align 2
