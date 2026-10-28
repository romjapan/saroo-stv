AS      := sh-elf-as
LD      := sh-elf-ld
OBJCOPY := sh-elf-objcopy

ASFLAGS := --big --isa=sh2
LDFLAGS := -T ldscript

all: stv-native-hle.bin

SHIENRYU_OBJ := reloc_veneers-shienryu.o

SMOKE_OBJ := tests/smpc_smoke.o

reloc_veneers.o: reloc_veneers.s
	$(AS) $(ASFLAGS) -o $@ $<

reloc_veneers-shienryu.o: reloc_veneers.s
	$(AS) $(ASFLAGS) --defsym SHIENRYU_PROFILE=1 -o $@ $<

stv-native-hle.elf: reloc_veneers.o ldscript
	$(LD) $(LDFLAGS) $< -o $@

stv-native-hle.bin: stv-native-hle.elf
	$(OBJCOPY) -O binary $< $@
	@echo "Size: $$(stat -c%s $@) bytes"

stv-native-hle-shienryu.elf: $(SHIENRYU_OBJ) ldscript
	$(LD) $(LDFLAGS) $< -o $@

stv-native-hle-shienryu.bin: stv-native-hle-shienryu.elf
	$(OBJCOPY) -O binary $< $@
	@echo "Shienryu HLE size: $$(stat -c%s $@) bytes"

test-build: stv-native-hle.bin
	python3 verify_build.py stv-native-hle.elf
	sh-elf-objdump -d stv-native-hle.elf

test-shienryu: stv-native-hle-shienryu.bin
	python3 verify_build.py stv-native-hle-shienryu.elf shienryu

# Relink the same position-independent native image into HWRAM and pair it
# with a tiny runner. Yabause can load both binaries to exercise real SMPC
# INTBACK without requiring the SAROO CS1 mapping.
tests/smpc_smoke.o: tests/smpc_smoke.s
	$(AS) $(ASFLAGS) -o $@ $<

tests/smpc_smoke_pressed.o: tests/smpc_smoke.s
	$(AS) $(ASFLAGS) --defsym EXPECT_PRESSED=1 -o $@ $<

tests/reloc_veneers_smoke.o: reloc_veneers.o
	$(OBJCOPY) --rename-section .text=.hle $< $@

tests/smpc_smoke.elf: $(SMOKE_OBJ) tests/reloc_veneers_smoke.o
	$(LD) -e _start -Ttext 0x06004000 --section-start=.hle=0x06008000 $^ -o $@

tests/smpc_smoke.bin: tests/smpc_smoke.elf
	$(OBJCOPY) -j .text -j .hle -O binary $< $@

test-input-image: tests/smpc_smoke.bin
	@echo "Yabause smoke binaries built"

tests/reloc_veneers_pressed.o: reloc_veneers.s
	$(AS) $(ASFLAGS) --defsym SMPC_TEST_VECTOR=1 -o $@ $<

tests/reloc_veneers_pressed_smoke.o: tests/reloc_veneers_pressed.o
	$(OBJCOPY) --rename-section .text=.hle $< $@

tests/smpc_smoke_pressed.elf: tests/smpc_smoke_pressed.o tests/reloc_veneers_pressed_smoke.o
	$(LD) -e _start -Ttext 0x06004000 --section-start=.hle=0x06008000 $^ -o $@

tests/smpc_smoke_pressed.bin: tests/smpc_smoke_pressed.elf
	$(OBJCOPY) -j .text -j .hle -O binary $< $@

test-input-pressed-image: tests/smpc_smoke_pressed.bin
	@echo "Yabause pressed-input smoke binary built"

clean:
	rm -f reloc_veneers.o $(SHIENRYU_OBJ) stv-native-hle.elf stv-native-hle.bin \
		stv-native-hle-shienryu.elf stv-native-hle-shienryu.bin \
		$(SMOKE_OBJ) tests/smpc_smoke_pressed.o tests/reloc_veneers_smoke.o \
		tests/reloc_veneers_pressed.o tests/reloc_veneers_pressed_smoke.o \
		tests/smpc_smoke.elf tests/smpc_smoke.bin \
		tests/smpc_smoke_pressed.elf tests/smpc_smoke_pressed.bin

.PHONY: all test-build test-shienryu test-input-image test-input-pressed-image clean
