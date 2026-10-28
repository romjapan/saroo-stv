! Experimental one-window HBlank worker. Dispatcher caller registers saved.
    .text
    .org 0x4d00,0
cd_pad_window_dispatch:
    sts.l pr,@-r15
    mov.l r7,@-r15
    mov.l r4,@-r15
    bsr cd_pad_frame_clock
    nop
    mov.l @r15+,r4
    mov r4,r0
    cmp/eq #0x40,r0
    bt window_arm
    cmp/eq #0x41,r0
    bt window_disable
    cmp/eq #0x42,r0
    bf window_return
    bsr cd_pad_timed_poll
    nop
    mov.l window_pad_state,r1
    mov.b @r1,r0
    tst r0,r0
    bf window_disable
    mov.l window_clock,r1
    mov.l @(12,r1),r0
    tst r0,r0
    bt window_disable
    bra window_return
    nop
window_arm:
    mov.l window_main,r1
    mov.l @r1,r0
    tst r0,r0
    bt window_return
    mov.l window_handler,r1
    mov.l @r1,r0
    tst r0,r0
    bf window_return
    mov.l window_vector,r1
    mov.l @r1,r0
    mov.l window_entry_ptr,r2
    cmp/eq r2,r0
    bt window_owned
    mov.l window_default_vector,r3
    cmp/eq r3,r0
    bf window_return
    mov.l r2,@r1
window_owned:
    mov.l window_pad_state,r1
    mov.b @r1,r0
    tst r0,r0
    bf window_return
    mov.l window_ist,r1
    mov #-5,r0
    mov.l r0,@r1
    mov.l window_mask,r1
    mov.l @r1,r0
    mov #-5,r2
    and r2,r0
    bra window_write_mask
    nop
window_disable:
    mov.l window_vector,r1
    mov.l @r1,r0
    mov.l window_entry_ptr,r2
    cmp/eq r2,r0
    bf window_return
    mov.l window_mask,r1
    mov.l @r1,r0
    or #4,r0
window_write_mask:
    mov.l r0,@r1
    mov.l window_ims,r1
    mov.l r0,@r1
window_return:
    mov.l @r15+,r7
    lds.l @r15+,pr
    rts
    nop
    .align 2
window_main: .long 0x2021f02c
window_handler: .long 0x06000908
window_vector: .long 0x06000108
window_default_vector: .long stv_resident_irq_return
window_entry_ptr: .long cd_pad_hblank_entry
window_pad_state: .long 0x06000be0
window_clock: .long 0x2021f060
window_mask: .long 0x06000348
window_ims: .long 0x25fe00a0
window_ist: .long 0x25fe00a4
cd_pad_hblank_entry:
    mov.l r0,@-r15
    mov #0x42,r0
    mov.l r1,@-r15
    mov.l window_dispatch_ptr,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
window_dispatch_ptr: .long cd_extended_irq_dispatch
