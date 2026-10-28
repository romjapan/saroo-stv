! Baku Baku source-address relocation veneers for current SAROO PCBs.
!
! The PCB does not route Saturn AA24 to the FPGA.  The canonical cart image's
! bytes 16 MB+ are therefore exposed through CS1 at 0x04000000 instead of the
! original upper CS0 window at 0x03000000.  Runtime tracing found exactly two
! game copy routines reading that window.  These replacements translate only
! their source argument, leaving data and unrelated pointer-like values alone.

    .section .text, "ax"
    .align 2

    .global stv_long_copy_reloc
    .global stv_memmove_reloc
    .global stv_install_reloc_veneers

! r4=dst, r5=src, r6=count in 32-bit longs.
! Match the original routine's r5/r7/r2 loop behavior after translating src.
stv_long_copy_reloc:
    mov.l   cart_upper_low, r0
    cmp/hs  r0, r5
    bf      long_src_ready
    mov.l   cart_upper_high, r0
    cmp/hs  r0, r5
    bt      long_src_ready
    mov.l   cart_reloc_delta, r0
    add     r0, r5
long_src_ready:
    mov     r5, r7
    bra     long_copy_check
    mov     r4, r5
long_copy_loop:
    mov     r5, r2
    add     #4, r5
    mov.l   @r7+, r1
    mov.l   r1, @r2
    add     #-1, r6
long_copy_check:
    tst     r6, r6
    bf      long_copy_loop
    rts
    nop

    .align 2
cart_upper_low:    .long 0x03000000
cart_upper_high:   .long 0x03400000
cart_reloc_delta:  .long 0x01000000

! r4=dst, r5=src, r6=len in bytes; return r0=original dst.
! Overlap-safe in both directions, matching the clean-HLE contract.
    .align 2
stv_memmove_reloc:
    mov.l   mem_upper_low, r0
    cmp/hs  r0, r5
    bf      mem_src_ready
    mov.l   mem_upper_high, r0
    cmp/hs  r0, r5
    bt      mem_src_ready
    mov.l   mem_reloc_delta, r0
    add     r0, r5
mem_src_ready:
    mov     r4, r0
    cmp/eq  r5, r4
    bt      mem_done
    tst     r6, r6
    bt      mem_done
    cmp/hs  r5, r4
    bt      mem_backward

    mov     r4, r2
    mov     r5, r3
mem_forward_loop:
    mov.b   @r3+, r1
    mov.b   r1, @r2
    add     #1, r2
    dt      r6
    bf      mem_forward_loop
    bra     mem_done
    nop

mem_backward:
    mov     r4, r2
    add     r6, r2
    mov     r5, r3
    add     r6, r3
mem_backward_loop:
    add     #-1, r3
    mov.b   @r3, r1
    add     #-1, r2
    mov.b   r1, @r2
    dt      r6
    bf      mem_backward_loop
mem_done:
    rts
    nop

    .align 2
mem_upper_low:     .long 0x03000000
mem_upper_high:    .long 0x03400000
mem_reloc_delta:   .long 0x01000000

! Install absolute jump stubs into the two traced HWRAM routines.  Call this
! after copying the FPR body to HWRAM and before executing any game code.
! Stub encoding at each target:
!   mov.l @(1,pc),r0 ; jmp @r0 ; nop ; nop ; .long native_target
    .align 2
stv_install_reloc_veneers:
    mov.l   patch_long_addr, r1
    mov.l   patch_opcodes_0, r0
    mov.l   r0, @r1
    mov.l   patch_opcodes_1, r0
    mov.l   r0, @(4, r1)
    mov.l   patch_long_target, r0
    mov.l   r0, @(8, r1)

    mov.l   patch_mem_addr, r1
    mov.l   patch_opcodes_0, r0
    mov.l   r0, @r1
    mov.l   patch_opcodes_1, r0
    mov.l   r0, @(4, r1)
    mov.l   patch_mem_target, r0
    mov.l   r0, @(8, r1)
    rts
    nop

    .align 2
patch_long_addr:   .long 0x0604AFD4
patch_mem_addr:    .long 0x06053C98
patch_opcodes_0:   .long 0xD001402B
patch_opcodes_1:   .long 0x00090009
patch_long_target: .long stv_long_copy_reloc
patch_mem_target:  .long stv_memmove_reloc

! ---------------------------------------------------------------------------
! Clean-HLE leaf services.  Keep each entry at a fixed address: redirect data
! and the boot trampoline may refer to these symbols before the full runtime
! module is linked.
! ---------------------------------------------------------------------------

    .org 0x100, 0
    .global stv_signed_accumulate
! BIOS 0x0ECC: r0=r4+r5. If a negative r4 crosses to non-negative, return -1.
stv_signed_accumulate:
    mov     r4, r0
    cmp/pz  r4
    bt      signed_add_normal
    add     r5, r0
    cmp/pz  r0
    bf      signed_done
    mov     #-1, r0
signed_done:
    rts
    nop
signed_add_normal:
    rts
    add     r5, r0

    .org 0x120, 0
    .global stv_packed_status_test
! BIOS 0x3E4E: return 1 if any nibble of [0x06000658].word is below 8.
stv_packed_status_test:
    mov.l   status_word_ptr, r1
    mov.w   @r1, r2
    extu.w  r2, r2
    mov     #4, r3
status_nibble_loop:
    mov     r2, r0
    and     #0x0F, r0
    mov     #8, r1
    cmp/hs  r1, r0
    bf      status_found
    shlr2   r2
    shlr2   r2
    dt      r3
    bf      status_nibble_loop
    rts
    mov     #0, r0
status_found:
    rts
    mov     #1, r0
    .align 2
status_word_ptr: .long 0x06000658

    .org 0x160, 0
    .global stv_workspace_byte_set
! BIOS 0x4596: mirror r5.byte to HWRAM and the ST-V system window.
stv_workspace_byte_set:
    mov.l   workspace_h_ptr, r1
    add     r4, r1
    mov.b   r5, @r1
    mov     r4, r0
    shll    r0
    mov.l   workspace_s_ptr, r2
    add     r0, r2
    mov.b   r5, @r2
    rts
    nop
    .align 2
workspace_h_ptr: .long 0x0600065A
workspace_s_ptr: .long 0x20100075

    .org 0x1A0, 0
    .global stv_cart_layout_nibble
! BIOS 0x4680: select a packed layout nibble using channel 1..3, else nibble 0.
stv_cart_layout_nibble:
    mov.l   layout_channel_ptr, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    mov.l   layout_word_ptr, r1
    mov.w   @r1, r2
    extu.w  r2, r2
    cmp/eq  #1, r0
    bt      layout_shift_4
    cmp/eq  #2, r0
    bt      layout_shift_8
    cmp/eq  #3, r0
    bt      layout_shift_12
    bra     layout_mask
    nop
layout_shift_12:
    shlr2   r2
    shlr2   r2
layout_shift_8:
    shlr2   r2
    shlr2   r2
layout_shift_4:
    shlr2   r2
    shlr2   r2
layout_mask:
    mov     r2, r0
    and     #0x0F, r0
    rts
    nop
    .align 2
layout_channel_ptr: .long 0x06000650
layout_word_ptr:    .long 0x0600064C

    .org 0x1E0, 0
    .global stv_channel_address
! BIOS 0x372C: sign-extended low-word(channel * 0x0F00) + 0x20180100.
stv_channel_address:
    mov.l   channel_index_ptr, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    mov.w   channel_stride, r3
    mulu.w  r3, r0
    sts     macl, r0
    exts.w  r0, r0
    mov.l   channel_base, r2
    add     r2, r0
    rts
    nop
    .align 1
channel_stride:    .word 0x0F00
    .align 2
channel_index_ptr: .long 0x06000650
channel_base:      .long 0x20180100

    .org 0x220, 0
    .global stv_memset
! BIOS 0x2CAC: r4=dst, r5=byte, r6=len; return the original destination.
stv_memset:
    mov     r4, r0
    tst     r6, r6
    bt      memset_done
    mov     r4, r2
memset_loop:
    mov.b   r5, @r2
    add     #1, r2
    dt      r6
    bf      memset_loop
memset_done:
    rts
    nop

    .org 0x260, 0
    .global stv_vblank_clock_update
! BIOS 0x0EFC steady-state path: add the NTSC fixed-point increment to
! [0x06000758].  The signed-overflow callback branch is reserved below; the
! steady-state path is the one exercised throughout the 3600-frame oracle.
stv_vblank_clock_update:
    mov.l   vblank_acc_ptr, r1
    mov.l   @r1, r2
    mov     r2, r4
    mov.l   vblank_increment, r3
    add     r3, r2
    mov.l   r2, @r1
    mov     r1, r7
    mov     r3, r0
    cmp/pz  r4
    bf      vblank_done
    cmp/pz  r2
    bt      vblank_done

    sts.l   pr, @-r15
    mov.l   r8, @-r15
    mov.l   vblank_strided_base, r4
    bsr     stv_read_strided_long
    nop
    mov     r0, r8
    mov     r0, r6
    add     #3, r6
    cmp/pz  r8
    bt      vblank_counter_ready
    cmp/pz  r6
    bf      vblank_counter_ready
    mov     #-1, r6
vblank_counter_ready:
    mov     r6, r5
    mov.l   vblank_strided_base, r4
    bsr     stv_write_strided_long
    nop
    mov     r8, r4
    mov.l   @r15+, r8
    lds.l   @r15+, pr
    mov.l   vblank_acc_ptr, r7
    mov.l   vblank_callback_ptr, r1
    mov.l   vblank_strided_byte, r5
    mov     r6, r0
    shlr8   r0
    shlr8   r0
    shlr8   r0
    mov     r0, r6
    mov     #0, r0
    mov     #0, r2
vblank_done:
    rts
    nop
    .align 2
vblank_acc_ptr:   .long 0x06000758
vblank_increment: .long 0x55929FAD
vblank_strided_base: .long 0x20180000
vblank_strided_byte: .long 0x20180001
vblank_callback_ptr: .long 0x06000544

! ---------------------------------------------------------------------------
! BIOS 0x3842 channel table dispatch.  The four selectors used by Baku Baku
! update strided 32-bit values and tail-jump through [0x06000648].
! ---------------------------------------------------------------------------
    .org 0x300, 0
    .global stv_read_strided_long
stv_read_strided_long:
    mov     r4, r3
    add     #1, r3
    mov.b   @r3, r0
    extu.b  r0, r0
    shll8   r0
    shll8   r0
    shll8   r0
    add     #2, r3
    mov.b   @r3, r1
    extu.b  r1, r1
    shll8   r1
    shll8   r1
    or      r1, r0
    add     #2, r3
    mov.b   @r3, r1
    extu.b  r1, r1
    shll8   r1
    or      r1, r0
    add     #2, r3
    mov.b   @r3, r1
    extu.b  r1, r1
    or      r1, r0
    rts
    nop

stv_write_strided_long:
    mov     r5, r0
    mov     r4, r3
    add     #7, r3
    mov.b   r0, @r3
    shlr8   r0
    add     #-2, r3
    mov.b   r0, @r3
    shlr8   r0
    add     #-2, r3
    mov.b   r0, @r3
    shlr8   r0
    add     #-2, r3
    mov.b   r0, @r3
    rts
    nop

    .org 0x400, 0
    .global stv_channel_table_dispatch
stv_channel_table_dispatch:
    mov     r4, r0
    tst     r0, r0
    bt      channel_simple_840
    cmp/eq  #0x10, r0
    bt      channel_simple_830
    cmp/eq  #1, r0
    bt      channel_delta
    cmp/eq  #0x20, r0
    bt      channel_range
    rts
    nop

channel_simple_840:
    mov.l   channel_current_ptr, r4
    mov.l   channel_output_840, r5
    bra     channel_simple_common
    nop
channel_simple_830:
    mov.l   channel_current_ptr, r4
    mov.l   channel_output_830, r5
channel_simple_common:
    sts.l   pr, @-r15
    mov     r5, r3
    mov.l   r3, @-r15
    bsr     stv_read_strided_long
    nop
    mov.l   @r15+, r1
    lds.l   @r15+, pr
    mov.l   r0, @r1
    mov.l   channel_tail_ptr, r2
    mov.l   @r2, r2
    mov     r2, r6
    mov     #0x37, r3
    shll8   r3
    add     #0x44, r3
    mov     #1, r4
    mov.l   channel_tail_data, r5
    mov     #0, r6
    jmp     @r2
    nop

channel_delta:
    sts.l   pr, @-r15
    mov.l   channel_current_ptr, r4
    bsr     stv_read_strided_long
    nop
    mov     r0, r7
    mov.l   channel_baseline_840, r1
    mov.l   @r1, r1
    sub     r1, r7
    mov.l   channel_delta_base_a, r4
    bsr     stv_read_strided_long
    nop
    mov     r0, r6
    add     r7, r0
    cmp/pz  r6
    bt      delta_a_ready
    cmp/pz  r0
    bf      delta_a_ready
    mov     #-1, r0
delta_a_ready:
    mov     r0, r6
    mov     r6, r5
    mov.l   channel_delta_base_a, r4
    bsr     stv_write_strided_long
    nop
    mov.l   channel_delta_base_b, r4
    bsr     stv_read_strided_long
    nop
    mov     r0, r6
    add     r7, r0
    cmp/pz  r6
    bt      delta_b_ready
    cmp/pz  r0
    bf      delta_b_ready
    mov     #-1, r0
delta_b_ready:
    mov     r0, r6
    mov     r6, r5
    mov.l   channel_delta_base_b, r4
    bsr     stv_write_strided_long
    nop
    lds.l   @r15+, pr
    mov.l   channel_tail_ptr, r2
    mov.l   @r2, r2
    mov     r4, r0
    add     #7, r0
    mov.b   @r0, r1
    mov.l   channel_tail_h, r3
    mov.l   @r3, r3
    mov     #3, r4
    mov.l   channel_delta_base_b, r5
    add     #1, r5
    mov     r6, r0
    shlr8   r0
    shlr8   r0
    shlr8   r0
    mov     r0, r6
    mov     #0, r0
    jmp     @r2
    nop

channel_range:
    sts.l   pr, @-r15
    mov.l   r8, @-r15
    mov.l   channel_current_ptr, r4
    bsr     stv_read_strided_long
    nop
    mov     r0, r8
    mov     r0, r7
    mov.l   channel_baseline_830, r1
    mov.l   @r1, r1
    sub     r1, r7
    mov.l   channel_range_accum, r4
    bsr     stv_read_strided_long
    nop
    mov     r0, r6
    add     r7, r0
    cmp/pz  r6
    bt      range_accum_ready
    cmp/pz  r0
    bf      range_accum_ready
    mov     #-1, r0
range_accum_ready:
    mov     r0, r6
    mov     r6, r5
    mov.l   channel_range_accum, r4
    bsr     stv_write_strided_long
    nop
    mov.l   channel_range_lower, r4
    bsr     stv_read_strided_long
    nop
    cmp/hs  r8, r0
    bt      range_upper_check
    mov     r8, r5
    mov.l   channel_range_lower, r4
    bsr     stv_write_strided_long
    nop
range_upper_check:
    mov.l   channel_range_upper, r4
    bsr     stv_read_strided_long
    nop
    tst     r0, r0
    bt      range_write_upper
    cmp/hi  r8, r0
    bf      range_tail
range_write_upper:
    mov     r8, r5
    mov.l   channel_range_upper, r4
    bsr     stv_write_strided_long
    nop
range_tail:
    mov     r8, r6
    mov.l   @r15+, r8
    lds.l   @r15+, pr
    mov.l   channel_tail_ptr, r2
    mov.l   @r2, r2
    mov     #0, r0
    mov.l   channel_tail_h, r3
    mov.l   @r3, r3
    mov     #3, r4
    mov.l   channel_range_upper, r5
    add     #1, r5
    shlr8   r6
    shlr8   r6
    shlr8   r6
    jmp     @r2
    nop

    .align 2
channel_current_ptr:   .long 0x20180000
channel_output_840:    .long 0x06000840
channel_output_830:    .long 0x06000830
channel_tail_ptr:      .long 0x06000648
channel_tail_data:     .long 0x20180007
channel_baseline_840:  .long 0x06000840
channel_baseline_830:  .long 0x06000830
channel_delta_base_a:  .long 0x20183D54
channel_delta_base_b:  .long 0x20183DAC
channel_tail_h:         .long 0x06001412
channel_range_accum:    .long 0x20183DA4
channel_range_lower:    .long 0x20183D94
channel_range_upper:    .long 0x20183D9C

! Machine-readable redirect metadata for the future clean resident dispatcher.
! Each record is {original ST-V BIOS entry, native CS1 entry}; zero terminates.
    .org 0x700, 0
    .global stv_service_redirect_table
    .global stv_service_redirect_table_end
stv_service_redirect_table:
    .long 0x00000EFC, stv_vblank_clock_update
    .long 0x00000ECC, stv_signed_accumulate
    .long 0x00002C64, stv_memmove_reloc
    .long 0x00002CAC, stv_memset
    .long 0x0000372C, stv_channel_address
    .long 0x00003E4E, stv_packed_status_test
    .long 0x00004596, stv_workspace_byte_set
    .long 0x00004680, stv_cart_layout_nibble
    .long 0x00003842, stv_channel_table_dispatch
    .long 0x00004114, stv_bootstrap_handoff
    .long 0x0000426C, stv_handler_table_update
    .long 0x000034C4, stv_video_shutdown_fast
stv_service_redirect_table_end:
    .long 0x00000000, 0x00000000

! ---------------------------------------------------------------------------
! Clean cold-boot resident foundation.  This replaces the BIOS-copied HWRAM
! resident with generated state: zeroed workspace, native vector handlers,
! and the minimum Baku Baku callback seam.  No Sega BIOS bytes are embedded.
! ---------------------------------------------------------------------------
    .org 0x800, 0
    .global stv_resident_init
stv_resident_init:
    ! Clear 0x06000000..0x0600EFFF, leaving the SEGA page/game image intact.
    mov     #0, r0
    mov.l   resident_base, r1
    mov.l   resident_clear_longs, r2
resident_clear_loop:
    mov.l   r0, @r1
    add     #4, r1
    dt      r2
    bf      resident_clear_loop

    ! Default every vector to a harmless RTE, then make the first twelve
    ! reset/exception vectors trap visibly instead of returning corrupt state.
    mov.l   resident_base, r1
    mov.l   resident_irq_return_ptr, r0
    mov.l   resident_vector_count, r2
resident_vector_loop:
    mov.l   r0, @r1
    add     #4, r1
    dt      r2
    bf      resident_vector_loop

    mov.l   resident_base, r1
    mov.l   resident_exception_ptr, r0
    mov     #12, r2
resident_exception_loop:
    mov.l   r0, @r1
    add     #4, r1
    dt      r2
    bf      resident_exception_loop

    ! SCU VBLANK-IN is vector 0x40.  The wrapper preserves caller registers,
    ! invokes the game callback, then RTEs through the SH-2 interrupt frame.
    mov.l   resident_vblank_vector, r1
    mov.l   resident_vblank_ptr, r0
    mov.l   r0, @r1
    add     #4, r1
    add     #6, r0
    mov.l   r0, @r1
    add     #0x28, r1
    add     #6, r0
    mov.l   r0, @r1
    add     #8, r1
    add     #6, r0
    mov.l   r0, @r1

    ! Native service/callback seam used by the verified game vblank handler.
    mov.l   resident_service_610, r1
    mov.l   resident_clock_ptr, r0
    mov.l   r0, @r1
    mov.l   resident_service_63c, r1
    mov.l   resident_channel_address_ptr, r0
    mov.l   r0, @r1
    mov.l   resident_service_660, r1
    mov.l   resident_copy_20_ptr, r0
    mov.l   r0, @r1
    mov.l   resident_callback_640, r1
    mov.l   resident_noop_ptr, r0
    mov.l   r0, @r1
    mov.l   resident_callback_644, r1
    mov.l   r0, @r1
    mov.l   resident_callback_648, r1
    mov.l   r0, @r1

    ! Baku calls the 0x426C transition through this slot while pending != 0.
    mov.l   resident_transition_slot, r1
    mov.l   resident_transition_ptr, r0
    mov.l   r0, @r1
    mov.l   resident_transition_pending, r1
    mov     #1, r0
    mov.l   r0, @r1


    mov.l   resident_handler_a00, r1
    mov.l   resident_game_vblank, r0
    mov.l   r0, @r1
    mov.l   resident_handler_a04, r1
    mov.l   resident_game_aux, r0
    mov.l   r0, @r1
    mov.l   resident_handler_a08, r1
    mov.l   resident_noop_ptr, r0
    mov.l   r0, @r1
    mov.l   r0, @(4, r1)
    mov.l   r0, @(8, r1)
    sts.l   pr, @-r15
    mov.l   resident_veneer_installer_ptr, r0
    jsr     @r0
    nop
    lds.l   @r15+, pr
    rts
    nop

    .align 2
resident_base:            .long 0x06000000
resident_clear_longs:     .long 0x00003C00
resident_vector_count:    .long 0x00000100
resident_vblank_vector:   .long 0x06000100
resident_service_610:     .long 0x06000610
resident_service_63c:     .long 0x0600063C
resident_service_660:     .long 0x06000660
resident_callback_640:    .long 0x06000640
resident_callback_644:    .long 0x06000644
resident_callback_648:    .long 0x06000648
resident_transition_slot: .long 0x06000320
resident_transition_pending: .long 0x06000324
resident_handler_a00:     .long 0x06000A00
resident_handler_a04:     .long 0x06000A04
resident_handler_a08:     .long 0x06000A08
resident_exception_ptr:   .long stv_resident_exception
resident_irq_return_ptr:  .long stv_resident_irq_return
resident_vblank_ptr:      .long stv_resident_vblank
resident_clock_ptr:       .long stv_vblank_clock_update
resident_channel_address_ptr: .long stv_channel_address
resident_copy_20_ptr:     .long stv_resident_copy_20
resident_noop_ptr:        .long stv_resident_noop
    .ifdef SHIENRYU_PROFILE
    ! At the measured 0x06004010 handoff these table entries still point at
    ! the BIOS default handler.  Shienryu installs 0x06004632/0x06004744
    ! later through the 0x06000300 handler API, after its video/state tables
    ! are ready.  Calling either one early corrupts TVMD and loses VBLANK-IN.
resident_game_vblank:     .long stv_resident_noop
resident_game_aux:        .long stv_resident_noop
    .else
resident_game_vblank:     .long 0x06035278
resident_game_aux:        .long 0x06035C48
    .endif
resident_transition_ptr:  .long stv_handler_table_update
resident_veneer_installer_ptr: .long stv_install_resident_veneers

    .org 0x900, 0
    .global stv_resident_exception
stv_resident_exception:
    ! Preserve the complete observable exception context before using any
    ! scratch register.  On SH-2 the hardware exception frame at the original
    ! R15 is PC followed by SR.  The resulting 22-long raw record is:
    ! VBR, GBR, MACL, MACH, PR, R14..R0, PC, SR.
    mov.l   r0, @-r15
    mov.l   r1, @-r15
    mov.l   r2, @-r15
    mov.l   r3, @-r15
    mov.l   r4, @-r15
    mov.l   r5, @-r15
    mov.l   r6, @-r15
    mov.l   r7, @-r15
    mov.l   r8, @-r15
    mov.l   r9, @-r15
    mov.l   r10, @-r15
    mov.l   r11, @-r15
    mov.l   r12, @-r15
    mov.l   r13, @-r15
    mov.l   r14, @-r15
    sts.l   pr, @-r15
    sts.l   mach, @-r15
    sts.l   macl, @-r15
    stc.l   gbr, @-r15
    stc.l   vbr, @-r15

    mov.l   resident_exception_diag, r0
    mov.l   resident_crash_ptr, r1
    mov.l   r0, @r1
    add     #4, r1
    mov     #22, r0
    mov.l   r0, @r1
    add     #4, r1
    mov     r15, r0
    mov     #22, r2
resident_exception_copy:
    mov.l   @r0+, r3
    mov.l   r3, @r1
    add     #4, r1
    dt      r2
    bf      resident_exception_copy

    ! Keep the original one-word diagnostic for existing probes.
    mov.l   resident_exception_diag, r0
    mov.l   resident_diag_ptr, r1
    mov.l   r0, @r1
resident_exception_halt:
    bra     resident_exception_halt
    nop

    .align 2
    .global stv_resident_irq_return
stv_resident_irq_return:
    rte
    nop

    .global stv_resident_noop
stv_resident_noop:
    rts
    nop

    .global stv_resident_vblank
stv_resident_vblank:
    mov.l   r0, @-r15
    bra     resident_scu_irq_dispatch
    mov     #0x40, r0

    .global stv_resident_vblank_out
stv_resident_vblank_out:
    mov.l   r0, @-r15
    bra     resident_scu_irq_dispatch
    mov     #0x41, r0

    .global stv_resident_dma0_irq
stv_resident_dma0_irq:
    mov.l   r0, @-r15
    bra     resident_scu_irq_dispatch
    mov     #0x4B, r0

    .global stv_resident_vdp1_end_irq
stv_resident_vdp1_end_irq:
    mov.l   r0, @-r15
    bra     resident_scu_irq_dispatch
    mov     #0x4D, r0

resident_scu_irq_dispatch:
    sts.l   pr, @-r15
    mov.l   r1, @-r15
    mov.l   r2, @-r15
    mov.l   r3, @-r15
    mov.l   r4, @-r15
    mov.l   r5, @-r15
    mov.l   r6, @-r15
    mov.l   r7, @-r15
    mov     r0, r7
    cmp/eq  #0x40, r0
    bf      resident_scu_irq_lookup
    mov.l   r7, @-r15
    mov.l   resident_input_poll_ptr, r0
    jsr     @r0
    nop
    mov.l   @r15+, r7
resident_scu_irq_lookup:
    ! Match the BIOS common dispatcher by masking the active SCU source for
    ! the duration of its callback.  Vectors 0x40..0x4F map directly to IMS
    ! bits 0..15.  Without this guard VDP1 END can recursively retrigger while
    ! its handler submits the next command list.
    mov     #1, r4
    mov     r7, r6
    add     #-0x40, r6
    tst     r6, r6
    bt      resident_scu_mask_ready
resident_scu_mask_loop:
    shll    r4
    dt      r6
    bf      resident_scu_mask_loop
resident_scu_mask_ready:
    mov.l   resident_mask_shadow_irq, r1
    mov.l   @r1, r2
    mov.l   r2, @-r15
    or      r4, r2
    mov.l   r2, @r1
    mov.l   resident_scu_ims_irq, r3
    mov.l   r2, @r3

    mov.l   resident_handler_table_irq, r0
    shll2   r7
    mov.l   @(r0, r7), r0
    tst     r0, r0
    bt      resident_scu_irq_restore
    jsr     @r0
    nop
resident_scu_irq_restore:
    mov.l   resident_scu_ims_irq, r3
    mov.l   resident_mask_shadow_irq, r1
    mov.l   @r15+, r2
    mov.l   r2, @r1
    mov.l   r2, @r3
    mov.l   @r15+, r7
    mov.l   @r15+, r6
    mov.l   @r15+, r5
    mov.l   @r15+, r4
    mov.l   @r15+, r3
    mov.l   @r15+, r2
    mov.l   @r15+, r1
    lds.l   @r15+, pr
    mov.l   @r15+, r0
    rte
    nop

    .align 2
resident_diag_ptr:          .long 0x06000BFC
resident_crash_ptr:         .long 0x06000B80
resident_exception_diag:    .long 0xDEADE001
resident_handler_table_irq: .long 0x06000900
resident_input_poll_ptr:    .long stv_resident_input_poll
resident_mask_shadow_irq:   .long 0x06000348
resident_scu_ims_irq:       .long 0x25FE00A0

! Non-returning clean equivalent of the BIOS bootstrap transition at 0x4114.
! The trampoline has already copied the FPR image, so record the observable
! handoff state and enter the loaded game phase directly.
    .org 0xA00, 0
    .global stv_bootstrap_handoff
stv_bootstrap_handoff:
    mov.l   handoff_extended_ptr, r0
    jmp     @r0
    nop
    .align 2
handoff_extended_ptr: .long stv_bootstrap_handoff_extended

! Baku Baku's observed 0x426C path is called once with r4=0.  The handler
! pointers remain unchanged; its resident-state contract is to consume the
! pending transition flag and mark system initialization complete.  Hardware
! reset/initialization is owned by the clean trampoline layer.
    .org 0xA40, 0
    .global stv_handler_table_update
stv_handler_table_update:
    mov.l   handler_pending_ptr, r1
    mov     #0, r0
    mov.l   r0, @r1
    mov.l   handler_status_ptr, r1
    mov.l   @r1, r0
    mov     #0x40, r2
    shll    r2
    or      r2, r0
    mov.l   r0, @r1

    ! Match the caller-visible scratch registers captured at the return PC.
    mov     #0x10, r0
    mov     #1, r4
    shll8   r4
    mov.l   handler_r5_value, r5
    rts
    nop

    .align 2
handler_pending_ptr: .long 0x06000324
handler_status_ptr:  .long 0x06000824
handler_r5_value:    .long 0x06000C34

! ---------------------------------------------------------------------------
! Native implementations of the HWRAM resident entry points reached directly
! from Baku Baku game code.  The installer below places clean absolute jump
! stubs at their original HWRAM addresses.
! ---------------------------------------------------------------------------
    .org 0xB00, 0
    .global stv_resident_mask_set
stv_resident_mask_set:
    mov.l   resident_mask_shadow, r3
    mov.l   r4, @r3
    mov.l   resident_scu_ims, r3
    mov.l   r4, @r3
    rts
    nop
    .align 2
resident_mask_shadow: .long 0x06000348
resident_scu_ims:     .long 0x25FE00A0

    .org 0xB20, 0
    .global stv_resident_mask_update
stv_resident_mask_update:
    mov.l   resident_mask_shadow_u, r7
    mov.l   @r7, r6
    or      r5, r6
    and     r4, r6
    mov.l   r6, @r7
    mov.l   resident_scu_ims_u, r3
    mov.l   r6, @r3
    rts
    nop
    .align 2
resident_mask_shadow_u: .long 0x06000348
resident_scu_ims_u:     .long 0x25FE00A0

    .org 0xB40, 0
    .global stv_resident_clock_dispatch
stv_resident_clock_dispatch:
    mov.l   resident_clock_native, r0
    jmp     @r0
    nop
    .align 2
resident_clock_native: .long stv_vblank_clock_update

    .org 0xB60, 0
    .global stv_resident_queue_pop
stv_resident_queue_pop:
    mov     #0x5E, r6
    mov     #0x70, r7
    bra     resident_queue_pop_common
    nop

resident_queue_pop_common:
    mov.l   resident_queue_base, r5
    mov     r6, r0
    mov.b   @(r0, r5), r4
    add     #1, r0
    mov.b   @(r0, r5), r3
    cmp/eq  r3, r4
    bf      resident_queue_available
    rts
    mov     #0, r0
resident_queue_available:
    mov     r4, r0
    add     #1, r0
    and     #0x0F, r0
    mov     r6, r1
    add     r5, r1
    mov.b   r0, @r1
    mov     r7, r0
    add     r5, r0
    mov.b   @(r0, r4), r0
    rts
    nop
    .align 2
resident_queue_base: .long 0x06000700

    .global stv_resident_queue_pop_alt
stv_resident_queue_pop_alt:
    mov     #0x5C, r6
    mov     #0x60, r7
    bra     resident_queue_pop_common
    nop

    .org 0xBA0, 0
    .global stv_resident_system_flag
stv_resident_system_flag:
    mov     r4, r0
    cmp/eq  #0, r0
    bt      resident_flag_clear_bit
    cmp/eq  #1, r0
    bt      resident_flag_clear_word
    rts
    nop
resident_flag_clear_bit:
    mov.l   resident_flag_long_ptr, r1
    mov.l   @r1, r3
    mov     #-33, r2
    and     r2, r3
    mov.l   r3, @r1
    rts
    nop
resident_flag_clear_word:
    mov.l   resident_flag_word_ptr, r1
    mov     #0, r2
    mov.w   r2, @r1
    rts
    nop
    .align 2
resident_flag_long_ptr: .long 0x06000824
resident_flag_word_ptr: .long 0x06000820

    .org 0xBE0, 0
    .global stv_resident_strided_dispatch
stv_resident_strided_dispatch:
    mov     r4, r0
    cmp/eq  #0, r0
    bt      resident_strided_read_word
    cmp/eq  #1, r0
    bt      resident_strided_read_long
    cmp/eq  #2, r0
    bt      resident_strided_write_word
    cmp/eq  #3, r0
    bt      resident_strided_write_long
    rts
    nop
resident_strided_read_word:
    add     #1, r5
    mov.b   @r5, r0
    extu.b  r0, r0
    shll8   r0
    add     #2, r5
    mov.b   @r5, r1
    extu.b  r1, r1
    or      r1, r0
    rts
    nop
resident_strided_read_long:
    mov     r5, r4
    bra     stv_read_strided_long
    nop
resident_strided_write_word:
    add     #3, r5
    mov.b   r6, @r5
    shlr8   r6
    add     #-2, r5
    mov.b   r6, @r5
    rts
    nop
resident_strided_write_long:
    mov     r5, r4
    mov     r6, r5
    bra     stv_write_strided_long
    nop

    .org 0xC40, 0
    .global stv_resident_vector_set
stv_resident_vector_set:
    tst     r5, r5
    bf      resident_vector_value_ready
    mov.l   resident_irq_default, r5
resident_vector_value_ready:
    stc     vbr, r0
    shll2   r4
    mov.l   r5, @(r0, r4)

    ! Saturn's Slave SH-2 mask-BIOS waits for the shared "2RDY" word before
    ! entering the 0x06000600 master-supplied bootstrap.  The original BIOS
    ! vector service refreshed both pieces whenever it installed a slave
    ! entry (Shienryu uses vector 0x94, then issues SMPC SSHON).  Recreate the
    ! same generic contract here; 0x06000600..0x0600060B is the unused gap
    ! immediately before the resident service pointer table.
    mov.l   resident_slave_ready_ptr, r1
    mov.l   resident_slave_ready, r2
    mov.l   r2, @r1
    mov.l   resident_slave_boot_ptr, r1
    mov.l   resident_slave_boot_0, r2
    mov.l   r2, @r1
    mov.l   resident_slave_boot_1, r2
    mov.l   r2, @(4, r1)
    mov.l   resident_slave_vector_ptr, r2
    mov.l   r2, @(8, r1)
    rts
    nop
    .align 2
resident_irq_default: .long stv_resident_irq_return
resident_slave_ready_ptr:  .long 0x06000240
resident_slave_ready:      .long 0x32524459
resident_slave_boot_ptr:   .long 0x06000600
resident_slave_boot_0:     .long 0xD0016002
resident_slave_boot_1:     .long 0x402B0009
resident_slave_vector_ptr: .long 0x06000250

    .org 0xC80, 0
    .global stv_resident_handler_set
stv_resident_handler_set:
    tst     r5, r5
    bf      resident_handler_value_ready
    mov.l   resident_exception_default, r5
resident_handler_value_ready:
    mov.l   resident_handler_table, r0
    shll2   r4
    mov.l   r5, @(r0, r4)
    rts
    nop
    .align 2
resident_exception_default: .long stv_resident_exception
resident_handler_table:      .long 0x06000900

    .org 0xCC0, 0
    .global stv_resident_copy_128
stv_resident_copy_128:
    mov.l   resident_copy_128_dst, r0
    mov     #32, r3
resident_copy_128_loop:
    mov.l   @r4+, r2
    mov.l   r2, @r0
    add     #4, r0
    dt      r3
    bf      resident_copy_128_loop
    rts
    nop
    .align 2
resident_copy_128_dst: .long 0x06000A80

    .org 0xD00, 0
    .global stv_resident_copy_20
stv_resident_copy_20:
    mov.l   resident_copy_20_src, r5
    mov     r4, r6
    mov     #20, r3
resident_copy_20_loop:
    mov.b   @r5+, r1
    mov.b   r1, @r6
    add     #1, r6
    dt      r3
    bf      resident_copy_20_loop
    rts
    nop
    .align 2
resident_copy_20_src: .long 0x06000740

! Install two compact close-packed veneers at 0xC00/0xC0A, then ordinary
! 12-byte absolute veneers for the remaining resident entry points.
    .org 0xE00, 0
    .global stv_install_resident_veneers
stv_install_resident_veneers:
    mov.l   resident_c00_ptr, r1
    mov.w   resident_c00_load, r0
    mov.w   r0, @r1
    add     #2, r1
    mov.w   resident_jump_op, r0
    mov.w   r0, @r1
    add     #2, r1
    mov.w   resident_nop_op, r0
    mov.w   r0, @r1

    mov.l   resident_c0a_ptr, r1
    mov.w   resident_c0a_load, r0
    mov.w   r0, @r1
    add     #2, r1
    mov.w   resident_jump_op, r0
    mov.w   r0, @r1
    add     #2, r1
    mov.w   resident_nop_op, r0
    mov.w   r0, @r1

    mov.l   resident_c20_ptr, r1
    mov.l   resident_c00_target, r0
    mov.l   r0, @r1
    mov.l   resident_c24_ptr, r1
    mov.l   resident_c0a_target, r0
    mov.l   r0, @r1

    ! Restore the pointer/vector API slots which overlap the VBR page.
    mov.l   resident_slot_300_e, r1
    mov.l   resident_handler_set_e, r0
    mov.l   r0, @r1
    mov.l   resident_slot_304_e, r1
    mov.l   resident_handler_get_e, r0
    mov.l   r0, @r1
    mov.l   resident_slot_310_e, r1
    mov.l   resident_vector_set_e, r0
    mov.l   r0, @r1
    mov.l   resident_slot_314_e, r1
    mov.l   resident_vector_get_e, r0
    mov.l   r0, @r1

    mov.l   resident_veneer_table_ptr_e, r1
resident_veneer_loop:
    mov.l   @r1+, r2
    tst     r2, r2
    bt      resident_veneer_done
    mov.l   @r1+, r3
    mov.l   resident_abs_op0, r0
    mov.l   r0, @r2
    mov.l   resident_abs_op1, r0
    mov.l   r0, @(4, r2)
    mov.l   r3, @(8, r2)
    bra     resident_veneer_loop
    nop
resident_veneer_done:
    ! Tail-call the shared queue-slot initializer; it returns directly to the
    ! resident constructor through our unchanged PR.
    bra     stv_resident_queue_init
    nop

    .align 2
resident_c00_ptr:    .long 0x06000C00
resident_c0a_ptr:    .long 0x06000C0A
resident_c20_ptr:    .long 0x06000C20
resident_c24_ptr:    .long 0x06000C24
resident_c00_target: .long stv_resident_mask_set
resident_c0a_target: .long stv_resident_mask_update
resident_slot_300_e: .long 0x06000300
resident_slot_304_e: .long 0x06000304
resident_slot_310_e: .long 0x06000310
resident_slot_314_e: .long 0x06000314
resident_handler_set_e: .long stv_resident_handler_set
resident_handler_get_e: .long stv_resident_handler_get
resident_vector_set_e:  .long stv_resident_vector_set
resident_vector_get_e:  .long stv_resident_vector_get
resident_abs_op0:    .long 0xD001402B
resident_abs_op1:    .long 0x00090009
resident_veneer_table_ptr_e: .long resident_veneer_table
    .align 1
resident_c00_load: .word 0xD007
resident_c0a_load: .word 0xD006
resident_jump_op:  .word 0x402B
resident_nop_op:   .word 0x0009
    .align 2
resident_veneer_table:
    .long 0x06000D14, stv_resident_clock_dispatch
    .long 0x06001198, stv_resident_queue_pop
    .long 0x0600120E, stv_resident_system_flag
    .long 0x06001412, stv_resident_strided_dispatch
    .long 0x06001494, stv_resident_vector_set
    .long 0x060014A8, stv_resident_handler_set
    .long 0x060014C0, stv_resident_copy_128
    .long 0x060014E0, stv_resident_copy_20
    .long 0x00000000, 0x00000000

! Baku's game-visible 0x34C4 call occurs after the BIOS boot/reset passes have
! already completed.  Its steady-state contract is display-off plus the
! caller-visible success/T/default-handler values; clean hardware setup lives
! in the trampoline instead of recursively reproducing the BIOS reset chain.
    .org 0xF00, 0
    .global stv_video_shutdown_fast
stv_video_shutdown_fast:
    mov.l   video_tvmd_ptr, r3
    mov.w   @r3, r0
    and     #1, r0
    mov.w   r0, @r3
    mov.l   video_default_handler, r4
    mov     #1, r0
    sett
    rts
    nop
    .align 2
video_tvmd_ptr:        .long 0x25F80000
video_default_handler: .long stv_resident_exception

    .org 0xF40, 0
stv_bootstrap_handoff_extended:
    ! Recreate the measured BIOS->game frame at the first 0x06010808 entry.
    mov.l   handoff_stack_seed_ptr, r1
    mov.l   handoff_stack_base, r2
    mov     #8, r3
handoff_stack_loop:
    mov.l   @r1+, r0
    mov.l   r0, @r2
    add     #4, r2
    dt      r3
    bf      handoff_stack_loop

    mov.l   handoff_phase_ptr, r1
    mov.l   handoff_phase_value, r0
    mov.l   r0, @r1
    mov.l   handoff_ready_ptr, r1
    mov     #1, r0
    mov.l   r0, @r1
    mov.l   handoff_game_index_ptr, r1
    mov.l   handoff_game_index_0, r0
    mov.l   r0, @r1
    mov.l   handoff_game_index_1, r0
    mov.l   r0, @(4, r1)

    ! The constructor kept every SCU source masked. Enable only the measured
    ! game-time set immediately before SR is opened.
    mov.l   handoff_scu_ims_ptr, r1
    mov.l   handoff_scu_ims_value, r0
    mov.l   r0, @r1

    mov.l   handoff_gbr, r0
    ldc     r0, gbr
    mov.l   handoff_initial_pr, r0
    lds     r0, pr
    mov     #0, r0
    ldc     r0, sr

    mov.l   handoff_stack_base, r15
    mov     #0, r14
    mov     #0, r13
    mov     #0, r12
    mov     #0, r11
    mov     #0, r10
    mov.l   handoff_game_entry, r9
    mov     #0, r8
    mov.l   handoff_r7, r7
    mov     #0, r6
    mov.l   handoff_r5, r5
    mov.l   handoff_r4, r4
    mov     #0, r3
    mov     #0x10, r2
    mov.l   handoff_r1, r1
    mov     #0, r0
    jmp     @r9
    mov     #0, r9

    .align 2
handoff_stack_base:  .long 0x060FFFDC
handoff_phase_ptr:   .long 0x060002C4
handoff_phase_value: .long 0x00003470
handoff_ready_ptr:   .long 0x06000800
handoff_game_index_ptr: .long 0x06083238
handoff_game_index_0:   .long 0x0001FFFF
handoff_game_index_1:   .long 0x00000001
handoff_game_entry:  .long 0x06010808
handoff_gbr:         .long 0x060D28C8
handoff_initial_pr:  .long 0x06010660
handoff_r1:          .long 0xFF79A6F1
handoff_r4:          .long 0x00000120
handoff_r5:          .long 0x20180108
handoff_r7:          .long 0x45A07058
handoff_stack_seed_ptr: .long handoff_stack_seed
handoff_scu_ims_ptr:   .long 0x25FE00A0
handoff_scu_ims_value: .long 0xFFFFE1FC
handoff_stack_seed:
    .long 0x39A0500E, 0x00000000, 0x20180108, 0x45A00000
    .long 0x0601025E, 0x00000000, 0x00000000, 0x06010006

    ! Both supported games consume the two BIOS resident event queues through
    ! pointer slots 0x06000668 and 0x06000670.  Keep this outside the crowded
    ! 0x800 constructor and install it for every profile.
    .org 0x1000, 0
    .global stv_resident_queue_init
stv_resident_queue_init:
    mov.l   resident_queue_slot_668, r1
    mov.l   resident_queue_pop_init, r0
    mov.l   r0, @r1
    add     #0x34, r0
    mov.l   r0, @(8, r1)
    rts
    nop
    .align 2
resident_queue_slot_668: .long 0x06000668
resident_queue_pop_init: .long stv_resident_queue_pop

    .org 0x1100, 0
    .global stv_resident_handler_get
stv_resident_handler_get:
    mov.l   resident_handler_table_get, r0
    shll2   r4
    mov.l   @(r0, r4), r0
    rts
    nop
    .align 2
resident_handler_table_get: .long 0x06000900

    .org 0x1120, 0
    .global stv_resident_vector_get
stv_resident_vector_get:
    stc     vbr, r0
    shll2   r4
    mov.l   @(r0, r4), r0
    rts
    nop

    ! Read the MCU-owned active-low IOGA shadow through SAROO's reachable CS2
    ! control window. Saturn cannot route ST-V's original 0x00400000 page to
    ! the cartridge, so publish the same active-high HWRAM input words that
    ! the original 0x06002098 poller produced.
    .org 0x1140, 0
    .global stv_resident_input_poll
stv_resident_input_poll:
    sts.l   pr, @-r15
    mov.l   ioga_shadow_ab, r0
    mov.w   @r0, r1
    swap.b  r1, r4
    extu.b  r4, r4
    not     r4, r4
    extu.b  r4, r4
    extu.b  r1, r5
    not     r5, r5
    extu.b  r5, r5
    mov.l   ioga_port_a_dst, r0
    mov.l   r4, @r0
    mov.l   ioga_port_b_dst, r0
    mov.l   r5, @r0

    mov.l   ioga_shadow_ce, r0
    mov.w   @r0, r1
    swap.b  r1, r6
    extu.b  r6, r6
    not     r6, r6
    extu.b  r6, r6
    extu.b  r1, r7
    not     r7, r7
    extu.b  r7, r7
    mov.l   ioga_port_c_dst, r0
    mov.l   r6, @r0
    mov.l   ioga_port_e_dst, r0
    mov.l   r7, @r0

    mov.l   ioga_shadow_fd, r0
    mov.w   @r0, r1
    swap.b  r1, r2
    extu.b  r2, r2
    not     r2, r2
    extu.b  r2, r2
    mov.l   ioga_port_f_dst, r0
    mov.l   r2, @r0

    ! Preserve the original resident's compact derived system byte:
    ! ~(((A >> 1) & 4) | (C & 3) | (B & 8)).
    mov     r4, r0
    shlr    r0
    and     #4, r0
    mov     r0, r3
    mov     r6, r0
    and     #3, r0
    or      r0, r3
    mov     r5, r0
    and     #8, r0
    or      r0, r3
    not     r3, r3
    mov.l   ioga_system_dst, r0
    mov.b   r3, @r0
    mov.l   input_sound_poll_ptr, r0
    jsr     @r0
    nop
    mov.l   input_pad_poll_ptr, r0
    jsr     @r0
    nop
    lds.l   @r15+, pr
    rts
    nop

    .align 2
ioga_shadow_ab:  .long 0x25807020
ioga_shadow_ce:  .long 0x25807022
ioga_shadow_fd:  .long 0x25807024
ioga_port_a_dst: .long 0x06002864
ioga_port_b_dst: .long 0x06002868
ioga_port_c_dst: .long 0x0600286C
ioga_port_e_dst: .long 0x06002870
ioga_port_f_dst: .long 0x06002874
ioga_system_dst: .long 0x06000730
input_pad_poll_ptr: .long stv_smpc_pad_poll
input_sound_poll_ptr: .long stv_scsp_sound_poll

    ! Configure Saturn SMPC for INTBACK pad acquisition. The boot trampoline
    ! calls this once before entering the game.
    .org 0x1200, 0
    .global stv_smpc_pad_init
stv_smpc_pad_init:
    mov     #0, r0
    mov.l   smpc_ireg0_ptr, r1
    mov.b   r0, @r1
    add     #2, r1
    mov     #0x0A, r0
    mov.b   r0, @r1
    add     #2, r1
    mov     #0xF0, r0
    mov.b   r0, @r1
    mov     #0, r0
    mov.l   smpc_ddr1_ptr, r1
    mov.b   r0, @r1
    add     #4, r1
    mov.b   r0, @r1
    add     #2, r1
    mov.b   r0, @r1
    mov.l   smpc_pad_state_ptr_i, r1
    mov.l   r0, @r1
    mov.l   smpc_sound_last_ptr_i, r1
    mov.l   r0, @r1
    rts
    nop
    .align 2
smpc_ireg0_ptr: .long 0x20100001
smpc_ddr1_ptr:  .long 0x20100079
smpc_pad_state_ptr_i: .long 0x06000BE0
smpc_sound_last_ptr_i:.long 0x06000BE4

    ! Non-blocking INTBACK state machine. One VBlank issues the command; a
    ! later VBlank consumes OREG2/3. No CPU spin waits on SMPC hardware.
    .org 0x1280, 0
    .global stv_smpc_pad_poll
stv_smpc_pad_poll:
    mov.l   smpc_sound_state_ptr, r2
    mov.b   @r2, r0
    tst     r0, r0
    bf      smpc_pad_return
    mov.l   smpc_pad_state_ptr, r1
    mov.b   @r1, r0
    tst     r0, r0
    bf      smpc_pad_pending

    mov.l   smpc_sf_ptr, r2
    mov.b   @r2, r0
    tst     #1, r0
    bf      smpc_pad_return
    mov     #1, r0
    mov.b   r0, @r2
    mov.l   smpc_comreg_ptr, r2
    mov     #0x10, r0
    mov.b   r0, @r2
    mov     #1, r0
    mov.b   r0, @r1
    mov     #0, r0
    mov.b   r0, @(1, r1)
smpc_pad_return:
    rts
    nop

smpc_pad_pending:
    mov.l   smpc_sf_ptr, r2
    mov.b   @r2, r0
    tst     #1, r0
    bt      smpc_read_pad
    mov.b   @(1, r1), r0
    add     #1, r0
    mov.b   r0, @(1, r1)
    cmp/eq  #60, r0
    bf      smpc_pad_return
    mov     #0, r0
    mov.b   r0, @r1
    mov.b   r0, @(1, r1)
    rts
    nop

smpc_read_pad:
    mov     #0, r0
    mov.b   r0, @r1
    mov.b   r0, @(1, r1)
    .ifdef SMPC_TEST_VECTOR
    mov     #0x5F, r4       ! Left+Up+A+B+C+Start
    mov     #0x48, r5       ! X+L(coin)
    bra     smpc_pad_values_ready
    nop
    .endif
    mov.l   smpc_oreg2_ptr, r2
    mov.b   @r2, r4
    extu.b  r4, r4
    not     r4, r4
    extu.b  r4, r4
    add     #2, r2
    mov.b   @r2, r5
    extu.b  r5, r5
    not     r5, r5
    extu.b  r5, r5
smpc_pad_values_ready:
    mov.l   smpc_ireg0_ptr_p, r1
    mov     #0x40, r0
    mov.b   r0, @r1

    ! Saturn OREG2: R,L,D,U,Start,A,C,B -> ST-V Port A:
    ! L,R,U,D,button4,button3,button2,button1.
    mov     #0, r6
    mov     r4, r0
    tst     #0x80, r0
    bt      smpc_no_right
    mov     #0x40, r0
    or      r0, r6
smpc_no_right:
    mov     r4, r0
    tst     #0x40, r0
    bt      smpc_no_left
    mov     #0x80, r0
    or      r0, r6
smpc_no_left:
    mov     r4, r0
    tst     #0x20, r0
    bt      smpc_no_down
    mov     #0x10, r0
    or      r0, r6
smpc_no_down:
    mov     r4, r0
    tst     #0x10, r0
    bt      smpc_no_up
    mov     #0x20, r0
    or      r0, r6
smpc_no_up:
    mov     r4, r0
    tst     #0x04, r0
    bt      smpc_no_a
    mov     #0x01, r0
    or      r0, r6
smpc_no_a:
    mov     r4, r0
    tst     #0x01, r0
    bt      smpc_no_b
    mov     #0x02, r0
    or      r0, r6
smpc_no_b:
    mov     r4, r0
    tst     #0x02, r0
    bt      smpc_no_c
    mov     #0x04, r0
    or      r0, r6
smpc_no_c:
    mov     r5, r0
    tst     #0x40, r0
    bt      smpc_no_x
    mov     #0x08, r0
    or      r0, r6
smpc_no_x:
    extu.b  r6, r6

    ! Saturn Start -> ST-V Start1, Saturn L -> Coin1.
    mov     #0, r7
    mov     r4, r0
    tst     #0x08, r0
    bt      smpc_no_start
    mov     #0x10, r0
    or      r0, r7
smpc_no_start:
    mov     r5, r0
    tst     #0x08, r0
    bt      smpc_no_coin
    mov     #0x01, r0
    or      r0, r7
smpc_no_coin:

    mov.l   smpc_port_a_dst, r1
    mov.l   @r1, r4
    or      r6, r4
    mov.l   r4, @r1
    mov.l   smpc_port_c_dst, r1
    mov.l   @r1, r6
    or      r7, r6
    mov.l   r6, @r1

    ! Recompute the derived system byte after merging the Saturn pad.
    mov.l   smpc_port_b_dst, r1
    mov.l   @r1, r5
    mov     r4, r0
    shlr    r0
    and     #4, r0
    mov     r0, r3
    mov     r6, r0
    and     #3, r0
    or      r0, r3
    mov     r5, r0
    and     #8, r0
    or      r0, r3
    not     r3, r3
    mov.l   smpc_system_dst, r1
    mov.b   r3, @r1
    rts
    nop

    .align 2
smpc_sf_ptr:       .long 0x20100063
smpc_comreg_ptr:   .long 0x2010001F
smpc_oreg2_ptr:    .long 0x20100025
smpc_ireg0_ptr_p:  .long 0x20100001
smpc_port_a_dst:   .long 0x06002864
smpc_port_b_dst:   .long 0x06002868
smpc_port_c_dst:   .long 0x0600286C
smpc_system_dst:   .long 0x06000730
smpc_pad_state_ptr:.long 0x06000BE0
smpc_sound_state_ptr:.long 0x06000BE2

    ! Deterministic cold hardware baseline. Avoid inheriting Saturn BIOS or
    ! emulator defaults: stop SCU DMA, mask interrupts, park Slave SH-2, reset
    ! VDP1 drawing, and program the measured Baku VDP2 cycle layout with DISP
    ! held off until the trampoline diagnostics/game transition.
    .org 0x1400, 0
    .global stv_hardware_init
stv_hardware_init:
    sts.l   pr, @-r15
    mov.l   hw_cache_ccr, r1
    mov     #0x10, r0
    mov.b   r0, @r1       ! purge address/data cache arrays
    mov     #0, r0
    mov.b   r0, @r1       ! deterministic cache-off handoff
    mov.l   hw_scu_d0en, r1
    mov.l   r0, @r1
    mov.l   hw_scu_d1en, r1
    mov.l   r0, @r1
    mov.l   hw_scu_d2en, r1
    mov.l   r0, @r1
    mov.l   hw_scu_dstp, r1
    mov     #7, r0
    mov.l   r0, @r1
    mov.l   hw_scu_ims, r1
    mov     #-1, r0
    mov.l   r0, @r1
    mov.l   hw_scu_ist, r1
    mov.l   r0, @r1

    mov     #0, r0
    mov.l   hw_vdp1_base, r1
    mov.w   r0, @r1
    mov.w   r0, @(2, r1)
    mov.w   r0, @(4, r1)
    mov.w   r0, @(6, r1)
    mov.w   r0, @(8, r1)
    mov.w   r0, @(10, r1)

    mov.l   hw_vdp2_base, r1
    mov.w   r0, @r1
    mov.w   r0, @(2, r1)
    mov.w   hw_ramctl, r0
    mov.w   r0, @(14, r1)
    mov.l   hw_cycle_values_ptr, r2
    mov     #8, r3
    add     #0x10, r1
hw_cycle_copy:
    mov.w   @r2+, r0
    mov.w   r0, @r1
    add     #2, r1
    dt      r3
    bf      hw_cycle_copy
    mov     #0, r0
    mov.l   hw_vdp2_bgon, r1
    mov.w   r0, @r1

    ! Saturn BIOS may have left Slave SH-2 active. Park it for the current
    ! verified single-master Baku path; no fabricated slave entry is started.
    mov     #3, r4
    mov.l   hw_smpc_command_ptr, r0
    jsr     @r0
    nop
    lds.l   @r15+, pr
    rts
    nop

    .align 2
hw_scu_d0en: .long 0x25FE0010
hw_cache_ccr:.long 0xFFFFFE92
hw_scu_d1en: .long 0x25FE0030
hw_scu_d2en: .long 0x25FE0050
hw_scu_dstp: .long 0x25FE0060
hw_scu_ims:  .long 0x25FE00A0
hw_scu_ist:  .long 0x25FE00A4
hw_vdp1_base:.long 0x25D00000
hw_vdp2_base:.long 0x25F80000
hw_vdp2_bgon:.long 0x25F80020
hw_smpc_command_ptr: .long stv_smpc_command
hw_cycle_values_ptr: .long hw_cycle_values
hw_ramctl:   .word 0x1000
hw_cycle_values:
    .word 0x4455, 0x77FF, 0xFFFF, 0xFFFF
    .word 0x3036, 0x0112, 0xFFFF, 0xFFFF
    .align 2

    ! Bounded synchronous SMPC command helper. R4=command, R0=0 success/-1
    ! timeout. Used only during trampoline construction, never from game code.
    .org 0x1500, 0
    .global stv_smpc_command
stv_smpc_command:
    mov.l   smpc_cmd_sf, r2
    mov.w   smpc_cmd_timeout, r3
smpc_cmd_wait_idle:
    mov.b   @r2, r0
    tst     #1, r0
    bt      smpc_cmd_issue
    dt      r3
    bf      smpc_cmd_wait_idle
    mov     #-1, r0
    rts
    nop
smpc_cmd_issue:
    mov     #1, r0
    mov.b   r0, @r2
    mov.l   smpc_cmd_comreg, r1
    mov.b   r4, @r1
    mov.w   smpc_cmd_timeout, r3
smpc_cmd_wait_done:
    mov.b   @r2, r0
    tst     #1, r0
    bt      smpc_cmd_ok
    dt      r3
    bf      smpc_cmd_wait_done
    mov     #-1, r0
    rts
    nop
smpc_cmd_ok:
    mov     #0, r0
    rts
    nop
    .align 2
smpc_cmd_sf:      .long 0x20100063
smpc_cmd_comreg:  .long 0x2010001F
smpc_cmd_timeout: .word 0x4000
    .align 2

    ! Real Saturn does not automatically reset the SCSP 68K when the game
    ! replaces its reset vector. Detect a new valid vector and sequence
    ! SNDOFF -> SNDON asynchronously, sharing SMPC with the pad state machine.
    .org 0x1600, 0
    .global stv_scsp_sound_poll
stv_scsp_sound_poll:
    mov.l   sound_state_ptr, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    cmp/eq  #1, r0
    bt      sound_wait_off
    cmp/eq  #2, r0
    bt      sound_wait_on

    mov.l   sound_pad_state_ptr, r2
    mov.b   @r2, r0
    tst     r0, r0
    bf      sound_return
    mov.l   sound_sf_ptr, r2
    mov.b   @r2, r0
    tst     #1, r0
    bf      sound_return
    mov.l   sound_vector_ptr, r2
    mov.l   @r2, r4
    tst     r4, r4
    bt      sound_return
    mov.l   sound_vector_limit, r2
    cmp/hs  r2, r4
    bt      sound_return
    mov.l   sound_last_ptr, r2
    mov.l   @r2, r3
    cmp/eq  r3, r4
    bt      sound_return
    mov.l   r4, @r2
    mov     #7, r4
    mov.l   sound_sf_ptr, r2
    mov     #1, r0
    mov.b   r0, @r2
    mov.l   sound_comreg_ptr, r2
    mov.b   r4, @r2
    mov     #1, r0
    mov.b   r0, @r1
    mov     #0, r0
    mov.b   r0, @(1, r1)
sound_return:
    rts
    nop

sound_wait_off:
    mov.l   sound_sf_ptr, r2
    mov.b   @r2, r0
    tst     #1, r0
    bf      sound_age_tick
    mov     #6, r4
    mov     #1, r0
    mov.b   r0, @r2
    mov.l   sound_comreg_ptr, r2
    mov.b   r4, @r2
    mov     #2, r0
    mov.b   r0, @r1
    mov     #0, r0
    mov.b   r0, @(1, r1)
    rts
    nop

sound_wait_on:
    mov.l   sound_sf_ptr, r2
    mov.b   @r2, r0
    tst     #1, r0
    bf      sound_age_tick
    mov     #0, r0
    mov.b   r0, @r1
    mov.b   r0, @(1, r1)
    rts
    nop

sound_age_tick:
    mov.b   @(1, r1), r0
    add     #1, r0
    mov.b   r0, @(1, r1)
    cmp/eq  #60, r0
    bf      sound_return
    mov     #0, r0
    mov.b   r0, @r1
    mov.b   r0, @(1, r1)
    rts
    nop

    .align 2
sound_state_ptr:    .long 0x06000BE2
sound_pad_state_ptr:.long 0x06000BE0
sound_last_ptr:     .long 0x06000BE4
sound_vector_ptr:   .long 0x25A00004
sound_vector_limit: .long 0x00080000
sound_sf_ptr:       .long 0x20100063
sound_comreg_ptr:   .long 0x2010001F

    ! Shienryu's normal entry immediately installs its own stack and masked
    ! SR before calling game initialization. The clean trampoline has already
    ! materialized the measured program image and resident state.
    .org 0x1700, 0
    .global stv_shienryu_handoff
stv_shienryu_handoff:
    mov.l   shien_handoff_vbr, r0
    ldc     r0, vbr
    mov.l   shien_handoff_gbr, r0
    ldc     r0, gbr
    ! Restore Shienryu's measured SCU interrupt mask before opening SR.
    ! Leaving the cold-init 0xFFFFFFFF mask installed suppresses VBLANK-IN,
    ! freezes the game clock, and prevents VDP1 aircraft commands from being
    ! submitted even though the VDP2 playfield remains visible.
    mov.l   shien_handoff_scu_ims_ptr, r1
    mov.l   shien_handoff_scu_ims_value, r0
    mov.l   r0, @r1
    mov     #1, r0
    ldc     r0, sr
    mov.l   shien_handoff_stack, r15
    mov.l   shien_handoff_pr, r0
    lds     r0, pr
    mov.l   shien_handoff_entry, r7
    jmp     @r7
    nop
    .align 2
shien_handoff_vbr:   .long 0x06000000
shien_handoff_gbr:   .long 0xFFFFFE00
shien_handoff_stack: .long 0x06100000
shien_handoff_pr:    .long 0x00004516
shien_handoff_entry: .long 0x06004010
shien_handoff_scu_ims_ptr:   .long 0x25FE00A0
shien_handoff_scu_ims_value: .long 0xFFFF7FFE

    .org 0x1740, 0
    .global stv_shienryu_profile_init
stv_shienryu_profile_init:
    mov.l   shien_slot_340, r1
    mov.l   shien_mask_set, r0
    mov.l   r0, @r1
    add     #4, r1
    mov.l   shien_mask_update, r0
    mov.l   r0, @r1
    ! 0x06000348 overlaps the VBR page and was filled with the default
    ! exception target by stv_resident_init.  It is data, not a vector: the
    ! resident 0xC0A service treats it as the SCU IMS shadow.  Seed the value
    ! measured at Shienryu's BIOS handoff so its first two updates produce
    ! 0xFFFF77FE and 0xFFFF57FC instead of masking VBLANK-IN.
    mov.l   shien_mask_shadow, r1
    mov.l   shien_mask_initial, r0
    mov.l   r0, @r1
    .ifdef SHIENRYU_PROFILE
    mov.l   shien_slot_640, r1
    mov.l   shien_backup_probe_ptr, r0
    mov.l   r0, @r1
    mov.l   shien_slot_644, r1
    mov.l   shien_backup_access_ptr, r0
    mov.l   r0, @r1
    mov.l   shien_slot_648, r1
    mov.l   shien_backup_mark_ptr, r0
    mov.l   r0, @r1
    mov.l   shien_slot_61c, r1
    mov.l   shien_eeprom_load_ptr, r0
    mov.l   r0, @r1
    mov.l   shien_slot_620, r1
    mov.l   shien_eeprom_save_ptr, r0
    mov.l   r0, @r1
    mov.l   shien_slot_624, r1
    mov.l   r0, @r1
    mov.l   shien_channel_ptr, r1
    mov     #4, r0
    mov.b   r0, @r1
    sts.l   pr, @-r15
    mov.l   shien_eeprom_load_ptr, r0
    jsr     @r0
    nop
    lds.l   @r15+, pr
    .endif
    rts
    nop
    .align 2
shien_slot_340:    .long 0x06000340
shien_mask_shadow: .long 0x06000348
shien_mask_initial:.long 0xFFFF7FFE
shien_mask_set:    .long 0x06000C00
shien_mask_update: .long 0x06000C0A
    .ifdef SHIENRYU_PROFILE
shien_slot_640:    .long 0x06000640
shien_slot_644:    .long 0x06000644
shien_slot_648:    .long 0x06000648
shien_slot_61c:    .long 0x0600061C
shien_slot_620:    .long 0x06000620
shien_slot_624:    .long 0x06000624
shien_channel_ptr: .long 0x06000650
shien_backup_probe_ptr:  .long stv_shienryu_backup_probe
shien_backup_access_ptr: .long stv_resident_strided_dispatch
shien_backup_mark_ptr:   .long stv_shienryu_backup_mark
shien_eeprom_load_ptr:   .long stv_shienryu_eeprom_load
shien_eeprom_save_ptr:   .long stv_shienryu_eeprom_save

    ! BIOS 0x3744 probes the start of the interleaved battery-backed area by
    ! dispatching mode 1 through resident callback 0x06000644.  Keep it native
    ! so Shienryu can validate and initialize its per-game backup channel.
    .org 0x17E0, 0
    .global stv_shienryu_backup_probe
stv_shienryu_backup_probe:
    mov     #1, r4
    mov.l   shien_backup_base, r5
    mov     #0, r6
    bra     stv_resident_strided_dispatch
    nop
    .align 2
shien_backup_base: .long 0x20180000

    ! Resident 0x06001190 marks the channel state dirty/ready for the BIOS
    ! backup service.  Shienryu reaches it through callback slot 0x06000648.
    .org 0x1800, 0
    .global stv_shienryu_backup_mark
stv_shienryu_backup_mark:
    mov.l   shien_backup_flag, r1
    mov     #1, r0
    mov.b   r0, @r1
    rts
    nop
    .align 2
shien_backup_flag: .long 0x06000653

    ! The clean path does not expose an ST-V 93C46 on Saturn's SMPC pins.
    ! Keep the BIOS-compatible 128-byte workspace at 0x06000780, seed it
    ! from the game image on first boot, and persist it in otherwise unused
    ! ST-V backup channel 15.  Physical backup RAM stores bytes at odd
    ! addresses, hence the two-byte stride below.
    .org 0x1840, 0
    .global stv_shienryu_eeprom_load
stv_shienryu_eeprom_load:
    sts.l   pr, @-r15
    mov.l   shien_eeprom_store_base, r1
    add     #1, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    cmp/eq  #'S', r0
    bf      shien_eeprom_seed
    add     #2, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    cmp/eq  #'R', r0
    bf      shien_eeprom_seed
    add     #2, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    cmp/eq  #'E', r0
    bf      shien_eeprom_seed
    add     #2, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    cmp/eq  #'E', r0
    bf      shien_eeprom_seed
    add     #2, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    cmp/eq  #1, r0
    bf      shien_eeprom_seed

    ! Header: "SREE", version, checksum, checksum complement.
    add     #2, r1
    mov.b   @r1, r2
    extu.b  r2, r2
    shll8   r2
    add     #2, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    or      r0, r2
    add     #2, r1
    mov.b   @r1, r3
    extu.b  r3, r3
    shll8   r3
    add     #2, r1
    mov.b   @r1, r0
    extu.b  r0, r0
    or      r0, r3
    not     r2, r0
    extu.w  r0, r0
    cmp/eq  r3, r0
    bf      shien_eeprom_seed

    add     #2, r1
    mov.l   shien_eeprom_workspace, r6
    mov     #0, r4
    mov     #0x7F, r5
    add     #1, r5
shien_eeprom_load_loop:
    mov.b   @r1, r0
    extu.b  r0, r0
    mov.b   r0, @r6
    add     r0, r4
    add     #2, r1
    add     #1, r6
    dt      r5
    bf      shien_eeprom_load_loop
    extu.w  r4, r4
    cmp/eq  r2, r4
    bf      shien_eeprom_seed
    mov     #0, r0
    lds.l   @r15+, pr
    rts
    nop

shien_eeprom_seed:
    mov.l   shien_eeprom_seed_source, r1
    mov.l   shien_eeprom_workspace, r2
    mov     #0x7F, r3
    add     #1, r3
shien_eeprom_seed_loop:
    mov.b   @r1+, r0
    mov.b   r0, @r2
    add     #1, r2
    dt      r3
    bf      shien_eeprom_seed_loop
    bsr     stv_shienryu_eeprom_save
    nop
    lds.l   @r15+, pr
    rts
    nop

    .align 2
shien_eeprom_store_base:  .long 0x2018E200
shien_eeprom_workspace:   .long 0x06000780
shien_eeprom_seed_source: .long 0x04E00000

    .org 0x1940, 0
    .global stv_shienryu_eeprom_save
stv_shienryu_eeprom_save:
    ! Invalidate the record before rewriting its data and checksums.
    mov.l   shien_eeprom_save_base, r1
    add     #1, r1
    mov     #0, r0
    mov.b   r0, @r1

    mov.l   shien_eeprom_save_workspace, r2
    mov.l   shien_eeprom_save_data, r3
    mov     #0, r4
    mov     #0x7F, r5
    add     #1, r5
shien_eeprom_save_loop:
    mov.b   @r2+, r0
    extu.b  r0, r0
    mov.b   r0, @r3
    add     r0, r4
    add     #2, r3
    dt      r5
    bf      shien_eeprom_save_loop
    extu.w  r4, r4

    ! Store checksum and complement before publishing the magic byte.
    mov.l   shien_eeprom_save_checksum, r1
    mov     r4, r0
    shlr8   r0
    mov.b   r0, @r1
    add     #2, r1
    mov.b   r4, @r1
    not     r4, r0
    extu.w  r0, r0
    add     #2, r1
    mov     r0, r2
    shlr8   r2
    mov.b   r2, @r1
    add     #2, r1
    mov.b   r0, @r1

    mov.l   shien_eeprom_save_base, r1
    add     #3, r1
    mov     #'R', r0
    mov.b   r0, @r1
    add     #2, r1
    mov     #'E', r0
    mov.b   r0, @r1
    add     #2, r1
    mov.b   r0, @r1
    add     #2, r1
    mov     #1, r0
    mov.b   r0, @r1
    mov.l   shien_eeprom_save_base, r1
    add     #1, r1
    mov     #'S', r0
    mov.b   r0, @r1
    mov     #0, r0
    rts
    nop

    .align 2
shien_eeprom_save_base:      .long 0x2018E200
shien_eeprom_save_data:      .long 0x2018E213
shien_eeprom_save_checksum:  .long 0x2018E20B
shien_eeprom_save_workspace: .long 0x06000780
    .endif
