/* STM32L072CBT6: 128 KB flash, 20 KB SRAM (DS10689 Table 2). */
ENTRY(Reset_Handler)

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 128K
  RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 20K
}

_estack = ORIGIN(RAM) + LENGTH(RAM);
_min_stack = 0x800;                      /* 2 KB reserved for the stack */

SECTIONS
{
  .isr_vector : { KEEP(*(.isr_vector)) } > FLASH

  .text :
  {
    *(.text*) *(.rodata*)
    KEEP(*(.init)) KEEP(*(.fini))
    . = ALIGN(4);
  } > FLASH

  .ARM.exidx : { *(.ARM.exidx*) } > FLASH

  .preinit_array : { PROVIDE_HIDDEN(__preinit_array_start = .); KEEP(*(.preinit_array*)); PROVIDE_HIDDEN(__preinit_array_end = .); } > FLASH
  .init_array    : { PROVIDE_HIDDEN(__init_array_start = .); KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array*)); PROVIDE_HIDDEN(__init_array_end = .); } > FLASH
  .fini_array    : { PROVIDE_HIDDEN(__fini_array_start = .); KEEP(*(SORT(.fini_array.*))) KEEP(*(.fini_array*)); PROVIDE_HIDDEN(__fini_array_end = .); } > FLASH

  _sidata = LOADADDR(.data);
  .data :
  {
    . = ALIGN(4); _sdata = .;
    *(.data*)
    . = ALIGN(4); _edata = .;
  } > RAM AT > FLASH

  .bss (NOLOAD) :
  {
    . = ALIGN(4); _sbss = .; __bss_start__ = _sbss;
    *(.bss*) *(COMMON)
    . = ALIGN(4); _ebss = .; __bss_end__ = _ebss;
  } > RAM

  /* not cleared by the startup code, so a value written here survives a software reset (the DFU request flag) */
  .noinit (NOLOAD) : { . = ALIGN(4); *(.noinit*) . = ALIGN(4); } > RAM

  . = ALIGN(8);
  end = .; _end = .;                     /* heap start for newlib's _sbrk */
  ASSERT(. + _min_stack <= _estack, "RAM overflow: not enough room left for the stack")
}
