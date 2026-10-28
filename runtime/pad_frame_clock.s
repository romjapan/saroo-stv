! Read-only FRT stamp. Called after IRQ dispatcher has saved caller registers.
! r4 = SCU vector. State: FRC, TCR, FTCSR, valid. Observation only.
    .text
    .org 0x4a00,0
cd_pad_frame_clock:
    mov r4,r0
    cmp/eq #0x40,r0
    bt cd_pad_stamp
    cmp/eq #0x41,r0
    bf cd_pad_clock_return
    mov.l cd_pad_clock_state,r1
    mov #0,r0
    mov.l r0,@(12,r1)
    rts
    nop
cd_pad_stamp:
    ! Diagnostic VBlank-in counter (0x2021f070) for frame-rate measurement.
    mov.l cd_pad_vbl_count,r1
    mov.l @r1,r0
    add #1,r0
    mov.l r0,@r1
    stc.l sr,@-r15
    stc sr,r0
    or #0xf0,r0
    ldc r0,sr
    mov.l cd_pad_frc,r1
    mov.b @r1,r0
    extu.b r0,r0
    shll8 r0
    add #1,r1
    mov.b @r1,r2
    extu.b r2,r2
    or r2,r0
    mov.l cd_pad_clock_state,r2
    mov.l r0,@r2
    add #3,r1
    mov.b @r1,r0
    extu.b r0,r0
    mov.l r0,@(4,r2)
    add #-5,r1
    mov.b @r1,r0
    extu.b r0,r0
    mov.l r0,@(8,r2)
    mov #1,r0
    mov.l r0,@(12,r2)
    ldc.l @r15+,sr
cd_pad_clock_return:
    rts
    nop
    .align 2
cd_pad_frc: .long 0xfffffe12
cd_pad_clock_state: .long 0x2021f060
cd_pad_vbl_count: .long 0x2021f070
