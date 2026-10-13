# rice-fern-microclimate-monitor: notes for AI agents

A battery-powered LTE-M logger for monitoring the microclimate around resurrection ferns. Sensors are on Qwiic I2C;
readings go over cellular to AWS. Field biologists deploy it, so robustness and easy firmware updates matter.

## Where things are
- `hardware/lte_board/`: the KiCad 9 project (STM32L072 + SIMCom SIM7080G, rev 0.3).
  - **Read `hardware/lte_board/DESIGN.md` before changing anything.** It covers the requirements, every major
    decision and its rationale, the power budget, the layout toolchain, lessons learned and open items.
  - `README.md`: user-facing summary, MCU pin map, modem power sequence, JLCPCB ordering notes.
  - `layout_scripts/`: placement/routing/fab-file generators (`pipeline.sh` runs them all).
  - `bom_jlcpcb.csv`, `cpl_jlcpcb.csv`: the files to order from. They are generated, never hand-edited.
- No firmware yet. DESIGN.md §8 lists what it must do.

## Rules
- **Don't reverse a decision in DESIGN.md §4 without asking the project owner.** Several were their explicit
  choices: single-sided assembly, the two-chip design over the nRF9151, USB-select solder jumpers, keeping DTR/DCD,
  no on-board charging, the THT battery connector, board size.
- **Verify after every change** (DESIGN.md §7.5): ERC 0, DRC with `--schematic-parity` 0/0/0, and regenerate
  BOM/CPL with `layout_scripts/make_jlc.py` until it reports no mismatches. Report real results; never claim clean
  without running them.
- `pipeline.sh` **regenerates the board from scratch** and discards GUI edits. Use it only while the layout is still
  script-owned, and run it on a copy first.
- After any `pcbnew.SaveBoard()`, re-run `layout_scripts/mkpro.py lte_board.kicad_pro`. SaveBoard resets the
  design rules and net classes.
- Use KiCad's bundled Python for anything that imports `pcbnew`
  (`/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3` on macOS).
- Take pinouts from datasheets or LCSC's EasyEDA symbols (`easyeda2kicad --symbol --lcsc_id=C...`), never from memory.
  ST, LCSC and SIMCom PDFs can't be fetched by script, so ask the human to download them.
- Never commit vendor datasheets (copyright), `production/` (stale Fabrication Toolkit output) or `*.kicad_prl`.
