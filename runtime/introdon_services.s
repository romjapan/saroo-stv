! Clean native implementations of BIOS service effects; no BIOS code.
! Called only by the guarded paid-answer query literal 060207a0. Native
! menu local selected-row is @(8,caller-SP); the normal helper reports edges.
intro_answer_query:
    sts.l pr,@-r15
    mov.l r5,@-r15
    mov.l intro_answer_native,r0
    jsr @r0
    nop
    mov.l @r15+,r2
    mov.w intro_answer_mask,r1
    cmp/eq r1,r2
    bf intro_answer_done
    mov.l intro_answer_pending,r1
    mov.l @r1,r1
    tst r1,r1
    bt intro_answer_done
    mov.w intro_answer_confirm,r3
    mov r1,r0
    mov #0,r2
    tst #1,r0
    bf intro_answer_store
    mov #1,r2
    tst #2,r0
    bf intro_answer_store
    mov #2,r2
    tst #4,r0
    bf intro_answer_store
    mov #3,r2
    tst #8,r0
    bt intro_answer_restore
intro_answer_store:
    mov.l r2,@(12,r15)
    mov.l intro_answer_pending,r1
    mov.l r2,@(4,r1) ! diagnostic last row, zero based
    mov.l intro_answer_pending,r1
    mov #0,r2
    mov.l r2,@r1
intro_answer_restore:
    mov r3,r0
intro_answer_done:
    lds.l @r15+,pr
    rts
    nop
    .align 2
intro_answer_mask: .word 0x0700
intro_answer_confirm: .word 0x0100
    .align 2
intro_answer_native: .long 0x0600ffb0
intro_answer_cache: .long 0x06000be8
intro_answer_pending: .long 0x2600a080
! The first A/B/C edge is the buzzer. Preserve its direct answer until the
! native selection task asks for confirmation (possibly several frames later).
intro_answer_buzz:
    sts.l pr,@-r15
    mov.l intro_buzz_native,r0
    jsr @r0
    nop
    tst r0,r0
    bt intro_answer_buzz_done
    ! Sample held identity at the native consume point. A long hold must work
    ! even if an earlier edge latch is absent; release falls back to acquisition.
    mov.l intro_buzz_held,r1
    mov.l @r1,r2
    tst r2,r2
    bf intro_buzz_identity
    mov.l intro_buzz_cache,r1
    mov.l @r1,r2
intro_buzz_identity:
    ! Native edge may come from a packet already released by the time the
    ! task runs. Never overwrite an earlier intent with a zero held mask.
    mov r2,r1
    mov #15,r2
    and r1,r2
    tst r2,r2
    bt intro_answer_buzz_done
    mov.l intro_buzz_pending,r1
    mov.l r2,@r1
intro_answer_buzz_done:
    lds.l @r15+,pr
    rts
    nop
    .align 2
intro_buzz_native: .long 0x0600ffb0
intro_buzz_cache: .long 0x2600a0ac
intro_buzz_held: .long 0x2600a0b0
intro_buzz_pending: .long 0x2600a080
! This file is appended only by --introdon-profile.
    .align 2
intro_install:
    sts.l pr,@-r15
    mov.l intro_shared_install,r0
    jsr @r0
    nop
    ! BIOS reset 0x2be..2c4 seeds the IMS shadow to -1.
    mov.l intro_shadow,r1
    mov #-1,r0
    mov.l r0,@r1
    bsr intro_slots
    nop
    lds.l @r15+,pr
    rts
    nop
    .align 2
intro_shared_install: .long cd_scu_install
intro_shadow: .long 0x06000348
intro_slots:
    mov.l intro_slot_table,r1
intro_slot_loop:
    mov.l @r1+,r2
    tst r2,r2
    bt intro_slot_done
    mov.l @r1+,r0
    mov.l r0,@r2
    bra intro_slot_loop
    nop
intro_slot_done:
    rts
    nop
    .align 2
intro_slot_table: .long intro_slots_data
intro_slots_data:
    .long 0x0600060c,0x0600ffd0
    .long 0x06000340,stv_resident_mask_set
    .long 0x06000344,stv_resident_mask_update
    .long 0x06000618,stv_resident_noop
    .long 0x06000628,intro_reinit
    .long 0x06000630,intro_record_write
    .long 0x06000634,intro_record_read
    .long 0x06000674,intro_backup_reset
    .long 0,0

! Channel displacement wraps and sign extends AFTER multiplication.
intro_record_write:
    mov.l intro_channel,r2
    mov.b @r2,r3
    mov r3,r6
    shll2 r3
    add r6,r3
    shll r3
    exts.b r3,r3
    mov.l intro_records,r2
    add r2,r3
    add #2,r3
    mov r3,r6
    mov #8,r5
intro_write_loop:
    mov.b @r4+,r1
    mov.b r1,@r6
    mov r6,r3
    add #1,r6
    dt r5
    bf intro_write_loop
    rts
    nop
intro_record_read:
    mov.l intro_channel,r2
    mov.b @r2,r3
    mov r3,r6
    shll2 r3
    add r6,r3
    shll r3
    exts.b r3,r3
    mov.l intro_records,r2
    add r2,r3
    add #2,r3
    mov r3,r6
    mov #8,r5
intro_read_loop:
    mov.b @r6+,r1
    mov.b r1,@r4
    mov r4,r3
    add #1,r4
    dt r5
    bf intro_read_loop
    rts
    nop
    .align 2
intro_channel: .long 0x06000650
intro_records: .long 0x0600079c

intro_reinit:
    sts.l pr,@-r15
    mov.l intro_work_flags,r1
    mov.l @r1,r0
    mov #-65,r2
    and r2,r0
    mov.l r0,@r1
    mov #0xf0,r0
    extu.b r0,r0
    ldc r0,sr
    mov #-2,r4
    mov.w intro_reset_mask,r5
    mov.l intro_mask_update,r0
    jsr @r0
    nop
    mov #3,r4
    mov.l intro_smpc,r0
    jsr @r0
    nop
    ! Preserve helper result for postmortem; timeout is bounded, never a hang.
    mov.l intro_smpc_result,r1
    mov.l r0,@r1
    mov.l intro_ireg_shadow,r1
    mov.b @r1,r0
    or #0x10,r0
    mov.b r0,@r1
    mov.l intro_ireg,r1
    mov.b r0,@r1
    mov.l intro_bcr,r1
    mov.l @r1,r0
    mov #-2,r2
    and r2,r0
    mov.l r0,@r1
    bsr intro_scu_reset
    nop
    ! Purge while CE stays enabled. CP invalidates all ways, replacing the
    ! BIOS's manual address-array clear without turning caching off.
    mov.l intro_ccr,r1
    mov #0x11,r0
    mov.b r0,@r1
    bsr intro_onchip_reset
    nop
    bsr intro_vectors
    nop
    mov.l intro_panel_init_ptr,r0
    jsr @r0
    nop
    bsr intro_slots
    nop
    mov.l intro_vbr,r1
    ldc r1,vbr
    mov.l intro_mask_set,r0
    mov.l intro_shadow_reset,r1
    mov.l @r1,r4
    jsr @r0
    nop
    mov #0,r0
    ldc r0,sr
    ! Display-off only after the system reinit, matching the outer service.
    mov.l intro_tvmd,r1
    mov.w @r1,r0
    extu.w r0,r0
    mov r0,r4
    shll16 r0
    cmp/pz r0
    bt intro_display_done
    mov r4,r0
    and #1,r0
    mov r0,r4
    mov.l intro_tvstat,r2
    mov.l intro_video_timeout,r3
intro_wait_vblank:
    mov.w @r2,r0
    tst #8,r0
    bf intro_display_write
    dt r3
    bf intro_wait_vblank
intro_display_write:
    mov.w r4,@r1
intro_display_done:
    lds.l @r15+,pr
    rts
    nop
    .align 2
intro_work_flags: .long 0x06000824
intro_panel_init_ptr: .long 0x0600fe10
intro_mask_update: .long stv_resident_mask_update
intro_mask_set: .long stv_resident_mask_set
intro_smpc: .long stv_smpc_command
intro_smpc_result: .long 0x2021e040
intro_ireg_shadow: .long 0x0600065b
intro_ireg: .long 0x20100077
intro_bcr: .long 0xffffffb0
intro_ccr: .long 0xfffffe92
intro_vbr: .long 0x06000000
intro_shadow_reset: .long 0x06000348
intro_tvmd: .long 0x25f80000
intro_tvstat: .long 0x25f80004
intro_video_timeout: .long 0x00100000
intro_reset_mask: .word 0x7ffe
    .align 2

intro_scu_reset:
    ! Three DMA groups: six longs zero, mode=7; 0x1c reserved untouched.
    mov.l intro_scu_base,r1
    mov #3,r3
    mov #0,r0
intro_dma_group:
    mov #6,r2
intro_dma_register:
    mov.l r0,@r1
    add #4,r1
    dt r2
    bf intro_dma_register
    mov #7,r2
    mov.l r2,@r1
    add #8,r1
    dt r3
    bf intro_dma_group
    mov.l intro_scu_values,r1
intro_scu_values_loop:
    mov.l @r1+,r2
    tst r2,r2
    bt intro_scu_values_done
    mov.l @r1+,r0
    mov.l r0,@r2
    bra intro_scu_values_loop
    nop
intro_scu_values_done:
    mov.l intro_mode_flags,r1
    mov.l @r1,r0
    tst #8,r0
    mov #13,r2
    bt intro_mode_ready
    mov #12,r2
intro_mode_ready:
    mov.l intro_mode_port,r1
    mov.w r2,@r1
    rts
    nop
    .align 2
intro_scu_base: .long 0x25fe0000
intro_mode_flags: .long 0x06000248
intro_mode_port: .long 0x257ffffc
intro_scu_values: .long intro_scu_data
intro_scu_data:
    .long 0x25fe0060,0, 0x25fe0080,0
    .long 0x25fe00b0,0x1ff01ff0, 0x25fe00b4,0x1ff01ff0
    .long 0x25fe00b8,0x1f, 0x25fe00a8,1
    .long 0x25fe0090,0x3ff, 0x25fe0094,0x1ff, 0x25fe0098,0
    .long 0,0

! On-chip reset leaves GBR=0xfffffe00 as the BIOS chain does.
intro_onchip_reset:
    mov.l intro_onchip_base,r3
    ldc r3,gbr
    mov #1,r0
    mov.w r0,@(224,gbr)
    mov #0,r0
    mov.w r0,@(226,gbr)
    mov.w intro_ipra,r0
    mov.w r0,@(96,gbr)
    mov.w intro_vcra,r0
    mov.w r0,@(98,gbr)
    mov.w intro_vcrb,r0
    mov.w r0,@(100,gbr)
    mov.w intro_vcrc,r0
    mov.w r0,@(102,gbr)
    mov.w intro_vcrd,r0
    mov.w r0,@(104,gbr)
    mov.w intro_vcrwdt,r0
    mov.w r0,@(228,gbr)
    mov #0x6c,r0
    mov.l r0,@(424,gbr)
    mov #0x6d,r0
    mov.l r0,@(416,gbr)
    mov #0x6e,r0
    mov.l r0,@(268,gbr)
    mov #0x81,r0
    mov.b r0,@(16,gbr)
    rts
    nop
    .align 2
intro_onchip_base: .long 0xfffffe00
intro_ipra: .word 0x0100
intro_vcra: .word 0x6061
intro_vcrb: .word 0x6263
intro_vcrc: .word 0x6465
intro_vcrd: .word 0x6600
intro_vcrwdt: .word 0x6869
    .align 2

! Reset both 0x200-byte vector pages, without copying any ROM data or
! clearing unrelated work state. Shared native IRQ wrappers dispatch callbacks.
intro_vectors:
    sts.l pr,@-r15
    mov.l intro_master_page,r1
    bsr intro_vector_page
    nop
    mov.l intro_slave_page,r1
    bsr intro_vector_page
    nop
    mov.l intro_master_page,r1
    add #0x7f,r1
    add #0x7f,r1
    add #2,r1
    mov.l intro_vblank_handler,r0
    mov.l r0,@r1
    add #4,r1
    add #6,r0
    mov.l r0,@r1
    add #0x28,r1
    add #6,r0
    mov.l r0,@r1
    add #8,r1
    add #6,r0
    mov.l r0,@r1
    ! All SCU sources need a dispatcher wrapper: the SCU masks every
    ! source on vector fetch, so a bare RTE permanently loses interrupts.
    mov.l intro_scu_vectors,r1
    mov.l intro_scu_entries,r3
    mov #32,r2
intro_scu_vector_loop:
    mov.l @r3+,r0
    mov.l r0,@r1
    add #4,r1
    dt r2
    bf intro_scu_vector_loop
    mov.l intro_callbacks,r1
    mov.l intro_default_callback,r0
    mov #32,r2
intro_callback_loop:
    mov.l r0,@r1
    add #4,r1
    dt r2
    bf intro_callback_loop
    ! Rebuild native defaults from interrupt levels/mask relationships.
    bsr intro_priority_reset
    nop
    ! intro_vectors calls a local helper: restore its caller via saved PR.
    lds.l @r15+,pr
    rts
    nop
intro_vector_page:
    ! First call pushes the outer PR in the entry shim below.
    mov.l intro_default_vector,r0
    mov #0x7f,r2
    add #1,r2
intro_page_loop:
    mov.l r0,@r1
    add #4,r1
    dt r2
    bf intro_page_loop
    add #-128,r1
    add #-128,r1
    add #-128,r1
    add #-128,r1
    mov.l intro_fatal_vector,r0
    mov #12,r2
intro_fatal_loop:
    mov.l r0,@r1
    add #4,r1
    dt r2
    bf intro_fatal_loop
    rts
    nop
    .align 2
intro_master_page: .long 0x06000000
intro_slave_page: .long 0x06000400
intro_default_vector: .long stv_resident_irq_return
intro_fatal_vector: .long stv_resident_exception
intro_vblank_handler: .long stv_resident_vblank
intro_callbacks: .long 0x06000a00
intro_default_callback: .long stv_resident_noop
intro_priority_table: .long 0x2021f100
intro_scu_vectors: .long 0x06000100
intro_scu_entries: .long intro_scu_entry_table

! ST-V PDR2 bit4 resets the sound CPU; Saturn requires SMPC commands.
! Original upload routine remains intact; preserve its complete result state.
    .align 2
intro_sound_boot:
    sts.l pr,@-r15
    stc.l sr,@-r15
    mov.l r0,@-r15
    mov.l r1,@-r15
    mov.l r2,@-r15
    mov.l r3,@-r15
    mov.l r4,@-r15
    mov.l r5,@-r15
    mov.l r6,@-r15
    mov.l r7,@-r15
    mov #0xf0,r0
    extu.b r0,r0
    ldc r0,sr
    mov #7,r4
    mov.l intro_sound_command,r0
    jsr @r0
    nop
    mov.l @r15+,r7
    mov.l @r15+,r6
    mov.l @r15+,r5
    mov.l @r15+,r4
    mov.l @r15+,r3
    mov.l @r15+,r2
    mov.l @r15+,r1
    mov.l @r15+,r0
    ldc.l @r15+,sr
    mov.l intro_sound_original,r0
    jsr @r0
    nop
    stc.l sr,@-r15
    mov.l r0,@-r15
    mov.l r1,@-r15
    mov.l r2,@-r15
    mov.l r3,@-r15
    mov.l r4,@-r15
    mov.l r5,@-r15
    mov.l r6,@-r15
    mov.l r7,@-r15
    mov #0xf0,r0
    extu.b r0,r0
    ldc r0,sr
    mov #6,r4
    mov.l intro_sound_command,r0
    jsr @r0
    nop
    mov.l @r15+,r7
    mov.l @r15+,r6
    mov.l @r15+,r5
    mov.l @r15+,r4
    mov.l @r15+,r3
    mov.l @r15+,r2
    mov.l @r15+,r1
    mov.l @r15+,r0
    ldc.l @r15+,sr
    lds.l @r15+,pr
    rts
    nop
    .align 2
intro_sound_original: .long 0x060c77b8
intro_sound_command: .long stv_smpc_command

    .align 2
intro_scu_entry_table:
    .long intro_irq_0
    .long intro_irq_1
    .long intro_irq_2
    .long intro_irq_3
    .long intro_irq_4
    .long intro_irq_5
    .long intro_irq_6
    .long intro_irq_7
    .long intro_irq_8
    .long intro_irq_9
    .long intro_irq_a
    .long intro_irq_b
    .long intro_irq_c
    .long intro_irq_d
    .long intro_irq_e
    .long intro_irq_f
    .long intro_irq_10
    .long intro_irq_11
    .long intro_irq_12
    .long intro_irq_13
    .long intro_irq_14
    .long intro_irq_15
    .long intro_irq_16
    .long intro_irq_17
    .long intro_irq_18
    .long intro_irq_19
    .long intro_irq_1a
    .long intro_irq_1b
    .long intro_irq_1c
    .long intro_irq_1d
    .long intro_irq_1e
    .long intro_irq_1f
    .align 2
intro_irq_0:
    mov.l r0,@-r15
    mov #0x40,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_0,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_0: .long cd_extended_irq_dispatch
    .align 2
intro_irq_1:
    mov.l r0,@-r15
    mov #0x41,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_1,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_1: .long cd_extended_irq_dispatch
    .align 2
intro_irq_2:
    mov.l r0,@-r15
    mov #0x42,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_2,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_2: .long cd_extended_irq_dispatch
    .align 2
intro_irq_3:
    mov.l r0,@-r15
    mov #0x43,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_3,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_3: .long cd_extended_irq_dispatch
    .align 2
intro_irq_4:
    mov.l r0,@-r15
    mov #0x44,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_4,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_4: .long cd_extended_irq_dispatch
    .align 2
intro_irq_5:
    mov.l r0,@-r15
    mov #0x45,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_5,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_5: .long cd_extended_irq_dispatch
    .align 2
intro_irq_6:
    mov.l r0,@-r15
    mov #0x46,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_6,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_6: .long cd_extended_irq_dispatch
    .align 2
intro_irq_7:
    mov.l r0,@-r15
    mov #0x47,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_7,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_7: .long cd_extended_irq_dispatch
    .align 2
intro_irq_8:
    mov.l r0,@-r15
    mov #0x48,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_8,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_8: .long cd_extended_irq_dispatch
    .align 2
intro_irq_9:
    mov.l r0,@-r15
    mov #0x49,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_9,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_9: .long cd_extended_irq_dispatch
    .align 2
intro_irq_a:
    mov.l r0,@-r15
    mov #0x4a,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_a,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_a: .long cd_extended_irq_dispatch
    .align 2
intro_irq_b:
    mov.l r0,@-r15
    mov #0x4b,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_b,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_b: .long cd_extended_irq_dispatch
    .align 2
intro_irq_c:
    mov.l r0,@-r15
    mov #0x4c,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_c,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_c: .long cd_extended_irq_dispatch
    .align 2
intro_irq_d:
    mov.l r0,@-r15
    mov #0x4d,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_d,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_d: .long cd_extended_irq_dispatch
    .align 2
intro_irq_e:
    mov.l r0,@-r15
    mov #0x4e,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_e,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_e: .long cd_extended_irq_dispatch
    .align 2
intro_irq_f:
    mov.l r0,@-r15
    mov #0x4f,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_f,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_f: .long cd_extended_irq_dispatch
    .align 2
intro_irq_10:
    mov.l r0,@-r15
    mov #0x50,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_10,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_10: .long cd_extended_irq_dispatch
    .align 2
intro_irq_11:
    mov.l r0,@-r15
    mov #0x51,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_11,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_11: .long cd_extended_irq_dispatch
    .align 2
intro_irq_12:
    mov.l r0,@-r15
    mov #0x52,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_12,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_12: .long cd_extended_irq_dispatch
    .align 2
intro_irq_13:
    mov.l r0,@-r15
    mov #0x53,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_13,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_13: .long cd_extended_irq_dispatch
    .align 2
intro_irq_14:
    mov.l r0,@-r15
    mov #0x54,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_14,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_14: .long cd_extended_irq_dispatch
    .align 2
intro_irq_15:
    mov.l r0,@-r15
    mov #0x55,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_15,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_15: .long cd_extended_irq_dispatch
    .align 2
intro_irq_16:
    mov.l r0,@-r15
    mov #0x56,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_16,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_16: .long cd_extended_irq_dispatch
    .align 2
intro_irq_17:
    mov.l r0,@-r15
    mov #0x57,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_17,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_17: .long cd_extended_irq_dispatch
    .align 2
intro_irq_18:
    mov.l r0,@-r15
    mov #0x58,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_18,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_18: .long cd_extended_irq_dispatch
    .align 2
intro_irq_19:
    mov.l r0,@-r15
    mov #0x59,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_19,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_19: .long cd_extended_irq_dispatch
    .align 2
intro_irq_1a:
    mov.l r0,@-r15
    mov #0x5a,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_1a,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_1a: .long cd_extended_irq_dispatch
    .align 2
intro_irq_1b:
    mov.l r0,@-r15
    mov #0x5b,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_1b,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_1b: .long cd_extended_irq_dispatch
    .align 2
intro_irq_1c:
    mov.l r0,@-r15
    mov #0x5c,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_1c,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_1c: .long cd_extended_irq_dispatch
    .align 2
intro_irq_1d:
    mov.l r0,@-r15
    mov #0x5d,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_1d,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_1d: .long cd_extended_irq_dispatch
    .align 2
intro_irq_1e:
    mov.l r0,@-r15
    mov #0x5e,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_1e,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_1e: .long cd_extended_irq_dispatch
    .align 2
intro_irq_1f:
    mov.l r0,@-r15
    mov #0x5f,r0
    mov.l r1,@-r15
    mov.l intro_irq_ptr_1f,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
intro_irq_ptr_1f: .long cd_extended_irq_dispatch

! BIOS 3a9c/4908: rebuild the selected backup header and its mirror.
! The 54-byte default template is statically verified to be all zero.
    .align 2
intro_backup_reset:
    sts.l pr,@-r15
    mov.l intro_backup_channel,r1
    mov.b @r1,r0
    extu.b r0,r0
    mov r0,r2
    shll r2
    mov.l intro_backup_lengths,r1
    add r2,r1
    mov.w @r1,r6
    extu.w r6,r6
    shll2 r0
    shll2 r0
    shll2 r0
    mov.l intro_backup_records,r5
    add r0,r5
    mov #2,r4
    mov.l intro_backup_access,r0
    jsr @r0
    nop
    ! Recompute the record start; backup API advances R5.
    mov.l intro_backup_channel,r1
    mov.b @r1,r0
    extu.b r0,r0
    shll2 r0
    shll2 r0
    shll2 r0
    mov.l intro_backup_records,r1
    add r0,r1
    add #4,r1
    mov #54,r2
    mov #0,r0
intro_backup_clear:
    mov.b r0,@r1
    add #1,r1
    dt r2
    bf intro_backup_clear
    mov.l intro_backup_payload,r4
    mov.w intro_backup_payload_size,r5
    bsr intro_backup_checksum
    nop
    mov r0,r6
    mov.l intro_backup_header,r5
    mov #2,r4
    mov.l intro_backup_access,r0
    jsr @r0
    nop
    mov.l intro_backup_header,r5
    mov.l intro_backup_mirror,r4
    mov #96,r6
intro_backup_mirror_loop:
    mov.l @r5+,r1
    mov.l r1,@r4
    add #4,r4
    dt r6
    bf intro_backup_mirror_loop
    lds.l @r15+,pr
    rts
    nop
    .align 2
intro_backup_channel: .long 0x06000650
intro_backup_lengths: .long 0x060006b8
intro_backup_records: .long 0x20223d80
intro_backup_header: .long 0x20223d00
intro_backup_payload: .long 0x20223d04
intro_backup_mirror: .long 0x20223e80
intro_backup_access: .long cd_backup_access
intro_backup_payload_size: .word 0x17c
    .align 2
! CRC-like sparse-byte checksum; R4 physical address, R5 physical bytes.
! Each stored byte occupies the low lane of a word. Same arithmetic as
! resident 060013e6, written natively rather than copying its instructions.
intro_backup_checksum:
    mov.l intro_crc_seed,r0
    mov.l intro_crc_polynomial,r3
    shlr r5
intro_crc_byte:
    mov.w @r4+,r1
    extu.b r1,r1
    or r1,r0
    mov #8,r2
intro_crc_bit:
    shll r0
    bf intro_crc_no_xor
    xor r3,r0
intro_crc_no_xor:
    dt r2
    bf intro_crc_bit
    dt r5
    bf intro_crc_byte
    mov #8,r2
intro_crc_finish:
    shll r0
    bf intro_crc_finish_no_xor
    xor r3,r0
intro_crc_finish_no_xor:
    dt r2
    bf intro_crc_finish
    rts
    shlr16 r0
    .align 2
intro_crc_seed: .long 0xdebdeb00
intro_crc_polynomial: .long 0x10210000

    .align 2
intro_priority_reset:
    mov.l intro_priority_destination,r1
    mov #32,r2
    mov #0,r3
intro_priority_entry:
    mov #7,r4
    cmp/hs r4,r3
    bt intro_priority_lower
    mov #0xf0,r4
    extu.b r4,r4
    mov r3,r5
    shll2 r5
    shll2 r5
    sub r5,r4
    mov #-1,r0
    mov r3,r5
    tst r5,r5
    bt intro_priority_combine
intro_priority_shift:
    shll r0
    dt r5
    bf intro_priority_shift
    bra intro_priority_combine
    nop
intro_priority_lower:
    mov #9,r4
    cmp/hs r4,r3
    bt intro_priority_lowest
    mov #0x80,r4
    extu.b r4,r4
    mov #-128,r0
    bra intro_priority_combine
    nop
intro_priority_lowest:
    mov #0x70,r4
    mov #-2,r0
    shll8 r0
intro_priority_combine:
    shll16 r4
    extu.w r0,r0
    or r4,r0
    mov.l r0,@r1
    add #4,r1
    add #1,r3
    dt r2
    bf intro_priority_entry
    rts
    nop
    .align 2
intro_priority_destination: .long 0x2021f100
