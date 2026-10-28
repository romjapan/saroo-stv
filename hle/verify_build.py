#!/usr/bin/env python3
"""Static build checks for the SH-2 relocation veneer image."""

from pathlib import Path
import re
import subprocess
import sys


def tool_output(*args: str) -> str:
    return subprocess.check_output(args, text=True)


def main() -> int:
    elf = Path(sys.argv[1] if len(sys.argv) > 1 else "stv-native-hle.elf")
    profile = sys.argv[2] if len(sys.argv) > 2 else "bakubaku"
    symbols = tool_output("sh-elf-nm", "-n", str(elf))
    disasm = tool_output("sh-elf-objdump", "-d", str(elf))

    expected = {
        "stv_long_copy_reloc": 0x04400000,
        "stv_memmove_reloc": 0x04400034,
        "stv_install_reloc_veneers": 0x04400088,
        "stv_signed_accumulate": 0x04400100,
        "stv_packed_status_test": 0x04400120,
        "stv_workspace_byte_set": 0x04400160,
        "stv_cart_layout_nibble": 0x044001A0,
        "stv_channel_address": 0x044001E0,
        "stv_memset": 0x04400220,
        "stv_vblank_clock_update": 0x04400260,
        "stv_channel_table_dispatch": 0x04400400,
        "stv_service_redirect_table": 0x04400700,
        "stv_resident_init": 0x04400800,
        "stv_resident_exception": 0x04400900,
        "stv_bootstrap_handoff": 0x04400A00,
        "stv_handler_table_update": 0x04400A40,
        "stv_resident_mask_set": 0x04400B00,
        "stv_resident_mask_update": 0x04400B20,
        "stv_resident_vblank_out": 0x0440095E,
        "stv_resident_dma0_irq": 0x04400964,
        "stv_resident_vdp1_end_irq": 0x0440096A,
        "stv_resident_queue_pop_alt": 0x04400B94,
        "stv_resident_clock_dispatch": 0x04400B40,
        "stv_resident_queue_pop": 0x04400B60,
        "stv_resident_system_flag": 0x04400BA0,
        "stv_resident_strided_dispatch": 0x04400BE0,
        "stv_resident_vector_set": 0x04400C40,
        "stv_resident_handler_set": 0x04400C80,
        "stv_resident_copy_128": 0x04400CC0,
        "stv_resident_copy_20": 0x04400D00,
        "stv_install_resident_veneers": 0x04400E00,
        "stv_video_shutdown_fast": 0x04400F00,
        "stv_resident_queue_init": 0x04401000,
        "stv_resident_handler_get": 0x04401100,
        "stv_resident_vector_get": 0x04401120,
        "stv_resident_input_poll": 0x04401140,
        "stv_smpc_pad_init": 0x04401200,
        "stv_smpc_pad_poll": 0x04401280,
        "stv_hardware_init": 0x04401400,
        "stv_smpc_command": 0x04401500,
        "stv_scsp_sound_poll": 0x04401600,
        "stv_shienryu_handoff": 0x04401700,
        "stv_shienryu_profile_init": 0x04401740,
    }
    if profile == "shienryu":
        expected.update({
            "stv_shienryu_backup_probe": 0x044017E0,
            "stv_shienryu_backup_mark": 0x04401800,
            "stv_shienryu_eeprom_load": 0x04401840,
            "stv_shienryu_eeprom_save": 0x04401940,
        })
    required = {}
    for name, expected_address in expected.items():
        match = re.search(rf"^([0-9a-fA-F]+)\s+\w\s+{name}$", symbols,
                          re.MULTILINE)
        if not match:
            raise SystemExit(f"missing symbol: {name}")
        address = int(match.group(1), 16)
        if not 0x04400000 <= address < 0x04410000:
            raise SystemExit(f"{name} outside CS1 HLE window: {address:#x}")
        if address != expected_address:
            raise SystemExit(
                f"{name} moved: {address:#x}, trampoline expects {expected_address:#x}")
        required[name] = address

    for instruction in ("cmp/hs", "mov.l", "jmp", "dt"):
        if instruction not in disasm:
            raise SystemExit(f"expected instruction absent: {instruction}")

    raw = elf.with_suffix(".bin").read_bytes()
    if profile == "shienryu":
        for value in (0x06004010,
                      0x25FE00A0, 0xFFFF7FFE,
                      0x0600061C, 0x06000620, 0x06000624,
                      0x06000640, 0x06000644, 0x06000648,
                      0x06000650, 0x06000653, 0x20180000,
                      0x06000780, 0x04E00000,
                      0x2018E200, 0x2018E213,
                      required["stv_resident_strided_dispatch"],
                      required["stv_shienryu_backup_probe"],
                      required["stv_shienryu_backup_mark"],
                      required["stv_shienryu_eeprom_load"],
                      required["stv_shienryu_eeprom_save"]):
            if value.to_bytes(4, "big") not in raw:
                raise SystemExit(
                    f"Shienryu profile literal absent: {value:#010x}")
    for value in (0x03000000, 0x03400000, 0x01000000,
                  0x0604AFD4, 0x06053C98, 0xD001402B, 0x00090009,
                  required["stv_long_copy_reloc"],
                  required["stv_memmove_reloc"], 0x06000100,
                  0x06000300, 0x06000304, 0x06000310, 0x06000314,
                  0x06000340, 0x06000348,
                  0x06000240, 0x32524459,
                  0x06000600, 0xD0016002, 0x402B0009, 0x06000250,
                  0x06000668,
                  0x06000610, 0x0600063C, 0x06000660,
                  0x06000A00, 0x06000B80, 0xDEADE001,
                  0x25807020, 0x25807022, 0x25807024,
                  0x06002864, 0x06002868, 0x0600286C,
                  0x06002870, 0x06002874, 0x06000730,
                  0x20100001, 0x2010001F, 0x20100025,
                  0x20100063, 0x20100079,
                  0x25FE0010, 0x25FE0030, 0x25FE0050,
                  0x25FE0060, 0x25FE00A0, 0x25FE00A4,
                  0x25D00000, 0x25F80000, 0x25F80020,
                  0xFFFFE1FC, 0xFFFFFE92,
                  0x06000BE0, 0x06000BE2, 0x06000BE4,
                  0x25A00004, 0x00080000):
        if value.to_bytes(4, "big") not in raw:
            raise SystemExit(f"required big-endian word absent: {value:#010x}")

    if profile == "shienryu":
        for callback in (0x06004632, 0x06004744):
            if callback.to_bytes(4, "big") in raw:
                raise SystemExit(
                    f"premature Shienryu callback literal present: {callback:#010x}")
    else:
        callback = 0x06035278
        if callback.to_bytes(4, "big") not in raw:
            raise SystemExit(f"profile callback absent: {callback:#010x}")

    for value in (0x060FFFDC, 0x060D28C8, 0x06010660, 0xFF79A6F1,
                  0x00000120, 0x20180108, 0x45A07058,
                  0x39A0500E, 0x0601025E, 0x06010006, 0x06083238,
                  0x0001FFFF):
        if value.to_bytes(4, "big") not in raw:
            raise SystemExit(f"handoff state word absent: {value:#010x}")

    redirects = (
        (0x00000EFC, 0x04400260),
        (0x00000ECC, 0x04400100),
        (0x00002C64, 0x04400034),
        (0x00002CAC, 0x04400220),
        (0x0000372C, 0x044001E0),
        (0x00003E4E, 0x04400120),
        (0x00004596, 0x04400160),
        (0x00004680, 0x044001A0),
        (0x00003842, 0x04400400),
        (0x00004114, 0x04400A00),
        (0x0000426C, 0x04400A40),
        (0x000034C4, 0x04400F00),
        (0x00000000, 0x00000000),
    )
    table = b"".join(
        original.to_bytes(4, "big") + native.to_bytes(4, "big")
        for original, native in redirects
    )
    if raw[0x700:0x700 + len(table)] != table:
        raise SystemExit("service redirect table contents mismatch")

    veneer_match = re.search(
        r"^([0-9a-fA-F]+)\s+\w\s+resident_veneer_table$",
        symbols, re.MULTILINE)
    if not veneer_match:
        raise SystemExit("missing resident veneer metadata")
    veneer_offset = int(veneer_match.group(1), 16) - 0x04400000
    veneer_records = (
        (0x06000D14, 0x04400B40),
        (0x06001198, 0x04400B60),
        (0x0600120E, 0x04400BA0),
        (0x06001412, 0x04400BE0),
        (0x06001494, 0x04400C40),
        (0x060014A8, 0x04400C80),
        (0x060014C0, 0x04400CC0),
        (0x060014E0, 0x04400D00),
        (0x00000000, 0x00000000),
    )
    veneer_table = b"".join(
        address.to_bytes(4, "big") + target.to_bytes(4, "big")
        for address, target in veneer_records
    )
    if raw[veneer_offset:veneer_offset + len(veneer_table)] != veneer_table:
        raise SystemExit("resident veneer metadata mismatch")

    # The fixed-size vector setter ends with the Saturn mask-BIOS Slave SH-2
    # ready word and its 12-byte indirect jump bootstrap.  Keep the block
    # exact: Shienryu depends on it before issuing SMPC SSHON.
    slave_contract = b"".join(value.to_bytes(4, "big") for value in (
        0x06000240, 0x32524459, 0x06000600,
        0xD0016002, 0x402B0009, 0x06000250,
    ))
    if raw[0xC68:0xC80] != slave_contract:
        raise SystemExit("Slave SH-2 startup contract mismatch")

    for opcode in (0xD007, 0xD006, 0x402B, 0x0009):
        if opcode.to_bytes(2, "big") not in raw[0xE00:0xF00]:
            raise SystemExit(f"compact resident opcode absent: {opcode:#06x}")

    print("verified", len(raw), "bytes", required)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
