# LTE sensor board: design document (rev 0.3)

This is the design record for `hardware/lte_board`. It covers what the board must do, how it's built,
why each major decision went the way it did, how the layout is generated, what went wrong along the way,
and what's still open. It's written for whoever picks the project up next, human or AI agent.
`README.md` in this folder is the user-facing summary (block overview, pin map, power sequence,
ordering notes). This file is the "why" and "how to keep working on it".

## 1. Purpose and requirements

The board is the logger for a **resurrection-fern microclimate monitor**: a small box in a tree that reads
temperature, humidity and UV sensors and sends the readings over cellular to AWS.

| Requirement | Target | Where it shows up |
|---|---|---|
| Uplink | LTE-M (Cat-M1), NB-IoT as fallback; MQTT/TLS to AWS IoT | SIM7080G modem |
| Cadence | One message every 15 min; hourly batches are acceptable if needed | Power budget, §5 |
| Battery life | **60 days** on 1-cell Li-ion (18650s in parallel), charged off-board | Battery input, §4.7 |
| Users | Field biologists: robust, easy to deploy, **no debug probe needed** to update firmware | USB DFU, §4.2 |
| Sensors | Qwiic/STEMMA QT I2C (3.3 V) | J3 |
| Manufacturing | JLCPCB, **single-sided assembly**, parts from the LCSC library | BOM/CPL, §7.5 |
| Size | Started as "under 2 in x 1 in"; now **63.5 x 46 mm** (2.5 in x 1.81 in) after trade-offs | §4.1 |

## 2. Status

| Item | State |
|---|---|
| Schematic (`lte_board.kicad_sch`, rev 0.3) | ERC: 0 errors, 0 warnings |
| PCB (`lte_board.kicad_pcb`) | DRC: 0 violations, 0 unconnected, 0 schematic-parity issues |
| `bom_jlcpcb.csv` / `cpl_jlcpcb.csv` | 43 lines / 92 parts, every part has an LCSC #, BOM and CPL list identical designators |
| Fabricated / tested | **No.** Nothing has been built yet. |
| Firmware | **None yet.** See §8 for what it has to do. |

## 3. Architecture

```
                       USB-C (J1) --USBLC6 ESD--+--> JP3/JP4 3-pad jumpers --(1-2, default)--> STM32 USB (PA11/PA12)
                                                |                           --(2-3)----------> R3/R4 --> SIM7080G USB
                                     +5V -------+--> D4 Schottky --+
J9 JST-PH --Q3 reverse-polarity P-FET--> VBAT --> Q4 P-FET (off w/ USB) -+--> VSYS --+--> U2 SY8089 buck (EN = PB1 via R28) --> +3V8 --> SIM7080G VBAT
     |  (U9 DW01A + Q5 FS8205A in the negative lead)                                 +--> U3 TPS7A0233 LDO --> +3V3 --> MCU, TXS0108 B side, Qwiic, LEDs
     +--> U8 MAX17048 fuel gauge on VBAT (I2C 0x36, ALRT -> PA8)

STM32L072CBT6 (U4) --USART2 + RTS/CTS + DTR/DCD/RI/STATUS--> TXS0108E (U5, 3.3V<->1.8V, OE = VDD_EXT) --> SIM7080G (U6)
                   --PB0--> Q1 --> PWRKEY      --PB1--> buck EN      <--PB12-- STATUS      --I2C1 (PB6/PB7)--> Qwiic J3 + U8
SIM7080G --> nano-SIM J8 (22R series in the gap under pins 15-17, ESD U7), LTE U.FL J6 (pi-match R19/C40/C41), GNSS U.FL J7
```

The full pin map and block descriptions are in `README.md`. The schematic is one A2 sheet; the rev 0.2 and
rev 0.3 additions are in labelled blocks along the bottom.

## 4. Decisions and rationale

Each entry gives the choice, why it was made, and what was rejected. Don't reverse one of these without
checking its reason first. Several were explicit choices by the project owner.

### 4.1 Board size and assembly
- **2 in x 1 in was infeasible.** The summed courtyard area of the parts (about 1,350 mm²) exceeded the
  board (1,290 mm²). The modem (17.6 x 15.7 mm), push-push SIM holder, USB-C and LQFP-48 alone fill half of it.
- History:
  - 51 x 40 mm: routable only with many leftovers.
  - **63.5 x 40 mm:** the owner chose "roomier" over "slimmer, SIM beside the modem".
  - Four **M2 corner holes** (2.2 mm NPTH, 2.5 mm from each edge, 4.9 mm copper keep-outs).
  - **63.5 x 46 mm** to fit the battery section.
- **Single-sided assembly** was the owner's preference. Everything is SMD on top except J9 (through-hole by
  choice, for strength) and the DNP 2.54 mm headers J4/J5.

### 4.2 Two chips (STM32 + SIM7080G) instead of a cellular SoC
- The alternative was the **Nordic nRF9151**: LTE-M/NB-IoT + GNSS with an application core, about $17.07
  at JLC. The two-chip core parts cost about $18.06, so cost is a wash.
- Two-chip was chosen because the **STM32L072 ROM bootloader does USB DFU from a blank chip**, so field users
  never need a probe. A blank nRF9151 needs SWD once to load MCUboot. The owner valued the no-probe flow.
- Accepted costs: the AT-command handling and the modem's low-power modes are fiddlier. That's mitigated by
  the power-off strategy (§4.5), and the EnviroDIY/TinyGSM libraries support the SIM7080 family.
- The nRF9151 remains the better option if **over-the-air updates** become a requirement.

### 4.3 MCU: STM32L072CBT6 (was STM32L071)
- The L071 has no USB. The L072 is pin-identical in LQFP-48 except **pin 36: VDDIO2 -> VDD_USB** (on +3V3).
- USB is FS on PA11/PA12. That pushed the modem UART to **USART2** (PA2/PA3, CTS/RTS on PA0/PA1) and the
  debug UART to **USART1** (PA9/PA10, header J4).
- **BOOT0 button SW2:** hold it and tap RESET (SW1) to enter DFU. R10 pulls BOOT0 low.

### 4.4 One USB-C port for two devices
- **Chosen:** 3-pad solder jumpers JP3 (D+) / JP4 (D-), pre-bridged 1-2 = MCU; re-bridge 2-3 for the modem.
  The owner picked the simplest option.
- **Rejected:**
  - a hub;
  - an FSUSB42 analog switch (fine, about $0.32);
  - modem USB on test pads only;
  - wiring the USB-C A and B rows to different devices (out of spec).
- **Modem-USB mode extras:**
  - JP1 feeds 5 V to the modem's USB_VBUS. Keep it open normally: the modem can't sleep with VBUS present.
  - JP5 forces the modem rail on. SIMCom: no voltage on any pin while VBAT is off.
  - TP4 (GND) sits next to TP2 (PWRKEY) for a manual power-on. Never tie PWRKEY low: the modem resets after 12.6 s.
  - R28 (1k) sits between PB1 and the buck EN, so JP5 can't short a driven pin.

### 4.5 Modem power strategy (firmware contract)
- **Power the modem fully off between uploads.** Each upload:
  1. buck on (PB1);
  2. PWRKEY low for about 1.2 s (PB0 high);
  3. wait for STATUS (at least 1.8 s);
  4. attach, then TLS + MQTT publish;
  5. `AT+CPOWD=1`;
  6. wait for STATUS to go low;
  7. **then** buck off.
- **Cutting VBAT while the modem runs is the hung-modem recovery only.** SIMCom V1.04 §3.2.2 warns it can
  corrupt the module's file system.
- **PSM was evaluated and rejected** for this cadence. It saves the attach, but TLS still has to be redone,
  the network's RRC inactivity tail (~10-20 s) and the T3324 active time cost more, and the buck would stay
  on all the time. Estimated 3.4 J/msg vs 2.8 J/msg for power-off. Revisit only if the network supports
  Release Assistance (RAI) and TLS session resumption is used.

### 4.6 Level shifting: TXS0108E, all 8 lines
- The modem's I/O is 1.8 V (VDD_EXT), with a **2.1 V absolute max**, and 1.8 V is below a reliable 3.3 V STM32
  input high. The shifter's **OE is tied to VDD_EXT**, so it goes Hi-Z when the modem is off, which prevents
  back-powering an unpowered modem.
- All 8 lines are kept: TXD, RXD, RTS, CTS, DTR, DCD, RI, STATUS. The owner wanted DTR/DCD, and a 4-channel
  part would save only about 2 mm² and pennies.
- **SIMCom V1.04 §3.3:** pull resistors on the 3.3 V side of a shifter IC must be **at least 47 kΩ**. So
  R29/R30/R31 are 100k pull-ups (RXD, DCD, CTS) and R32 is a 100k pull-down (RI). **Don't** use the STM32's
  internal pulls (about 40 kΩ). R27 (100k) pulls STATUS low so a powered-off modem reads as "off".

### 4.7 Battery input (rev 0.3)
- **Connector:** JST PH 2.0 mm **through-hole** B2B-PH-K-S-GW (genuine JST, C5251182). The owner chose THT for
  strength. **Pin 1 = +**, with "+ J9 -" on the silkscreen. JST-PH battery polarity isn't standardized, hence Q3.
- **Q3 (AO3401A):** reverse-polarity protection in the + lead. Gate to GND via R33; the body diode points
  battery -> VBAT.
- **U9 DW01A + Q5 FS8205A (SOT-23-6)** in the negative lead: BATT_N -> FETs -> GND. Over-discharge at about
  2.4 V and overcurrent/short at about 3 A. No on-board charging (owner's choice: cells are charged externally).
  - Values: R35 100R + C43 100n on VCC; R36 1k on VM.
  - Pinouts came from LCSC's EasyEDA symbols. The SOT-23-6 FS8205A pinout differs from the TSSOP-8 version:
    S1=1, D=2/5, S2=3, G2=4, G1=6.
- **OR-ing into VSYS:**
  - USB through **D4 (B5819W)**;
  - the battery through **Q4 (AO3401A)**, whose gate is +5V (R34 pull-down), so it turns off whenever USB is
    present and USB never back-feeds the cells.
  - VSYS feeds the buck (SY8089, which makes 3.93 V and must run at 100% duty when the cell is below about
    3.9 V; **unconfirmed**, §9) and the LDO.
  - USB 5 V can't go straight to the modem: VBAT max is 4.8 V.
- **U8 MAX17048** fuel gauge (C2682616): VDD/CELL on VBAT, I2C 0x36 on the Qwiic bus, ALRT -> PA8 (R37 pull-up).
  Firmware should stop uploading at about 3.3 V; the DW01A is only the hardware backstop.
- **Always-on loads fixed in rev 0.3:**
  - D1 (red LED) now runs from USB +5V. It was 1k from +3V3: about 6.5 mW, more than all the uploads combined.
  - R24 (SIM card-detect pull-up) is now 1 MΩ. At 10k it drew 330 µA whenever **no** card was inserted (the holder's switch shorts CD to GND with no card; see §4.9).

### 4.8 Regulators
- **3.3 V: TPS7A0233PDBVR** (25 nA Iq, SOT-23-5, same pinout as the ME6211 it replaced, which drew about 40 µA).
- **Modem: SY8089 buck** (3.93 V; R7/R8 divider). Its EN is the modem power switch.

### 4.9 RF, SIM, USB pair
- **LTE:** pin 32 -> R19 0R (+ DNP C40/C41 pi-match) -> J6. **GNSS:** pin 68, escaping through the module's
  top-left corner -> R20 -> J7. Both are hand-routed at 0.35 mm, an estimate for 50 Ω (§9). In1 is solid GND
  under the RF half.
- **SIM:** the 22R series resistors R21-R23 sit vertically in the 2.6 mm gap between modem pins 15-17 and the
  SIM contacts. The SIM7080G supports **1.8 V SIM cards only**.
- **SIM holder (XunPu SMN-303) mechanics, checked against the manufacturer drawing (Rev A):**
  - The card inserts from the end opposite the contact row, which faces the board's bottom edge. The holder sits
    with its opening about 0.4 mm from the edge, so the card (which ejects about 4.2 mm) can be gripped.
  - The drawing marks six areas under the contact springs "NO PATTERN AND VIA HOLE IN THIS AREA". `preroute.py`
    adds them as F.Cu keep-outs (`sim_spring_keepout_1..6`: no tracks, vias or pour), so DRC, the autorouter,
    `stitch.py` and the maze router all respect them.
  - Card detect: the CD switch is closed to GND with no card and open with a card inserted.
- **USB to the modem:** a coupled pair on B.Cu, 0.30 mm / 0.15 mm gap (my estimate for ~90 Ω on JLC04161H-7628;
  **verify**). In2 has a track keep-out under it. The MCU side of the jumpers is plain autorouted (USB FS).

## 5. Power budget (summary)

The modem is off between uploads; the figures are at the 5 V/VSYS level, and the always-on fixes in §4.7 are assumed.

| | Best | Typical | Poor coverage |
|---|---|---|---|
| Awake per upload | 11 s | 16 s | 56 s |
| Energy per upload | 1.8 J | **2.8 J** | 15 J |
| Average power, 15-min uploads | 2.0 mW | **3.1 mW** | 16.7 mW |
| Li-ion for 60 days (mild / ~0 °C) | 1,100 / 1,400 mAh | **1,700 / 2,150 mAh** | 9,300 / 11,600 mAh |
| Hourly batches of 4 | 0.5 mW | 0.8 mW | 4.2 mW |

- **Sleep floor:** about 17 µW, plus about 6 µA for the DW01A and MAX17048 in rev 0.3, which is negligible.
- **From datasheets:** the SIM7080G currents (V1.04 Table 33: idle 18 mA, PSM 3 µA, Cat-M TX 91-121 mA,
  0.5 A peak), the TXS0108E Icc (<= 1.4 µA with VCCA = 0) and the TPS7A02 Iq (25 nA).
- **Estimates:** the per-phase durations and average currents (attach, TLS). **Measure them on the first
  prototype** (Nordic PPK2 or a Joulescope). Coverage at the site is the dominant variable.
- **Field notes:**
  - standard Li-ion must not be charged below 0 °C;
  - power banks often shut off at µA loads, so prefer a direct cell or a power bank with an "always-on" mode.

## 6. PCB

- **Stackup:** 4-layer, JLC04161H-7628 assumed.
  - **F.Cu:** components, signals, GND pour.
  - **In1:** solid GND, with a track keep-out for x >= 38.5 mm (the modem/RF/SIM/buck half).
  - **In2:** signals + GND pour, a +3V8 strip from the buck to the modem VBAT pins, and a track keep-out under the USB pair.
  - **B.Cu:** signals, the +5V highway, the USB pair, GND pour.
- **Rules (`lte_board.kicad_pro`, written by `mkpro.py`):**
  - 0.15 mm track and clearance;
  - 0.5/0.3 mm vias;
  - 0.25 mm copper-to-edge.
  - Net classes:

    | Class | Width | Nets |
    |---|---|---|
    | VBAT | 0.6 mm | +3V8 |
    | Power | 0.3 mm | +5V, +3V3, BUCK_SW |
    | Batt | 0.4 mm | BATT_IN, BATT_N, VBAT, VSYS |
    | RF | 0.35 mm | RF feeds |
    | USB | 0.30 mm / 0.15 mm gap | USB pair |
    | Long | default | the long-run nets (`mkpro.py` LONG list; used by an abandoned two-stage experiment) |

- **Hand-routed in `preroute.py`, all locked:**
  - the LTE and GNSS feeds;
  - the 0.6 mm VBAT bus to C30-C34;
  - the +3V8 vias;
  - the USB select chain and the coupled pair;
  - the +5V highway: J1 -> B.Cu down x = 8.9 mm, along y = 30.6 mm -> D4;
  - the modem pin 39-42 escape vias;
  - the U1 GND via;
  - the zones and keep-outs.
- **Placement regions** (`gen_board.py` PLACE table, mm from the board's top-left corner):
  - **USB-C + ESD + USB jumpers:** top-left.
  - **MCU:** left-centre.
  - **TXS0108 + modem-control transistors:** centre (the "MID" group, offset +5 mm).
  - **Modem + RF + SIM + buck:** right (the "BIG" group, offset +11 mm).
  - **Battery block:** bottom-left.
  - **OR-ing (D4/Q4/R34):** between SW2 and the SIM holder. **LDO (U3/C4/C5):** bottom-right corner, by the buck.
  - **SIM holder J8:** card opening about 0.4 mm from the bottom edge. Nothing may be placed in front of it (§7.4, lesson 12).
  - **LEDs:** bottom-middle.
  - **J4/J5/SW2:** bottom edge.

## 7. Layout toolchain

### 7.1 Environment (tested on macOS, KiCad 9.0.8)
- **KiCad 9:**
  - `kicad-cli` is at `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`.
  - The **pcbnew Python API** is only in KiCad's bundled interpreter:
    `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`.
  - System `python3` is fine for `mkpro.py`, `make_jlc.py` and the schematic scripts (plain text/JSON).
- **Freerouting 2.5.0** (`freerouting-2.5.0.jar`, GitHub releases) needs **Java 25**: class file version 69;
  Java 21 fails. A portable Temurin JRE works: `https://api.adoptium.net/v3/binary/latest/25/ga/mac/aarch64/jre/hotspot/normal/eclipse`.
  Keep both somewhere persistent such as `~/tools`. macOS clears `/tmp`, and a vanished jar once made Freerouting
  silently produce no session (`pipeline.sh` now checks for that and stops).
- **`easyeda2kicad`** (`pip install easyeda2kicad`) imports LCSC footprints, symbols and 3D models by C-number.
  It's also the most reliable **pinout source** when datasheets can't be downloaded.
- **Part search/stock:** JLC's parts API answers a POST to
  `https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList` with
  `{"keyword": "...", "currentPage": 1, "pageSize": 10}`. Fields used: `componentCode`, `stockCount`,
  `componentPrices`, `componentLibraryType` (base/expand), `dataManualUrl`.
- **Datasheets:** TI PDFs download from scripts; **ST, LCSC and SIMCom block scripted downloads**, so ask a
  human to download them. The SIMCom *SIM7080G Hardware Design* V1.04 is not in the repo (copyright).

### 7.2 Scripts (`layout_scripts/`)

| Script | Runs with | Does |
|---|---|---|
| `pipeline.sh` | bash | Everything below, in order: best-of-N autorouting, maze finish, clean-ups, DRC, BOM/CPL. **Overwrites the board.** |
| `gen_board.py netlist proj out.kicad_pcb` | KiCad python | New board from the netlist: footprints, nets, symbol links (UUID paths), **PLACE table**, outline, M2 holes |
| `preroute.py board dsn` | KiCad python | Hand routes, vias, zones (In1 GND, +3V8), rule areas |
| `hole_keepouts.py board` | KiCad python | 4.9 mm copper/track/via keep-outs at the holes |
| `export_dsn.py board dsn` | KiCad python | Sets In1 to signal type + track keep-out over the RF half; exports Specctra DSN |
| `postroute.py board ses` | KiCad python | Imports the Freerouting session; adds GND pours on F/In2/B; fills |
| `stitch.py board` | KiCad python | GND stitching vias on a 1.3 mm grid wherever they clear everything (not under screw heads) |
| `fixup.py board` | KiCad python | U1 GND via, widens <0.1 mm necks, island removal, refill |
| `drop_dangling.py board drc.rpt` | KiCad python | Deletes dangling vias/stubs listed in a DRC report, unless that adds an unconnected item |
| `maze_route.py board NET...` | KiCad python | 0.1 mm grid A*/Dijkstra router over 4 layers; joins a net's copper islands one by one. Removes free stitching vias first |
| `final_fixes.py board drc.rpt` | KiCad python | Replaces "dangling" vias that only bridge two same-layer track ends; adds a via to every orphan F.Cu GND island (all-layer clearance check) |
| `silk_marks.py board` | KiCad python | "+ J9 -" / "BAT 3.0-4.2V" silkscreen |
| `mkpro.py lte_board.kicad_pro` | python3 | Writes design rules and net classes into the project file |
| `make_jlc.py netlist pos.csv outdir` | python3 | `bom_jlcpcb.csv` + `cpl_jlcpcb.csv`; fails on a missing LCSC #; reports BOM/CPL mismatches |
| `sch_rev02.py`, `sch_rev03.py` | python3 | The schematic edits for each revision (already applied; reference for how to edit the schematic by script) |

Typical run:

```bash
cd hardware/lte_board
FR_JAR=~/tools/freerouting-2.5.0.jar JAVA=~/tools/jre25/bin/java ATTEMPTS=3 ./layout_scripts/pipeline.sh
```

Run it on a copy first (`PROJ=/tmp/copy/lte_board ...`). Results vary between runs (§7.4). **Expect to finish a few
items by hand.** A test run on 2026-10-13 (ATTEMPTS=1) went: autorouter 18 unconnected -> maze router fixed all
16 nets it was given -> final DRC: 1 clearance (0.125 mm) + 2 unconnected (GND pour islands with no room for a via).
The committed board is a hand-finished, fully clean run, so don't overwrite it unless you mean to.

### 7.3 Editing the design
- **Moving parts:** edit the `PLACE` table in `gen_board.py`. Refs in the `BIG` set get +11 mm in x; refs in
  `MID` get +5 mm (historical offsets from widening the board). Check courtyards with a DRC before routing.
  Board size is `W, H` in `gen_board.py`, **and also** in `preroute.py`, `postroute.py`, `stitch.py`,
  `hole_keepouts.py`, `maze_route.py`, `final_fixes.py` and `export_dsn.py`. Keep them in sync.
- **Schematic changes:** the schematic was generated by a script. Every pin has a 2.54 mm wire stub ending in
  a **net label** or a **power symbol**. Re-assigning a pin is just changing the label text at the stub end.
  New parts need:
  - a lib symbol in **both** the schematic's embedded `lib_symbols` and `lte_board.kicad_sym`;
  - an instance block with `(instances (project "lte_board" (path "/7ded1cb8-0547-516d-a7f6-d4c083a7d11d" ...)))`;
  - stub wires plus labels or power symbols.

  `sch_rev03.py` has reusable helpers (`part()`, `box()`, `repower()`). Local labels make nets named `/NAME`.
  Power symbols make global nets (`GND`, `+3V3`, `+5V`, `+3V8`), and the two don't merge. Put
  `exclude_from_bom` (`in_bom no`) on copper-only/DNP parts.
- **Hand-tuning in the KiCad GUI is fine,** but once you do, **stop using `pipeline.sh`**. It regenerates the
  board from scratch. Move tweaks back into the scripts if you want them reproducible.

### 7.4 Lessons learned (read before touching the scripts)
1. **`pcbnew.SaveBoard()` rewrites `lte_board.kicad_pro`** with default rules and drops the net classes. Run
   `mkpro.py` after *every* Python step that saves.
2. **KiCad 9 SWIG:** after `board.Remove(item)`, a later `board.GetTracks()` can raise
   `TypeError: 'SwigPyObject' object is not iterable`. Collect lists *before* removing anything.
3. `zone.GetLayerName()` is misleading for zones; use `zone.GetFirstLayer()` / `GetLayerSet()`.
4. **`kicad-cli` 9 has no zone-refill option.** Refill in Python: `board.BuildConnectivity()`, then
   `ZONE_FILLER(board).Fill(board.Zones())`, and save. Island removal "always" needs connectivity built first.
5. **Freerouting quirks:**
   - With In1 as a `power` layer it starves routing (about 20 unconnected). As a plain signal layer it cuts
     up the GND plane. The fix is a signal layer plus a **track keep-out rule area** over the RF half.
   - `--router.ignore_net_classes` / `router.autorouter.ignore_net_classes` had **no effect** in 2.5.0.
   - **Don't empty net pin lists in the DSN** to limit what it routes: it then sees routed copper overlapping
     "netless" pads and reports hundreds of violations.
   - It doesn't credit connectivity made through zones, so its own "unrouted" count is pessimistic. Trust KiCad's DRC.
   - Results vary run to run (4-12 unrouted for the same input), hence best-of-N.
   - Locked KiCad tracks are exported as fixed wiring.
6. **Route-long-nets-first (two-stage) made things worse** (42 unrouted): the locked long runs boxed in the
   short local nets. What worked instead:
   - fix placement so pins can escape;
   - hand-route only the truly long/critical nets (USB pair, +5V highway);
   - autoroute;
   - finish with the maze router.
7. **Placement bugs that caused most of the failed routes:**
   - decoupling caps in a row right under the LQFP's bottom pins;
   - the buck's FB/EN resistors on the wrong side of the SOT-23-5;
   - the SIM series resistors rotated 180° (pad 1 away from the modem);
   - R3/R4 orientation crossing the USB pair.

   Check pin-to-pad direction before routing.
8. **Stitching vias added after routing block the channels for later fixes.** `maze_route.py` removes the free
   ones first; re-run `stitch.py` afterwards.
9. **Via placement must be checked on all four layers plus drill-to-drill and board edge.** A top-layer-only
   check shorted GND to NRST on In1 once. `final_fixes.py:via_ok()` is the correct check.
10. **easyeda2kicad imports need checking:**
    - footprint names (renamed `LCC-SMD_SIM7080G` -> `SIM7080G`);
    - pad numbers vs the symbol (the SMN-303 SIM holder had `C1..C7/CD/8-11`; renumbered so card-detect is 8,
      not a GND shell tab);
    - NPTH pegs imported as PTH;
    - 3D paths (made `${KIPRJMOD}`-relative).
    - The TS-1187A switch has only one *diagonal* pad pair numbered, which is correct whichever way the
      internal pairs are wired.
11. **JLCPCB "designators don't exist in the CPL file":** non-parts (jumpers, test pads, DNP) were in the BOM.
    Keep them `in_bom no`. The Fabrication Toolkit plugin needs `"EXCLUDE DNP": true` (set in
    `fabrication-toolkit-options.json`). `make_jlc.py` is the source of truth.
12. **DRC can't see mechanical access.** In rev 0.3 the OR-ing parts and LDO were placed in the "free" strip in
    front of the SIM holder's card slot, blocking insertion, and copper and vias ran under the holder's contact
    springs. Both were fixed on branch `hardware/sim-holder-fix`. Before moving parts, check every connector's,
    card's and button's access path, and any "no copper" areas, against the part's mechanical drawing.

### 7.5 Verification checklist (every change)

```bash
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$K sch erc -o /tmp/erc.rpt lte_board.kicad_sch                          # expect 0 errors, 0 warnings
$K pcb drc --schematic-parity -o /tmp/drc.rpt lte_board.kicad_pcb        # expect 0 / 0 / 0
$K sch export netlist --format kicadsexpr -o /tmp/net.net lte_board.kicad_sch
$K pcb export pos --format csv --units mm --side front --exclude-dnp -o /tmp/pos.csv lte_board.kicad_pcb
python3 layout_scripts/make_jlc.py /tmp/net.net /tmp/pos.csv .           # expect "none" / "none" mismatches
$K pcb render --side top --quality high -o pcb_render_top.png lte_board.kicad_pcb   # eyeball it
```

## 8. Firmware requirements (not started)

- **Bootloader:** BOOT0 (SW2) + RESET -> ST ROM DFU over USB-C (jumpers JP3/JP4 at their default 1-2).
- **Modem:**
  - on/off per §4.5;
  - AT over USART2 at 115200 (auto-baud), RTS/CTS available;
  - MQTT/TLS to AWS IoT through the modem's built-in SSL/MQTT AT commands (see the SIM7080 AT command manual).
- **Pins while the modem is off:**
  - shifter lines idle safely via R29-R32: inputs, no internal pulls;
  - DTR/DCD/RI are available but not needed for the power-off strategy.
- **Sleep:** STM32 Stop mode + RTC (about 1 µA), with the independent watchdog armed.
- **Battery:**
  - MAX17048 on I2C 0x36 (check for sensor address clashes);
  - ALRT on PA8 (EXTI) for low-SOC/voltage alerts;
  - stop uploading around 3.3 V/cell.
- **Data:** store readings when coverage fails. The L072CB has 6 KB of EEPROM, 128 KB of flash and 20 KB of RAM; no external
  flash (declined by the owner).
- **SIM:** card detect on PB5, pulled up by R24 = 1M. The holder's switch shorts CD to GND with **no** card and opens with a card, so **PB5 high = card present** (SMN-303 drawing). SIM must be 1.8 V-capable.

## 9. Open items

This is the master checklist; §8 remains the firmware specification and the board README
remains the operating/ordering guide.

Keep the IDs below stable when items are resolved. Record evidence and date beside each item: exact
part/document revision and page/table for a documentation check, or board revision, conditions and results
for a hardware test. Use **Open**, **Reported; evidence pending**, **Verified from documentation**,
**Implemented; test pending**, **Verified on hardware**, or **Deferred (reason)**. A datasheet finding does
not close the corresponding prototype test. Nothing is marked independently verified by this consolidation.

### 9.1 Hardware review before ordering prototypes

| ID | Status | Task / evidence needed | Source |
|---|---|---|---|
| H01 | Reported; evidence pending | **SY8089AAAC (C78988) 100% duty cycle:** owner reports support. Record the exact datasheet revision/page and low-input-voltage behavior, then update the uncertainty in §4.7 and the README block overview. If the exact part does not meet the requirement, review an alternative before changing the design. Low-battery operation still needs T01. | Original §9 item 1; §4.7; README block overview |
| H02 | Open | **DW01A (C351410) / FS8205A (C908265):** check exact-part values, protection thresholds, SOT-23-6 pinout and actual symbol-to-pad connections against datasheets. Do not substitute the TSSOP-8 pinout. | Original §9 item 2; §4.7 |
| H03 | Open | **MAX17048 (C2682616):** verify VDD bypass value and exposed-pad land pattern/pin connections against the exact package documentation. | Original §9 item 2 |
| H04 | Open | **U7 ESDA6V1W5:** confirm pin 2 ground and pins 1/3/4/5 I/O against ST's datasheet; the earlier check used a pin-compatible second source. Compare with the actual footprint. | README: Check these before ordering, item 1 |
| H05 | Verified from documentation (2026-10-30); hardware test pending (T02) | **J8 SMN-303:** Evidence: XunPu SMN-303 drawing (Rev A, linked in DATASHEETS.md). Contact order C3/C7/C2/C6/C1/C5/CD, 2 × 6.50 mm and 12.00 mm tab spacing and the two Ø0.75 mm pegs match the footprint; CD is normally shorted to GND and opens with a card (PB5 high = card present); card inserts from the bottom edge; the drawing's six no-copper areas are now keep-outs. Minor: the drawing's contact row sits about 0.14 mm further from the tabs than the LCSC footprint's pads, which is well inside the pads' length. Original task: verify the already-renumbered footprint against the holder drawing: 1/2/3/5/6/7 = SIM C1/C2/C3/C5/C6/C7, 8 = card detect, 9-11 = shell ground; confirm locating pegs and inserted-card detect polarity. Hardware verification is T02. | README: ordering checks and footprint fixes |
| H06 | Open | **Stackup and impedance:** confirm the actual fabrication stackup and calculate RF 50 Ω and USB 90 Ω differential geometry, including reference planes and adjacent ground. Current 0.35 mm RF and 0.30/0.15 mm USB width/gap are estimates. Update geometry/rules if required. | Original §9 item 3; §4.9; README impedance and original layout guidance |
| H07 | Open | **Layout review:** inspect autorouted traces, especially MCU/U5; inspect buck placement/current loops, modem decoupling, supply paths, RF returns and USB reference continuity. Resolve the README's original 1.5-2 mm modem-supply recommendation versus the implemented 0.6 mm bus with a documented assessment. Existing connectivity checks do not close this review. | README: Before ordering; PCB layout; original layout guidance |
| H08 | Open | **Sensors:** select temperature/humidity/UV devices; confirm 3.3 V compatibility, I2C addresses (including gauge 0x36), combined pull-ups and active/standby current. Qwiic is always powered; define sensor sleep configuration. | Original §9 item 7; §8 address-clash check; standby-current review added in discussion |
| H09 | Open | **Low-battery supply margin:** assess the proposed ~3.3 V upload cutoff against TPS7A0233 dropout, selected sensors' supply limits, wiring/FET losses and modem burst sag. Record assumptions for T01/F05; this is a review task, not a confirmed defect. | §4.7/§8 cutoff requirement; review added in discussion |

### 9.2 Manufacturing and deployment preparation

| ID | Status | Task / evidence needed | Source |
|---|---|---|---|
| M01 | Open; repeat at order time | **Parts availability/cost:** refresh JLC stock and Basic/Extended classifications/setup fees. README stock counts are a historical 2026-10-07 snapshot. | README: Check these before ordering, items 3-4 |
| M02 | Open; repeat at order time | **Assembly preview/options:** verify rotations/polarity, especially SOT-23/-6, TDFN U8, LEDs and D4; confirm SIM7080G MSL3/X-ray assembly requirements with the assembler. | Original §9 item 4; README ordering checks |
| M03 | Open | **Battery connector/pack:** confirm J9 pin 1 positive against the chosen pack lead and silkscreen; choose JLC THT assembly or hand-soldering for J9. Retain external charging and the single-cell/parallel-cell architecture. | §4.7; README battery/ordering notes |
| M04 | Open; repeat after hardware changes and before ordering | **Release checks/files:** run §7.5 ERC, DRC with schematic parity, BOM/CPL regeneration and designator cross-check; review the render and fabrication output. Preserve DNP/copper-only exclusions and order the verified impedance-controlled stackup. Record results for the actual revision being ordered; earlier clean reports are historical. | §7.5; CLAUDE.md verification rules; README ordering instructions |
| M05 | Open | **Antennas:** select LTE and any needed GNSS antenna, connector/cable and placement; plan LTE pi-match measurement/tuning (R19 = 0R, C40/C41 DNP initially). Validate with the intended enclosure in T05. | Original §9 item 6; README RF/layout guidance |
| M06 | Open | **Enclosure/mounting:** choose enclosure and sensor mounting; check connector/card access, antenna placement and four M2 holes (2.2 mm) with screw-head clearance. Tidy overlapping silkscreen references. | Original §9 item 7; §4.1/§6; README layout guidance |

### 9.3 Firmware implementation (none yet; see §8 for pin-level requirements)

| ID | Status | Task / evidence needed | Source |
|---|---|---|---|
| F01 | Open | **Programming/bring-up:** establish a firmware build/flash path using ROM USB DFU (BOOT0 + RESET, JP3/JP4 default); retain SWD/debug access for diagnosis. | §1/§8; README programming instructions |
| F02 | Open | **Modem driver:** USART2 AT interface at the specified baud, optional RTS/CTS, PB1 rail control, Q1/PWRKEY timing and STATUS waits; graceful power-down before rail removal, with bounded timeouts and hard-cut recovery only for a hung modem. | §4.5/§8; README modem power sequence |
| F03 | Open | **Cellular/cloud:** choose a 1.8 V-capable SIM/operator, configure LTE-M and intended NB-IoT fallback, and implement modem MQTT/TLS uploads to AWS IoT. Define endpoint/certificate provisioning, payload and delivery-success handling. | §1/§8; README SIM notes; provisioning/delivery details added in discussion |
| F04 | Open | **Sampling/storage:** implement sensor acquisition, timestamps, 15-minute uploads or hourly batches, and retained readings during coverage failures. Define buffer capacity, persistence/write endurance and overflow policy within 6 KB EEPROM/128 KB flash/20 KB RAM; no external flash. | §1/§8; README batch strategy; buffer details added in discussion |
| F05 | Open | **Battery handling:** read MAX17048 at 0x36, configure/handle ALRT on PA8 and stop uploads at the validated low-battery threshold (H09/T01); define recovery behavior. | §4.7/§8 |
| F06 | Open | **Sleep/recovery:** implement Stop mode + RTC wake, independent watchdog, safe modem-off GPIO states without internal pulls, and sensor sleep settings. Fully power off the modem between uploads as chosen in §4.5. | §4.5/§4.6/§8; README field strategy |
| F07 | Open | **SIM detect:** implement PB5 card detection using the verified H05 polarity and test missing/inserted-card behavior. | §8; README pin map/ordering checks |

### 9.4 Prototype validation before a production batch

These tasks expand the original current-measurement item into the staged validation discussed during review;
they require physical hardware and do not imply that a prototype has already been ordered.

| ID | Status | Task / evidence needed | Source |
|---|---|---|---|
| T01 | Open; requires prototype | **Power bring-up:** inspect assembly/shorts, start with a current-limited supply and modem disabled, then verify both supplies and modem sequencing. Sweep the intended battery range, capture startup/transmit voltage sag and test USB/battery switchover and off-state leakage; validate H09/F05 cutoff. Verify protection behavior in a controlled test setup. | Original §9 item 5; power assumptions in §4; staged tests added in discussion |
| T02 | Open; requires prototype | **Interfaces/programming:** demonstrate DFU, sensor/gauge I2C and alert operation, SIM detection, translated UART/status behavior and modem-off isolation. If modem USB is used, validate the README jumper/power sequence. | §8; README interface/USB instructions; staged tests added in discussion |
| T03 | Open; requires prototype | **Energy/battery life:** measure complete-board sleep current with selected sensors, plus startup/attach/TLS/publish/shutdown energy in representative coverage. Update §5 and battery sizing for the 60-day target, including temperature and batching assumptions. | §5; original §9 item 5 |
| T04 | Open; requires prototype and firmware | **End-to-end/recovery:** demonstrate sensor-to-AWS delivery and repeated sleep/upload cycles; exercise absent SIM, unavailable network, failed uploads, watchdog/reset and low battery. Confirm retained data and bounded retries/recovery. | §4.5/§8; failure tests added in discussion |
| T05 | Open; requires prototype | **RF/field pilot:** measure/tune the LTE match as needed and evaluate connectivity, energy and sensor operation with the selected antenna, enclosure and deployment conditions before a larger batch. | Original §9 items 5-7; field validation added in discussion |

### 9.5 Documentation follow-up and optional work

| ID | Status | Task / evidence needed | Source |
|---|---|---|---|
| D01 | Open | **Keep descriptions consistent:** as findings are checked, update the relevant §4/§5/§8 text and README instructions, record evidence here and point CLAUDE.md to this master list. Reconcile KiCad version wording, historic versus current check results, and original layout advice versus actual geometry. Add navigation links to the root README when updating the summaries. | All Markdown files; consolidation follow-up |
| O01 | Optional; undecided | **VBUS fuse:** decide whether to add the README's suggested polyfuse; document the choice without treating it as an already-approved circuit change. Check USB source/cable current margin in the power review/test. | README: Check these before ordering, item 7 |
| O02 | Optional; deferred unless space is needed | **DNP headers:** reduce/remove J4/J5 only if needed; J5 is 25 mm long. | Original §9 item 8 |
| O03 | Optional; deferred unless requirements change | **Alternative modem sleep/features:** DTR/DCD/RI remain available for UART sleep/carrier/wake features. Revisit PSM only with the §4.5 RAI/TLS-resumption conditions and measured benefit. OTA updates would require revisiting §4.2; neither is part of the current firmware baseline. | §4.2/§4.5/§8; README modem strategy |

## 10. References

See [DATASHEETS.md](DATASHEETS.md) for the 2026-10-24 exact-part access check, working document links,
revision/access limits and initial findings for H01-H09. Access alone does not close the hardware review.

- SIMCom, *SIM7080G Hardware Design* V1.04 (2020-09-27). Used: §3.2 power on/off, Table 8 timing,
  §3.3 UART/level shifting (>= 47k pulls), §3.4 USB (VBUS 3.5-5.25 V, 90 Ω), Table 28 abs max
  (digital I/O 2.1 V), Table 33 currents. Get it from https://www.simcom.com/product/SIM7080G.html
- TI TXS0108E: https://www.ti.com/lit/ds/symlink/txs0108e.pdf. TI TPS7A02: https://www.ti.com/lit/ds/symlink/tps7a02.pdf
- ST STM32_open_pin_data (L071 vs L072 LQFP-48 pinouts): https://github.com/STMicroelectronics/STM32_open_pin_data
- AOS AO3401A: https://www.aosmd.com/res/datasheets/AO3401A.pdf
- LCSC datasheets (script downloads blocked; open them in a browser):
  [SY8089](https://www.lcsc.com/datasheet/lcsc_datasheet_2108261630_Silergy-Corp-SY8089AAAC_C78988.pdf),
  [DW01A](https://www.lcsc.com/datasheet/lcsc_datasheet_1912111437_PUOLOP-DW01A_C351410.pdf),
  [FS8205A](https://www.lcsc.com/datasheet/lcsc_datasheet_2010271837_FUXINSEMI-FS8205A_C908265.pdf),
  [MAX17048](https://www.lcsc.com/datasheet/lcsc_datasheet_2410121738_Analog-Devices-Inc--Maxim-Integrated-MAX17048G-T10_C2682616.pdf)
- Nordic Online Power Profiler for LTE (an LTE-M energy cross-check): https://devzone.nordicsemi.com/power/w/opp/3/online-power-profiler-for-lte
