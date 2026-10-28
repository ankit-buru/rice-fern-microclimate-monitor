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
