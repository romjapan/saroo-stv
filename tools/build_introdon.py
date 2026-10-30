"""Introdon native-cart loader and guarded game patches."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
import build_boot_diag as boot


DMA_HELPERS = (
    (0x06034d10, 0x06034d38, '1016172088913381f4d38908c130ceba403bdd036926c1a358aaa311308d4a2d'),
    (0x060cf944, 0x060cf9a4, '3f8d40efd377ff71520926801d1c5835d5a174f93f9f2884d0aac29cf65a90ee'),
    (0x060cf9a4, 0x060cfa74, '0741cc3072b62d18a1a442100303af0e3b5da9a2d0a138ab1ff438c3cc269782'),
)


def guard_dma_helpers(program):
    for start, end, expected in DMA_HELPERS:
        if hashlib.sha256(program[start-0x06010000:end-0x06010000]).hexdigest()!=expected:
            raise ValueError('Unexpected introdon DMA helper at '+hex(start))


def boot_contract(fpr):
    """The BIOS copy loop decrements once per longword (ROM 0x454e)."""
    if len(fpr)<0xf20:
        raise ValueError('Truncated ST-V load table')
    source,destination,longs,entry=(int.from_bytes(fpr[i:i+4],'big')
                                  for i in range(0xf10,0xf20,4))
    return dict(cart_source=source & 0x1fffffff, size=longs*4,
                destination=destination,entry=entry)


def cart_image(descriptor, rom_dir):
    image = bytearray(b'\xff' * descriptor['image_size'])
    for record in descriptor['roms']:
        raw = (rom_dir / record['name']).read_bytes()
        if len(raw) != record['size'] or hashlib.sha1(raw).hexdigest() != record['sha1']:
            raise ValueError('ROM mismatch: ' + record['name'])
        for op in record['operations']:
            offset = op['offset']
            span = len(raw) * (2 if op['type'] == 'load16_byte' else 1)
            if offset < 0 or offset + span - (op['type'] == 'load16_byte') > len(image):
                raise ValueError('ROM operation outside cart image')
            if op['type'] == 'load16_byte':
                image[offset:offset + 2 * len(raw):2] = raw
            elif op['type'] == 'word_swap':
                swapped = bytearray(raw)
                swapped[::2], swapped[1::2] = raw[1::2], raw[::2]
                image[offset:offset + len(raw)] = swapped
            else:
                raise ValueError('Unsupported ROM operation')
    return bytes(image)


def build(a):
    descriptor = json.loads(a.descriptor.read_text())
    if descriptor['game'] != 'introdon' or not a.saroo_native_rom or not a.saroo_direct:
        raise ValueError('introdon requires --saroo-native-rom --saroo-direct')
    if a.experimental_sound or a.experimental_sound_pad_yield or a.saroo_diag or a.experimental_mpr0_cart_ram:
        raise ValueError('Baku experimental patches are unavailable for introdon')
    out = a.output_dir.resolve() / 'game'
    out.mkdir(parents=True)
    image = cart_image(descriptor, a.rom_dir)
    (out.parent.parent / 'introdon-stvcart.bin').write_bytes(image)
    resident = descriptor['resident_rom']
    offset, size = resident['cart_offset'], resident['size']
    if offset < 0xc8000 or offset + size > 0x2000000 or size % 0x10000:
        raise ValueError('Resident range overlaps menu or exceeds SDRAM')
    payload = image[offset:offset + size]
    (out / 'INTRODON.BIN').write_bytes(payload)
    hashes = []
    for pos in range(0, size, 0x10000):
        h = 2166136261
        for i in range(pos, pos + 0x10000, 4):
            h = ((h ^ int.from_bytes(payload[i:i+4], 'big')) * 16777619) & 0xffffffff
        hashes.append(h)
    # BIOS 0x454e..4556 counts longwords, not bytes.
    program = image[0x200000:0x2e0000]
    guard_dma_helpers(program)
    fpr = (a.rom_dir / descriptor['roms'][0]['name']).read_bytes()
    if fpr[0xf10:0xf20] != bytes.fromhex('22200000060100000003800006010000'):
        raise ValueError('Unexpected ST-V program load table')
    if descriptor['boot'] != boot_contract(fpr):
        raise ValueError('Unsupported introdon boot contract')
    # Guard the two instructions and literal used by the entry trampoline.
    if program[:12].hex() != 'd102e0002100d002402b0009':
        raise ValueError('Unexpected introdon entry')
    services=json.loads((out.parent/'hle/manifest.json').read_text())['introdon_services']
    patches=[(0x06034dd0,0x060c77b8,int(services['intro_sound_boot'],16))]
    patches.append((0x0602ca04,0x20100077,0x2600a0d8))
    if program[0x26e02:0x26e0c].hex()!='d31a6232e402420b0009' or int.from_bytes(program[0x26e6c:0x26e70],'big')!=0x0600060c:
        raise ValueError('Unexpected native TEST EXIT BIOS-service contract')
    if hashlib.sha256(program[0x2bc88:0x2bca0]).hexdigest()!='19be8ca59c495b411dc575004a943ee20b5a643d56514fd0e72799630284cf8a':
        raise ValueError('Unexpected native foreground frame-wait contract')
    if hashlib.sha256(program[0x1f780:0x1f798]).hexdigest()!='56cb4b328e764d14f0afdfe37b8d375c7dbe1db0100e12e5ba8057a6f5a8d808':
        raise ValueError('Unexpected native frame-delay contract')
    patches.extend((0x06010000+i,0x0602f780,0x0600fec0)
        for i in range(0,len(program)-3,4) if program[i:i+4]==bytes.fromhex('0602f780'))
    patches.extend((0x06010000+i,0x0603bc88,0x0600fee0)
        for i in range(0,len(program)-3,4) if program[i:i+4]==bytes.fromhex('0603bc88'))
    # This literal is shared only by the menu's down/confirm queries. The
    # adapter changes the row only on a native 0x700 confirmation edge.
    patches.append((0x060207a0,0x0602c9da,int(services['intro_answer_query'],16)))
    patches.append((0x060203fc,0x0602c9da,int(services['intro_answer_buzz'],16)))
    if hashlib.sha256(program[0x1c9da:0x1c9f4]).hexdigest()!='543a71588d4f3a6df58206e41a61c7f439e10934c23de73d01f9975c0a90bc7b':
        raise ValueError('Unexpected native edge-query contract')
    patches.extend((0x06010000+i,0x0602c9da,0x0600ffb0)
        for i in range(0,len(program)-3,4) if program[i:i+4]==bytes.fromhex('0602c9da')
        and 0x06010000+i not in (0x060207a0,0x060203fc))
    if hashlib.sha256(program[0x103d4:0x108a4]).hexdigest()!= '51e257e1e720f4a983d548b67c09b9781578a8cba1bf9b961d3f9a88a7e4be63':
        raise ValueError('Unexpected paid-answer task/stack contract')
    if program[0x10782:0x10790].hex()!='950854f5d306430b000920088909':
        raise ValueError('Unexpected paid-answer menu confirmation seam')
    # All four literal callers of the direct helper, plus the sole parameter
    # block submit caller. Original helpers remain callable by the adapters.
    patches.extend((site,0x06034d10,int(services['intro_dma_direct'],16))
                   for site in (0x06035d80,0x06036394,0x060368d4))
    patches.append((0x060cef74,0x060cf944,int(services['intro_dma_config'],16)))
    for port,sites in {
        1:(0x0602c9fc,0x0603be74),3:(0x0602ca14,0x0603be78),
        5:(0x0602ca00,0x0603be7c),
        7:(0x06010650,0x060107bc,0x06030900,0x06034844),
        0x11:(0x0601064c,)}.items():
        patches.extend((site,0x20400000+port,0x2600a040+port) for site in sites)
    for address,original,replacement in patches:
        if int.from_bytes(program[address-0x06010000:address-0x06010000+4],'big')!=original:
            raise ValueError('Unexpected introdon patch original at '+hex(address))
    config = ('#define INTRO_ASSUME %d\n' % a.saroo_native_assume +
              '#define INTRO_FORCE_TCR2 %d\n' % bool(os.environ.get('SAROO_STV_FORCE_TCR2')) +
              '#define INTRO_ROM_BASE 0x%08xu\n' % (0x02000000 + offset) +
              '#define INTRO_ROM_SIZE 0x%xu\n' % size +
              '#define INTRO_SDRAM 0x%xu\n' % offset +
              '#define INTRO_SD_FILE ' + json.dumps(resident['sd_file']) + '\n' +
              'static const unsigned int intro_hash[]={' + ','.join(hex(h)+'u' for h in hashes) + '};\n'+
              'static const unsigned int intro_patches[][3]={'+
              ','.join('{'+','.join(hex(v)+'u' for v in p)+'}' for p in patches)+'};\n')
    runtime = Path(__file__).resolve().parents[1] / 'runtime'
    extra_files={'HLE.BIN': (out.parent/'hle/HLE.BIN').read_bytes()}
    panel=out/'panel.s'
    panel.write_text((runtime/'introdon_panel.s').read_text().replace(
        'panel_command: .long 0','panel_command: .long '+services['stv_smpc_command']).replace('PANEL_COMMAND',services['stv_smpc_command']))
    subprocess.run(['sh-elf-as','--big','--isa=sh2',str(panel),'-o',str(out/'panel.o')],check=True)
    (out/'panel.ld').write_text('OUTPUT_ARCH(sh)\nSECTIONS { . = 0x0600fe00; .text : { *(.text*) } }\nASSERT(SIZEOF(.text)<=0x200,"Panel too large")\n')
    subprocess.run(['sh-elf-ld','-EB','-T',str(out/'panel.ld'),str(out/'panel.o'),'-o',str(out/'panel.elf')],check=True)
    subprocess.run(['sh-elf-objcopy','-O','binary',str(out/'panel.elf'),str(out/'PANEL.BIN')],check=True)
    extra_files['PANEL.BIN']=(out/'PANEL.BIN').read_bytes()
    persist=out/'persist.s'
    subprocess.run(['sh-elf-gcc','-m2','-mb','-Os','-ffreestanding','-fno-builtin','-S',str(runtime/'introdon_persist.c'),'-o',str(persist)],check=True)
    entry=out/'persist-entry.s'
    entry.write_text('.text\nmov.l tick,r0\njmp @r0\nnop\n.align 2\ntick: .long _intro_persist_tick\n.org 0x10\nmov.l init,r0\njmp @r0\nnop\n.align 2\ninit: .long _intro_persist_init\n.global _intro_persist_command\n_intro_persist_command:\nmov.l command,r0\njmp @r0\nnop\n.align 2\ncommand: .long '+services['stv_smpc_command']+'\n')
    for src,obj in [(persist,out/'persist.o'),(entry,out/'persist-entry.o')]:
        subprocess.run(['sh-elf-as','--big','--isa=sh2',str(src),'-o',str(obj)],check=True)
    (out/'persist.ld').write_text('OUTPUT_ARCH(sh)\nSECTIONS { . = 0x0600bc00; .text : { *(.text*) *(.rodata*) } /DISCARD/ : { *(.comment) *(.note*) } }\nASSERT(SIZEOF(.text)<=0x1400,"Persistence overlaps snapshot")\n')
    subprocess.run(['sh-elf-ld','-EB','-T',str(out/'persist.ld'),str(out/'persist-entry.o'),str(out/'persist.o'),'-o',str(out/'persist.elf')],check=True)
    subprocess.run(['sh-elf-objcopy','-O','binary',str(out/'persist.elf'),str(out/'PERSIST.BIN')],check=True)
    extra_files['PERSIST.BIN']=(out/'PERSIST.BIN').read_bytes()
    config+='#define INTRO_PROGRESS %d\n'%a.loading_screen
    config+='#define INTRO_CD_WORK %du\n'%sum(len(v) for v in extra_files.values())
    probe = out / 'introdon_loader.c'
    probe.write_text(config + (runtime / 'introdon_loader.c').read_text())
    handoff = out / 'introdon_handoff.s'
    # Reuse the cache/VBR/IMS handoff, entering the actual load-table entry.
    handoff.write_text((runtime / 'game_handoff.s').read_text().replace(
        '_game_handoff:\n', '_game_handoff:\n    mov.l intro_stack,r15\n').replace(
        'vector_base: .long', 'intro_stack: .long 0x06100000\nvector_base: .long').replace(
        'bootstrap: .long 0x00210a00', 'bootstrap: .long 0x06010000').replace(
        'game_mask: .long 0xffffe1fc', 'game_mask: .long 0xffffffff'))
    boot.main(['--sega-dir', str(a.sega_dir), '--output-dir', str(out),
               '--cd-read', '--relocate-loader', '--visible-copy-errors'],
              probe_source=probe, extra_sources=[runtime/'saroo_rom.c', handoff]+([runtime/'load_progress.c'] if a.loading_screen else []),
              extra_files=extra_files,
              stack_address=0x20300000, disc_id="SAROOSTV02", disc_title="SAROO-STV INTRO DON DON")
    manifest = json.loads((out / 'manifest.json').read_text())
    manifest.update(game='introdon', boot=descriptor['boot'],
                    shared_loading_screen=a.loading_screen,
                    runtime_diagnostics=False,
                    force_tcr2=bool(os.environ.get('SAROO_STV_FORCE_TCR2')),
                    guarded_patches=patches,
                    guarded_dma_helpers=DMA_HELPERS,
                    resident_rom=resident, assume_emulator_cart=a.saroo_native_assume,
                    cart_sha256=hashlib.sha256(image).hexdigest(),
                    payload_sha256=hashlib.sha256(payload).hexdigest(),
                    program_sha256=hashlib.sha256(program).hexdigest(),
                    hardware_accepted=False, sound_patches=False)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))
