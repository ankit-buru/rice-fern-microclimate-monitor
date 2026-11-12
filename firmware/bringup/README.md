# Bring-up firmware (STM32L072, TreeWeather LTE board rev 0.9)

A command console on the board's USB-C port (it shows up as a USB serial port) for checking the hardware one block
at a time. C on ST's CMSIS register headers, with TinyUSB for the USB serial port. No HAL, no RTOS. About 23 KB of
flash (of 128) and 3 KB of RAM (of 20).

## Build

Needs the Arm GNU Toolchain (`arm-none-eabi-gcc` on the PATH: `brew install --cask gcc-arm-embedded`), CMake and
`dfu-util` (`brew install dfu-util`).

```bash
./fetch_deps.sh
```
```bash
cmake -B build && cmake --build build
```

`fetch_deps.sh` downloads the pinned libraries into `third_party/` (not committed): ST `cmsis-device-l0` v1.9.4,
Arm `CMSIS_5` 5.9.0, TinyUSB 0.21.0.

## Flash (USB DFU, no probe needed)

1. JP3/JP4 at their default (1-2 = USB to the MCU).
2. First time: hold **BOOT0** (SW2), tap **RESET** (SW1), release BOOT0. The board enumerates as `0483:df11`
   ("STM32 BOOTLOADER"). Later: type `dfu` in the console instead.
3. Run:
   ```bash
   cmake --build build --target flash
   ```
   This is `dfu-util -a 0 -s 0x08000000:leave -D build/bringup.bin`; the board starts the new firmware when it's done.

ST's AN2606 notes that the L07x ROM DFU can fail behind some high-speed USB host controllers. If `dfu-util` can't
find or talk to the board, go through a USB hub.

## Connect

The user LED D2 flashes once a second when the firmware runs, even if USB doesn't come up. Then:

```bash
screen /dev/cu.usbmodem* 115200
```

(any terminal works; the baud rate is ignored on USB). Type `help`. The same console is on J4 pins 3/5 (USART1,
115200 8N1) if J4 is fitted.

## Bring-up order

| Step | Command | Expect | If not, look at |
|---|---|---|---|
| 1 | (power over USB) | D1 (red) on, D2 heartbeat | USB-C J1, D4, Q4, LDO U3 |
| 2 | `selftest` | everything PASS | the failing block |
| 3 | `vdda` | 3.30 V +-3 % | LDO U3, C4/C5 |
| 4 | `i2c` | 0x36 on I2C1; I2C2/I2C3 lines high | R41/R42, R12/R13, R43/R44 |
| 5 | `fg` (with a cell on J9) | VCELL = the cell voltage | U8, Q3/U9/Q5 battery path |
| 6 | `lse`, then `rtc 10` | LSE ready in < 2 s, RTC counts 10 s in ~10 000 ms | Y1, C54/C55 |
| 7 | `pins` with and without a SIM | SIM_DET follows the card | J8 CD switch, R24 |
| 8 | `gnss on`, `gnss off` | 3.3 V on the J7 centre pin, OC flag ok | U10, L2/R38 |
| 9 | `mdm on` | STATUS high in ~2-3 s, then "AT OK" | +3V8 buck U2 (EN = PC13), Q1, U5 |
| 10 | `mdm info` | model, firmware, IMEI, SIM state, RAT/band settings | U5 RXD/TXD |
| 11 | `mdm scan` (antenna on J6) | a list of operators, access tech 7 = Cat-M, 9 = NB-IoT (1-3 min) | antenna, J6, RF path R19/C61/D6 |
| 12 | `mdm watch` | RSSI in dBm, serving cell (band, RSRP/RSRQ), registration | antenna placement, SIM |
| 13 | `mdm off` | "NORMAL POWER DOWN", STATUS low, then the rail off | |

The modem commands are read-only: they never write the modem's stored settings. The AT commands were checked
against the SIM7070/SIM7080/SIM7090 Series AT Command Manual V1.05. Without a SIM it can't register; whether it
will scan and report a cell without one isn't stated in the manual, so try it.

`bridge` passes the console straight to the modem's UART for interactive AT sessions (Ctrl-] leaves).
`mdm kill` cuts the modem rail at once: only for a hung modem, since SIMCom warns it can corrupt the modem's
file system.

## Not yet verified against documents

These came from memory and are marked in the code; check them on the first board:

- I2C timing `0x30420F13` (100 kHz at 16 MHz): scope SCL.
- MAX17048 register map and scaling (`fg`): check against the datasheet (19-6171 Rev 7).
- ROM bootloader address 0x1FF00000 (`dfu`): if `dfu` doesn't bring up `0483:df11`, use BOOT0 + RESET.
- Unique-ID word layout (the USB serial number).
