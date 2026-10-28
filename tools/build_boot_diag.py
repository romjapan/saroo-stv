"""Build a local-only Saturn CD bootstrap diagnostic with supplied Sega objects."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ASM = """.section .text
.global _start
_start:
    mov #0x0f,r0
    shll2 r0
    shll2 r0
    ldc r0,sr
    mov.l heartbeat,r1
    mov.l magic,r0
    mov.l r0,@r1
    mov.l vdp2,r1
    mov #0,r0
    add #0x20,r1
    mov.w r0,@r1
    mov.l back_upper,r1
    mov #0,r0
    mov.w r0,@r1
    mov.w r0,@(2,r1)
    mov.l vram,r1
    mov.l green,r0
    mov.w r0,@r1
    mov.l vdp2,r1
    mov.l tvmd,r0
    mov.w r0,@r1
halt:
    bra halt
    nop
.align 2
heartbeat: .long 0x060ff000
magic: .long 0x43444254
vdp2: .long 0x25f80000
back_upper: .long 0x25f800ac
vram: .long 0x25e00000
green: .long 0x000083e0
tvmd: .long 0x00008000
"""


def run(*args):
    subprocess.run(args, check=True)


def main(argv=None, probe_source=None, extra_sources=(), extra_files=None, stack_address=None):
    p = argparse.ArgumentParser()
    p.add_argument("--sega-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("build/boot-diag"))
    p.add_argument("--cd-read", action="store_true")
    p.add_argument("--visible-cd-errors", action="store_true")
    p.add_argument("--visible-copy-errors", action="store_true")
    p.add_argument("--fpr-rom-dir", type=Path,
                   help="Verify Baku FPR, load its 0xF0000-byte body from CD, do not execute")
    p.add_argument("--hle-bin", type=Path, help="RAM-linked HLE diagnostic, requires FPR mode")
    p.add_argument("--test-input-shadow", action="store_true")
    p.add_argument("--relocate-loader", action="store_true",
                   help="Copy CD runtime to LWRAM before native resident initialization")
    p.add_argument("--test-real-pad", action="store_true")
    a = p.parse_args(argv)
    if a.visible_cd_errors and (not a.cd_read or a.fpr_rom_dir):
        p.error('--visible-cd-errors requires standalone --cd-read')
    if a.hle_bin and not a.fpr_rom_dir:
        p.error("--hle-bin requires --fpr-rom-dir")
    if a.test_input_shadow and not a.hle_bin:
        p.error("--test-input-shadow requires adapted --hle-bin")
    if a.relocate_loader and not (a.cd_read or a.fpr_rom_dir):
        p.error("--relocate-loader requires a CD runtime")
    if a.test_real_pad and not (a.relocate_loader and a.test_input_shadow):
        p.error("--test-real-pad requires relocated loader and software-shadow test")
    fpr_body = None
    fpr_hash = None
    if a.fpr_rom_dir:
        fpr = (a.fpr_rom_dir/"fpr17969.13").read_bytes()
        if len(fpr)!=0x100000 or hashlib.sha1(fpr).hexdigest()!= "1d226db72d6ef68fd294f60659df7f882b25def6":
            raise ValueError("Baku FPR hash/size mismatch")
        # Match the existing trampoline's 0x3C000 longword copy, not all tail bytes.
        fpr_body=fpr[0x1000:0xf1000]
        fpr_hash=2166136261
        for byte in fpr_body:
            fpr_hash=((fpr_hash^byte)*16777619)&0xffffffff
        a.cd_read=True
    out = a.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    parts = [a.sega_dir / (name + ".bin") for name in
             ("sys_sec", "sys_arej", "sys_aret", "sys_areu", "sys_aree")]
    blobs = [f.read_bytes() for f in parts]
    if len(blobs[0]) != 0xd00 or any(len(b) != 0x20 for b in blobs[1:]):
        raise ValueError("Unexpected security/area code lengths")
    aip_addr = 0x06002000 + 0x100 + sum(map(len, blobs))
    source = ASM
    if a.cd_read:
        source = """.section .text.entry
.global _start
_start:
    mov #0x0f,r0
    shll2 r0
    shll2 r0
    ldc r0,sr
    mov.l bss_begin,r1
    mov.l bss_limit,r2
    mov #0,r0
clear_bss:
    cmp/hs r2,r1
    bt cleared
    mov.l r0,@r1
    bra clear_bss
    add #4,r1
cleared:
    mov.l cache_ptr,r1
    mov #0x10,r0
    mov.b r0,@r1
    mov.l entry,r0
    jmp @r0
    nop
.align 2
entry: .long _probe_main
bss_begin: .long __bss_start+0x20000000
bss_limit: .long __bss_end+0x20000000
cache_ptr: .long 0xfffffe92
"""
    if a.relocate_loader:
        source=""".section .text.entry
.global _start
_start:
    mov #0x0f,r0
    shll2 r0
    shll2 r0
    ldc r0,sr
    mov.l source_ptr,r4
    mov.l destination_ptr,r5
    mov.l count_ptr,r6
copy:
    mov.l @r4+,r0
    mov.l r0,@r5
    add #4,r5
    dt r6
    bf copy
    mov.l bss_begin,r1
    mov.l bss_limit,r2
    mov #0,r0
clear_bss:
    cmp/hs r2,r1
    bt cleared
    mov.l r0,@r1
    bra clear_bss
    add #4,r1
cleared:
    mov.l cache_ptr,r1
    mov #0x10,r0
    mov.b r0,@r1
    mov.l entry_ptr,r0
    jmp @r0
    nop
.align 2
source_ptr: .long __runtime_load
destination_ptr: .long 0x20240000
count_ptr: .long __runtime_longs
cache_ptr: .long 0xfffffe92
entry_ptr: .long _probe_main
bss_begin: .long __bss_start+0x20000000
bss_limit: .long __bss_end+0x20000000
"""
    (out / "diag.s").write_text(source)
    run("sh-elf-as", "--big", "--isa=sh2", "-o", str(out/"diag.o"), str(out/"diag.s"))
    objs = [str(out/"diag.o")]
    if a.cd_read:
        runtime=Path(__file__).resolve().parent.parent/"runtime"
        names = ["fpr_probe" if fpr_body is not None else "cd_probe", "cd_io"]
        sources=[runtime/(name+'.c') for name in names]
        if probe_source is not None:
            sources[0]=Path(probe_source)
        sources.extend(map(Path,extra_sources))
        if (a.visible_cd_errors or a.visible_copy_errors) and runtime/'diagnostic_screen.c' not in sources:
            sources.append(runtime/'diagnostic_screen.c')
        for src in sources:
            name=src.stem
            defines=[] if fpr_hash is None else ["-DEXPECTED_FPR_HASH="+hex(fpr_hash)+"u"]
            if a.visible_cd_errors:defines.append('-DVISIBLE_CD_ERRORS=1')
            if a.visible_copy_errors:defines.append('-DVISIBLE_COPY_ERRORS=1')
            if a.hle_bin:
                defines.extend(["-DHAVE_NATIVE_HLE=1", "-DEXPECTED_HLE_SIZE="+str(a.hle_bin.stat().st_size)])
            if a.test_input_shadow:
                defines.append("-DTEST_INPUT_SHADOW=1")
            if a.relocate_loader:
                defines.append("-DTEST_RESIDENT_INIT=1")
            if a.test_real_pad:
                defines.append("-DTEST_REAL_PAD=1")
            asm=src
            if src.suffix!='.s':
                asm=out/(name+'.s')
                run("sh-elf-gcc", "-m2", "-mb", "-Os", "-ffreestanding", "-fno-builtin",
                    *defines, '-I'+str(runtime), "-S", str(src), "-o", str(asm))
            run("sh-elf-as", "--big", "--isa=sh2", "-o", str(out/(name+".o")), str(asm))
            objs.append(str(out/(name+".o")))
    if a.relocate_loader:
        script=("SECTIONS { . = "+hex(aip_addr)+
            "; .entry : { *(.text.entry) } "
            ".runtime 0x00240000 : AT(LOADADDR(.entry)+SIZEOF(.entry)) "
            "{ *(.text*) *(.rodata*) . = ALIGN(4); } "
            ".bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(4); __bss_end = .; } "
            "__runtime_load = LOADADDR(.runtime); __runtime_longs = SIZEOF(.runtime)/4; "
            "/DISCARD/ : { *(.stack) *(.comment) *(.note*) } } "
            "ASSERT(SIZEOF(.runtime)+SIZEOF(.bss) < 0x10000, \"loader too big\")")
    else:
        script=("SECTIONS { . = " + hex(aip_addr) +
            "; .text : { *(.text.entry) *(.text*) *(.rodata*) . = ALIGN(4); } " +
            ".bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(4); __bss_end = .; } " +
            "/DISCARD/ : { *(.stack) *(.comment) *(.note*) } }")
    (out/"diag.ld").write_text(script)
    run("sh-elf-ld", "-EB", "-T", str(out/"diag.ld"), "-e", "_start", "-o",
        str(out/"diag.elf"), *objs)
    sections=["-j",".entry","-j",".runtime"] if a.relocate_loader else ["-j",".text"]
    run("sh-elf-objcopy", *sections, "-O", "binary", str(out/"diag.elf"), str(out/"diag.bin"))
    header = bytearray(b" " * 0xd0 + b"\0" * 0x30)
    for offset, width, value in [(0,16,"SEGA SEGASATURN "),(0x10,16,"SEGA TP T-999"),
         (0x20,10,"SAROOSTV01"),(0x2a,6,"V0.001"),(0x30,8,"20261009"),
         (0x38,8,"CD-1/1"),(0x40,10,"JTUE"),(0x50,16,"J"),
         (0x60,112,"SAROO-STV BAKU BAKU ANIMAL")]:
        header[offset:offset+width] = value.encode().ljust(width, b" ")
    ip = header + b"".join(blobs) + (out/"diag.bin").read_bytes()
    size = max(0x1000, (len(ip)+3)&~3)
    if size > 0x8000:
        raise ValueError("IP exceeds Saturn system-area size")
    ip.extend(bytes(size-len(ip)))
    struct.pack_into(">I", ip, 0xe0, size)
    struct.pack_into(">I", ip, 0xe8, stack_address if stack_address is not None else
                     (0x20300000 if fpr_body is not None else 0x06100000))
    (out/"IP.BIN").write_bytes(ip)
    tree = out/"disc"
    tree.mkdir(exist_ok=True)
    (tree/"README.TXT").write_text(
        "Saturn CD diagnostic only; not a playable game.\n"
        + ("CD read verification: initial blue, green after verifying 6144 bytes; red on error.\n"
           if a.cd_read and fpr_body is None else
           "Extended diagnostic: consult manifest.json for the configured test.\n"
           if fpr_body is not None else
           "Boot-only diagnostic: expected green screen; no CD data read test.\n"))
    if a.cd_read:
        (tree/"PROBE.BIN").write_bytes(bytes(((i*37)^(i>>3)^0xa5)&255 for i in range(6144)))
    if fpr_body is not None:
        (tree/"FPR.BIN").write_bytes(fpr_body)
    if a.hle_bin:
        data=a.hle_bin.read_bytes()
        if not 0<len(data)<=0x10000: raise ValueError("Invalid HLE length")
        (tree/"HLE.BIN").write_bytes(data)
    for name,data in (extra_files or {}).items():
        if Path(name).name!=name: raise ValueError('Extra CD file must be a basename')
        (tree/name).write_bytes(data)
    iso = out/"boot-diag.iso"
    run("xorriso", "-as", "mkisofs", "-quiet", "-iso-level", "1", "-V", "SAROO_STV",
        "-sysid", "SEGA SEGASATURN", "-G", str(out/"IP.BIN"), "-o", str(iso), str(tree))
    with iso.open("rb") as f:
        assert f.read(size) == ip
        f.seek(16*2048)
        assert f.read(7) == b"\x01CD001\x01"
    manifest = {"status":"diagnostic-not-game", "aip_address":hex(aip_addr),
        "ip_size":size,"heartbeat_address":"0x060ff000",
        "heartbeat":("0x50415353" if a.cd_read else "0x43444254"),
        "expected":("green after 6144-byte CD file verification; red on error" if a.cd_read else "green back screen; CPU halt loop"), "iso_sha256":hashlib.sha256(iso.read_bytes()).hexdigest(),
        "boot_objects":[{"name":f.name,"sha256":hashlib.sha256(b).hexdigest()} for f,b in zip(parts,blobs)]}
    if fpr_body is not None:
        manifest.update(expected="green after Baku FPR CD load and full FNV-1a verification",
                        fpr_bytes=len(fpr_body), fpr_hash=hex(fpr_hash),
                        fpr_destination="0x06010000..0x060fffff",
                        heartbeat_address="0x0600e000", stack="0x20300000")
    if a.hle_bin:
        manifest.update(hle_sha256=hashlib.sha256(a.hle_bin.read_bytes()).hexdigest(),
            expected="green after full FPR verification and RAM-native HLE leaf tests")
    if a.test_input_shadow:
        manifest["expected"]="green after FPR, HLE leaf and software-input-shadow tests"
    if a.relocate_loader:
        manifest.update(loader_ram="0x00240000",heartbeat_address="0x0021e000",
            expected="green after relocated loader, resident initialization, post-init CD read")
    if a.test_real_pad:
        manifest["expected"]="wait for real INTBACK idle, press Left+Start+L, release; green on pass"
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))


if __name__ == "__main__":
    main()
