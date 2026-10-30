! BIOS-page fe00..ffff: NMI latches TEST; native main-loop/wait adapters
! run foreground work. Every original register result is preserved.
.text
    mov.l tick_ptr,r0
    jmp @r0
    nop
.align 2
tick_ptr: .long panel_tick
.org 0x10
    mov.l init_ptr,r0
    jmp @r0
    nop
.align 2
init_ptr: .long panel_init
.org 0x20
panel_tick:
    mov.l state_ptr,r1
    mov.l @r1,r0
    tst r0,r0
    bt combo
    add #-1,r0
    mov.l r0,@r1
combo:
    mov.l id_ptr,r2
    mov.b @r2,r0
    cmp/eq #2,r0
    bt valid
    cmp/eq #0x16,r0
    bf clear
valid:
    mov.l raw_ptr,r2
    mov.b @r2,r0
    not r0,r0
    and #15,r0
    cmp/eq #15,r0
    bt held
clear:
    mov #0,r0
    mov.l r0,@(4,r1)
    rts
    nop
held:
    mov.l @(4,r1),r0
    add #1,r0
    mov.l r0,@(4,r1)
    cmp/eq #120,r0
    bf tick_return
    mov.l exit_ptr,r2
    mov #1,r0
    mov.l r0,@r2
tick_return:
    rts
    nop
.align 2
state_ptr: .long 0x2600a0d0
raw_ptr: .long 0x2600a08a
id_ptr: .long 0x2600a089
exit_ptr: .long 0x2600a0e0
panel_init:
    mov.l vector_ptr,r1
    mov.l nmi_ptr,r0
    mov.l r0,@r1
    mov #25,r4
    mov.l command_ptr,r0
    jmp @r0
    nop
.align 2
vector_ptr: .long 0x2600002c
command_ptr: .long PANEL_COMMAND
nmi_ptr: .long panel_nmi
panel_nmi:
    mov.l r0,@-r15
    mov.l r1,@-r15
    mov.l pulse_ptr,r1
    mov #60,r0
    mov.l r0,@r1
    mov #1,r0
    mov.l r0,@(24,r1)
    mov.l @r15+,r1
    mov.l @r15+,r0
    rte
    nop
.align 2
pulse_ptr: .long 0x2600a0d0
.org 0xc0
main_adapter:
    sts.l pr,@-r15
    mov.l main_native,r0
    jsr @r0
    nop
    bsr work
    nop
    lds.l @r15+,pr
    rts
    nop
.align 2
main_native: .long 0x0602f780
.org 0xe0
wait_adapter:
    sts.l pr,@-r15
    mov.l wait_native,r0
    jsr @r0
    nop
    bsr work
    nop
    lds.l @r15+,pr
    rts
    nop
.align 2
wait_native: .long 0x0603bc88
.org 0x100
work:
    sts.l pr,@-r15
    mov.l r0,@-r15
    mov.l r1,@-r15
    mov.l r2,@-r15
    mov.l r3,@-r15
    mov.l r4,@-r15
    mov.l r5,@-r15
    mov.l r6,@-r15
    mov.l r7,@-r15
    sts.l mach,@-r15
    sts.l macl,@-r15
    stc.l sr,@-r15
    stc sr,r0
    mov.l last_sr,r1
    mov.l r0,@r1
    and #0xf0,r0
    tst r0,r0
    bf restore
    mov #0xf0,r0
    extu.b r0,r0
    ldc r0,sr
    mov.l persist_ptr,r0
    jsr @r0
    nop
    mov.l request_ptr,r1
    mov.l @r1,r0
    tst r0,r0
    bt restore
    mov.l mode_ptr,r2
    mov.l @r2,r0
    cmp/eq #1,r0
    bf enter_test
    mov #0,r0
    mov.l r0,@r1
    bra restore
    nop
enter_test:
    mov #0,r0
    mov.l r0,@r1
    add #-24,r1
    mov.l r0,@r1
    mov.l depth_ptr,r1
    mov.l r0,@r1
    mov.l stack_ptr,r15
    mov.l test_ptr,r0
    jmp @r0
    nop
restore:
    ldc.l @r15+,sr
    lds.l @r15+,macl
    lds.l @r15+,mach
    mov.l @r15+,r7
    mov.l @r15+,r6
    mov.l @r15+,r5
    mov.l @r15+,r4
    mov.l @r15+,r3
    mov.l @r15+,r2
    mov.l @r15+,r1
    mov.l @r15+,r0
    lds.l @r15+,pr
    rts
    nop
.align 2
last_sr: .long 0x2600a0e4
persist_ptr: .long 0x0600bc00
request_ptr: .long 0x2600a0e8
mode_ptr: .long 0x2609eacc
depth_ptr: .long 0x2600a010
stack_ptr: .long 0x06100000
test_ptr: .long 0x06010020
.org 0x1b0
query_adapter:
    sts.l pr,@-r15
    mov.l query_native,r0
    jsr @r0
    nop
    bsr work
    nop
    lds.l @r15+,pr
    rts
    nop
.align 2
query_native: .long 0x0602c9da
.org 0x1d0
test_adapter:
    ! Verified native TEST EXIT calls BIOS60c with R4=2, non-returning.
    mov #0xf0,r0
    extu.b r0,r0
    ldc r0,sr
    mov #0,r0
    mov.l test_pulse,r1
    mov.l r0,@r1
    mov.l r0,@(24,r1)
    mov.l test_depth,r1
    mov.l r0,@r1
    mov.l test_stack,r15
    mov.l normal_entry,r0
    jmp @r0
    nop
.align 2
test_pulse: .long 0x2600a0d0
test_depth: .long 0x2600a010
test_stack: .long 0x06100000
normal_entry: .long 0x06010000
