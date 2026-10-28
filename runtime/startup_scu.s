! Experimental master-SH2 SCU services for the original Baku initializer.
! Linked after the isolated NV module. All data remains in owned LWRAM.
    .org 0x1e00,0
cd_scu_install:
    sts.l pr,@-r15
    mov.l cd_original_install,r0
    jsr @r0
    nop
    mov.l cd_priority_data,r1
    mov #32,r2
    mov #-1,r0
cd_priority_default:
    mov.l r0,@r1
    add #4,r1
    dt r2
    bf cd_priority_default
    mov.l cd_slot_280,r1
    mov.l cd_priority_entry,r0
    mov.l r0,@r1
    mov.l cd_slot_300,r1
    mov.l cd_register_entry,r0
    mov.l r0,@r1
    mov.l cd_slot_340,r1
    mov.l cd_mask_entry,r0
    mov.l r0,@r1
    mov.l cd_mask_change_entry,r0
    mov.l r0,@(4,r1)
    mov.l cd_vector_49,r1
    mov.l cd_irq_49_ptr,r0
    mov.l r0,@r1
    mov.l cd_irq_4a_ptr,r0
    mov.l r0,@(4,r1)
    mov.l cd_irq_4c_ptr,r0
    mov.l r0,@(12,r1)
    lds.l @r15+,pr
    rts
    nop
    .align 2
cd_priority_data: .long 0x2021f100
cd_original_install: .long stv_install_resident_veneers
cd_slot_280: .long 0x06000280
cd_slot_300: .long 0x06000300
cd_slot_340: .long 0x06000340
cd_priority_entry: .long cd_scu_priority
cd_register_entry: .long cd_scu_register
cd_mask_entry: .long cd_scu_mask_set
cd_mask_change_entry: .long cd_scu_mask_change
cd_vector_49: .long 0x06000124
cd_irq_49_ptr: .long cd_irq_49
cd_irq_4a_ptr: .long cd_irq_4a
cd_irq_4c_ptr: .long cd_irq_4c
cd_scu_priority:
    mov.l cd_priority_data_copy,r1
    mov #32,r2
    mov r4,r3
cd_priority_copy:
    mov.l @r3+,r0
    mov.l r0,@r1
    add #4,r1
    dt r2
    bf cd_priority_copy
    rts
    nop
cd_scu_register:
    mov r4,r0
    add #-0x40,r0
    mov #31,r1
    cmp/hi r1,r0
    bt cd_scu_bad
    cmp/eq #14,r0
    bt cd_scu_bad
    cmp/eq #15,r0
    bt cd_scu_bad
    mov r4,r0
    shll2 r0
    mov.l cd_handlers,r1
    add r0,r1
    mov r5,r0
    tst r0,r0
    bf cd_register_store
    mov.l cd_noop,r0
cd_register_store:
    mov.l r0,@r1
    rts
    nop
cd_scu_mask_change:
    mov.l cd_mask_shadow,r1
    mov.l @r1,r0
    and r4,r0
    or r5,r0
    mov r0,r2
    mov r4,r0
    or r5,r0
    bra cd_mask_write
    nop
cd_scu_mask_set:
    mov r4,r2
    mov r4,r0
cd_mask_write:
    mov.l cd_mask_shadow,r1
    mov.l r2,@r1
    mov.l cd_ims,r1
    mov.l r2,@r1
    mov.w cd_abus_bit,r3
    extu.w r3,r3
    tst r3,r2
    bf cd_mask_status
    extu.w r0,r0
cd_mask_status:
    mov.l r0,@(4,r1)
    tst r3,r2
    bf cd_mask_return
    mov #1,r0
    mov.l r0,@(8,r1)
cd_mask_return:
    rts
    nop
cd_irq_49:
    mov.l r0,@-r15
    mov #0x49,r0
    bra cd_irq_jump
    nop
cd_irq_4a:
    mov.l r0,@-r15
    mov #0x4a,r0
    bra cd_irq_jump
    nop
cd_irq_4c:
    mov.l r0,@-r15
    mov #0x4c,r0
cd_irq_jump:
    mov.l r1,@-r15
    mov.l cd_dispatch,r1
    jmp @r1
    mov.l @r15+,r1
cd_scu_bad:
    mov.l cd_failure_trace,r1
    mov.l cd_failure_tag,r0
    mov.l r0,@r1
    mov.w cd_failure_code,r0
    mov.l r0,@(4,r1)
cd_scu_bad_spin:
    bra cd_scu_bad_spin
    nop
    .align 2
cd_handlers: .long 0x06000900
cd_priority_data_copy: .long 0x2021f100
cd_noop: .long stv_resident_noop
cd_mask_shadow: .long 0x06000348
cd_ims: .long 0x25fe00a0
cd_dispatch: .long cd_extended_irq_dispatch
cd_failure_trace: .long 0x2021e000
cd_failure_tag: .long 0x4641494c
cd_abus_bit: .word 0x8000
cd_failure_code: .word 0x0b02
