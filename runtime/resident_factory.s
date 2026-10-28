! Only the measured blank-configuration factory branch; not EEPROM persistence.
    .org 0x2e00,0
cd_resident_factory:
    mov.l factory_slot_66c,r1
    mov.l factory_copy4_ptr,r0
    mov.l r0,@r1
    mov.l factory_destination,r1
    mov #16,r3
    mov #0,r2
factory_blank_scan:
    mov.b @r1+,r0
    or r0,r2
    dt r3
    bf factory_blank_scan
    tst r2,r2
    bf factory_return
    mov.l factory_destination,r1
    mov.l factory_source,r2
    mov #16,r3
factory_copy:
    mov.b @r2+,r0
    mov.b r0,@r1
    add #1,r1
    dt r3
    bf factory_copy
factory_return:
    rts
    nop
    .align 2
factory_destination: .long 0x0600078c
factory_source: .long factory_rom_table
factory_slot_66c: .long 0x0600066c
factory_copy4_ptr: .long cd_resident_copy4
factory_rom_table:
    ! FACTORY_BYTES
    .org 0x2f00,0
! Original resident060011c8, no game ledger writes.
cd_resident_copy4:
    mov r4,r6
    mov.l copy4_destination,r5
    mov #4,r4
copy4_loop:
    add #-2,r4
    mov.b @r6+,r1
    mov.b r1,@r5
    add #1,r5
    mov.b @r6+,r1
    mov r5,r3
    add #1,r5
    tst r4,r4
    bf/s copy4_loop
    mov.b r1,@r3
    rts
    nop
    .align 2
copy4_destination: .long 0x06000828
