    .section .text
    .align 2
    .global _game_handoff
_game_handoff:
    ! Native handoff writes this IMS value to SCU. Its dispatcher restores
    ! the SOFTWARE shadow, not readable IMS (write-only on Saturn).
    ! The resident constructor's service-table fill leaves this slot holding
    ! an IRQ-return address; establish the matching mask before opening SR.
    mov.l mask_shadow,r1
    mov.l game_mask,r0
    mov.l r0,@r1
    mov.l vector_base,r0
    ldc r0,vbr
    ! The ST-V BIOS starts games with the cache on (CCR=1); our loader and
    ! hardware init leave it off (CCR=0x10). Real SAROO runs measured ~0.2
    ! main passes per VBlank with the master cache off. Purge + enable.
    mov.l cache_ccr,r1
    mov #0x11,r0
    mov.b r0,@r1
    mov #0,r4
    mov.l bootstrap,r0
    jmp @r0
    nop
    .align 2
vector_base: .long 0x06000000
bootstrap: .long 0x00210a00
mask_shadow: .long 0x06000348
game_mask: .long 0xffffe1fc
cache_ccr: .long 0xfffffe92
