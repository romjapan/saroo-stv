"""Relink existing native HLE into LWRAM for CD diagnostic calls only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import re
import os
from align_resident_veneers import adapt as align_resident_veneers

def hle_linker_script(base=0x00210000,limit=0x10000):
    # Let the selected SH linker choose its supported ELF format. Explicit
    # -EB at link time fixes target endianness without a binutils-specific name.
    return ('OUTPUT_ARCH(sh)\n'
        f'SECTIONS {{ . = 0x{base:08x}; .text : {{ *(.text*) *(.rodata*) }} '
        '/DISCARD/ : { *(.stack) *(.comment) *(.note*) } }\n'
        f'ASSERT(SIZEOF(.text) <= 0x{limit:x}, "HLE too large")\n')

def validate_factory_bios(bios):
    if len(bios)!=0x80000 or bios[0x672c:0x673c]!=bytes.fromhex('000000000100010100000000000808fd'):
        raise ValueError('Unrecognized ST-V BIOS factory configuration table')
    if bios[0x4b14:0x4b18]!=bytes.fromhex('0000672c') or bios[0x4b10:0x4b14]!=bytes.fromhex('06000780'):
        raise ValueError('Unrecognized original factory initializer literals')
    return bios[0x672c:0x673c]

def validate_credit_limits(bios):
    values=[int.from_bytes(bios[i:i+4],'big') for i in range(0x31c10,0x31c50,4)]
    if len(bios)!=0x80000 or values!=[24 if i==4 else 9 for i in range(16)]:
        raise ValueError('Unrecognized immutable resident credit-limit table')
    return values

def redirect_nvram_literals(source):
    literals=re.findall(r'0x2018[0-9a-fA-F]{4}',source)
    if len(literals)!=18:raise ValueError('Unexpected native backup-address inventory')
    return re.sub(r'0x2018[0-9a-fA-F]{4}',
        lambda m:hex(0x20220000+(int(m.group(),16)-0x20180000)),source)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument('--introdon-profile',action='store_true')
    p.add_argument("--output-dir",type=Path,default=Path("build/hle-ram"))
    p.add_argument("--software-input-shadow",action="store_true")
    p.add_argument("--irq-depth",action="store_true")
    p.add_argument("--hardware-cd-fixes",action="store_true")
    p.add_argument("--boot-static-input",action="store_true")
    p.add_argument("--software-nvram-shadow",action="store_true")
    p.add_argument("--startup-scu-services",action="store_true")
    p.add_argument("--cold-game-state",action="store_true")
    p.add_argument("--system-flag-slot",action="store_true")
    p.add_argument("--coin-trial",action="store_true")
    p.add_argument("--coin-at-poll",type=int,default=1200)
    p.add_argument("--coin-main-clock",action="store_true")
    p.add_argument("--resident-backup-callbacks",action="store_true")
    p.add_argument("--resident-input-edges",action="store_true")
    p.add_argument("--resident-player-input",action="store_true")
    p.add_argument("--resident-game-ports",action="store_true")
    p.add_argument("--resident-system-config",action="store_true")
    p.add_argument("--resident-session-stats",action="store_true")
    p.add_argument("--resident-factory-config",action="store_true")
    p.add_argument("--resident-state-publish",action="store_true")
    p.add_argument("--resident-credit-baseline",action="store_true")
    p.add_argument("--resident-start-baseline",action="store_true")
    p.add_argument("--start-trial",action="store_true")
    p.add_argument("--start-at-main",type=int,default=1260)
    p.add_argument("--confirm-trial",action="store_true")
    p.add_argument("--confirm-at-main",type=int,default=1400)
    p.add_argument("--difficulty-confirm-at-main",type=int,default=0)
    p.add_argument("--gameplay-right-trial",action="store_true")
    p.add_argument("--gameplay-trial-word",type=lambda s:int(s,0),default=0x7fff)
    p.add_argument("--gameplay-trial-duration",type=int,default=8)
    p.add_argument("--saturn-pad-input",action="store_true")
    p.add_argument("--manual-pad-profile",action="store_true")
    p.add_argument("--pad-frame-clock",action="store_true")
    p.add_argument("--pad-timed-poll",action="store_true")
    p.add_argument("--pad-hblank-worker",action="store_true")
    p.add_argument("--stv-bios",type=Path)
    a=p.parse_args();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    if a.introdon_profile and not a.startup_scu_services:
        p.error('--introdon-profile requires the shared startup profile')
    if a.coin_main_clock and not a.coin_trial:p.error('--coin-main-clock requires --coin-trial')
    if a.resident_backup_callbacks and not a.startup_scu_services:p.error('--resident-backup-callbacks requires startup SCU services')
    if a.resident_input_edges and not a.resident_backup_callbacks:p.error('--resident-input-edges requires guarded backup callbacks')
    if a.resident_player_input and not a.resident_factory_config:p.error('--resident-player-input requires factory-config baseline')
    if a.resident_game_ports and not a.resident_player_input:p.error('--resident-game-ports requires player-input baseline')
    if a.resident_system_config and not a.resident_game_ports:p.error('--resident-system-config requires direct-port baseline')
    if a.resident_session_stats and not (a.resident_system_config and a.resident_backup_callbacks):p.error('--resident-session-stats requires system config and backup callbacks')
    if a.resident_factory_config and not (a.resident_input_edges and a.stv_bios):p.error('--resident-factory-config requires resident edges and explicit --stv-bios')
    if a.resident_state_publish and not a.resident_factory_config:p.error('--resident-state-publish requires factory configuration')
    if a.resident_credit_baseline and not a.resident_state_publish:p.error('--resident-credit-baseline requires state publication')
    if a.resident_start_baseline and not a.resident_credit_baseline:p.error('--resident-start-baseline requires guarded resident credit baseline')
    if a.start_trial and not (a.resident_start_baseline and a.coin_main_clock):p.error('--start-trial requires start baseline and native main clock')
    if a.start_trial and not (a.coin_at_poll+8<a.start_at_main<=32759):p.error('--start-at-main must follow coin release and fit SH2 word range')
    if a.confirm_trial and not (a.start_trial and a.resident_session_stats and a.start_at_main+8<a.confirm_at_main<=32759):p.error('--confirm-trial requires session stats and follows Start')
    if a.difficulty_confirm_at_main and not (a.confirm_trial and a.confirm_at_main+8<a.difficulty_confirm_at_main<=32759):p.error('--difficulty-confirm-at-main requires later confirm window')
    if a.gameplay_right_trial and not (a.difficulty_confirm_at_main and a.difficulty_confirm_at_main+8<2300):p.error('--gameplay-right-trial requires earlier difficulty confirmation')
    if a.gameplay_trial_word not in (0x7fff,0xbfff,0xdfff,0xefff,0xfeff,0xfdff,0xfbff):p.error('--gameplay-trial-word must select one isolated P1 bit')
    if not 1<=a.gameplay_trial_duration<=256:p.error('--gameplay-trial-duration must be 1..256')
    if a.saturn_pad_input and not (a.resident_session_stats and a.boot_static_input):p.error('--saturn-pad-input requires bounded session profile and isolated sound')
    if a.manual_pad_profile and not (a.saturn_pad_input and a.coin_main_clock):p.error('--manual-pad-profile requires Saturn pad and main clock')
    if a.pad_frame_clock and not (a.saturn_pad_input and a.irq_depth):p.error('--pad-frame-clock requires Saturn pad and IRQ dispatcher')
    if a.pad_timed_poll and not (a.pad_frame_clock and a.manual_pad_profile):p.error('--pad-timed-poll requires frame clock and manual pad')
    if a.pad_hblank_worker and not a.pad_timed_poll:p.error('--pad-hblank-worker requires timed poll')
    factory=None
    if a.resident_factory_config:
        bios=a.stv_bios.read_bytes()
        factory=validate_factory_bios(bios)
        if a.resident_credit_baseline:credit_limits=validate_credit_limits(bios)
    if a.startup_scu_services and not (a.software_nvram_shadow and a.irq_depth and a.hardware_cd_fixes):
        p.error('--startup-scu-services requires NV shadow, IRQ depth and hardware fixes')
    if a.cold_game_state and not a.startup_scu_services:
        p.error('--cold-game-state requires --startup-scu-services')
    if a.system_flag_slot and not a.startup_scu_services:
        p.error('--system-flag-slot requires --startup-scu-services')
    if a.coin_trial and not (a.system_flag_slot and a.boot_static_input):
        p.error('--coin-trial requires system slot and isolated input')
    if not 1<=a.coin_at_poll<=32759:
        p.error('--coin-at-poll must fit the positive SH2 word literal with an eight-poll pulse')
    src=a.source.resolve()
    if a.irq_depth and not a.software_input_shadow:
        p.error('--irq-depth currently requires --software-input-shadow')
    if a.hardware_cd_fixes and not a.software_input_shadow:
        p.error('--hardware-cd-fixes requires --software-input-shadow')
    if a.boot_static_input and not (a.software_input_shadow and a.irq_depth and a.hardware_cd_fixes):
        p.error('--boot-static-input requires input-shadow, IRQ-depth and hardware fixes')
    if a.software_nvram_shadow and not a.software_input_shadow:
        p.error('--software-nvram-shadow requires --software-input-shadow')
    assemble_src=src
    redirects={"0x25807020":"0x2021F000","0x25807022":"0x2021F002","0x25807024":"0x2021F004"}
    if a.software_input_shadow:
        adapted=src.read_text()
        if a.cold_game_state:
            anchor='handoff_game_index_0:   .long 0x0001FFFF'
            if adapted.count(anchor)!=1:raise ValueError('Unexpected measured game-state seed')
            # Original 0601024E copies TWO bytes from 060550C4: mode=0,
            # substate=0. The measured hot checkpoint seed skipped substate 0.
            adapted=adapted.replace(anchor,'handoff_game_index_0:   .long 0x0000FFFF')
        if a.software_nvram_shadow:
            adapted=redirect_nvram_literals(adapted)
            anchor='    extu.b  r0, r0\n    mov.w   channel_stride, r3'
            if adapted.count(anchor)!=1: raise ValueError('Unexpected channel selector site')
            adapted=adapted.replace(anchor,'    extu.b  r0, r0\n'
                '    stc sr,r2\n    mov #8,r3\n    cmp/hi r3,r0\n    bt cd_nv_bad_channel\n'
                '    ldc r2,sr\n'
                '    mov.w   channel_stride, r3')
            anchor='    .org 0x220, 0'
            adapted=adapted.replace(anchor,'''cd_nv_bad_channel:
    mov.l cd_nv_halt_ptr,r0
    jmp @r0
    nop
    .align 2
cd_nv_halt_ptr: .long cd_nv_halt

'''+anchor,1)
            adapted+='''
    .org 0x1d00,0
cd_nv_halt:
    mov.l cd_nv_trace,r1
    mov.l cd_nv_fail,r0
    mov.l r0,@r1
    mov.l cd_nv_code,r0
    mov.l r0,@(4,r1)
cd_nv_spin:
    bra cd_nv_spin
    nop
    .align 2
cd_nv_trace: .long 0x2021e000
cd_nv_fail: .long 0x4641494c
cd_nv_code: .long 0xb01
'''
        if a.hardware_cd_fixes:
            old='    mov.l   hw_scu_ist, r1\n    mov.l   r0, @r1'
            if adapted.count(old)!=1: raise ValueError('Unexpected SCU IST hardware-init site')
            adapted=adapted.replace(old,'    mov.l   hw_scu_ist, r1\n'
                '    mov     #0, r0\n    mov.l   r0, @r1 ! IST: write zero clears, not -1')
        for old,new in redirects.items():
            if adapted.count(old)!=1: raise ValueError(f"Unexpected input reference count: {old}")
            adapted=adapted.replace(old,new)
        anchor=("    bf      smpc_pad_return\n    mov     #1, r0\n"
                "    mov.b   r0, @r2\n    mov.l   smpc_comreg_ptr, r2")
        if adapted.count(anchor)!=1: raise ValueError("Unexpected SMPC command-issue site")
        replacement=("    bf      smpc_pad_return\n"
            "    ! Break left IREG0=0x40; each fresh INTBACK needs IREG0=0.\n"
            "    mov.l   smpc_ireg0_ptr_p, r2\n    mov     #0, r0\n"
            "    mov.b   r0, @r2\n    mov.l   smpc_sf_ptr, r2\n"
            "    mov     #1, r0\n    mov.b   r0, @r2\n    mov.l   smpc_comreg_ptr, r2")
        adapted=adapted.replace(anchor,replacement)
        if a.saturn_pad_input:
            parameter_anchor='    mov.b   r0, @r2\n    mov.l   smpc_sf_ptr, r2'
            if adapted.count(parameter_anchor)!=1:raise ValueError('Unexpected INTBACK parameter seam')
            adapted=adapted.replace(parameter_anchor,'''    mov.b   r0, @r2
    add #2,r2
    mov #0x0a,r0
    mov.b r0,@r2
    add #2,r2
    mov #0xf0,r0
    mov.b r0,@r2
    mov.l   smpc_sf_ptr, r2''',1)
        # Cache only pad bits, not software-shadow bits. Replay them while the
        # asynchronous next INTBACK is pending, instead of releasing every other frame.
        anchor="smpc_no_coin:\n\n    mov.l   smpc_port_a_dst, r1"
        if adapted.count(anchor)!=1: raise ValueError("Unexpected pad merge site")
        adapted=adapted.replace(anchor,"smpc_no_coin:\n"
            "    mov.l   cd_pad_cache_ptr, r1\n    mov.l   r6, @r1\n"
            "    mov.l   r7, @(4, r1)\n\n    mov.l   smpc_port_a_dst, r1")
        anchor="smpc_pad_return:\n    rts\n    nop"
        if adapted.count(anchor)!=1: raise ValueError("Unexpected pad return site")
        adapted=adapted.replace(anchor,"smpc_pad_return:\n    bra stv_cd_pad_replay\n    nop")
        anchor="smpc_sound_state_ptr:.long 0x06000BE2"
        if adapted.count(anchor)!=1: raise ValueError("Unexpected pad literal pool")
        adapted=adapted.replace(anchor,anchor+"\ncd_pad_cache_ptr: .long 0x06000BE8")
        anchor="    mov.l   smpc_sound_last_ptr_i, r1\n    mov.l   r0, @r1\n    rts"
        if adapted.count(anchor)!=1: raise ValueError("Unexpected pad init tail")
        adapted=adapted.replace(anchor,"    mov.l   smpc_sound_last_ptr_i, r1\n"
            "    mov.l   r0, @r1\n    add #4, r1\n    mov.l r0, @r1\n"
            "    add #4, r1\n    mov.l r0, @r1\n    rts")
        adapted+="""
    .org 0x1800, 0
stv_cd_pad_replay:
    mov.l cd_cache_ptr, r1
    mov.l @r1, r6
    mov.l @(4,r1), r7
    mov.l cd_port_a, r1
    mov.l @r1, r4
    or r6, r4
    mov.l r4, @r1
    mov.l cd_port_c, r1
    mov.l @r1, r6
    or r7, r6
    mov.l r6, @r1
    mov.l cd_port_b, r1
    mov.l @r1, r5
    mov r4, r0
    shlr r0
    and #4, r0
    mov r0, r3
    mov r6, r0
    and #3, r0
    or r0, r3
    mov r5, r0
    and #8, r0
    or r0, r3
    not r3, r3
    mov.l cd_system, r1
    mov.b r3, @r1
    rts
    nop
    .align 2
cd_cache_ptr: .long 0x06000BE8
cd_port_a: .long 0x06002864
cd_port_b: .long 0x06002868
cd_port_c: .long 0x0600286C
cd_system: .long 0x06000730
"""
        if a.irq_depth:
            replacements={
                'stv_resident_init:\n':'stv_resident_init:\n'
                    '    mov.l cd_irq_depth_ptr,r1\n    mov #0,r0\n    mov.l r0,@r1\n',
                '    mov     r0, r7\n    cmp/eq  #0x40, r0':
                    '    mov     r0, r7\n'
                    '    mov.l cd_irq_depth_ptr,r1\n    mov.l @r1,r2\n'
                    '    add #1,r2\n    mov.l r2,@r1\n    cmp/eq  #0x40, r0',
                'resident_scu_irq_restore:\n':
                    'resident_scu_irq_restore:\n'
                    '    mov.l cd_irq_depth_ptr,r1\n    mov.l @r1,r2\n'
                    '    add #-1,r2\n    mov.l r2,@r1\n',
                'resident_scu_ims_irq:       .long 0x25FE00A0':
                    'resident_scu_ims_irq:       .long 0x25FE00A0\n'
                    'cd_irq_depth_ptr: .long 0x2021F010'}
            for old,new in replacements.items():
                if adapted.count(old)!=1: raise ValueError('Unexpected IRQ instrumentation anchor: '+old)
                adapted=adapted.replace(old,new)
            # The fixed 0x800..0x9ff resident region has no space for added
            # depth instructions. Move dispatcher to a local extension while
            # preserving entry addresses and the original nearby literal pool.
            begin=adapted.index('resident_scu_irq_dispatch:\n')
            end=adapted.index('    .align 2\nresident_diag_ptr:',begin)
            pool_end=adapted.index('! Non-returning clean equivalent',end)
            dispatcher=adapted[begin:end]
            pool=adapted[end:pool_end]
            labels=re.findall(r'^([A-Za-z_][A-Za-z_0-9]*):',pool,re.M)
            for label in labels:
                dispatcher=re.sub(r'\b'+label+r'\b','cd_extended_'+label,dispatcher)
                pool=re.sub(r'\b'+label+r'\b','cd_extended_'+label,pool)
            dispatcher=dispatcher.replace('resident_scu_irq_dispatch:', 'cd_extended_irq_dispatch:')
            if a.pad_frame_clock:
                seam='    mov     r0, r7\n'
                if dispatcher.count(seam)!=1:raise ValueError('Unexpected frame-clock IRQ seam')
                dispatcher=dispatcher.replace(seam,seam+'''    mov r7,r4
    mov.l cd_frame_clock_call,r1
    jsr @r1
    nop
    mov r7,r0
''',1)
                pool+='\n    .align 2\ncd_frame_clock_call: .long cd_pad_frame_clock\n'
            trampoline='''resident_scu_irq_dispatch:
    mov.l r1,@-r15
    mov.l cd_extended_irq_ptr,r1
    jmp @r1
    mov.l @r15+,r1
    .align 2
cd_extended_irq_ptr: .long cd_extended_irq_dispatch

'''
            adapted=adapted[:begin]+trampoline+adapted[end:]
            adapted+='\n    .org 0x1a00,0\n'+dispatcher+pool
        if a.boot_static_input:
            for old in ('input_pad_poll_ptr: .long stv_smpc_pad_poll',
                        'input_sound_poll_ptr: .long stv_scsp_sound_poll'):
                if adapted.count(old)!=1: raise ValueError('Unexpected boot-isolation anchor')
                adapted=adapted.replace(old,old.split(':')[0]+': .long cd_boot_poll_disabled')
            if a.saturn_pad_input:
                adapted=adapted.replace('input_pad_poll_ptr: .long cd_boot_poll_disabled',
                    'input_pad_poll_ptr: .long cd_pad_after_main',1)
        adapted+='\n    .org 0x1c00,0\ncd_boot_poll_disabled:\n    rts\n    nop\n'
        # The NV guard is the last module: fixed .org regions cannot go backwards.
        if a.software_nvram_shadow:
            start=adapted.index('    .org 0x1d00,0')
            end=adapted.index('    .org 0x1800, 0',start)
            guard=adapted[start:end]
            adapted=adapted[:start]+adapted[end:]+guard
        if a.startup_scu_services:
            anchor='resident_veneer_installer_ptr: .long stv_install_resident_veneers'
            if adapted.count(anchor)!=1: raise ValueError('Unexpected resident installer return')
            adapted=adapted.replace(anchor,'resident_veneer_installer_ptr: .long cd_scu_install')
            begin=adapted.index('    mov     #1, r4\n',adapted.index('cd_extended_irq_dispatch:'))
            end=adapted.index('    mov.l   cd_extended_resident_mask_shadow_irq, r1',begin)
            adapted=adapted[:begin]+'''    mov r7,r6
    add #-0x40,r6
    shll2 r6
    mov.l cd_irq_priority_table,r4
    add r6,r4
    mov.l @r4,r4
    mov r4,r6
    shlr16 r6
    extu.w r4,r4
    mov.w cd_irq_abus_bit,r3
    extu.w r3,r3
    tst r3,r4
    bt cd_irq_priority_ready
    extu.w r4,r4
    mov #-1,r3
    shll16 r3
    or r3,r4
cd_irq_priority_ready:
'''+adapted[end:]
            anchor='    mov.l   cd_extended_resident_handler_table_irq, r0'
            if adapted.count(anchor)!=1: raise ValueError('Unexpected extended dispatcher lookup')
            adapted=adapted.replace(anchor,'    ldc r6,sr\n'+anchor)
            # Keep dispatcher literals in reach; the new module follows all existing modules.
            adapted=adapted.replace('    .org 0x1c00,0',
                '    .align 2\ncd_irq_priority_table: .long 0x2021f100\ncd_irq_abus_bit: .word 0x8000\n    .org 0x1c00,0',1)
            module=(Path(__file__).resolve().parents[1]/'runtime/startup_scu.s').read_text()
            if a.system_flag_slot:
                anchor='    mov.l cd_priority_data,r1'
                if module.count(anchor)!=1:raise ValueError('Unexpected system flag installation site')
                module=module.replace(anchor,'    mov.l cd_system_slot,r1\n'
                    '    mov.l cd_system_target,r0\n    mov.l r0,@r1\n'+anchor)
                module+='\n    .align 2\ncd_system_slot: .long 0x06000680\n'
                module+='cd_system_target: .long stv_resident_system_flag\n'
            if a.resident_backup_callbacks:
                module=module.replace('    mov.l cd_priority_data,r1',
                    '    mov.l backup_slot_install,r1\n    mov.l backup_access_install,r0\n    mov.l r0,@r1\n'
                    '    mov.l backup_mark_install,r0\n    mov.l r0,@(4,r1)\n    mov.l cd_priority_data,r1',1)
                module+='\n    .align 2\nbackup_slot_install: .long 0x06000644\n'
                module+='backup_access_install: .long cd_backup_access\nbackup_mark_install: .long cd_backup_mark\n'
            if a.resident_factory_config:
                module=module.replace('    mov.l cd_priority_data,r1',
                    '    mov.l factory_install_ptr,r0\n    jsr @r0\n    nop\n    mov.l cd_priority_data,r1',1)
                module+='\n    .align 2\nfactory_install_ptr: .long cd_resident_factory\n'
            if a.resident_state_publish:
                module=module.replace('    mov.l cd_priority_data,r1',
                    '    mov.l state_slot_install,r1\n    mov.l state_start_install,r0\n    mov.l r0,@r1\n'
                    '    mov.l state_notification_install,r0\n    mov.l r0,@(4,r1)\n    mov.l cd_priority_data,r1',1)
                module+='\n    .align 2\nstate_slot_install: .long 0x06000664\n'
                module+='state_start_install: .long cd_resident_start_consume\nstate_notification_install: .long cd_resident_notification\n'
            if a.resident_system_config:
                module=module.replace('    mov.l cd_priority_data,r1',
                    '    mov.l system_config_init_ptr,r0\n    jsr @r0\n    nop\n    mov.l cd_priority_data,r1',1)
                module+='\n    .align 2\nsystem_config_init_ptr: .long cd_resident_system_config_init\n'
            if a.resident_session_stats:
                module=module.replace('    mov.l cd_priority_data,r1',
                    '    mov.l session_slot_install,r1\n    mov.l session_target_install,r0\n    mov.l r0,@r1\n    mov.l cd_priority_data,r1',1)
                module+='\n    .align 2\nsession_slot_install: .long 0x06000688\nsession_target_install: .long cd_resident_session_stats\n'
            adapted+='\n'+module
            if a.coin_trial:
                anchor='stv_resident_input_poll:\n    sts.l   pr, @-r15'
                if adapted.count(anchor)!=1:raise ValueError('Unexpected coin poll anchor')
                adapted=adapted.replace(anchor,anchor+'\n    mov.l coin_tick_ptr,r0\n    jsr @r0\n    nop')
                anchor='ioga_shadow_ab:  .long 0x2021F000'
                if adapted.count(anchor)!=1:raise ValueError('Unexpected coin literal anchor')
                adapted=adapted.replace(anchor,'coin_tick_ptr: .long cd_coin_tick\n'+anchor)
                anchor='    mov.l cd_priority_data,r1'
                adapted=adapted.replace(anchor,'    mov.l coin_count_reset,r1\n    mov #0,r0\n    mov.l r0,@r1\n    mov.l r0,@(8,r1)\n'+anchor)
                adapted+='\n    .align 2\ncoin_count_reset: .long 0x2021f020\n'
                coin=(Path(__file__).resolve().parents[1]/'runtime/coin_trial.s').read_text()
                coin=coin.replace('coin_begin: .word 1200',f'coin_begin: .word {a.coin_at_poll}')
                coin=coin.replace('coin_end: .word 1208',f'coin_end: .word {a.coin_at_poll+8}')
                if a.start_trial:
                    coin=coin.replace('coin_publish:\n','''coin_publish:
    mov.l coin_arm,r1
    mov.l @r1,r2
    tst r2,r2
    bt start_idle_done
    mov.l coin_count,r1
    mov.l @r1,r2
    mov.w start_begin,r1
    cmp/hs r1,r2
    bf start_idle_done
    mov.w start_end,r1
    cmp/hs r1,r2
    bt start_idle_done
    mov.w start_pressed,r0
start_idle_done:
''')
                    coin+=f'\n    .align 2\nstart_begin: .word {a.start_at_main}\nstart_end: .word {a.start_at_main+8}\nstart_pressed: .word 0xefff\n'
                if a.confirm_trial:
                    anchor='    mov.w r0,@r1\n    ldc.l @r15+,sr'
                    if coin.count(anchor)!=1:raise ValueError('Unexpected confirm input seam')
                    coin=coin.replace(anchor,'''    mov.w r0,@r1
    mov #-1,r0
    mov.l coin_arm,r1
    mov.l @r1,r2
    tst r2,r2
    bt confirm_publish
    mov.l coin_count,r1
    mov.l @r1,r2
    mov.w confirm_begin,r1
    cmp/hs r1,r2
    bf confirm_publish
    mov.w confirm_end,r1
    cmp/hs r1,r2
    bt confirm_publish
    mov.w confirm_pressed,r0
confirm_publish:
    mov.l confirm_shadow,r1
    mov.w r0,@r1
    ldc.l @r15+,sr''')
                    coin+=f'\n    .align 2\nconfirm_shadow: .long 0x2021f000\nconfirm_begin: .word {a.confirm_at_main}\nconfirm_end: .word {a.confirm_at_main+8}\nconfirm_pressed: .word 0xfeff\n'
                    if a.difficulty_confirm_at_main:
                        coin=coin.replace('confirm_publish:\n','''confirm_publish:
    mov.w difficulty_begin,r1
    cmp/hs r1,r2
    bf difficulty_publish
    mov.w difficulty_end,r1
    cmp/hs r1,r2
    bt difficulty_publish
    mov.w confirm_pressed,r0
difficulty_publish:
''',1)
                        coin+=f'\n    .align 2\ndifficulty_begin: .word {a.difficulty_confirm_at_main}\ndifficulty_end: .word {a.difficulty_confirm_at_main+8}\n'
                if a.gameplay_right_trial:
                    coin=coin.replace('    mov.l confirm_shadow,r1\n','''    mov.w gameplay_right_begin,r1
    cmp/hs r1,r2
    bf gameplay_right_publish
    mov.w gameplay_right_end,r1
    cmp/hs r1,r2
    bt gameplay_right_publish
    mov.w gameplay_right_pressed,r0
gameplay_right_publish:
    mov.l confirm_shadow,r1
''',1)
                    coin+=f'\n    .align 2\ngameplay_right_begin: .word 2300\ngameplay_right_end: .word {2300+a.gameplay_trial_duration}\ngameplay_right_pressed: .word {hex(a.gameplay_trial_word)}\n'
                if a.coin_main_clock:
                    coin=coin.replace('    add #1,r2\n    mov.l r2,@r1\n','')
                    coin=coin.replace('coin_count: .long 0x2021f020','coin_count: .long 0x2021f02c')
                    coin+='\n'+(Path(__file__).resolve().parents[1]/'runtime/coin_main.s').read_text()
                adapted+='\n'+coin
        if a.resident_backup_callbacks:
            adapted+='\n'+(Path(__file__).resolve().parents[1]/'runtime/resident_backup.s').read_text()
        if a.resident_input_edges:
            anchor='    mov.b   r3, @r0\n    mov.l   input_sound_poll_ptr, r0'
            if adapted.count(anchor)!=1:raise ValueError('Unexpected input edge call site')
            if a.saturn_pad_input:
                after='    mov.l   input_pad_poll_ptr, r0\n    jsr     @r0\n    nop'
                if adapted.count(after)!=1:raise ValueError('Unexpected post-pad input seam')
                adapted=adapted.replace(after,after+'\n    mov.l cd_input_edges_ptr,r0\n    jsr @r0\n    nop',1)
            else:
                adapted=adapted.replace(anchor,'    mov.b   r3, @r0\n    mov.l cd_input_edges_ptr,r0\n    jsr @r0\n    nop\n    mov.l   input_sound_poll_ptr, r0')
            anchor='ioga_shadow_ab:  .long 0x2021F000'
            adapted=adapted.replace(anchor,'cd_input_edges_ptr: .long cd_resident_input_edges\n'+anchor,1)
            assembly=out/'resident-input-edges.s'
            subprocess.run(['sh-elf-gcc','-m2','-mb','-Os','-ffreestanding','-fno-builtin','-S']+
                (['-DRESIDENT_STATE_PUBLISH'] if a.resident_state_publish else [])+
                (['-DRESIDENT_CREDIT_BASELINE'] if a.resident_credit_baseline else [])+
                (['-DRESIDENT_PLAYER_INPUT'] if a.resident_player_input else [])+
                (['-DRESIDENT_GAME_PORTS'] if a.resident_game_ports else [])+[
                str(Path(__file__).resolve().parents[1]/'runtime/resident_input_edges.c'),'-o',str(assembly)],check=True)
            adapted+='\n    .org 0x2a00,0\n'+assembly.read_text().replace('_cd_resident_','cd_resident_')
        if a.resident_factory_config:
            factory_module=(Path(__file__).resolve().parents[1]/'runtime/resident_factory.s').read_text()
            adapted+='\n'+factory_module.replace('    ! FACTORY_BYTES','    .byte '+','.join(hex(v) for v in factory))
        if a.resident_state_publish:
            assembly=out/'resident-state.s'
            subprocess.run(['sh-elf-gcc','-m2','-mb','-Os','-ffreestanding','-fno-builtin','-S']+
                (['-DRESIDENT_START_BASELINE'] if a.resident_start_baseline else [])+[
                str(Path(__file__).resolve().parents[1]/'runtime/resident_state.c'),'-o',str(assembly)],check=True)
            adapted+='\n    .org 0x3000,0\n'+assembly.read_text().replace('_cd_resident_','cd_resident_').replace('.L','.Lstate')
        if a.resident_credit_baseline:
            assembly=out/'resident-credit.s'
            subprocess.run(['sh-elf-gcc','-m2','-mb','-Os','-ffreestanding','-fno-builtin','-S',
                str(Path(__file__).resolve().parents[1]/'runtime/resident_credit.c'),'-o',str(assembly)],check=True)
            adapted+='\n    .text\n    .org 0x3800,0\n'+assembly.read_text().replace('_cd_','cd_').replace('.L','.Lcredit')
            adapted+='\n    .text\n    .align 2\n    .global cd_credit_limits\ncd_credit_limits: .long '+','.join(str(v) for v in credit_limits)+'\n'
        if a.resident_player_input:
            assembly=out/'resident-player-input.s'
            subprocess.run(['sh-elf-gcc','-m2','-mb','-Os','-ffreestanding','-fno-builtin','-S',
                str(Path(__file__).resolve().parents[1]/'runtime/resident_player_input.c'),'-o',str(assembly)],check=True)
            adapted+='\n    .text\n    .org 0x4000,0\n'+assembly.read_text().replace('_cd_','cd_').replace('.L','.Lplayer')
        if a.resident_game_ports:
            assembly=out/'resident-game-ports.s'
            subprocess.run(['sh-elf-gcc','-m2','-mb','-Os','-ffreestanding','-fno-builtin','-S',
                *(['-DSATURN_PAD_INPUT'] if a.saturn_pad_input else []),
                *(['-DINTRODON_INPUT'] if a.introdon_profile else []),
                str(Path(__file__).resolve().parents[1]/'runtime/resident_game_ports.c'),'-o',str(assembly)],check=True)
            adapted+='\n    .text\n    .org 0x4200,0\n'+assembly.read_text().replace('_cd_','cd_').replace('.L','.Lports')
        if a.resident_system_config:
            if bios[0x31c0c:0x31c10]!=bytes.fromhex('000a147f'):raise ValueError('Unexpected original system policy table')
            assembly=out/'resident-system-config.s'
            subprocess.run(['sh-elf-gcc','-m2','-mb','-Os','-ffreestanding','-fno-builtin','-S',
                str(Path(__file__).resolve().parents[1]/'runtime/resident_system_config.c'),'-o',str(assembly)],check=True)
            adapted+='\n    .text\n    .org 0x4400,0\n'+assembly.read_text().replace('_cd_','cd_').replace('.L','.Lsysconfig')
            adapted+='\n    .global cd_system_policy\ncd_system_policy: .byte 0,10,20,127\n'
        if a.resident_session_stats:
            assembly=out/'resident-session-stats.s'
            subprocess.run(['sh-elf-gcc','-m2','-mb','-Os','-ffreestanding','-fno-builtin','-S',
                str(Path(__file__).resolve().parents[1]/'runtime/resident_session_stats.c'),'-o',str(assembly)],check=True)
            adapted+='\n    .text\n    .org 0x4600,0\n'+assembly.read_text().replace('_cd_','cd_').replace('.L','.Lsession')
        if a.saturn_pad_input:
            adapted+='''
    .text
    .org 0x4800,0
cd_pad_after_main:
    mov.l cd_pad_main_clock,r1
    mov.l @r1,r0
    tst r0,r0
    bt cd_pad_before_main
    mov.l cd_pad_real_poll,r0
    jmp @r0
    nop
cd_pad_before_main:
    rts
    nop
    .align 2
cd_pad_main_clock: .long 0x2021f02c
cd_pad_real_poll: .long stv_smpc_pad_poll
'''
        if a.manual_pad_profile:
            anchor='coin_tick_ptr: .long cd_coin_tick'
            if adapted.count(anchor)!=1:raise ValueError('Unexpected automatic-input call pointer')
            adapted=adapted.replace(anchor,'coin_tick_ptr: .long cd_boot_poll_disabled',1)
        if a.pad_frame_clock:
            adapted+='\n'+(Path(__file__).resolve().parents[1]/'runtime/pad_frame_clock.s').read_text()
        if a.pad_timed_poll:
            adapted=adapted.replace('cd_pad_real_poll: .long stv_smpc_pad_poll','cd_pad_real_poll: .long cd_pad_timed_poll',1)
            adapted=adapted.replace('cd_coin_main_return:\n','''cd_coin_main_return:
    mov.l r0,@-r15
    mov.l cd_main_pad_worker,r0
    jsr @r0
    nop
    mov.l @r15+,r0
''',1)
            adapted=adapted.replace('main_resume: .long 0x060102f0','main_resume: .long 0x060102f0\ncd_main_pad_worker: .long cd_pad_main_worker',1)
            adapted+='\n'+(Path(__file__).resolve().parents[1]/'runtime/pad_timed_poll.s').read_text()
        if a.pad_hblank_worker:
            adapted=adapted.replace('cd_frame_clock_call: .long cd_pad_frame_clock','cd_frame_clock_call: .long cd_pad_window_dispatch',1)
            adapted+='\n'+(Path(__file__).resolve().parents[1]/'runtime/pad_hblank_worker.s').read_text()
        if a.introdon_profile:
            if bios[0x67b8:0x67ee] != bytes(54):
                raise ValueError('Unexpected backup reset zero template')
            from introdon_hle import adapt
            adapted=adapt(adapted)
            assembly=out/'introdon-dma.s'
            subprocess.run(['sh-elf-gcc','-m2','-mb','-Os','-ffreestanding','-fno-builtin','-S',
                str(Path(__file__).resolve().parents[1]/'runtime/introdon_dma.c'),
                '-o',str(assembly)],check=True)
            adapted+='\n    .text\n'+assembly.read_text().replace('_intro_dma','intro_dma').replace('.L','.Lintrodma')
            assembly=out/'introdon-error-screen.s'
            subprocess.run(['sh-elf-gcc','-m2','-mb','-Os','-ffreestanding','-fno-builtin','-S',
                str(Path(__file__).resolve().parents[1]/'runtime/diagnostic_screen.c'),
                '-o',str(assembly)],check=True)
            adapted+='\n    .text\n'+assembly.read_text().replace('.L','.Lintroscreen')
        adapted=align_resident_veneers(adapted)
        assemble_src=out/"hle-cd-input.s"
        assemble_src.write_text(adapted)
    ld=out/"hle.ld"
    base=0x06004000 if a.introdon_profile else 0x00210000
    ld.write_text(hle_linker_script(base,0x6000 if a.introdon_profile else 0x10000))
    subprocess.run(["sh-elf-as","--big","--isa=sh2","-o",str(out/"hle.o"),str(assemble_src)],check=True)
    subprocess.run(["sh-elf-ld","-EB","-T",str(ld),"-o",str(out/"hle.elf"),str(out/"hle.o")],check=True)
    subprocess.run(["sh-elf-objcopy","-j",".text","-O","binary",str(out/"hle.elf"),str(out/"HLE.BIN")],check=True)
    symbols=subprocess.check_output(["sh-elf-nm","-n",str(out/"hle.elf")],text=True)
    table={parts[2]:int(parts[0],16) for line in symbols.splitlines()
           if len(parts:=line.split())==3}
    offsets={"stv_long_copy_reloc":0,"stv_memmove_reloc":0x34,
             "stv_signed_accumulate":0x100,"stv_channel_address":0x1e0,
             "stv_memset":0x220,"stv_vblank_clock_update":0x260}
    for name,offset in offsets.items():
        if table.get(name)!=base+offset: raise ValueError(f"Unexpected entry {name}")
    data=(out/"HLE.BIN").read_bytes()
    if a.software_input_shadow:
        for old in redirects:
            if int(old,16).to_bytes(4,"big") in data:
                raise ValueError("Custom CS2 input pointer remains")
    manifest={"status":"ram-relocation-diagnostic-not-game-runtime",
        "base":f'0x{base:08x}',"uncached_load_address":f'0x{base|0x20000000:08x}',
        "size":len(data),"source":str(src),"source_sha256":hashlib.sha256(src.read_bytes()).hexdigest(),
        "sha256":hashlib.sha256(data).hexdigest(),
        "leaf_entries":{name:hex(table[name]) for name in offsets},
        "unadapted_dependencies":["CS0/CS1 source relocation","custom CS2 input shadow","hardware init/resident ownership"]}
    if a.introdon_profile:
        manifest['introdon_services']={name:hex(table[name]) for name in
            ('intro_reinit','intro_record_write','intro_record_read','intro_sound_boot',
             'intro_dma_direct','intro_dma_config','intro_answer_query','intro_answer_buzz')}
        manifest['introdon_services']['diagnostic_grid']=hex(table['_diagnostic_grid'])
    if a.software_input_shadow:
        manifest["input_shadow_redirects"]=redirects
        manifest["adapted_source_sha256"]=hashlib.sha256(assemble_src.read_bytes()).hexdigest()
        manifest["unadapted_dependencies"].remove("custom CS2 input shadow")
        manifest["software_shadow_init"]="three active-low words at 0x2021F000/2/4, initially 0xFFFF"
        manifest["smpc_fix"]="clear IREG0 before each new peripheral-only INTBACK"
        manifest["held_input_fix"]="cache pad A/C at 0x06000BE8/BEC and replay pending samples"
    if a.irq_depth:
        manifest['irq_depth']='SCU dispatcher nesting at uncached 0x2021F010; constructor resets zero'
    if a.pad_frame_clock:
        manifest['pad_frame_clock']={'state':'0x2021f060: FRC/TCR/FTCSR/valid',
            'stamp':'SCU vector 0x40; high then low byte, SR interrupt-masked',
            'invalidate':'SCU vector 0x41 when delivered',
            'timer_writes':False,'command_timing_guard':False,
            'status':'observation-only; not initialized before first frame interrupt'}
    if a.pad_timed_poll:
        manifest['pad_timed_poll']={'status':'experimental-not-accepted',
            'timer_mode':'read-only FRT phi/8; other dividers fail closed',
            'window_ticks':[1200,12000],'requires_vblank':True,
            'worker':'one attempt at native main-call return',
            'busy_wait':False,'timer_writes':False,
            'warning':'worker may miss VBlank; command starvation must be tested'}
    if a.pad_hblank_worker:
        manifest['pad_hblank_worker']={'status':'experimental-emulator-regression-required',
            'vector':'SCU 0x42','mask_bit':2,'callback_guard':'0x06000908 must be zero',
            'vector_guard':'default IRQ return or own entry',
            'arm':'VBlank-IN after main starts and when pad command idle',
            'disarm':'after issue or VBlank-OUT while vector owned',
            'busy_wait':False,'timer_register_writes':False,
            'hardware_accepted':False}
    if a.startup_scu_services:
        manifest['startup_scu_services']='experimental master-only priority table, SCU registration, mask services and vectors 49/4A/4C'
    if a.cold_game_state:
        manifest['cold_game_state']='mode/substate bytes 0/0 matching original 060550C4 template; remaining measured seed unchanged'
    if a.system_flag_slot:
        manifest['system_flag_slot']='06000680 aliases native stv_resident_system_flag; reference ST-V resident pointer 0600120E'
    if a.resident_backup_callbacks:
        manifest['resident_backup_callbacks']={'access':'0x00212600','slot':'0x06000644','mark_slot':'0x06000648',
            'original_range':'20180000..2018ffff','shadow_range':'20220000..2022ffff','failure':'0xc11'}
    if a.resident_input_edges:
        manifest['resident_input_edges']={'entry':hex(table['cd_resident_input_edges']),
            'words':'06000728..072f','pending':'06000754..757','credit_writes':False}
    if a.resident_player_input:
        manifest['resident_player_input']={'entry':hex(table['cd_resident_player_input']),
            'profile':'mode1 config0; ROM0305a4/03069c/0306dc record subset',
            'records':'06000708..0727','system_flag_dispatch':False,'failure':'0xc61'}
    if a.resident_game_ports:
        manifest['resident_game_ports']={'literal':'06037014','original':'20400001','mirror':'2021f041',
            'raw_ports':'2021f041/043/045','failure':'0xc71','game_state_writes':False}
    if a.resident_session_stats:
        manifest['resident_session_stats']={'slot':'06000688','source':'ROM00003842..000039d2',
            'commands':[0,1,16,32],'snapshots':['06000840','06000830'],'clock_source':'odd-strided backup20220000',
            'ledgers':['20223d54','20223dac + channel * 64'],'accumulation':'BIOS signed-overflow saturation',
            'full_statistics_service':False,'failure':'0xcc1','diagnostic_only':True}
    if a.resident_system_config:
        manifest['resident_system_config']={'source':'ROM0304f4..03054a; ROM031c0c..031c0f',
            'profile':'initial default08fd/config0 publication only','system_word':'06000654',
            'expected_initial_word':'0314','full_dispatcher':False,'diagnostic_only':True,'failure':'0xc81'}
    if a.resident_factory_config:
        manifest['resident_factory_config']={'bios_sha256':hashlib.sha256(bios).hexdigest(),
            'source':'BIOS ROM 0000672c..673b factory table; original branch 00004a66..4a76',
            'destination':'0600078c..079b','bytes':factory.hex(),'blank_only':True,'persistent':False}
    if a.resident_state_publish:
        manifest['resident_state_publish']={'start_entry':hex(table['cd_resident_start_consume']),
            'publish_entry':hex(table['cd_resident_state_publish']),
            'notification_entry':hex(table['cd_resident_notification']),
            'available_start_branch':'default shared-credit baseline' if a.resident_start_baseline else 'unimplemented; explicit FAIL c41','credit_awards':False}
    if a.resident_start_baseline:
        manifest['resident_start_baseline']={'supported':'player0/1; mode1; config0; bonus0; shared credit',
            'source':'resident060016b0; BIOS ROM00030ab0..30c5e',
            'statistics':'odd-strided saturating counters; game index06000650',
            'persistent':False,'start_injected':False,'unsupported_failure':'0xc41'}
    if a.resident_credit_baseline:
        manifest['resident_credit_baseline']={'entry':hex(table['cd_resident_credit_tick']),
            'limits_rom':'00031c10..31c4f','limits':credit_limits,'supported':'config0795=0; bonus0791=0; shared credit',
            'failure':'0xc51','game_credit_patch':False,'start_injected':False}
    if a.coin_trial:
        manifest['coin_trial']={'poll_counter':'0x2021f020','pressed_polls':[a.coin_at_poll,a.coin_at_poll+7],
            'shadow':'0x2021f002','pressed_word':'0xfeff','otherwise':'0xffff','start_injected':False,
            'arm':'0x2021f028','arm_before_native_handoff':True}
        manifest['coin_trial']['main_clock']=a.coin_main_clock
        if a.coin_main_clock:
            manifest['coin_trial']['main_counter']='0x2021f02c'
            manifest['coin_trial']['pressed_main_iterations']=manifest['coin_trial'].pop('pressed_polls')
    if a.saturn_pad_input:
        manifest['saturn_pad_input']={'poll':'async SMPC INTBACK; cached during pending',
            'input_edges':'after SMPC merge','direct_game_mirror':'inverted native port A/B/C',
            'physical_hardware_tested':False,'sound_isolated':True,'diagnostic_only':True}
    if a.gameplay_right_trial:
        manifest['gameplay_right_trial']={'shadow':'2021f000','pressed_word':f'{a.gameplay_trial_word:04x}',
            'pressed_main_iterations':[2300,2299+a.gameplay_trial_duration],'diagnostic_only':True,'game_state_writes':False}
    if a.confirm_trial:
        manifest['confirm_trial']={'shadow':'0x2021f000','pressed_word':'0xfeff',
            'pressed_main_iterations':[a.confirm_at_main,a.confirm_at_main+7],
            'active_low_p1_bit':'0x01','diagnostic_only':True,'game_state_writes':False}
        if a.difficulty_confirm_at_main:
            manifest['confirm_trial']['difficulty_pressed_main_iterations']=[a.difficulty_confirm_at_main,a.difficulty_confirm_at_main+7]
    if a.start_trial:
        manifest['start_trial']={'shadow':'0x2021f002','pressed_word':'0xefff',
            'pressed_main_iterations':[a.start_at_main,a.start_at_main+7],
            'active_low_portc_bit':'0x10','start_injected':True,'diagnostic_only':True}
    if a.hardware_cd_fixes:
        manifest['hardware_cd_fixes']='SCU IST cleared by writing zero (ST-097 Table 3.8)'
    if a.boot_static_input:
        manifest['boot_polls_isolated']='Idle software input only; native async pad/sound poll tails disabled'
    if a.software_nvram_shadow:
        allowed=set()
        if a.resident_backup_callbacks:
            allowed={table[name]-base for name in ('backup_base','backup_word_end','backup_long_end')}
        if any(0x20180000<=int.from_bytes(data[o:o+4],'big')<0x20190000
               for o in range(0,len(data)-3,2) if o not in allowed):
            raise ValueError('Native Saturn backup-RAM literal remains')
        manifest['nvram_shadow']={'base':'0x20220000','size':65536,'volatile':True,
            'original_base':'0x20180000','source_address_occurrences':18,'channel_max':8,
            'guard_entry':'0x00211d00','initialization':'loader clears before first constructor'}
        if a.introdon_profile:
            manifest['nvram_shadow'].update(base='0x2600b000',size=0x4000,
                channel_max=4,guard_entry=hex(table['cd_nv_halt']))
    if a.manual_pad_profile:
        manifest['manual_pad_profile']={'automatic_input_callback_disabled':True,
            'main_clock_retained':True,'software_shadows':'idle ffff','physical_hardware_tested':False}
        for profile in ('coin_trial','start_trial','confirm_trial','gameplay_right_trial'):
            if profile in manifest:
                manifest[profile]['enabled']=False
                if 'start_injected' in manifest[profile]:manifest[profile]['start_injected']=False
        manifest['boot_polls_isolated']='SMPC enabled after main; sound isolated; automatic input disabled'
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))


if __name__=="__main__":main()
