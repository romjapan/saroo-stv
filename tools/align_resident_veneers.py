"""Install SH-2 absolute veneers at either legal instruction alignment."""

OLD = '''    mov.l   resident_abs_op0, r0
    mov.l   r0, @r2
    mov.l   resident_abs_op1, r0
    mov.l   r0, @(4, r2)
    mov.l   r3, @(8, r2)'''

def adapt(source):
    if source.count(OLD) != 1:
        raise ValueError('Unexpected resident veneer installer')
    if source.count('resident_abs_op0:    .long 0xD001402B') != 1:
        raise ValueError('Unexpected resident veneer writer literal')
    source=source.replace(OLD,'''    mov.l   resident_abs_op0, r0
    jmp     @r0
    nop''')
    source=source.replace('resident_abs_op0:    .long 0xD001402B',
                          'resident_abs_op0:    .long cd_aligned_veneer_writer')
    # Keep this outside the original fixed .org slots. The instruction stream
    # is halfword aligned, but the PC-relative literal MUST be long aligned.
    return source+'''
    .align 2
cd_aligned_veneer_writer:
    mov.w cd_veneer_load_op,r0
    mov.w r0,@r2
    add #2,r2
    mov.w cd_veneer_jump_op,r0
    mov.w r0,@r2
    add #2,r2
    mov #9,r0
    mov.w r0,@r2
    add #2,r2
    mov r2,r0
    tst #2,r0
    bt cd_veneer_literal_aligned
    mov #9,r0
    mov.w r0,@r2
    add #2,r2
cd_veneer_literal_aligned:
    mov.l r3,@r2
    mov.l cd_veneer_loop_ptr,r0
    jmp @r0
    nop
    .align 2
cd_veneer_loop_ptr: .long resident_veneer_loop
cd_veneer_load_op: .word 0xd001
cd_veneer_jump_op: .word 0x402b
'''
