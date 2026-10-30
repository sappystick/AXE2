#!/usr/bin/env python3
"""RF1 phase 3 check (2026-10-29): DC operating points and ranges of the AB1 receive channel, baseline (AD7389-4 build) vs RF1, against the data-sheet limits
already in the repo. MODELED (ideal resistors, typical gain); every limit is cited.
  OPA2211 on a single 5 V supply (TI SBOS377L): input common mode (V-) + 2.0 .. (V+) - 1.4 V for VS < +-5 V; output (V-) + 0.2 .. (V+) - 0.2 V at RL 10 k,
     (V-) + 0.6 .. (V+) - 0.6 V at RL 600 ohm; GBW 80 MHz at G = 100; voltage noise 1.1 nV/rtHz at 1 kHz
  AD7389-4 (Rev. 0, DATASHEET_LOG U-DS-AD7389): differential range +-VREF, VREF 2.5 V; absolute input -0.1 .. VREF + 0.1 V; common mode 0.2 .. VREF - 0.2 V;
     LSB 2 VREF / 2^16 = 76.29 uV; track capacitance 18 pF
  Channel: RS (100 ohm GX / GY, 1 k others; ASSUMPTIONS 3), gain 1 + RF / RG, anti-alias RC into the ADC.
usage: python3 experiments/RF1_rigidflex/rf1_frontend_check.py"""
import os, json, math
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
VS, VREF, kT4 = 5.0, 2.5, 4 * 1.380649e-23 * 300
OPA = dict(cm_lo=2.0, cm_hi=VS - 1.4, out_lo_10k=0.2, out_hi_10k=VS - 0.2, out_lo_600=0.6, out_hi_600=VS - 0.6, gbw=80e6, en=1.1e-9)
ADC = dict(abs_lo=-0.1, abs_hi=VREF + 0.1, cm_lo=0.2, cm_hi=VREF - 0.2, diff=VREF, lsb=2 * VREF / 2 ** 16, ctrack=18e-12)

def channel(name, vref_amp, rf, rg, ra, rb, c, adc_minus, div_minus):
    g = 1 + rf / rg; gdiv = rb / (ra + rb) if rb else 1.0; gt = g * gdiv
    vin_cm = vref_amp                                                           # coil and RG return at the amplifier reference
    vout_dc = vref_amp
    # output swing limit (load: divider ra + rb to GND, or the ADC input through ra)
    load = (ra + rb) if rb else 1e6
    lo, hi = (OPA["out_lo_600"], OPA["out_hi_600"]) if load <= 2000 else (OPA["out_lo_10k"], OPA["out_hi_10k"])
    swing = min(vout_dc - lo, hi - vout_dc)                                     # symmetric usable output swing
    ain_p_dc = vout_dc * gdiv; ain_m_dc = adc_minus * (div_minus if div_minus else 1.0)
    d_max = swing * gdiv; ain_p_lo, ain_p_hi = ain_p_dc - d_max, ain_p_dc + d_max
    cm = 0.5 * (ain_p_dc + ain_m_dc)
    rth = (ra * rb / (ra + rb)) if rb else ra; fc = 1 / (2 * math.pi * rth * c)
    # input-referred noise of the divider resistors (both legs, thermal), 1 Hz, against the OPA2211
    en_div = math.sqrt(kT4 * rth * (2 if div_minus else 1)) / gt
    bw = OPA["gbw"] / g
    checks = dict(
        opa_input_in_range=OPA["cm_lo"] <= vin_cm <= OPA["cm_hi"],
        adc_cm_in_range=ADC["cm_lo"] <= cm <= ADC["cm_hi"],
        adc_abs_in_range=ADC["abs_lo"] <= ain_p_lo and ain_p_hi <= ADC["abs_hi"],
        adc_offset_mV=round((ain_p_dc - ain_m_dc) * 1e3, 3),
        c_over_ctrack=round(c / ADC["ctrack"], 1), closed_loop_bw_MHz=round(bw / 1e6, 2), fc_kHz=round(fc / 1e3, 1))
    ok = checks["opa_input_in_range"] and checks["adc_cm_in_range"] and checks["adc_abs_in_range"] and bw > 2 * fc and c > 20 * ADC["ctrack"]
    return dict(name=name, gain_stage=round(g, 1), gain_total=round(gt, 2), opa_input_dc_V=vin_cm, opa_input_range_V=[OPA["cm_lo"], OPA["cm_hi"]],
                opa_out_dc_V=vout_dc, usable_out_swing_V=round(swing, 2), ain_plus_dc_V=round(ain_p_dc, 3), ain_minus_dc_V=round(ain_m_dc, 3), adc_cm_V=round(cm, 3),
                adc_diff_full_scale_used_pct=round(100 * d_max / ADC["diff"], 1), divider_noise_input_nV=round(en_div * 1e9, 3), opa_noise_nV=OPA["en"] * 1e9,
                checks=checks, ok=ok)

if __name__ == "__main__":
    base = channel("baseline AD7389-4 build (VCM 1.25 V reference)", vref_amp=VREF / 2, rf=390, rg=10, ra=200, rb=0, c=2.2e-9, adc_minus=VREF / 2, div_minus=None)
    rf1 = channel("RF1 (VBIAS 2.5 V, matched 1 k / 1 k dividers on AIN+ and AIN-)", vref_amp=VREF, rf=820, rg=10, ra=1000, rb=1000, c=1e-9, adc_minus=VREF, div_minus=0.5)
    out = dict(status="MODELED: DC operating points against data-sheet limits", baseline=base, rf1=rf1)
    json.dump(out, open(os.path.join(OUT, "rf1_frontend_check.json"), "w"), indent=1)
    for r in (base, rf1): print(r["name"], "| ok", r["ok"], "| OPA in", r["opa_input_dc_V"], "range", r["opa_input_range_V"], "| ADC cm", r["adc_cm_V"], "| gain", r["gain_total"], "|", r["checks"])
