# Datasheet log (Step 5, read 2026-10-25)

Evidence file for the datasheet groups that replaced U-DS-PARTS (`scripts/signoff_status.py` DS_GROUPS). A group counts as closed only when its row is gone from docs/UNVERIFIED.md AND its heading here reads `## <ID>: VERIFIED`. Every number is quoted from the manufacturer PDF named in its row (document number and revision). Pages that could not be read are listed with the URL tried and the reply; nothing was filled from memory. A verified rating is a datasheet number, not a measurement of our parts.

## U-DS-PB1R: VERIFIED (PB1R bulk bank, shunt, clamp diode, damping resistors, comparator)

| Part (ref) | Source | Numbers used | Design effect |
|---|---|---|---|
| Panasonic EEHZC1H101P hybrid polymer-Al (PB1R CB1-CB9, PM2 CB1) | Panasonic "Technical Data ZC series" (Conductive Polymer Hybrid Aluminum Electrolytic Capacitor), https://industrial.panasonic.com/content/data/CP/PDF/ABA0000PE429.pdf, PDF of 2015-07-22, page ZC-16 | 50 V, 100 uF +-20 % (120 Hz), phi 10.0 x 10.2 mm (size code G: A, B 10.3; H 12.0 max; P 4.6; W 0.9), ESR 28 mohm max at 100 kHz, ripple 1600 mA rms max (100 kHz, 105 C), 125 C 4000 h, leakage 50 uA max. The 50 V ZC range ends at 100 uF (ZC-12 to ZC-16). | Replaces the six unverified 150 uF / 50 V polymer-Ta (7343-43): 9 cans keep 900 uF nominal, 720 uF at -20 % (>= 625 uF needed for 5 % droop at 19.6 V). PM2 CB1 470 uF -> 100 uF (no 470 uF 50 V part in this can). Eddy: the cans are closed aluminium loops that do not decay before the gate (pb1r_check WARN, OPEN_ITEMS 34). Land pattern: KiCad CP_Elec_10x10 (pads 4.0 x 2.6 at +-4.4 mm) covers the terminal span P 4.6 to H 12.0; Panasonic's recommended land was not in this document (bench/CAM item). Surge-voltage rating not in this document. |
| KEMET T521 polymer Ta, 50 V | not read from KEMET (search only: the largest 50 V X-case part listed in KEMET kits was 33 uF) | none used | the 150 uF / 50 V 7343-43 part was not found: replaced, see above |
| Vishay WSL2512 Power Metal Strip, 10 mohm (RS1S) | Vishay "WSL", https://www.vishay.com/docs/30100/wsl.pdf, document 30100, revision 23-Nov-2023 | WSL2512: 1.0 W at 70 C; 0.003-0.5 ohm at +-0.5 % / 0.0005-0.5 ohm at +-1 % | value text "10m 3W" -> "10m 1W"; the modeled RMS shunt current 1.8 A gives 32 mW (pb1r_check). Ordering code not checked. |
| Vishay WSK2512 four-terminal (considered for RS1S) | https://www.vishay.com/docs/30108/wsk2512.pdf, document 30108, revision 11-Dec-2023 | 1.0 W at 70 C, 0.0005-0.2 ohm; solder pad table a/b/c/d/e/l (0.005-0.2 ohm: a 2.29, b 3.30, c 0.76, d 0.51, e 1.70, l 3.68 mm) | NOT adopted: the 3-D pad drawing places the sense pads diagonally but gives no dimension for their position along the force-pad edge, so the land cannot be generated without guessing. Two-pad R2512 with the Kelvin sense track kept (handoff default). |
| Good-Ark ES3J (PB1R DC1 until 2026-10-28, SUPERSEDED by US3M) | Good-Ark "ES3D thru ES3J", https://goodarksemi.com/docs/datasheets/super_fast_recovery_rectifiers/ES3x.pdf (PDF modified 2025-06-16) | VRRM 600 V, IF(AV) 3.0 A, IFSM 100 A (8.3 ms), VF 1.7 V max at 3 A, trr 35 ns typ (IF 0.5 A, IR 1.0 A, Irr 0.25 A), CJ 40 pF | **WATCH (rule 6)**: 600 V < 630 V. No >= 630 V ultrafast SMC part was readable from a manufacturer: Vishay ES3 (https://www.vishay.com/docs/88589/es3.pdf, 88589, 08-Apr-2020) stops at 200 V; Vishay MURS340/360 (https://www.vishay.com/docs/88816/murs340.pdf, 88816, 08-Apr-2020) is 400/600 V, trr 50 ns; Vishay RS3 (https://www.vishay.com/docs/88709/rs3a.pdf, 88709, 25-Feb-2020) reaches 800 V but is a fast (trr 150/250/500 ns), not ultrafast, rectifier; Diodes, onsemi, MCC and Littelfuse pages answered 403 / Cloudflare. Modeled stress 466 V max (78 % of 600 V). ES3J kept. |
| Diodes Incorporated US3M (PB1R DC1 since 2026-10-28) | Diodes Inc. "US3M 3.0A Surface Mount Ultra-Fast Rectifier", Document number DS37228 Rev. 5 - 2, April 2015 (marked ADVANCED INFORMATION), manufacturer document via Farnell https://www.farnell.com/datasheets/2814468.pdf (the diodes.com asset link answered 404), saved as data/seed/datasheets/Diodes_US3M_DS37228_Rev5_2015-04.pdf (sha256 0f9dd572fdc58b25) | VRRM / VRWM 1,000 V, VR(RMS) 700 V, V(BR)R >= 1,000 V at 10 uA; IO 3.0 A at TT 75 C; IFSM 120 A; VF 1.5 typ / 1.8 max at 3.0 A; trr 70 typ / 85 max ns (IF 0.5 A, IR 1.0 A, Irr 0.25 A); CT 25 pF typ at 4 V; TJ -65 to +175 C; case SMC | meets rule 6 (1000 V >= 630 V; clamp node about 466 V: 47 %); same SMC footprint as ES3J. ADVANCED INFORMATION sheet: re-check the current Diodes revision before ordering. trr is longer than ES3J (35 ns): not in the transmit model (ASSUMPTIONS 45, bench 4.4) |
| Vishay D/CRCW e3, CRCW2512 (CB1D RDM1-3, 3 x 110 ohm) | Vishay "D/CRCW e3", https://www.vishay.com/docs/20035/dcrcwe3.pdf, document 20035, revision 14-Apr-2026 | CRCW2512 e3: P70 1.0 W, operating voltage Umax 500 V AC rms/DC, permissible voltage against ambient (insulation, 1 min) 300 V, 1 ohm - 10 Mohm | the stress table assumed 200 V working voltage: now 500 V (margin rises). WATCH: insulation 300 V against ambient, the chain node reaches about 466 V: the resistor bodies must not touch grounded metal or a conductive coating. |
| TI LM393 (PB1R U3) | TI SLCS005AH, revised April 2025, https://www.ti.com/lit/ds/symlink/lm393.pdf | pins (SOIC): 1 1OUT, 2 1IN-, 3 1IN+, 4 GND, 5 2IN+, 6 2IN-, 7 2OUT, 8 VCC (Table 4-1); supply (non-V devices) 2-30 V recommended, 36 V absolute; input range 0 to (V+) - 2.0 V | pinout matches `pw_design.LIB["LM393"]`; AUX12 = 12 V is inside the range; REF_I1 / ISENSE1 (about 0.2 V) are inside the input range |

## U-DS-POWERPATH: VERIFIED (PM2 and CB1D input: TVS, P-FET, gate zener, fuse)

| Part (ref) | Source | Numbers used | Design effect |
|---|---|---|---|
| SMCJ33A / SMCJ30A TVS (PM2 DTVS, CB1D DTV) | Vishay "SMCJ5.0A thru SMCJ188CA", https://www.vishay.com/docs/88394/smcj.pdf, document 88394, revision 09-Jan-2024 (Vishay second-source datasheet for the same part numbers; the Littelfuse page answered 403) | 1500 W (10/1000 us). SMCJ33A: VWM 33 V, VBR 36.7-40.6 V at 1 mA, IR 1.0 uA, IPPM 28.1 A, VC 53.3 V. SMCJ30A: VWM 30 V, VBR 33.3-36.8 V, IR 1.0 uA, IPPM 31.0 A, VC 48.4 V; VBR temperature coefficient 0.099-0.100 %/C | **Choice: SMCJ30A** (same SMC footprint). SMCJ33A's 53.3 V clamp exceeds the 50 V capacitors; SMCJ30A clamps at 48.4 V and its rated stand-off (30 V) is above the 29.4 V pack maximum. WATCH in the stress table: stand-off margin 2 % (rule 5 %); VBR min 33.3 V at 25 C is still 31.8 V at -20 C. |
| Vishay Si4401FDY P-MOSFET (PM2 Q1) | https://www.vishay.com/docs/75996/si4401fdy.pdf, document 75996, S17-1783-Rev. A, 27-Nov-17 | SO-8 single: 1, 2, 3 S; 4 G; 5-8 D (drawing, top view); VDS -40 V; VGS +-20 V; RDS(on) 0.0118 typ / 0.0142 max ohm at VGS -10 V, ID -10 A; 0.0183 max at -4.5 V; VGS(th) -1 to -2.3 V; EAS 20 mJ | pinout matches `PMOS_SO8`; the 15 mohm assumption holds (14.2 mohm max) |
| Vishay BZT52C15 zener (PM2 DZ1) | Vishay "BZT52 Series", https://www.vishay.com/docs/86342/bzt52_series.pdf, document 86342, Rev. 1.0, 22-Dec-2022 | VZ 14.25 / 15 / 15.60 V at IZT1 5 mA | Q1 gate clamp 15.6 V max < VGS 20 V |
| Bourns SF-1206S500-2 fuse (PM2 F1, CB1D F1) | Bourns "SinglFuse SF-1206S Series", https://www.bourns.com/docs/product-datasheets/sf-1206s.pdf, REV. J 04/21 | slow blow, 5.00 A, 32 VDC, interrupting 50 A at 32 VDC, 0.013 ohm typ, I2t 2.533 A2s; recommended pad layout 2.2 mm gap, 4.7 mm overall, 1.65 mm pad height (pads 1.25 x 1.65 mm); operating -20 to +105 C | replaces the "Littelfuse 0453005 class (verify DC rating)" 1812 part, whose page answered 403: new footprint FUSE1206B on PM2 and CB1D. 32 VDC vs 29.4 V pack maximum. |
| Amass MT60 (pack dock) | Amass "规格书" (specification) V1.2, MT60-M / MT60-F, PDF of 2016-06-07, manufacturer's sheet hosted by distributor ChipDip: https://static.chipdip.ru/lib/502/DOC008502173.pdf | DC 500 V, RC 30 A, MC 60 A, contact resistance 0.45 mohm, 1000 mating cycles, 12 AWG recommended, -20 to 120 C | ratings as assumed. The body envelope (ASSUMPTIONS 25) is in the drawing image, not read: stays in U-DS-PACK. |

## U-DS-RXAMP: VERIFIED (receive amplifier, VCM buffer, mux; OPEN_ITEMS 27)

| Part | Source | Numbers used | Design effect |
|---|---|---|---|
| TI OPA2365 (AB1 UB: VREF and VCM buffers) | TI SBOS365G, revised May 2023, https://www.ti.com/lit/ds/symlink/opa2365.pdf | supply 2.2-5.5 V; IB 0.2 pA typ; ISC +-65 mA; open-loop output impedance 30 ohm (1 MHz); section 8.3.3: "When operating in the unity-gain configuration, the OPAx365 remain stable with a pure capacitive load up to approximately 1 nF"; series resistor "typically 10 ohm to 20 ohm" for larger loads | OPEN_ITEMS 27, DC part: driving RS2 (1 kohm) into the idle MONO input costs at most 175 nA x 1 kohm = 0.18 mV: yes. NEW FINDING (OPEN_ITEMS 30): the buffers drive CVM 1 uF and CRF 10 uF per ADC directly at unity gain, far above the 1 nF the datasheet states. |
| TI OPA2211 (AB1 U1/U2) | TI SBOS377L, revised January 2020, https://www.ti.com/lit/ds/symlink/opa211.pdf, table 6.6 "Standard Grade OPAx211A" | supply 4.5-36 V; IB +-60 typ / +-175 max nA (25 C), +-250 nA max OPA2211A (-40 to 125 C); IOS +-25 / +-100 nA; en 1.1 nV/rtHz at 1 kHz, 1.4 at 100 Hz; In 1.7 pA/rtHz at 1 kHz; common-mode range for VS < +-5 V: (V-) + 2 V to (V+) - 1.4 V | noise as assumed (1.1 nV/rtHz). NEW FINDING (OPEN_ITEMS 31): on the single 5 V rail the input range is 2.0-3.6 V; VCM = VREF / 2 sits about 0.05 V above its lower end (VREF 4.096 V assumed, REF5041 not read). |
| TI CD74HC4051 (CB1D UM, 74HC4051) | TI SCHS122O, revised January 2026, https://www.ti.com/lit/ds/symlink/cd74hc4051.pdf | pins: 1 A4, 2 A6, 3 COM, 4 A7, 5 A5, 6 E (active low), 7 VEE, 8 GND, 9 S2, 10 S1, 11 S0, 12 A3, 13 A0, 14 A1, 15 A2, 16 VCC; VCC abs max 7 V; VCC - VEE 2-10 V; ron 70 ohm typ at 4.5 V | pinout matches `HC4051`; the Nexperia sheet (https://assets.nexperia.com/documents/data-sheet/74HC_HCT4051.pdf) answered 403, so the TI part is the verified one |

## U-DS-HALL: VERIFIED (HB2 trigger Hall switch)

| Part | Source | Numbers used | Design effect |
|---|---|---|---|
| TI DRV5023BIQLPG (HB2 HS1) | TI SLIS151G, revised September 2016, https://www.ti.com/lit/ds/symlink/drv5023.pdf | LPG (TO-92) pins: 1 VCC, 2 GND, 3 OUT (open drain, "requires a resistor pullup"); VCC 2.5-38 V; supply current 2.7 mA typ, 3.5 mA max; rDS(on) 22 ohm typ (25 C) / 50 ohm max (125 C) at 3.3 V, 10 mA; off leakage 1 uA max; output delay 13 typ / 25 max us; BI: BOP 6 / 14.5 / 24 mT, BRP 3 / 6 / 9 mT (min / typ / max, -40 to 125 C). TO-92 is orderable only as AJ and BI (FA is SOT-23 only, package addendum). | Chosen over AJ and FA because its worst-case BOP max / BRP min ratio (24 / 3 = 8) is the easiest to meet with the >= 2 mm extra magnet travel. Pin order matches `HALL_SW`. Vsat = I x 50 ohm, far below the 0.4 V the trigger check assumes. OPEN (OPEN_ITEMS 32): the magnet must give >= 24 mT at rest and <= 3 mT pressed at the sensor; no magnet field model yet. |

## U-DS-TXDRIVE: VERIFIED (main FET and gate driver; B7, 2026-10-28)

| Part | Source (saved in data/seed/datasheets/) | Datasheet values | Used for |
|---|---|---|---|
| Infineon IPB65R095C7 (PB1R Q1A/B) | Infineon "Datasheet IPB65R095C7", Final Data Sheet Rev. 2.0, 2013-10-11, https://www.infineon.com/assets/row/public/documents/24/49/infineon-ipb65r095c7-datasheet-en.pdf (HTTP 200; the old dgdl and product-page URLs answered 404 / 202) -> Infineon_IPB65R095C7_Rev2.0_2013-10-11.pdf | V(BR)DSS 650 V min (VGS 0, ID 1 mA), VDS 700 V at Tj,max (product summary); RDS(on) 84 typ / 95 max mohm (VGS 10 V, 11.8 A, 25 C), 202 mohm typ at 150 C; ID 24 A (TC 25 C) / 15 A (TC 100 C), ID,pulse 100 A; EAS 118 mJ, EAR 0.59 mJ, IAS 8.4 A; VGS +-20 V static / +-30 V dynamic; V(GS)th 3 / 3.5 / 4 V; Qg 45 nC typ (Qgs 12, Qgd 15, VDD 400 V); Ciss 2140 pF, Coss 33 pF (400 V); RG 0.9 ohm; dv/dt 100 V/ns | system_budget Vds and current rows (the values carried as unverified match), tx_vbus_sweep Ron, gate-charge row |
| Microchip TC4420 (PB1R U1, CB1D driver) | Microchip "TC4420/TC4429 6A High-Speed MOSFET Drivers" DS21419D (PDF 2012-12-13), https://ww1.microchip.com/downloads/en/DeviceDoc/21419D.pdf (HTTP 200; DS20001419H answered 403) -> Microchip_TC4420_DS21419D_2012.pdf | 6 A peak output; VDD 4.5-18 V operating, 20 V absolute; input -5 V .. VDD + 0.3 V; ROH 2.1 typ / 2.8 max ohm (10 mA, VDD 18 V); rise/fall 25 ns into 2500 pF; SOIC-8: 1 VDD, 2 INPUT, 3 NC, 4 GND, 5 GND, 6 OUTPUT, 7 OUTPUT, 8 VDD | pw_design TC4420 nets (AUX12 on 1/8, GND 4/5, NC 3, input 2): match; AUX12 12 V inside 4.5-18 V |

## U-DS-OKI: VERIFIED from a manufacturer document on a third-party host (B7)

| Part | Source | Datasheet values | Used for |
|---|---|---|---|
| Murata OKI-78SR-5/1.5-W36-C (M5 on CB1D) and the 12 V model (M12 on PB1R) | Murata Power Solutions "OKI-78SR Series" MDC_OKI-78SR-W36.C05 (20 pages, PDF modified 2017-12-01); murata.com answered HTTP 500 again (8807037992990, 8807028015134); copy from https://www.pdp8online.com/mfm/board/datasheets/oki-78sr.pdf -> Murata_OKI-78SR-W36_MDC_C05.pdf. Re-check against murata.com before ordering. | OKI-78SR-5/1.5-W36-C: 5 V, 1.5 A, 7.5 W, Vin 7-36 V, efficiency 89 / 90.5 %; 10.4 x 8.64 x 16.5 mm; pins 1 positive input, 2 common (ground), 3 positive output; input 36 V continuous absolute maximum; current limit inception 2.5 / 3.5 / 5.0 A. **The 12 V model in this sheet is OKI-78SR-12/1.0-W36-C: 12 V, 1.0 A (not 1.5 A), Vin 15-36 V** | M5 row; M12 renamed to the 1.0 A part (CORRECTIONS); pin maps match pw_design (VBUS 1, GND 2, out 3) |

## U-DS-PACK: VERIFIED from manufacturer documents on third-party hosts (B7)

| Part | Source | Datasheet values | Used for |
|---|---|---|---|
| Molicel INR-18650-P30B | Molicel "Product Data Sheet, Model INR-18650-P30B", Version 1.0 (PDF modified 2024-09-06); molicel.com 404 earlier; copy from https://fsaeonline.com/content/INR-18650-P30B-80111.pdf -> Molicel_INR-18650-P30B_PDS_v1.0.pdf | capacity 3000 mAh typ (10.8 Wh) / 2900 mAh min; 3.6 V nominal, 4.2 V charge, 2.5 V discharge; charge 3 A standard / 9 A max (60 C cut-off); discharge 30 A continuous (80 C cut-off); AC 8 mohm (30 % SOC), DC 17 mohm (50 % SOC); 18.6 mm max diameter, 65.2 mm max height, 47 g max | power_dock_check runtime, system_budget pack row, U7 cell bay (65.3 mm assumed: 0.1 mm conservative) |
| Amass MT60-M / MT60-F | Amass specification sheet V1.2 (MT60-F; MT60-M page), Changzhou Amass Electronics, copy from https://static.chipdip.ru/lib/502/DOC008502173.pdf -> Amass_MT60_spec_V1.2.pdf (drawing read from the rendered page) | contact resistance 0.45 mohm, DC 500 V, 30 A rated, 60 A momentary, 12 AWG, -20..120 C, UL94 V-0, 1000 cycles; **MT60-M body 27.50 long, 12.49 tall; MT60-F 26.70 long (8.70 cable end), 12.49 tall; mating face 12.00 x 12.50 (3 contacts)** | U6 pedestal / U7 front bay envelope: the assumed 20 x 16.5 x 8.6 mm was too small (CORRECTIONS, B7) |

## U-DS-BAV199: VERIFIED (receive input clamp; B7, 2026-10-28)

Source: Nexperia "BAV199 Low-leakage double diode", Product data sheet BAV199 v.3, 1 September 2020 (10 pages; revision history v.3 20200901, v.2 20011012). nexperia.com and assets.nexperia.com answered HTTP 403 (curl, WebFetch); the Nexperia-authored PDF was fetched from the mirror https://cdn.components.ru/media/PDF/1264335.pdf and is saved unchanged as data/seed/datasheets/BAV199_Nexperia_v3_2020-09-01.pdf (sha256 c09cdf672eb4274e...). A second-source Guangdong Hottech BAV199 sheet (owner-supplied) is kept as data/seed/datasheets/BAV199_GuangdongHottech_secondsource.pdf for reference only: its ratings (VR 70 V, IFM 500 mA, IO 215 mA, PD 200 mW, Tj 125 C) are NOT used for the Nexperia part.

| Item | Datasheet value (Nexperia v.3, Table) | Used for |
|---|---|---|
| Pinning | 1 = A1 (anode diode 1), 2 = K2 (cathode diode 2), 3 = K1 + A2 (Table 2) | afe_design D.1 = GND, D.2 = +5VA, D.3 = IN: matches (clamp below GND and above +5VA) |
| Reverse voltage | VR 75 V, VRRM 85 V (Table 5) | 5 V rails: no stress |
| Forward current, single diode | IF 160 mA continuous; IFRM 500 mA repetitive peak; IFSM 4 A non-repetitive (tp 1 us square, Tj(init) 25 C) (Table 5) | clamp current through RS (B4, B9 33 ohm option) |
| Power | Ptot 250 mW (Tamb <= 25 C) ; Tj 150 C max (Table 5) | |
| Forward voltage | VF max 900 mV at 1 mA, 1 V at 10 mA, 1.1 V at 50 mA, 1.25 V at 150 mA (Tj 25 C) | clamp level in sbq_damp2 |
| Leakage | IR 3 pA typ / 5 nA max at VR 75 V, Tj 25 C; 3 / 80 nA at 150 C | input offset: 5 nA x 100 ohm = 0.5 uV |
| Capacitance | Cd 2 pF typ (VR 0 V, 1 MHz) | input capacitance |
| Recovery | trr 0.8 us typ / 3 us max (IF = IR = 10 mA, IR(meas) 1 mA); VFRM 1.75 V max | clamp release after an overload |

## 74LVC1G66 (AB1 SW1-SW3 blank switch): VERIFIED (B9, 2026-10-28)

Source: TI "SN74LVC1G66 Single Bilateral Analog Switch", SCES323R (June 2001, revised September 2025), https://www.ti.com/lit/ds/symlink/sn74lvc1g66.pdf (HTTP 200) -> data/seed/datasheets/TI_SN74LVC1G66_SCES323R_2025-09.pdf

| Item | Datasheet value | Used for |
|---|---|---|
| Pinout (SOT-23-5, DBV) | 1 A, 2 B (bidirectional), 3 GND, 4 C control (H = ON), 5 VCC | afe_design SW.1 IN, SW.2 VCM, SW.3 GND, SW.4 BLANK, SW.5 +5VA: match |
| On-resistance | ron 5.5 typ / 10 max ohm at VCC 4.5 V, IS 32 mA; peak ron(p) 7.5 / 15 ohm (DBV) | sbq_damp2 (8 ohm assumed: inside), ab1_drive_option (5.5 / 10); ab1_options_model assumed 3 ohm (optimistic) |
| Absolute maximum | VCC -0.5..6 V (DBV); switch I/O -0.5 .. VCC + 0.5 V; IIOK +-50 mA; ON-state switch current IT +-50 mA; continuous through VCC/GND +-100 mA | ab1_drive_option switch-current margin |
| Leakage | IS(off) +-1 uA max (+-0.1 uA at 25 C), IS(on) +-1 uA max (5.5 V) | |

## U-DS-HVTERM: VERIFIED (flyback-net connector and clamp resistor bank; closed 2026-10-28)

Closed by removing the part that could not be verified and choosing one that can:
- **JL1**: no terminal block left on a flyback net. PB1R-v5 JL1 is plated solder holes for the AWG12 pair (pw_design `WIRE2_AWG12`, 2.6 mm), and CB1D JCL is plated holes for AWG22 600 V wire. interface_check lists no 5.08 mm terminal on any board (`terminals: []`). The 630 V question moved to the wire insulation (harness spec), not a connector.
- **RCL1**: 4 x Vishay BCcomponents PR03, 1 %, 1.24 kohm (E96), in series = 4.96 kohm (model 5.0 kohm, -0.8 %). Data sheet "PR01, PR02, PR03 Professional Metal Film Leaded Resistors", Document Number 28729, Revision 08-Jul-2025, https://www.vishay.com/docs/28729/pr010203.pdf (HTTP 200, application/pdf), saved unchanged as data/seed/datasheets/Vishay_PR01-02-03_28729_2025-07-08.pdf (sha256 1b65216400497850).

| Item | Datasheet value (PR03, Cu lead) | Used for |
|---|---|---|
| Rated dissipation P70 (1 ohm <= R) | 3 W (FeCu lead 2.5 W) | 1.18 W per part at the 4.7 W worst bank case: 39 % (src/mech/rcl1_fit.py) |
| Operating voltage Umax AC/DC | 750 V | 109 V peak per part (bank peak 436 V = Vds peak - VBUS, worst pack corner); each part alone >= 630 V (rule 6) |
| Resistance range, tolerance, E-series | 0.68 ohm to 1 Mohm; +-1 % (E96) | 1K24 1 % |
| Body | D 5.2 max, L1 16.7 max (0617), Cu wire 0.78 mm | NPM hot-zone fit (rcl1_fit.py, 1.0 mm clearance on the meshes) |
| Thermal resistance; hot-spot limit | 60 K/W; 250 C | bench item 4.5 (body temperature in the fill) |
| Endurance (1000 h at P70) | dR <= 5 % R + 0.1 ohm | the bank at 39 % of P70 |
| Termination caps | plated steel (magnetic) | the bank is in the neck module, 0.4 m from the head field |

Previous attempts (kept for the record):

| Part | URL tried | Reply | Kept as |
|---|---|---|---|
| PB1R JL1, 5.08 mm 2-way terminal block on DRAIN1 / VBUS | https://www.phoenixcontact.com/en-us/products/pcb-terminal-block-mkds-15-2-508-1715721 (404, Step 5); B7: WebSearch found Phoenix 7.62 mm-pitch blocks listed at 630 V (III/2) / 1000 V (II/2) (MKDS 5/2-7,62, GMKDS 3/x-7,62: distributor pages only); the one datasheet copy found (https://bpx.ie/dbdocument/104015/1731734.pdf) answered 403 | 404 / 403 | the 5.08 mm block's category rating is still unread; candidate for rule 6: a 7.62 mm-pitch Phoenix block (would change the PB1R footprint: not done) |
| PB1R JL1 and CB1D JCL, 5.08 mm 2-way terminal (2026-10-28, READ) | Phoenix Contact MKDS 1,5/ 2-5,08 (order 1715721) data sheet, copy at https://docs.rs-online.com/c702/0900766b817142b7.pdf (Phoenix page https://www.phoenixcontact.com/it/prodotti/1715721), saved as data/seed/datasheets/Phoenix_MKDS1.5-2-5.08_1715721_RS.pdf (sha256 4d9a2f2afe0b79f4) | read | conductor AWG 26 ... 14, rigid 0.14-2.5 mm2, flexible 0.14-1.5 mm2, strip 7 mm, torque 0.5-0.6 Nm; rated insulation voltage 250 V (III/3), UL 300 V / 10 A, dimensioning current 17.5 A. **This family does not fit: the AWG12 TX pair (3.3 mm2) is outside AWG 26-14, and DRAIN1 / COIL_B see about 460 V against 250 V** (src/pcb/interface_check.py FAILs; CORRECTIONS 2026-10-28) |
| PB1R RCL1, 5 kohm 10 W resistor bank under the lid | no part chosen; B7 close-out also read Yageo SQP/NSP (Product specification V.4, 6 Mar 2024, via TTI): SQP10A maximum working voltage 500 V, 48 x 9.5 x 9 mm | - | rejected: 500 V < 630 V rule and only one body fits the NPM hot zone; replaced by 4 x Vishay PR03 (above) |

## AMS1117-3.3 (CB1D UL, +3V3D for the AB1 ADCs): VERIFIED (B3, 2026-10-28)

Source: Advanced Monolithic Systems "AMS1117 1A Low Dropout Voltage Regulator" (DS1117, PDF created 2009-08-27, 8 pages), http://www.advanced-monolithic.com/pdf/ds1117.pdf (HTTP 200), saved unchanged as data/seed/datasheets/AMS1117_AdvancedMonolithic_DS1117_2009-08-27.pdf (sha256 189a2651878a87d5...). Second sources (UMW and others) use other dies: the order must name AMS or re-check against that maker's sheet.

| Item | Datasheet value | Used for |
|---|---|---|
| Pinning (SOT-223 top view) | 1 Ground/Adjust, 2 VOUT, 3 VIN, tab = output | pw_design SOT223 "1 GND/ADJ, 2 VOUT, 3 VIN, tab VOUT": matches (VERIFY tag can go) |
| Output | AMS1117-3.3 at VIN 4.8 V: 3.251 / 3.300 / 3.349 V (second row, the boldface full-temperature limits: 3.201 / 3.300 / 3.399 V); output current up to 1 A | +3V3D (AD7389-4 VCC 3.0-3.6 V: inside) |
| Dropout | 1.1 typ / 1.3 V max at IOUT 0.8 A (Note 4: higher above 0.8 A) | 5.0 -> 3.3 V leaves 1.7 V |
| Current limit | 900 min / 1100 typ / 1500 max mA at VIN-VOUT 1.5 V | |
| Minimum load | 5 typ / **10 mA max** to keep regulation (Note 5, 1.5 V <= VIN-VOUT <= 12 V) | **+3V3D load must stay >= 10 mA** (see system_budget) |
| Quiescent current | 5 typ / 11 mA max | +5V budget |
| Line / load regulation (3.3 V) | 0.5 / 10 mV (1.5-12 V); 3 / 15 mV (0-0.8 A, VIN 4.75 V) | |
| Ripple rejection | 72 dB typ (60 min) at 120 Hz, 22 uF tantalum, 1 A | |
| Thermal | theta-JA SOT-223 90 C/W (46 to > 90 C/W with copper); theta-JC 15 C/W; Tj -40..125 C; max dissipation 1.2 W SOT-223 (Note 2) | |
| Absolute maximum | VIN 15 V; lead 265 C 25 s | |

## U-DS-AD7389: VERIFIED from the user-supplied datasheet (AD7389-4 Rev. 0, 1/2022, 31 pages)

| Item | Datasheet value (page) | Used for |
|---|---|---|
| Channels / type | 4 fully differential, simultaneous sampling, 16 bit (p. 1) | one chip for AB1A (3 ch) and AB1B (2 ch) |
| Throughput | 2 MSPS, tCYC >= 500 ns, tCONVERT 190 ns, tACQUIRE 310 ns (p. 3, 5) | >= the 1 MSPS of the ADS8860 |
| Input range | AINx+ - AINx- = -VREF..+VREF (VREF 2.5 V); absolute input -0.1..VREF + 0.1 V; common mode 0.2..VREF - 0.2 V (p. 3) | VCM re-bias 2.048 V -> 1.25 V; usable single-ended swing 0..2.5 V |
| Absolute maximum, analog input | -0.3 V..VREF + 0.3 V or VCC + 0.3 V; ESD diodes conduct up to 10 mA (p. 8, 14) | series RAAF 200 ohm limits the over-range current |
| Input bandwidth | -3 dB 26.8 MHz, -0.1 dB 6.6 MHz; track capacitance 18 pF, hold 5 pF; R1 about 200 ohm, C2 15 pF (p. 4, 14) | the 360 kHz RC filter stays the limit |
| Accuracy | SNR 90.5 dB typ (89 min), THD -106 dB, INL +-0.1 typ (2.5 max) LSB, channel isolation -126 dB (p. 3) | |
| Reference | internal 2.5 V buffered, 2 ppm/C typ (10 max), 7 uV rms noise; REFOUT 1 uF; REFCAP 0.1 uF; "add a buffer when REFOUT is used for VCM" (p. 4, 9, 20) | REF5041 chain removed; VCM divider hangs on REFOUT through the OPA2365 half B |
| Supplies | VCC 3.0..3.6 V, VLOGIC 1.65..3.6 V, 1 uF each; REGCAP 1 uF; IVCC 21 mA typ operational, IVLOGIC 3.7 mA, total 89 mW typ (p. 4, 9) | +3V3D rail; power budget not checked |
| Interface | CS falling edge samples and converts; SPI; SDO bits (Configuration 2) 00 = 2-wire (default, reset 0x0): A and C on SDOA, B and D on SDOB, 32 SCLK (Table 13); one-cycle readback latency (p. 21); MSB first, twos complement, LSB = 2 VREF / 2^16 (p. 15); SDI word D15 WR, D14-D12 REGADDR: WR = 0 with REGADDR 0x0 / 0x6 / 0x7 is ignored and the next access reads conversion results (Table 17, p. 26), so SDI tied low is a NOP every frame (B3); tPOWERUP 5 ms to the first conversion, 11 ms settled within 1 % (internal reference), register access after 5 ms (p. 5) | B6 readout model src/sim/ad7389_readout.py; SDI low: no software reset, defaults only |
| Package | 24-lead LFCSP 4 x 4 x 0.55 mm (CP-24-25, PKG-005367, drawing rev 01-30-2017-A, JEDEC MO-248-UGGD), pitch 0.50 BSC, terminal b 0.20/0.25/0.30 x L 0.30/0.40/0.45, exposed pad 0.40/0.50/0.60 SQ with the pin-1 chamfer (leaders "PIN 1 INDICATOR" and "FOR PROPER CONNECTION OF THE EXPOSED PAD" both end on it), theta-JA 48.4 / theta-JC 0.432 C/W simulated (p. 8, 31). No land pattern, paste or mask is given. Source: owner-supplied PDF, saved unchanged as data/seed/footprints/AD7389-4_Rev0_datasheet_CP-24-25.pdf (sha256 803bf7a3...103f, Rev. 0, D22956-1/22(0), PDF modified 2022-01-28) | land 0.60 SQ EP + nominal terminals (afe_design `_ad7389()`, B1); theta-JC reads like a larger paddle: see ASSUMPTIONS 35 |

## U-DS-AD4134: READ (user-supplied datasheet, AD4134 Rev. A) and judged NOT a fit for AB1; not used in any design

| Item | Datasheet value | Why it matters |
|---|---|---|
| Type | 24-bit, 4-channel simultaneous continuous-time sigma-delta, ODR 0.01 to 1496 kSPS, bandwidth to 391.5 kHz, inherent anti-alias filter (p. 1, 4, 5) | could drop the 200 ohm / 2.2 nF filter; far more resolution than the AD7389-4 |
| Input | differential +-VREF, VREF 4.096 V or 5 V external, VCM VREF / 2 to AVDD5 / 2, differential input resistance 6.25 kohm, 317 uA/V (p. 6) | analog levels match the present 4.096 V / 2.048 V front end |
| Supplies | AVDD5 and DVDD5 4.5..5.5 V, AVDD1V8, DVDD1V8, CLKVDD and IOVDD 1.65..1.95 V, internal LDO from 2.6..5.5 V (p. 9) | needs 1.8 V rails and 1.8 V I/O: the Pico side is 3.3 V, so level shifting |
| Power | 450 to 556 mW (high performance, 374 kSPS), 254 to 386 mW (low power); full power-down 1 mW (p. 10) | about 5 to 6 times the 89 mW of the AD7389-4, inside a sealed potted cell |
| Clock and package | 48 MHz crystal or CMOS clock; 8 x 8 mm, 56-lead LFCSP, 0.75 mm tall (p. 1, 93) | more pins and area than the 4 x 4 mm AD7389-4 |
| Latency | wideband FIR group delay 39.8 / ODR; sinc3 7 / ODR, sinc6 9.5 / ODR (p. 7) | matters for sampling a decay right after turn-off |

## OPA2211 / OPA2365 supply current (AB1 +5VA load, viewer r2 system model): VERIFIED (2026-10-28)

Sources: TI SBOS377L "OPAx211 1.1-nV/rtHz Noise, Low Power, Precision Operational Amplifier" (October 2006, revised January 2020), https://www.ti.com/lit/ds/symlink/opa211.pdf (HTTP 200), saved unchanged as data/seed/datasheets/TI_OPA211_SBOS377L_2020-01.pdf (sha256 2415597a36a2108b...); TI SBOS365G "OPAx365 50-MHz, Zero-Crossover, Low-Distortion, High CMRR, RRI/O, Single-Supply Operational Amplifier" (May 2006, revised May 2023), https://www.ti.com/lit/ds/symlink/opa2365.pdf (HTTP 200), saved as data/seed/datasheets/TI_OPA2365_SBOS365G_2023-05.pdf (sha256 9a87d0790f4b118c...).

| Item | Datasheet value | Used for |
|---|---|---|
| OPA2211 IQ per channel, IOUT = 0 | 3.6 mA typ, 4.5 mA max (25 C); 6 mA max over -40..125 C (POWER SUPPLY table) | system_budget +5VA row (6 channels on AB1A + AB1B); system_live rail term (over-temperature value) |
| OPA2365 IQ per amplifier, IO = 0 | 4.6 mA typ, 5 mA max; 5 mA over -40..125 C | same (4 amplifiers) |
| OPA2365 supply range | 2.2-5.5 V | +5VA at 5 V: inside |

## LB1 LEDs and level shifter (LB1-v6 clocked upgrade): VERIFIED (2026-10-28)

| Part | Source (saved unchanged in data/seed/datasheets/) | Values used |
|---|---|---|
| SK9822-EC20 (chosen) | OPSCO "SK9822-EC20-000" Rev. A/0, https://atta.szlcsc.com/upload/public/pdf/source/20260416/0E56B06F3E16E5AE4EC8758FD09E8E05.pdf (HTTP 200), OPSCO_SK9822-EC20-000_RevA0.pdf (sha256 4136b81ad70d0227...) | 2.0 x 2.0 x 0.65 mm; top view 1 SDO, 2 GND, 3 SDI (left), 6 CKO, 5 VDD, 4 CKI (right); pads 0.76 (drawn "0.7-6") x 0.46, column gap 0.6, row gap 0.4; max serial clock 15 MHz; PWM 1.2 kHz; IDD 1 mA static; 5 V, 18 mA version |
| SK6812MINI-E (LB1-v5 part) | OPSCO SPC/SK6812MINI-E Rev. 02, https://cdn-shop.adafruit.com/product-files/4960/4960_SK6812MINI-E_REV02_EN.pdf, OPSCO_SK6812MINI-E_Rev02.pdf (164f1e44bdfb408b...) | 3.2 x 2.8 x 1.78 mm reverse mount (leads 0.84 below the top, body through a 3.2 x 2.8 cutout, pads 1.8 long outside); 800 kbit/s; PWM 1.2 kHz; pins 1 VDD, 2 DOUT, 3 GND, 4 DIN |
| SK9822 5050 (evaluated) | OPSCO SPC/SK9822 Rev. 01, https://cdn-shop.adafruit.com/product-files/2343/SK9822_SHIJI.pdf, OPSCO_SK9822_Rev01.pdf (c87f7bb1fe86155e...) | 5.0 x 5.0 x 1.6 mm (text 5.5 x 5.0); 30 MHz; TCLKH / TCLKL > 30 ns; frame 64 + 32 N bit; PWM 1.2 kHz; pins 1 SDI, 2 CKI, 3 GND, 4 VCC, 5 CKO, 6 SDO |
| SK6805-2427 (evaluated) | OPSCO SPC/SK6805-2427, Adafruit product 3484 datasheet, OPSCO_SK6805-2427.pdf (0bd417f5a15675fc...) | 2.4 x 2.7 x 1.1 mm top SMD, one-wire 800 kbit/s, PWM 1.2 kHz |
| APA102C (evaluated) | iPixel / Shiji APA102C (scanned, 5 pages), https://cdn-shop.adafruit.com/datasheets/APA102.pdf, iPixel_APA102C.pdf (3ce93e9ab1cd8c38...) | 5 x 5 x 1.4 mm; FOSC 800-1200 kHz; frame 32 x 0 + N x 32 + 32 x 1; no maximum clock stated (512 kHz example) |
| TLC5947 (evaluated, isolated option) | TI TLC5947, https://www.ti.com/lit/ds/symlink/tlc5947.pdf, TI_TLC5947.pdf (5212c127bb5e5230...) | 24 channels, 12-bit PWM, internal 4 MHz oscillator, BLANK input, HTSSOP-32 11.0 x 6.2 mm |
| SN74AHCT1G125 (U1, new U2) | TI SCLS378P (Aug 1997, revised Mar 2024), https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf, TI_SN74AHCT1G125_SCLS378P_2024-03.pdf (564b239f73ff629f...) | DBV pins 1 OE, 2 A, 3 GND, 4 Y, 5 VCC (Table 4-1); VIH 2 V, VIL 0.8 V (3.3 V -> 5 V translation); tpd 6 ns max at 5 V; +-8 mA |

## CB1D yaw gyro (sweep direction for the LED side display, owner approval 2026-10-28): VERIFIED (2026-10-28)

| Part | Source (saved unchanged in data/seed/datasheets/) | Values used |
|---|---|---|
| BMI270 (U9 on CB1D-C2) | Bosch Sensortec BMI270 datasheet, document BST-BMI270-DS000-08, revision 1.6, https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi270-ds000.pdf, Bosch_BMI270_BST-BMI270-DS000-08_rev1.6.pdf (sha256 f68ce3c74f011a80...) | LGA-14 2.5 x 3.0 x 0.83 mm; pins 1 SDO, 2 ASDx, 3 ASCx, 4 INT1, 5 VDDIO, 6 GNDIO, 7 GND, 8 VDD, 9 INT2, 10 OCSB, 11 OSDO, 12 CSB, 13 SCx, 14 SDx (s.7 connection table); I2C: SDO to GND (default address), CSB to VDDIO; unused INT1 / INT2 / OCSB / OSDO: DNC, unused ASDx / ASCx: VDDIO or DNC, never GND; VDD 1.71-3.6 V, VDDIO 1.2-3.6 V; 100 nF at pin 5 and pin 8; I2C standard / fast / fast-mode-plus 1000 kHz, 7-bit address; gyro +-125..+-2000 dps, ODR 25-6400 Hz, zero-rate offset +-0.5 dps (25 C), TCO +-0.015 dps/K; a configuration file must be loaded at start-up (s.4.4, INIT_DATA); landing pattern s.8.3 (drawing read: side pads 0.475 x 0.25 on 0.5 pitch, inner edge +-0.925 mm; top / bottom pads 0.25 x 0.475 at x -0.5 / 0 / +0.5, inner edge +-0.675 mm; pad tolerance +-50 um) |
| LSM6DSO (alternate for UG, owner-supplied) | ST DS12140 Rev 3 (June 2024), supplied by the owner 2026-10-28 (DS_lsm6dso.zip), ST_LSM6DSO_DS12140_Rev3_2024-06.pdf (sha256 dd899e37f2fc33b8...) | LGA-14L 2.5 x 3.0 mm, height 0.86 max in Figure 25 (0.83 in the summary); 14 terminals 0.25 +-0.05 x 0.475 +-0.05 on 0.5 pitch, same pin numbering as the BMI270: 1 SDO/SA0, 2 SDx, 3 SCx, 4 INT1, 5 VDDIO, 6 GND, 7 GND, 8 VDD, 9 INT2, 10 OCS_Aux, 11 SDO_Aux, 12 CS, 13 SCL, 14 SDA; mode 1: pins 2 / 3 to VDDIO or GND, pin 10 unconnected, pin 11 VDDIO or unconnected; VDD 1.71-3.6 V; I2C standard / fast mode 400 kHz (and MIPI I3C); gyro zero-rate +-1 dps, +-0.010 dps/C, rate noise 3.8 mdps/rtHz (high-performance), 0.55 mA combo; no configuration file at start-up. Land pattern: the datasheet refers to ST TN0018 (NOT on disk: UNVERIFIED that ST's recommended land equals the Bosch land used on CB1D-C2) |

## AU1 audio board (OPEN_ITEMS 41-43): VERIFIED (2026-10-28)
Downloaded from the manufacturers and saved in data/seed/datasheets; every number below is the one src/pcb/au1_check.py and the AU1 netlist use.

| Part | Source (URL, saved file, sha256 prefix) | Facts used |
|---|---|---|
| TPS560430 (UB, 5 V buck) | TI SLVSE22B (rev. June 2018), https://www.ti.com/lit/ds/symlink/tps560430.pdf, TI_TPS560430_SLVSE22B_2018-06.pdf (3c5e30aa5ce3422f) | 4-36 V in, 600 mA, 1.1 / 2.1 MHz variants; VREF 1.0 V so VOUT = 1.0 x (1 + RFBT / RFBB): 88k7 / 22k1 gives 5.014 V; RFBT 10-100 k recommended |
| TPA2005D1 (US, speaker amp) | TI SLOS369G (rev. Oct 2015), https://www.ti.com/lit/ds/symlink/tpa2005d1.pdf, TI_TPA2005D1_SLOS369G_2015-10.pdf (f5d959414918bfe7) | 1.4 W into 8 ohm at 5 V; gain = 2 x 150 k / RI (142-158 k spread); RI 150 k gives 2 V/V |
| TLV755P (UL, 3.3 V LDO) | TI SBVS320D (rev. Sep 2024), https://www.ti.com/lit/ds/symlink/tlv755p.pdf, TI_TLV755P_SBVS320D_2024-09.pdf (96e2706d4b13656d) | 1.45-5.5 V in, 500 mA, dropout 238 mV max at 500 mA (3.3 V out) |
| MSPM0G3507 (UM, controller) | TI SLASEX6C (rev. Oct 2025), https://www.ti.com/lit/ds/symlink/mspm0g3507.pdf, TI_MSPM0G3507_SLASEX6C_2025-10.pdf (0cba2418fd28709c) | 28-pin VSSOP (DGS28, 0.5 mm pitch, 7.1 x 4.9 mm); DGS28 pins from the pin-attributes table: 1 PA26, 2 PA27, 3 VCORE, 6 NRST, 7 VDD, 17 PA14, 18 PA15, 21 PA18, 22 PA19 / SWDIO, 23 PA20 / SWCLK, 24 PA21, 28 PA25 |
| TPA6132A2 (UH, headphone amp) | TI SLOS597B (rev. July 2017), https://www.ti.com/lit/ds/symlink/tpa6132a2.pdf, TI_TPA6132A2_SLOS597B_2017-07.pdf (e8a23e00bd0bbc17) | WQFN-16 3 x 3 mm; 2.3-5.5 V; 25 mW into 16 ohm; gain table 1: G0 >= 1.3 V, G1 <= 0.5 V gives 0 dB (-1.0 V/V) |
| SRN4018-220M (LB, buck inductor) | Bourns SRN4018 series, https://www.bourns.com/docs/Product-Datasheets/SRN4018.pdf, Bourns_SRN4018.pdf (8cffe38531926429) | 22 uH +-20 %, DCR 0.348 ohm max, Irms 0.9 A, Isat 0.95 A (inductance -30 % at Isat) |
| SF-1206S050-2 (PM2-B F2, AU1 feed fuse) | Bourns SF-1206S series, https://www.bourns.com/docs/product-datasheets/sf-1206s.pdf, Bourns_SF-1206S.pdf (703b1f579a261b6b) | slow-blow thin-film chip fuse, 1206; rated 0.50 A, 0.596 ohm typ; 63 VDC rating read from a cell shared by the low-current rows (layout of the extracted table: confirm on the printed page) |
| SJ-3524-SMT (headphone jack, panel-mounted, on wire pads) | Same Sky (CUI) SJ-352X-SMT, 2025-04-15, https://www.cuidevices.com/product/resource/sj-352x-smt.pdf, SameSky_SJ-352X-SMT_2025-04-15.pdf (1dfe6f11cad02647) | 3.5 mm stereo jack; part key: 3 = no switch, 4 = tip switch, so the plug-detect (HP_DET) needs SJ-3524-SMT; rated 12 Vdc, 1 A, 5000 cycles; its land pattern is not used (the jack is wired to the JHP pads) |

## Potting fillers (owner-proposed single matrix, 2026-10-28): 3M Glass Bubbles iM30K READ (manufacturer table on a third-party host)

| Part | Source | Facts used |
|---|---|---|
| 3M Glass Bubbles iM30K | 3M product information "3M Glass Bubbles K Series / S Series / iM", copy at https://Aircraftspruce.Com/catalog/pdf/3MGLASS%20BUBBLES.pdf (the 3M multimedia link answered HTML), saved as data/seed/datasheets/3M_GlassBubbles_K_S_iM_series_table.pdf (sha256 84a6fb820de49674) | true density 0.60 g/cc typical (0.57-0.63); isostatic crush strength 28,000 psi at 90 % survival (the iM30K data sheet Rev C, found by search, lists 27,000 psi: not read here); calculated thermal conductivity 0.200 W/mK; particle size 8.6 / 15.3 / 23.6 / 26.7 um (10th / 50th / 90th / effective top); dielectric constant of the series 1.2-2.0 at 100 MHz (theoretical); all "typical, not for specification" |

## Potting and shielding products (owner-supplied PDFs, 2026-10-28): READ

Uploads: 3m-glass-bubbles-im30k.pdf, tds-832tc-2parts.pdf, tds-841ar-l.pdf, Nickelliquid_.pdf (byte-identical to tds-841ar-l.pdf), Thermal_layer_.pdf (the 2017 841AR-Liquid sheet, not a thermal product). Used by src/sim/potting_matrix_eval.py (`products()`, `product_fit`).

| Part | Source | Facts used |
|---|---|---|
| 3M Glass Bubbles iM30K | 3M Advanced Materials Division data sheet, data/seed/datasheets/3M_GlassBubbles_iM30K_datasheet.pdf (sha256 b6380775496f836c) | crush strength 27,000 psi at 90 % survival by volume; true density 0.60 g/cc; packing factor 60 %; average diameter 18 um; softening point 600 C; flotation 90 %; volatiles 0.5 wt%; "not for specification purposes" |
| MG Chemicals 832TC thermally conductive epoxy (2 part) | TDS Ver. 4.3, 04 February 2026, data/seed/datasheets/MG_832TC_TDS_Ver4.3_2026-02-04.pdf (sha256 bd2744b8af148b0c) | mixed density 1.7 g/mL; mixed viscosity 27,000 cP; 1:1 by volume; working time 2 h; shrinkage 1.4 % (calculated); thermal conductivity 0.7 W/(m K) (ASTM E1461); Tg 50 C; CTE 142 ppm/C below Tg, 114 above; Shore 81 D; volume resistivity 8.2e12 ohm cm; breakdown 48,300 V at 3.175 mm (386 V/mil); dielectric constant 3.7 and dissipation factor 0.1 at 1 MHz; water absorption 0.2 %; service -30 to 175 C; cure 96 h at room temperature or 2 h 65 C / 1 h 80 C / 45 min 100 C; vacuum de-air 25 inHg about 2 min |
| MG Chemicals 841AR Super Shield nickel conductive coating | TDS Rev. 7.0, 17 Sept 2026, data/seed/datasheets/MG_841AR_TDS_Rev7.0_2026-09-17.pdf (sha256 25936db4ad592575) | resistivity 4.0e-3 ohm cm; surface resistance 1.60 ohm/sq at 25 um, 0.80 at 50 um; minimum film 25 um; magnetic class ferromagnetic; service -40 to 120 C; cure 24 h at 25 C or 30 min at 65 C; adhesion 5B on ABS, PC, polyamide, PVC, FR4 (0B aluminium, copper, glass; PETG not listed); density 1.7 g/mL; viscosity 1460 cP; shielding 42-55 dB 10-100 MHz, 67 dB at 1 MHz |
| MG Chemicals 841AR-Liquid (older sheet) | TDS Ver. 2.05, 31 October 2017, data/seed/datasheets/MG_841AR_Liquid_TDS_Ver2.05_2017-10-31.pdf (sha256 d5143940c2380858) | surface resistance 0.52 / 0.38 / 0.29 ohm/sq at 1 / 2 / 3 coats (1.6 / 4.0 / 5.8 mil); relative permeability >= 100, ferromagnetic; solvents acetone, dimethyl carbonate, heptan-2-one (etches ABS / PC / PVC); intermittent -50 to 125 C; shielding 84-89 dB at 10-100 kHz (IEEE 299, 51 um). Remanence and magnetic viscosity: not given on either sheet (UNVERIFIED, bench PT9) |

## RF2-DS-MP1V2: PARTLY VERIFIED (RF2 clean-sheet head, MP1 v2 preamp and analog supply candidates; read 2026-10-30)

These rows serve the RF2 side experiment (experiments/RF2_cleansheet/PARTS_RF2.md) and do not close any baseline group. Files are in data/seed/datasheets/. Analog Devices (analog.com, HTTP/2 reset and empty replies), Microchip (403 Access Denied) and Infineon (202 with an empty body) refused plain fetches on 2026-10-30, so ADA4896-2, LT6200/LT6201, LT3045 and DN2470 stay **UNVERIFIED**.

| Part | Source | Numbers used | Design effect |
|---|---|---|---|
| TI LMH6629 ultra-low-noise op-amp | TI SNOSB18I, Apr 2010, rev. Dec 2014, https://www.ti.com/lit/ds/symlink/lmh6629.pdf, TI_LMH6629_SNOSB18I_2014-12.pdf (sha256 5c37f7b1b67bdd90) | en 0.69 nV/rtHz, in 2.6 pA/rtHz; supply 2.7-5.5 V, specified at VS = 5 V single supply; supply current 15.5 mA typ; min stable gain 10 V/V (SOT-23-5) or 4 / 10 selectable (WSON-8, COMP pin); CMVR -0.30 to 3.8 V (CMRR > 70 dB); abs max: differential input 3 V, input current +-10 mA, analog input -0.5 V to VS; packages SOT-23-5 2.90 x 1.60 mm, WSON-8 3.00 x 3.00 mm | best verified voltage noise for MP1 v2 (0.69 vs OPA2211 1.1 nV/rtHz). WATCH: the +-10 mA input-current and -0.5 V input limits are far below the modeled clamp current (284 mA peak, generic model), so the clamp diodes must not sit directly on its pin: a series resistor between the clamp node and the op-amp input (about 50 ohm or more, to be sized against the -0.5 V limit), which adds noise. 15.5 mA per amplifier (single only: two parts for two stages). |
| TI OPA1612 audio op-amp (dual) | TI SBOS450C, Jul 2009, rev. Aug 2014, TI_OPA1612_SBOS450C_2014-08.pdf (sha256 a7b107d9642294fa) | en 1.1 nV/rtHz at 1 kHz (1.5 max); supply 4.5-36 V (+-2.25 to +-18 V); VCM (V-) + 2 to (V+) - 2 V | on 5 V the input range is 2.0-3.0 V (VBIAS 2.5 V fits); no noise gain over the verified OPA2211: not adopted |
| TI TPS7A94 1 A LDO | TI SBVS336C, Sep 2021, rev. Jun 2023, TI_TPS7A94_SBVS336C_2023-06.pdf (sha256 bf9c611825fdcd2b) | output noise 0.46 uVrms (10 Hz-100 kHz, CNR/SS 4.7 uF); PSRR 110 dB at 1 kHz, 95 dB at 10 kHz, 78 dB at 100 kHz; VIN 1.7-5.7 V; VOUT 0-5.5 V adjustable; dropout 150 mV at 1 A; WSON-10 3.00 x 3.00 mm | analog rail for MP1 / AB1 from the 5 V buck (for example 4.5 V out): 0.46 uVrms over 100 kHz is about 1.5 nV/rtHz flat if white, entering the preamp only through its PSRR. Chosen over TPS7A20 for MP1 v2. |
| TI TPS7A20 300 mA LDO | TI SBVS338H, Mar 2020, rev. Jul 2024, TI_TPS7A20_SBVS338H_2024-07.pdf (sha256 09b617bbe51310c0) | output noise 7 uVrms (10 Hz-100 kHz, IOUT 300 mA); PSRR 95 dB at 1 kHz; VIN 1.6-6.0 V; VOUT 0.8-5.5 V; SOT23-5 2.9 x 2.8 mm or 1 x 1 mm X2SON | 15 x the TPS7A94 noise: digital-side or LED-logic rail only |

## RF2-DS-DISPLAY: VERIFIED (RF2 dense LED display power, read 2026-10-30)

| Part | Source | Numbers used | Design effect |
|---|---|---|---|
| TI LMR36520 2 A synchronous buck | TI "LMR36520 SIMPLE SWITCHER 4.2V to 65V, 2A Synchronous Step-Down Converter", Rev. C, https://www.ti.com/lit/ds/symlink/lmr36520.pdf, data/seed/datasheets/TI_LMR36520_RevC.pdf (sha256 c5be6bd4f8a480f1) | VIN 4.2-65 V, input transient protection to 70 V; IOUT 0-2 A; VOUT 1 V to 95 % of VIN; 400 kHz; 90 % efficiency at 24 VIN / 5 VOUT / 1 A | own +5V_LED rail for the 522-LED display on CB1D: 1.372 A worst case (static + brightness cap) = 31 % margin; above the 7S pack and the PM2 TVS clamp (48.4 V) |
| TI TPS22918 load switch | TI "TPS22918 5.5-V, 2-A, 52-mohm On-Resistance Load Switch", Rev. C, https://www.ti.com/lit/ds/symlink/tps22918.pdf, data/seed/datasheets/TI_TPS22918_RevC.pdf (sha256 1b28eb58003d28b1) | VIN 1-5.5 V; 2 A maximum continuous; RON 52 mohm typ at 5 V; adjustable rise time (CT); SOT23-6 2.90 x 2.80 mm | gates the display rail off while the detector is silent (the 522 x 1 mA static current is otherwise always drawn) |
| OPSCO SK9822-EC20 static current | OPSCO "SK9822-EC20-000" Rev. A/0 (already on disk, see the LB1-v6 row) | IDD static power consumption 1 mA typ; output drive 16-21 mA per channel (18 mA version, VDS 1 V); serial clock max 15 MHz | display static load 522 mA; data clocked at 8 MHz |


## RF2-DS-HVFET: VERIFIED (owner-supplied PDFs, read 2026-10-30; closes the UNVERIFIED depletion-FET rows of RF2-DS-MP1V2)

| Part | Source | Numbers used | Design effect |
|---|---|---|---|
| Littelfuse / IXYS IXTY08N100D2 (TO-252), IXTA (TO-263), IXTP (TO-220), N-channel depletion mode | IXYS DS100182C (9/17), data/datasheets/Littelfuse_IXTY-IXTA-IXTP08N100D2_DS100182C_2017-09.pdf (sha256 4b54754922f701f3) | VDSX 1000 V (TJ 25-150 C); VGSX +-20 V continuous, +-30 V transient; PD 60 W (TC 25 C); BVDSX >= 1000 V at VGS -5 V, ID 25 uA; VGS(off) -2.0 to -4.0 V at VDS 25 V, ID 25 uA; IDSX(off) <= 1 uA (15 uA at 125 C); RDS(on) <= 21 ohm at VGS 0 V, ID 400 mA; ID(on) >= 800 mA at VGS 0 V, VDS 50 V; gfs 330 min / 560 typ mS; Ciss 325, Coss 24, Crss 6.5 pF typ (VGS -10 V, VDS 25 V); Qg 14.6 nC; body diode VSD 0.8 typ / 1.3 max V, trr 1.03 us; RthJC 2.08 C/W; weight TO-252 0.35 g | **chosen** for the MP1 v2 current limiter: 1000 V against the 460 V flyback (2.2x, rule 6), and the low Coss keeps the turn-off edge current into the clamps at 0.41-0.45 A (inside BAV199 IFRM 0.5 A). Package IXTY (TO-252) |
| Microchip DN2470 (TO-252), N-channel depletion-mode vertical DMOS | Microchip DS20005410A (2015), data/datasheets/Microchip_DN2470_DS20005410A_2015.pdf (sha256 429a901749dd8fb3) | BVDSX >= 700 V at VGS -5 V, ID 100 uA; VGS(off) -1.5 to -3.5 V at VDS 25 V, ID 10 uA; dVGS(off)/dT <= -4.5 mV/C; IGSS <= 100 nA; IDSS 500 mA typ at VGS 0 V, VDS 25 V; RDS(on) <= 42 ohm at VGS 0 V, ID 100 mA (+1.1 %/C); GFS >= 100 mmho; Ciss <= 540, Coss <= 60, Crss <= 25 pF; TO-252: ID 170 mA continuous, 500 mA pulsed, 2.52 W (FR4 25 x 25 x 1.57 mm), theta-ja 132 C/W; pins 1 gate, 3 source, 2 / 4 drain; body diode trr 800 ns | not chosen: 700 V (1.5x), twice the on-resistance (noise) and 2.5x the output capacitance: the modeled turn-off edge current reaches 0.86-1.09 A, above BAV199 IFRM 0.5 A and its own 500 mA pulsed rating. This also resolves the earlier distributor conflict (170 mA is the continuous, 500 mA the pulsed rating) |


## RF2-DS-FERRITE: VERIFIED material values (Ferroxcube material sheets downloaded 2026-10-30 from ferroxcube.com/upload/media/product/file/MDS/<grade>.pdf)

| Material | Source | Numbers used | Design effect |
|---|---|---|---|
| Ferroxcube 3C90 MnZn | data/datasheets/Ferroxcube_3C90_material.pdf (sha256 803f0da1bbc44a82) | mu_i 2300 +-20 % (25 C, <= 10 kHz, 0.25 mT); B 470 mT (25 C, 10 kHz) / 380 mT (100 C); rho about 5 ohm m (DC, 25 C); TC >= 220 C; density 4800 kg/m3 | hood material in rf2_hood.py (mu_i, saturation at 100 C, mass) |
| Ferroxcube 3C94 MnZn | data/datasheets/Ferroxcube_3C94_material.pdf (sha256 85baa0ebc78e351b) | mu_i 2300; B 470 / 380 mT; rho about 5 ohm m; density 4800 | alternative to 3C90 (same DC values) |
| Ferroxcube 3C95 MnZn | data/datasheets/Ferroxcube_3C95_material.pdf (sha256 21dd5bfbd5408100) | mu_i 3000 +-20 %; B 530 / 410 mT; rho about 5 ohm m; density 4800 | higher-mu, flatter-with-temperature alternative |
| Ferroxcube 3F3 MnZn | data/datasheets/Ferroxcube_3F3_material.pdf (sha256 2dd2931be058931f) | mu_i 2000; B 440 / 370 mT; rho about 2 ohm m; density 4750 | alternative |
| Ferroxcube 3E6 MnZn | data/datasheets/Ferroxcube_3E6_material.pdf (sha256 7154d57bc4f59643) | mu_i 10000 +-30 %; B 460 mT; rho about 0.1 ohm m; Tc >= 130 C | not used: low resistivity, Tc close to a hot-car / sun-loaded head |
| Ferroxcube 4A11 NiZn | data/datasheets/Ferroxcube_4A11_material.pdf (sha256 f28120bdbb943705) | mu_i 850 +-20 %; B 340 / 230 mT; rho about 1e5 ohm m; TC >= 150 C; density 5100; tan d / mu_i <= 100e-6 at 1 MHz | NiZn option: no conduction at all, flat to several MHz |
| Ferroxcube 4C65 NiZn | data/datasheets/Ferroxcube_4C65_material.pdf (sha256 5017f684c0f55135) | mu_i 125 +-20 %; B 380 / 340 mT; rho about 1e5 ohm m; density 4500 | low-mu bound (close to flexible-sheet values) |

Not on any of these sheets, and needed before a hood is built:
- **Magnetic viscosity / after-effect** (the slow decay a PI receiver sees from ferrite after the pulse): bench measurement.
- **Flexible sintered ferrite sheets:** permeability, thickness and saturation. The Wuerth WE-FSFS and TDK IFL downloads were refused by the vendor sites.

## RF2-DS-FERRITE-FR: VERIFIED material values (owner-supplied printouts of the Fair-Rite material web pages, read 2026-10-30)

| Material | Source | Numbers used | Design effect |
|---|---|---|---|
| Fair-Rite 77 MnZn ("frequencies up to 100 kHz") | fair-rite.com 77 Material Data Sheet page, data/datasheets/FairRite_77_material_webpage.pdf (sha256 f6c7fd5c6ef344e2) | mu_i 2000 (B < 10 G); B 5100 G (510 mT) at H 5 Oe; Br 1800 G; Hc 0.25 Oe; tan d / mu_i 15e-6 at 0.1 MHz; temperature coefficient of mu_i 1.2 %/C (20-70 C); Tc > 200 C; resistivity 100 ohm cm (1 ohm m); toroid 18/10/6 mm, 25 C, 10 kHz | rf2_hood_size.py material "Fair-Rite 77 MnZn" (mu 2000, 510 mT) |
| Fair-Rite 61 NiZn ("up to 25 MHz") | fair-rite.com 61 Material Data Sheet page, data/datasheets/FairRite_61_material_webpage.pdf (sha256 68fbfdbbe09363e1) | mu_i 125; B 2500 G (250 mT) at H 15 Oe; Br 1000 G; Hc 1.2 Oe; tan d / mu_i 90e-6 at 10 MHz; temperature coefficient 0.10 %/C; Tc > 300 C; resistivity 1e8 ohm cm (1e6 ohm m); "strong magnetic fields or excessive mechanical stresses may result in irreversible changes in permeability" | rf2_hood_size.py material "Fair-Rite 61 NiZn" (mu 125, 250 mT) |

Caveats:
- The 510 / 250 mT values are B at a stated H, not saturation at 100 C.
- The 77 sheet gives no 100 C value.
- The complex-permeability and power-loss curves are linked CSVs that are not in the printouts.

## RF2-DS-STAGE3: VERIFIED stage 3 parts (2026-10-30)

| Part | Source | Numbers used | Design effect |
|---|---|---|---|
| Wolfspeed C3M0280090J, 900 V SiC MOSFET, D2PAK-7 | Rev. 04 Dec 2024, assets.wolfspeed.com, data/datasheets/Wolfspeed_C3M0280090J_Rev04_2024-12.pdf (sha256 35fa07e6809cea1a) | V(BR)DSS >= 900 V; RDS(on) 320 typ / 360 max mohm (VGS 15 V, 7.5 A, 25 C); ID 11 A (TC 25 C), 7 A (100 C), IDM 22 A; VGS op -4 / +15 V, max -8 / +19 V; Ciss 204, Coss 26, Crss 3 pF (VDS 600 V, 1 MHz); Eoss 5.5 uJ; Fig. 17: Coss about 110 pF at 25 V (READ from the curve) | candidate TX switch: about 290 pF less node capacitance in the decay tail than the IPB65R095C7 (rf2_switch.py: first gate 17.1 -> 14.0 us) |
| Infineon IPB65R095C7 (today's TX switch) | already logged; Diagram 14 read | Coss 33 pF at 400 V; Co(er) 69 pF, Co(tr) 763 pF (0-400 V); Diagram 14: Coss falls from about 8 nF below 20 V to about 60 pF at 50 V; about 400 pF at 26 V (READ) | its Coss cliff sits at the tail voltage (VBUS 26 V) |
| onsemi NTBG080N120SC1, 1200 V SiC, D2PAK-7L | onsemi data sheet, data/datasheets/onsemi_NTBG080N120SC1.pdf (sha256 fdf3611472b49ea3) | VDSS 1200 V; RDS(on) 80 typ / 110 max mohm (VGS 20 V, 20 A); "typ. Coss 79 pF" | alternative with more margin, higher Coss; not chosen |
| ADI AD7389-4, 4-channel simultaneous 16-bit SAR | owner upload, data/datasheets/ADI_AD7389-4.pdf (sha256 803bf7a379a68471) | 16 bit, quad simultaneous sampling, fully differential inputs, 2 MSPS; internal 2.5 V reference 10 ppm/C; SNR 90.5 dB typ (97.9 dB with OSR 8 and RES = 1); INL 2 LSB max; 3.0-3.6 V; 4 x 4 mm LFCSP-24; -40 to 125 C | full-waveform receiver: mono, QA, QB and REF3 sampled together every 0.5 us; gates and matched filters move into firmware |
| ADI AD4134, 4-channel 24-bit alias-free | owner upload, data/datasheets/ADI_AD4134_RevA.pdf (sha256 dc35f97c97dfc247) | 24 bit, 4 ch simultaneous, ODR 0.01-1496 kSPS; 108 dB dynamic range (374 kSPS, FIR); 137 dB (10 SPS, sinc3); low-latency sinc3 / sinc6 to 391.5 kHz; 4.5-5.5 V + 1.65-1.95 V; 8 x 8 mm LFCSP-56 | alternative; its digital filters spread a decay in time, so the SAR suits time-gated decay capture better |
| TI LMH6629 | already on disk, data/datasheets/TI_LMH6629_SNOSB18I_2014-12.pdf | en 0.69 nV/rtHz, in 2.6 pA/rtHz | mono preamp (MP1 v2), unchanged |
| OPSCO SK9822-EC20 construction | already on disk, OPSCO Rev A0 | "2.0x2.0x0.65mm PCB holder package" | foil on a PCB, not a stamped lead frame: display echo 5e-6 x noise (rf2_zones) |
