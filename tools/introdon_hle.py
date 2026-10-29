"""Introdon-only adaptation after the shared manual profile is generated."""
from pathlib import Path
import re

def adapt(source):
    # Cold BIOS shadow initializer 1c8b0..1c8c2 leaves every cycle slot
    # unassigned (CPU access), not the measured Baku game layout.
    old='    .word 0x4455, 0x77FF, 0xFFFF, 0xFFFF\n    .word 0x3036, 0x0112, 0xFFFF, 0xFFFF'
    if source.count(old)!=1:raise ValueError('Unexpected VDP2 cold-cycle seam')
    source=source.replace(old,'    .word 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF\n    .word 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF')
    # Snapshot actual SMPC report before BREAK or another command changes OREG.
    # Digital ID02 and 3D ID16 share the first two digital data bytes. Do not
    # interpret disconnected/unsupported peripheral packets as button presses.
    anchor='    mov.l   smpc_oreg2_ptr, r2\n    mov.b   @r2, r4'
    if source.count(anchor)!=1:raise ValueError('Unexpected SMPC report seam')
    source=source.replace(anchor,'''    sts.l pr,@-r15
    mov.l intro_raw_call,r0
    jsr @r0
    nop
    lds.l @r15+,pr
    tst r0,r0
    bf intro_pad_supported
    mov #0,r4
    bra smpc_pad_values_ready
    mov #0,r5
intro_pad_supported:
    mov.l   smpc_oreg2_ptr, r2
    mov.b   @r2, r4''')
    source+='''
    .align 2
intro_raw_report:
    mov.l intro_raw_src,r2
    mov.l intro_raw_dst,r3
    mov #8,r4
intro_raw_copy:
    mov.b @r2,r0
    mov.b r0,@r3
    add #2,r2
    add #1,r3
    dt r4
    bf intro_raw_copy
    mov.l intro_raw_dst,r3
    mov.b @(1,r3),r0
    extu.b r0,r0
    cmp/eq #2,r0
    bt intro_raw_supported
    cmp/eq #0x16,r0
    bt intro_raw_supported
    rts
    mov #0,r0
intro_raw_supported:
    rts
    mov #1,r0
    .align 2
intro_raw_src: .long 0x20100021
intro_raw_dst: .long 0x2600a088
'''
    source=source.replace('cd_pad_cache_ptr: .long 0x06000BE8',
        'cd_pad_cache_ptr: .long 0x06000BE8\n'
        'intro_raw_call: .long intro_raw_report')
    # BIOS input service clears its raw ports before calling this hook. Replay
    # the packet acquired by the native frame dispatcher before edge/credit work.
    source=source.replace('input_pad_poll_ptr: .long cd_pad_after_main',
                          'input_pad_poll_ptr: .long stv_cd_pad_replay')
    source=source.replace('timed_min: .word 1200','timed_min: .word 0')
    # Introdon has its own frame loop; the Baku main-loop gate never opens.
    # Poll once per VBlank, so the asynchronous timeout still counts frames.
    # This native dispatcher runs at VBlank entry, before the game callback;
    # unlike Baku's delayed worker it needs no minimum elapsed-time gate.
    begin=source.index('cd_pad_window_dispatch:\n')
    end=source.index('    .align 2\nwindow_main:',begin)
    source=source[:begin]+'''cd_pad_window_dispatch:
    sts.l pr,@-r15
    mov.l r7,@-r15
    mov.l r4,@-r15
    bsr cd_pad_frame_clock
    nop
    mov.l @r15+,r4
    mov r4,r0
    cmp/eq #0x40,r0
    bf intro_pad_done
    bsr cd_pad_timed_poll
    nop
    mov.l intro_pad_publish,r0
    jsr @r0
    nop
intro_pad_done:
    mov.l @r15+,r7
    lds.l @r15+,pr
    rts
    nop
    .align 2
intro_pad_publish: .long cd_resident_game_ports
'''+source[end:]
    anchor='resident_veneer_installer_ptr: .long cd_scu_install'
    if source.count(anchor)!=1:
        raise ValueError('Unexpected introdon constructor seam')
    source=source.replace(anchor,'resident_veneer_installer_ptr: .long intro_install')
    source=source.replace('resident_game_vblank:     .long 0x06035278',
                          'resident_game_vblank:     .long stv_resident_noop')
    source=source.replace('resident_game_aux:        .long 0x06035C48',
                          'resident_game_aux:        .long stv_resident_noop')
    # Game handlers do not acknowledge IST themselves. Without clearing the
    # source, restoring IMS immediately re-enters the same interrupt forever.
    anchor='resident_scu_irq_lookup:\n'
    if source.count(anchor)!=1:
        raise ValueError('Unexpected SCU acknowledgement seam')
    source=source.replace(anchor,anchor+'''    mov r7,r2
    add #-0x40,r2
    mov #1,r0
    tst r2,r2
    bt intro_irq_ack_ready
intro_irq_ack_shift:
    shll r0
    dt r2
    bf intro_irq_ack_shift
intro_irq_ack_ready:
    not r0,r0
    mov.l cd_extended_resident_scu_ims_irq,r3
    mov.l r0,@(4,r3)
''')
    # This is a Baku patch installer, not a BIOS service. Introdon publishes
    # the same native port mirror; its guarded literal patches live in loader.
    begin=source.index('cd_resident_game_ports_install:\n')
    end=source.index('\t.size\tcd_resident_game_ports_install',begin)
    source=source[:begin]+'''cd_resident_game_ports_install:
    sts.l pr,@-r15
    mov.l intro_publish_ports,r0
    jsr @r0
    nop
    lds.l @r15+,pr
    rts
    mov #0,r0
    .align 2
intro_publish_ports: .long cd_resident_game_ports
'''+source[end:]
    source+='\n'+(Path(__file__).resolve().parents[1]/'runtime/introdon_services.s').read_text()
    source=source.replace('resident_clear_longs:     .long 0x00003C00',
                          'resident_clear_longs:     .long 0x00001000')
    return relocate_owned_addresses(source)


def relocate_owned_addresses(source):
    # The game owns LWRAM. Keep resident code/data in the reserved BIOS page:
    # 4000..9fff code, a000..a7ff scratch, a800..afff trace, b000..efff backup.
    source=source.replace('0x2018fffc','0x20183ffc').replace('0x2018fff8','0x20183ff8')
    source=source.replace('0x2022fffc','0x20223ffc').replace('0x2022fff8','0x20223ff8')
    source=source.replace('backup_delta: .long 0x000a0000',
                          'backup_delta: .long 0x05e8b000')
    def relocate_value(value):
        physical=value & 0x1fffffff
        uncached=value & 0x20000000
        if 0x0021f000<=physical<0x00220000:
            return hex(uncached| (0x0600a000+physical-0x0021f000))
        if 0x0021e000<=physical<0x0021e800:
            return hex(uncached| (0x0600a800+physical-0x0021e000))
        if 0x00210000<=physical<0x00216000:
            return hex(uncached| (0x06004000+physical-0x00210000))
        if 0x00220000<=physical<0x00224000:
            return hex(uncached| (0x0600b000+physical-0x00220000))
        return None
    source=re.sub(r'(?m)^(\s*\.long\s+)([0-9]{6,})(\s*)$',
        lambda m:m[1]+(relocate_value(int(m[2])) or m[2])+m[3],source)
    return re.sub(r'0x[0-9a-fA-F]+',
        lambda m:relocate_value(int(m.group(),16)) or m.group(),source)
