# Datasheet access and review sources

Access checked on **2026-10-24**. Scope: named devices in DESIGN.md H01-H09, plus supporting ICs,
power-path parts and the buck inductor. This is a source index, not a completed review of every BOM line.
Vendor PDFs are linked rather than committed. Manufacturer-authored documents hosted by distributors are
identified below; a similar part number from another manufacturer is not interchangeable evidence.

**Text readable** means the PDF body was opened and text extracted, not that every diagram, limit,
footprint or connection has been checked. **Drawing PDF located** means the file is accessible but has no
extractable text; it still needs visual inspection. Review tasks remain in DESIGN.md §9.

## Hardware-review sources

| Device / reference | Review items | Document and access result |
|---|---|---|
| Silergy SY8089AAAC, U2, C78988 | H01, H07, H09 | [SY8089/SY8089A application note, Rev. 0.9A](https://datasheet.lcsc.com/datasheet/pdf/400ca014d7a690f5be0127468f87fcc6.pdf?productCode=C78988), manufacturer document hosted by LCSC; **text readable**, 10 pages. [Mouser copy](https://www.mouser.com/datasheet/2/306/SY8089AAAC-3223250.pdf) also readable. Ordering table names SY8089AAAC. Do not use the different SY8089E1 as exact-part evidence. |
| PUOLOP DW01A, U9, C351410 | H02 | [DW01A, Rev. B, 2016-04-12](https://datasheet.lcsc.com/datasheet/pdf/0d2b2b5e8d1207bf276387cb4ff3a495.pdf?productCode=C351410), manufacturer document hosted by LCSC; **text readable**, 7 pages. Pin table p.2, application p.3, characteristics p.4. |
| FUXINSEMI FS8205A, Q5, C908265 | H02 | [FS8205A, Ver. 2.1](https://datasheet.lcsc.com/datasheet/pdf/5d5d336ed528176185784e3faf8fb551.pdf?productCode=C908265), manufacturer document hosted by LCSC; **text readable**, 4 pages. SOT-23-6L drawing/circuit on p.1 still needs visual comparison to the actual pad mapping. |
| Analog Devices/Maxim MAX17048G+T10, U8, C2682616 | H03, H08, H09 | [MAX17048/MAX17049, 19-6171 Rev. 7, 11/16](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX17048-MAX17049.pdf), manufacturer host; **text readable**, 19 pages. Pin/EP/bypass requirements p.6; ordering/package references p.18. Separate outline 21-0168 and land pattern 90-0065 for T822+3 still need retrieval/comparison. |
| ST ESDA6V1W5, U7, C48677 | H04 | [ESDAxxxWx family, Rev. 2, August 2005](https://www.st.com/resource/en/datasheet/esdaxxxwx.pdf), manufacturer host; **text readable**, 11 pages. Includes ESDA6V1W5 functional diagram on p.1. The guessed standalone esda6v1w5.pdf URL failed; use the family document. |
| XUNPU SMN-303, J8, C266888 | H05 | [SMN-303 drawing](https://datasheet.lcsc.com/datasheet/pdf/815f537256878844333070d705ba34f2.pdf?productCode=C266888), linked from LCSC's exact-part page; **drawing PDF located**, 2 pages, no extractable text. Contact numbering, detect switch, peg dimensions and view orientation remain to inspect visually. |
| TI TPS7A0233PDBVR, U3, C2887324 | H07, H09 | [TPS7A02, SBVS277C Rev. C, September 2022](https://www.ti.com/lit/ds/symlink/tps7a02.pdf), manufacturer host; **text readable**, 48 pages. Use DBV/SOT-23-5 and the 3.3 V option when checking pinout, dropout, capacitance and load limits. |
| ST STM32L072CBT6, U4, C465977 | H07, H09 | [STM32L072x8/xB/xZ, DS10689 Rev. 5, November 2019](https://www.st.com/resource/en/datasheet/stm32l072cb.pdf), manufacturer host; **text readable**, 160 pages. Select xB memory and LQFP-48 pin/package information. Firmware also needs the reference manual/bootloader documentation; this datasheet alone is not that review. |
| ST AN2606 (system-memory boot mode), U4 | F01, T02; DFU entry, bootloader interfaces | AN2606 Rev 70, **text readable** (owner-supplied copy; not committed). STM32L07x/08x is §66; the L072 uses bootloader V4.x (Table 148/149). |
| Seiko SC-32S 32.768 kHz 7 pF, Y1, C97604 | LSE crystal (rev 0.4) | Not yet opened. Confirm ESR/C0 against STM32L072 LSE gm_crit (DS10689 LSE table, AN2867) before ordering. |
| SIMCom SIM7080G Hardware Design **V1.05** (230731), U6 | rev 0.5 antenna circuits | Owner-supplied copy (not committed), **text readable**, 82 pages. §4.2 Fig. 28 LTE: 0R + 2 DNP + 100 pF series + TVS (BLE5V0CR05UB, not on LCSC). §4.3.2 Fig. 29 active GNSS: 0R + 2 NC, 100 pF DC block (mandatory, note 5), 47 nH + 10R feed, 0.1 µF, TVS WE05DGCF-B; switch the antenna supply off when GNSS is idle; LTE and GNSS RX can't run concurrently; GNSS on with AT+CGNSS. Note 6: the module may show a DC short (internal shunt inductor) at its antenna pin. V1.03 said 33 pF and AT+CGNSPWR. |
| Amphenol Connex 132322, J7/J10, C42394535 | SMA edge-launch footprint | [Drawing 132322 rev D](https://datasheet.lcsc.com/datasheet/pdf/e7f0379d2c6c8d097702e43f466272c5.pdf), via LCSC; drawing only (rendered and read). 50 Ω, DC-18 GHz, 1.57 mm board, recommended PCB layout: top 3 × 1.50 mm pads at 2.77 pitch (centre 4.25, grounds 3.95 long, grounds 0.30 further in), bottom 2 × 1.50 × 3.95 at 5.54. Edge-to-pad distance not dimensioned. |
| TI TPS22945DCKR, U10, C47507 | GNSS antenna switch | [TPS2294x](https://datasheet.lcsc.com/datasheet/pdf/611c8e98ab68f0bae79aaa69d0c6d70a.pdf), via LCSC; text readable. ILIM 100/150/200 mA min/typ/max at 3.3 V, IIN(OFF) 1 µA max, ON active high (VIH 1.4 V), OC open drain; 10 ms blanking, 80 ms auto-restart. Pinout 1 VOUT, 2 GND, 3 OC, 4 ON, 5 VIN (matches the LCSC EasyEDA symbol). |
| Murata LQW15AN47NJ00D, L2, C192855 | GNSS bias choke | [Murata LQW15AN catalog](https://datasheet.lcsc.com/datasheet/pdf/21cc2e6abe84f1c64c93eab152a87fc9.pdf), via LCSC. 47 nH ±5%, SRF ≥ 2.9 GHz, 210 mA, 1.08 Ω max. (LQG15HS47N: SRF 1 GHz, rejected.) |
| Wayon WE05DGCF-B, D5, C3039401 | GNSS TVS | [Datasheet](https://datasheet.lcsc.com/datasheet/pdf/ab1aa3a50531ff5487f3952a628c4ccf.pdf), via LCSC. VRWM 5 V, Cj 0.18 typ / 0.3 max pF, IEC ±12 kV contact. |
| Infineon ESD103-B1-02EL, D6, C535146 | LTE TVS | [Datasheet](https://datasheet.lcsc.com/datasheet/pdf/9f837311bec7e3ead15a9d62fb0575b0.pdf), via LCSC. VRWM ±15 V, 0.09 pF typ at 1 GHz, IEC ±10 kV contact. LCSC stock was low (about 200) on 2026-10-31; WE05DGCF-B fits the same area as a fallback (different land). |
| TI TXS0108EPWR, U5, C17206 | H07 | [TXS0108E, Rev. L](https://www.ti.com/lit/ds/symlink/txs0108e.pdf), manufacturer host; **text readable**, 42 pages. Use PW/TSSOP-20; check supply sides, OE, partial-power-down behavior and external loading/pulls against the circuit. |
| ST USBLC6-2SC6, U1, C7519 | H07 | [USBLC6-2 family](https://www.st.com/resource/en/datasheet/usblc6-2.pdf), manufacturer host; **text readable**, 20 pages. Use SC6/SOT23-6L pinout, not the SOT-666 option. |
| SIMCom SIM7080G, U6, C2943992 | H07, H09; modem power/interface/RF requirements | [Manufacturer product/download page](https://www.simcom.com/product/SIM7080G.html) readable and lists Hardware Design V1.05_230731. The [V1.04 copy cited by this project](https://www.texim-europe.com/Cmsfile/SMM-SIM7080G-Hardware-Design-V1.04-DS-200525-TE.pdf) was located but returned HTTP 502 twice. [SIMCom V1.03 hosted by Waveshare](https://files.waveshare.com/upload/e/e7/SIM7080G_Hardware_Design_V1.03.pdf) is **text readable**, 76 PDF pages. This older revision is background only; do not silently substitute its timing/table numbers for V1.04. Obtain V1.04 or review the changes to V1.05 before closing the modem requirements. |
| AOS AO3401A, Q3/Q4, C15127 | H07, H09; reverse-polarity/source switching | [AO3401A, Rev. 3.1, December 2023](https://www.aosmd.com/res/datasheets/AO3401A.pdf), manufacturer host; **text readable**, 5 pages. Pin/body-diode orientation and operation in each power-source state still need circuit review. |
| Sunlord SWPA4030S2R2NT, L1, C279948 | H07, H09; buck inductor | [SWPA4030S series specification, Rev. 11](https://www.alfatec.de/fileadmin/productfiles/datasheets/sunlord_swpa4030s_series.pdf), manufacturer document hosted by distributor Alfatec; **text readable**, 17 pages, includes the exact 2R2NT option. Check saturation/thermal current, DCR and land pattern with the converter design. |
| JSCJ B5819W SL, D4, C8598 | H07, H09; USB power path | [B5817W-5819W](https://datasheet.lcsc.com/datasheet/pdf/4ac2c059be7c462694ab0715ce987a85.pdf?productCode=C8598), manufacturer document linked by LCSC for C8598; **text readable**, 4 pages. Use the B5819W column; check loss/leakage and package polarity. |
| JSCJ MMBT3904, Q1/Q2, C20526 | H07; modem PWRKEY/NETLIGHT drivers | [MMBT3904 SOT-23](https://datasheet.lcsc.com/datasheet/pdf/9335632bcfa83df8351353eab379720e.pdf?productCode=C20526), exact LCSC-linked manufacturer document; **text readable**, 4 pages. Check pin numbering, drive and resistor values with the surrounding circuit. |

H06 needs the selected PCB stackup, copper/geometry and impedance calculation, rather than an IC datasheet.
H08 cannot have exact sensor datasheets yet because the sensors have not been selected. Resistor/capacitor
voltage ratings, tolerances, effective ceramic capacitance under bias and footprints still need checking
against the exact BOM parts during H07/H09; opening the IC datasheets does not complete that work.

## Initial findings to take into the review

- **H01:** the exact SY8089AAAC is in the ordering table on p.1. The same Rev. 0.9A document lists
  100% dropout operation on p.1 and maximum duty cycle 100% in the electrical-characteristics table on p.4.
  This supports the owner's finding. Input-to-output losses and low-battery transmit behavior remain T01.
- **H02:** PUOLOP's selected DW01A document lists nominal overdischarge detection at **2.50 V** (p.2/p.4),
  versus the approximate 2.4 V description in the project notes. Compare the exact limits and application
  circuit before reconciling the documentation; the current-trip threshold also depends on the FET path.
- **H03:** MAX17048 Rev. 7 p.6 specifies a **0.1 uF** VDD bypass and EP connection to GND. The current
  schematic/BOM uses **C44 = 1 uF**. This is a documented difference to evaluate, not proof that 1 uF is
  unsuitable. The exposed-pad land pattern remains a separate check.
- **H05 (checked 2026-10-30):** the SMN-303 drawing's top view shows the card inserted from the end opposite the
  contact row, with a 4.20 mm eject position. Its card-detect diagram reads "CD-GND: normal SHORT, inserting card
  OPEN", the reverse of the earlier project notes. Its recommended layout marks six "no pattern and via hole" areas
  under the springs. All three now drive the layout (branch `hardware/sim-holder-fix`).
- **AN2606 (checked 2026-10-31):** STM32L072 bootloader V4.x supports USART1, USART2 and USB DFU only, entered by
  Pattern 2 (BOOT0 = 1, nBOOT1 = 1). PA10/PA3 get internal pull-ups and DFU runs from HSI with no crystal.
  V4.1 limitation: DFU may fail behind some high-speed host controllers, so use a USB hub. No extra pull-ups needed.
- **Sunlord SWPA4030S (checked 2026-10-31):** Fig. 4-1/Table 4-1 give the land as pads b = 1.10 × c = 3.70 mm with
  gap a = 1.90 mm (centres ±1.5 mm). L1 now uses this land (`L_Sunlord_SWPA4030S`).
- **Modem source revision:** the project cites V1.04, the accessible Waveshare PDF is V1.03, and SIMCom's
  product page lists V1.05. Pin/sequence/RF checks must state the document revision used.

These are source-access findings. No schematic/PCB changes, full pin-to-pad audit, prototype measurements,
or production sign-off were performed in this pass. Update task status and repeated technical descriptions
together when each review item is closed.

## Access method

Several old LCSC PDF URLs redirect to a JavaScript viewer. Following its PDF link exposes a readable
`datasheet.lcsc.com/datasheet/pdf/...pdf?productCode=...` file. Thus an earlier failed download is not evidence
that the datasheet cannot be accessed. Hashed PDF URLs may change; the exact-part `www.lcsc.com/datasheet/C....pdf`
page can be used to rediscover the link. ST's MCU and ESD-family PDFs were also readable in this pass.
