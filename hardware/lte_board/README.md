# LTE-M / NB-IoT sensor board: STM32L072 + SIM7080G (KiCad project, rev 0.9)

A KiCad 9 project for a battery-powered board (1-cell Li-ion, e.g. 18650s in parallel; USB-C for power and programming) where an ultra-low-power
STM32L072CBT6 drives a SIMCom SIM7080G LTE Cat-M1/NB-IoT + GNSS modem, with a Qwiic/STEMMA QT I2C
port for temperature, humidity and UV sensors. Almost every part is in the LCSC/JLCPCB library, and
each symbol carries an `LCSC` field holding the JLCPCB part number.

Scope: schematic, BOM, and a **draft PCB layout** (`lte_board.kicad_pcb`, see [PCB layout (draft)](#pcb-layout-draft)).

## Files

| File | What it is |
|---|---|
| `DESIGN.md` | Design record: requirements, decisions and rationale, power budget, layout toolchain, lessons learned, open items. **Start here if you're continuing the work.** |
| `lte_board.kicad_pro` / `lte_board.kicad_sch` | The project and the one-sheet A2 schematic |
| `lte_board.kicad_sym` + `sym-lib-table` | Project symbol library (all symbols are also embedded in the schematic) |
| `fp-lib-table` + `lte_board_lcsc.pretty/` | Footprints imported from LCSC (SIM7080G, SMN-303, TS-1187A, ...), with the fixes listed under PCB layout |
| SIMCom *SIM7080G Hardware Design* V1.04 | Not included (SIMCom's copyright). Get it from [SIMCom's SIM7080G page](https://www.simcom.com/product/SIM7080G.html); section numbers cited here refer to V1.04 |
| `bom_jlcpcb.csv` / `cpl_jlcpcb.csv` | JLCPCB BOM and placement (CPL) files, generated from the design and cross-checked to list exactly the same parts (see below) |

## Block overview

- **Battery input (rev 0.3):** **J9** JST PH 2.0 mm through-hole (B2B-PH-K-S), **pin 1 = +**. Check your pack's polarity: JST-PH battery leads have no universal convention, but a reversed pack is safe (see Q3).
  - **Q3** (AO3401A P-FET, gate to GND via R33) is reverse-polarity protection: it only conducts with the battery the right way round.
  - **U9 DW01A + Q5 FS8205A** (in the negative lead, BATT_N to GND) disconnect the cells on over-discharge (about 2.4 V), overcurrent or short (about 3 A), so bare cells are safe. They reconnect once the cells are recharged externally. No on-board charging.
  - **U8 MAX17048** fuel gauge on VBAT: I2C address 0x36 on its **own I2C1 bus** (FG_SDA **PB7**, FG_SCL **PB8**, 4.7k pull-ups R41/R42), ALRT to **PB9**. Use it in firmware to stop uploads around 3.3 V; the DW01A is only the hardware backstop.
  - Battery life: about 2,000-2,500 mAh for 60 days of 15-minute uploads in typical coverage (see the power estimate).
- **VSYS:** USB 5V through Schottky **D4**, or the battery through P-FET **Q4**. Q4's gate is tied to USB 5V (R34 pull-down), so it turns off whenever USB is present, and USB never back-feeds the cells. VSYS feeds the modem buck and the 3.3V LDO.
- **USB-C** (J1, 5.1k CC pull-downs, USBLC6 ESD) gives +5V. **D1** (red) lights only when USB is connected; it no longer draws from the battery.
  - **U2 SY8089 buck** makes +3V8 (3.93V) for modem VBAT from VSYS. Below about 3.9V on the cell it runs at maximum duty and passes VSYS through (confirm 100% duty-cycle support in the SY8089 datasheet). The modem accepts 2.7-4.8V. Its EN pin is driven by MCU **PB3**, so firmware can hard power-cycle the modem; R6 keeps the modem off until firmware enables it.
  - **U3 TPS7A0233 LDO** makes +3V3 from VSYS for the MCU, level shifter, LEDs and sensors. Its 25 nA quiescent current keeps it out of the sleep budget (the ME6211 it replaced drew about 40 uA).
  - The MCU drives the buck EN through **R28 (1k)**, so **JP5** can force the 3.8V rail on without fighting a driven pin.
- **MCU:** STM32L072CBT6, with crystal-less USB FS and a **32.768 kHz crystal Y1** (C54/C55 = 10 pF) on PC14/PC15 for an accurate RTC (firmware: LSE drive **medium-high or high**; see DESIGN.md §4). It can be programmed over **USB with ST's built-in DFU bootloader** (hold **SW2 BOOT0**, tap **SW1 RESET**, then flash with STM32CubeProgrammer or `dfu-util`) or over SWD (J2, 10-pin 1.27mm Cortex header). R10 pulls BOOT0 low for normal boot.
- **Level shifting:** the modem's logic is **1.8V** (2.1V absolute max). U5 TXS0108E translates all 8 UART/status lines between 3.3V and the modem's VDD_EXT (1.8V). OE is tied to VDD_EXT, so the shifter goes Hi-Z whenever the modem is off and nothing back-powers it.
  - **R29/R30/R31** (100k, pull-up) on RXD, DCD and CTS, and **R32** (100k, pull-down) on RI, hold the MCU-side lines in a safe state while the shifter is Hi-Z. SIMCom requires at least 47k on these lines with a shifter IC (V1.04 section 3.3); don't use the STM32's internal pulls (about 40k) instead.
- **Modem:** SIM7080G.
  - VBAT decoupling: 100uF + 10uF + 100nF + 33pF + 10pF, plus the **D7** TVS (ESD5651N-2/TR), per SIMCom guidance.
  - **PWRKEY** is pulled low by NPN Q1 (MCU **PA7** high = button pressed), with ESD diode **D8** at the module pin. **NETLIGHT** drives a green LED via Q2.
  - **JP2** (+ R26 10k, per SIMCom) straps BOOT_CFG to VDD_EXT for USB download mode. Leave it open for normal use.
  - **R27** pulls the STATUS line low so the MCU reads "off" when the modem is unpowered and the level shifter is Hi-Z.
- **USB select (one USB-C port, two devices):** USB-C D+/D- go through the 3-pad solder jumpers **JP3 (D+)** and **JP4 (D-)**.
  - **Default, pads 1-2 bridged (pre-bridged on the board): USB goes to the MCU** (PA11/PA12) for the DFU bootloader or a USB device in firmware.
  - **Modem mode:** cut the 1-2 bridge on both jumpers and bridge 2-3. USB then goes to the modem through R3/R4 for SIMCom firmware updates, logs, or use as a USB modem from a PC. In modem mode, also:
    - bridge **JP1**, which feeds 5V to the modem's USB_VBUS (100k pull-down R25 when open). Keep it open in normal use: the modem can't sleep while USB_VBUS is present.
    - make sure the modem is powered before its USB lines see a cable (SIMCom: no voltage on any pin while VBAT is off). Either have firmware turn it on, or bridge **JP5**, which forces the 3.8V rail on.
    - start the modem with a PWRKEY press: firmware does it via PA7, or by hand, short **TP2 (PWRKEY)** to **TP4 (GND)** for about 1-2 s. Don't leave PWRKEY grounded, because the modem resets after 12.6 s.
- **SIM:** nano-SIM push-push holder (XunPu SMN-303), 22R series resistors, 33pF caps and an ESD array. The card slides in from the **bottom edge** of the board; keep the strip in front of the slot clear.
  - **Card detect:** per the SMN-303 drawing, the holder's switch **shorts CD to GND with no card and opens when a card is inserted**. With **R24 = 1M** pulling up to 3.3V, **PB6 reads high = card present**. At the original 10k, R24 drew about 330 uA whenever no card was inserted.
- **RF:**
  - **LTE** works out of the box on **U.FL J6** with any 50 Ω antenna. The R19/C40/C41 pi network is fitted as
    0R + two empty pads, only for tuning later. C61 (100 pF series) and D6 (TVS) protect the port from ESD.
    For an SMA antenna instead: hand-solder the optional **SMA J10** (Amphenol 132322, right edge) and fit
    **R40 = 0R** (LCSC C17168).
  - **GNSS** on **SMA J7** (Amphenol 132322, top edge, hand-soldered; LCSC C42394535). Use an **active** GNSS
    antenna (3.3 V, ≤ 25 mA) with a standard SMA plug, not RP-SMA. The board feeds it 3.3 V through a bias tee
    (L2 47 nH + R38 10R, C56 100 pF DC block), switched by U10 TPS22945 (current-limited): **PB0 high = antenna
    on**, **PB1 low = over-current**. GNSS is optional: LTE works without it, and the two can't run at the same time.
- **Expansion:** Qwiic J3 (I2C2 on PB13/PB11, 4.7k pull-ups R12/R13, 3.3V); the fuel gauge has its own bus, so a damaged sensor cable can't hang battery monitoring. A second Qwiic port J11 (left edge below J3, assembled, same JST SH part) is on a third bus, I2C3 (PA8 SCL / PB4 SDA, 4.7k pull-ups R43/R44), so the two sensor strings can't hang each other. J4 is a 2x5 2.54mm header, DNP (hand-solder if wanted): odd pins 1-9 = GND, DBG_RX (PA10), DBG_TX (PA9), 3V3, BOOT0 (the old 1x5 debug header, same positions); even pins 2-10 = PA15, PB3, PB4, PB5, GND, i.e. SPI1 NSS/SCK/MISO/MOSI, or USART5 on PB3/PB4, or timer/pulse inputs.

## MCU pin map

| STM32 pin | Function | Connects to |
|---|---|---|
| PA2 / PA3 | USART2 TX / RX | modem RXD / TXD (via U5) |
| PA0 / PA1 | USART2 CTS / RTS | modem CTS / RTS (via U5) |
| PA4 | GPIO in | modem STATUS (high = modem on) |
| PA5 | GPIO in | modem DCD |
| PH1 | GPIO out | modem DTR (sleep control) |
| PH0 | GPIO in / EXTI0 | modem RI (wake on SMS/URC) |
| PA7 | GPIO out | PWRKEY driver Q1 (high = press) |
| PC13 | GPIO out | modem power enable (buck EN, through R28); keep the RTC off this pin (no RTC_OUT / tamper) |
| PA11 / PA12 | USB DM / DP | USB-C through JP4 / JP3 (default) |
| PB13 / PB11 | I2C2 SCL (AF5) / SDA (AF6) | Qwiic J3 (sensors), R12/R13 pull-ups |
| PB8 / PB7 | I2C1 SCL (AF4) / SDA (AF1) | MAX17048 fuel gauge U8, R41/R42 pull-ups |
| PB9 | GPIO in / EXTI9 | MAX17048 alert (low battery / SOC change), R37 pull-up |
| PA9 / PA10 | USART1 TX / RX | debug header J4 (pins 5 / 3) |
| PB15 | GPIO out | user LED D2 |
| PA8 / PB4 | I2C3 SCL / SDA (AF7) | second Qwiic J11 (left edge, below J3), R43/R44 pull-ups; PB4 is also J4 pin 6 |
| PA15 / PB3 / PB4 / PB5 | expansion: SPI1 NSS / SCK / MISO / MOSI (AF0); also USART5 TX / RX on PB3 / PB4 (AF6), TIM2_CH1 / CH2 on PA15 / PB3, LPTIM1_IN1 on PB5 (AF2); EXTI 15 / 3 / 4 / 5 | J4 pins 2 / 4 / 6 / 8. Never AF4 on PA15 (USART2_RX = the modem UART). PB4 doubles as I2C3_SDA (4.7k pull-up R44): SPI1 and I2C3 can't both use it |
| PB6 | GPIO in / EXTI6 | SIM card detect (high = card present) |
| PA13 / PA14 | SWDIO / SWCLK | SWD header J2 |
| PB0 | GPIO out | GNSS antenna power (U10 ON; R39 pull-down = off) |
| PB1 | GPIO in, pull-up | GNSS antenna over-current flag (U10 OC, open drain, low = fault) |
| PC14 / PC15 | LSE | 32.768 kHz crystal Y1 |
| PA6, PB2, PB10, PB12, PB14 | spare | not connected |

## Modem power-on sequence (firmware)

1. Drive PC13 high (enables the 3.8V rail) and wait about 50 ms.
2. Drive PA7 high for about 1.2 s, then low. This holds PWRKEY low for that long; the modem needs at least 1 s.
3. Wait for PA4 (STATUS) to go high (at least 1.8 s). Then talk AT over USART2 at 115200 baud (the modem auto-bauds), with RTS/CTS optional.
4. To power off: send `AT+CPOWD=1` (or pulse PWRKEY again), wait for STATUS to go low, **then** drive PC13 low to cut the rail for zero sleep current. SIMCom warns that cutting VBAT while the modem runs risks corrupting its file system (V1.04 section 3.2.2), so use a hard cut only to recover a hung modem.

Recommended field strategy: keep the modem fully off between uploads. The MCU sleeps on its RTC (about 1 uA),
logs readings, and every N readings runs steps 1-4 to upload a batch. Arm the STM32 independent watchdog so a
stuck MCU recovers too. While the modem is off, U5 is Hi-Z and R29-R32 hold the MCU-side lines in a safe state,
so no internal pulls are needed. DTR and DCD are wired in case you later want UART sleep (`AT+CSCLK=1` + DTR)
or transparent-mode carrier detect. The power-off strategy doesn't need them.

**SIM cards:** the SIM7080G only supports **1.8V SIM cards**. Most modern IoT SIMs (1NCE, Hologram, etc.)
are fine; some old 3V-only cards won't be detected.

## Before layout: import the LCSC footprints

These parts use footprints that aren't in KiCad's standard library. Import them from LCSC/EasyEDA with
[easyeda2kicad](https://github.com/uPesy/easyeda2kicad.py) (run it in this project folder):

```
pip install easyeda2kicad
easyeda2kicad --footprint --3d --lcsc_id=C2943992 --output ./lte_board_lcsc   # U6 SIM7080G
easyeda2kicad --footprint --3d --lcsc_id=C266888  --output ./lte_board_lcsc   # J8 SMN-303 nano-SIM
easyeda2kicad --footprint --3d --lcsc_id=C318884  --output ./lte_board_lcsc   # SW1 (optional, replaces TL3342 stand-in)
easyeda2kicad --footprint --3d --lcsc_id=C279948  --output ./lte_board_lcsc   # L1 3D model (the land is L_Sunlord_SWPA4030S, per Sunlord's spec)
easyeda2kicad --footprint --3d --lcsc_id=C145956  --output ./lte_board_lcsc   # J3 (optional, check vs JST SH footprint)
easyeda2kicad --footprint --3d --lcsc_id=C47507   --output ./lte_board_lcsc   # U10 TPS22945 (courtyard redrawn to pads + 0.25)
easyeda2kicad --footprint --3d --lcsc_id=C3039401 --output ./lte_board_lcsc   # D5 WE05DGCF-B (courtyard redrawn)
easyeda2kicad --footprint --3d --lcsc_id=C535146  --output ./lte_board_lcsc   # D6 ESD103-B1-02EL (courtyard redrawn)
easyeda2kicad --footprint --3d --lcsc_id=C239784  --output ./lte_board_lcsc   # D7 ESD5651N-2/TR (courtyard redrawn)
# U8 MAX17048_TDFN-8_2x2mm: pads/EP replaced with Maxim land pattern 90-0065 rev E
# J7/J10 SMA_Amphenol_132322_EdgeMount is hand-made from Amphenol drawing 132322 rev D (no EasyEDA footprint)
```

Then point each part's Footprint field at the imported footprint. Use Tools → Edit Symbol Fields,
or Footprint Assignment.

## Check these before ordering

1. **U7 ESDA6V1W5 pinout.** Pin 2 is the common ground and pins 1/3/4/5 are I/O. This was checked against a pin-compatible second-source datasheet (ElecSuper), not ST's own, so confirm once against ST's datasheet.
2. **J8 SIM holder pad numbers.** After importing the SMN-303 footprint, check that its pad numbers match the symbol: 1 = C1 VCC, 2 = C2 RST, 3 = C3 CLK, 5 = C5 GND, 6 = C6 VPP, 7 = C7 I/O, 8 = CD. Card-detect polarity has been checked against the drawing: CD is shorted to GND with no card and open with a card, so PB6 is high when a card is present.
3. **Stock (JLCPCB, checked 2026-10-07):** STM32L072CBT6 C465977 (2,927), SIM7080G C2943992 (729), TXS0108EPWR C17206 (52k), TPS7A0233PDBVR C2887324 (8,010). Re-check before ordering.
4. **Basic vs Extended:** confirm in JLCPCB's parts search. Every Extended part adds a small setup fee.
5. **SIM7080G assembly:** JLCPCB lists it as MSL3 with X-ray inspection required, so pick an assembly option that includes that.
6. **Battery connector polarity:** J9 pin 1 is **+** (marked on the silkscreen). Reverse polarity is protected by Q3, but the board won't run until the pack is the right way round.
7. **USB power budget:** the board asks for USB default power (5.1k CC resistors, 500mA). Modem bursts (about 0.5A at 3.9V) fit, but avoid unpowered hubs and long, thin cables. There's no fuse on VBUS; add a polyfuse at layout time if you want one.

## PCB layout (draft)

![top render](pcb_render_top.png)

- **Board:** 63.5 x 46 mm (2.5" x 1.81"), 4 layers, all parts on the top side (the USB-select solder jumpers JP3/JP4 are bare copper on the bottom, between USB-C and the MCU). Everything is SMD except the battery connector J9 (through-hole, for strength) and the DNP header J4.
- **Mounting:** four M2 holes (2.2 mm, non-plated) centred 2.5 mm in from each corner. There is no copper, vias or parts under the screw heads (4.9 mm keep-out).
- **DRC:** clean (0 violations, 0 unconnected, matches the schematic).
- **Stackup use:**
  - F.Cu: signals + GND pour.
  - In1: solid GND, no tracks at all (rev 0.7).
  - In2: power only (+3V3, +5V, VDD_EXT, battery, GNSS antenna supply) + GND pour, plus a +3V8 strip from the buck to the modem VBAT pins. No tracks under the USB pair.
  - B.Cu: signals + GND pour. Signals use only F.Cu and B.Cu.
  - GND stitching vias everywhere.
- **Placement:**
  - Modem top right. LTE U.FL J6 and the optional SMA J10 on the right edge; GNSS SMA J7 and its bias tee on the top edge.
  - Nano-SIM below the modem; the card loads from the bottom edge. The 22R SIM resistors sit in the gap under modem pins 15-17.
  - Left edge, top to bottom: Qwiic J3, SWD J2, USB-C J1. The buck is in the bottom-right corner.
  - **MCU -> level shifter -> modem in one row** (rev 0.7): U4 is turned 180 degrees so its USART2 corner (PA0-PA3) faces U5, and U5's channels follow the modem's pin order, so the whole modem interface runs straight, in order, on F.Cu.
  - Status LEDs are in the bottom middle; RESET (SW1) is in the bottom-left corner below USB-C and BOOT0 (SW2) on the bottom edge (hold BOOT0, tap RESET).
  - **Battery block** (bottom left): J9, Q3, U9/Q5 protector, U8 fuel gauge. **USB/battery OR-ing** (D4, Q4, R34) sits between SW2 and the SIM holder; the LDO U3 (with C4/C5) is in the bottom-right corner by the buck. The SIM holder's opening is at the bottom edge, and six top-layer keep-outs (from the SMN-303 drawing's "no pattern and via hole" areas) keep copper and vias out from under its contact springs.
  - **USB select jumpers JP4 (D-) / JP3 (D+)** are on the bottom side, below-left of the MCU, between it and U1 (pad 1 = MCU side, west; pad 3 = modem side, east). **JP5** (modem power override) is below the MCU, by R28. **TP4** (GND) is next to **TP2** (PWRKEY), for starting the modem by hand.
- **Hand-routed:**
  - LTE and GNSS RF feeds (0.30 mm, about 49 ohm).
  - VBAT bus (0.6 mm) from pins 34/35 to all the VBAT caps.
  - USB D+/D-: J1 to U1 (flow-through) to the select jumpers on F.Cu. From the jumpers' modem side, a coupled pair runs on B.Cu to R3/R4 at the modem. The MCU side of the jumpers is short and autorouted (USB full-speed doesn't need impedance control).
  - +5V: a 0.5 mm In2 highway from J1 to D4.
  - Escape vias for modem pins 39-42.
  - The modem interface (rev 0.7): MCU -> U5 -> modem on F.Cu in pin order, U5's supply pins tied under its body to C21/C62, the pull resistors in line. DCD and NRST each drop to B.Cu once; STATUS crosses under the GNSS RF line on B.Cu; PWRKEY runs on B.Cu with one F.Cu hop over STATUS; NETLIGHT runs on B.Cu with one F.Cu hop over the modem USB pair.
  - VSYS and VBAT trunks (0.5 mm), the DW01A supply, the LSE crystal.
- **Autorouted:** everything else, with Freerouting (signals on F.Cu/B.Cu only, power may use In2); a small grid maze router (`layout_scripts/maze_route.py`) finishes any leftovers. +3V3, VDD_EXT and GNSS_BIAS then went to In2 at 0.5 mm (`rip_net.py` + `maze_route.py --wide`).
- **Rules:** JLC-friendly. 0.15 mm default track/space, 0.5/0.3 mm vias, 0.6 mm VBAT, 0.3 mm power, 0.30 mm RF. `lte_board.kicad_dru` adds the layer rules: no tracks on In1, power only on In2, and power tracks 0.5 mm on In2 / 0.3 mm outside (the interactive router uses these as its default widths).
- **The layout is now GUI-owned** (the owner hand-edited it on 2026-11-02). `pipeline.sh` would discard those edits; edit the board in KiCad or with the in-place scripts (`rip_net.py`, `maze_route.py`, `stitch.py`).

### USB pair impedance (90 ohm)

KiCad doesn't compute impedance. You choose a width and gap from a calculator and enter them in the net class.

- The `USB` net class is set to **0.25 mm width / 0.20 mm gap**: 92 ohm differential on JLC04161H-7628 (outer layer, 0.21 mm prepreg to the adjacent plane), from a 2D field solve including solder mask (DESIGN.md H06).
- JLC04161H-7628 is what JLC builds for a 4-layer 1.6 mm order with **no impedance requirement**, so no paid impedance-control option is needed. Results are then within normal fab tolerance, not guaranteed to ±10%.
- To adjust, change the diff-pair values in Board Setup -> Net Classes -> USB, then re-route with Route -> Differential Pair (shortcut 6). KiCad pairs `USB_DP`/`USB_DN` automatically from the P/N suffix.
- The RF feeds are 0.30 mm with a 0.2 mm gap to the GND pour: about 49 ohm on the same stackup.

### Before ordering

1. Check the impedances above.
2. Review the autorouted traces, especially around the MCU and level shifter.

### Ordering at JLCPCB (BOM and CPL)

- Upload `bom_jlcpcb.csv` and `cpl_jlcpcb.csv`. Both are generated from the design (`layout_scripts/make_jlc.py`) and cross-checked to contain exactly the same designators. Every BOM line has an LCSC number.
- **No vias in pads:** the layout scripts keep every via off SMD pads (`check_via_in_pad.py` reports 0), so JLC's via-in-pad filling option isn't needed.
- These are **deliberately not in either file**, because they aren't parts to place:
  - JP1-JP5 and TP1-TP4: copper-only solder jumpers and test pads;
  - C40/C41 and J4: do-not-populate;
  - H1-H4: mounting holes.

  If you export a BOM yourself from KiCad, keep "exclude DNP" on. Otherwise JLC warns that those designators "don't exist in the CPL file" (harmless, but confusing).
- **J9 is through-hole.** Either enable JLC's THT assembly for it or leave it out of the order and hand-solder it (2 pins).
- `cpl_jlcpcb.csv` already includes JLC's rotation and origin corrections (`JLC_CORR` in `make_jlc.py`, fitted against each part's LCSC footprint). Still check pin 1 and polarity in JLC's placement preview, especially J9 (+ = pin 1), SOT-23/SOT-23-6, and polarized parts (LEDs, D4). KiCad and JLC sometimes disagree on a part's zero orientation.

**Footprint fixes made during layout (in `lte_board_lcsc.pretty/`):**

- The imported SIM7080G footprint was renamed to `SIM7080G` so the schematic link resolves.
- The SMN-303 pads were renumbered to match the symbol (1/2/3/5/6/7 = C1-C7, 8 = CD, 9-11 = shell GND), and its two locating pegs were made NPTH.
- SW1 now uses the real TS-1187A footprint (`SW_TS-1187A`). Only one diagonal pad pair is numbered, which is correct whichever way the internal pairs are wired.
- L1 uses `L_Sunlord_SWPA4030S`: Sunlord's recommended land (1.10 × 3.70 mm pads, 1.90 mm gap; spec Rev. 11, Table 4-1). It replaces the Würth MAPI-4030 stand-in, whose pads barely reached the SWPA4030S terminals.

`layout_scripts/` holds the scripts that generate this board. `pipeline.sh` runs the whole flow (see DESIGN.md §7):

1. `gen_board.py`: placement.
2. `preroute.py`: hand routes, planes and keepouts.
3. `export_dsn.py`: export for Freerouting.
4. `postroute.py`, `stitch.py`, `fixup.py`, `drop_dangling.py`, `hole_keepouts.py` and `maze_route.py`: import, pours, stitching, cleanup and finishing leftover connections.
5. `sch_rev02.py`: the schematic edits that turned rev 0.1 into rev 0.2 (already applied; kept for reference).
6. `sch_rev03.py`: the rev 0.3 battery/fuel-gauge/VSYS schematic edits (already applied). `sch_rev04.py`: the LSE crystal and L1 land; `sch_rev05.py`: antennas; `sch_rev06.py`: audit parts; `sch_rev07.py`/`sch_rev08.py`: the rev 0.7 re-pinning for the MCU -> U5 -> modem row (all already applied).
7. `final_fixes.py`, `silk_marks.py`: last clean-ups (bridging stray vias, GND island vias, J9 polarity marks).
8. `make_jlc.py`: writes `bom_jlcpcb.csv` + `cpl_jlcpcb.csv` from the netlist and KiCad's position file, and checks they list the same parts.

Run them with KiCad's bundled Python and Freerouting. They regenerate the board from scratch, so don't rerun them once you start hand-editing.

## Layout guidance (original notes)

- Use a 4-layer board (e.g. JLC04161H-7628) with solid ground on layer 2.
- Route RF_ANT and GNSS_ANT as **50 ohm grounded coplanar waveguide**, sized with JLCPCB's impedance calculator. Keep them short, stitch ground vias along both sides, and keep the module's RF area clear of other traces.
- Make VBAT (+3V8) traces at least 1.5-2 mm wide. Put C30-C34 right at the module's VBAT pads, and keep the buck (U2, L1, C1, C3) compact with a short ground return.
- Route USB D+/D- as a 90 ohm differential pair. Put U1 next to J1.
- Put the SIM holder close to the module, and the ESD array (U7) and 33pF caps next to the holder.
- Add mounting holes and an antenna keep-out or edge placement as needed.

## Sources

- SIMCom SIM7080G Hardware Design V1.04 (pinout, power, PWRKEY, BOOT_CFG, SIM, RF)
- SIMCom SIM7080 Series AT Command Manual V1.02
- ST STM32_open_pin_data (STM32L072C(B-Z)Tx pinout; the L071 and L072 differ only at pin 36, VDDIO2 vs VDD_USB)
- LCSC / JLCPCB part pages for every LCSC number in the BOM
