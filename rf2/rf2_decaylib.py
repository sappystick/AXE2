#!/usr/bin/env python3
"""AXE2 decay-curve library v0 (SIMULATED seed) and a baseline classifier. The library format is the one bench and field recordings will use
(docs/DECAY_LIBRARY.md); v0 entries are generated from models, flagged source = "simulated", and are NOT evidence of field performance.
Receiver as qualified: full-waveform sampling every 0.5 us (AD7389-4, 2 MSPS) from the first gate 13.5 us (SiC switch + syntactic potting,
rf2_switch) for 500 us; mono noise 1.54 nV/rtHz (BAT15 clamp, rf2_qualify) over the 1 MHz sample bandwidth, 100 pulses averaged.
Physical classes (a PI decay sees conductivity x size^2, so 'gold' and 'aluminium' of a matching time constant are the SAME class by physics):
  compact_nonferrous  spheres of Au (4.1e7 S/m), Ag (6.3e7), Cu (5.96e7), Al (3.77e7), Pb (4.8e6), 0.1-30 g: multi-mode sphere decay (rf2_coil_search.vt)
  ring_foil           a single closed loop: one exponential, tau 3-300 us
  ferrous             steel sphere: eddy decay with tau scaled by mu_r 50-200 plus a 1/t viscous tail (ASSUMED model, to be replaced by bench data)
  ground_viscous      magnetic viscosity: V ~ 1/t (log-uniform relaxation), amplitude 10-3000 x noise at the first gate
  ground_conductive   wet / salt ground: exponential tau 2-8 us + weak 1/t (ASSUMED)
Every target sits 30-500 mm under the head centre, coupling from the option-B coil (Bz^2 x I), so amplitude follows depth; half of the target
entries also carry a viscous-ground background (unbalanced). Features: 12 geometric gate means over the 13.5-513 us record (ratio 1.354), normalised (shape), their log
ratios, and the log amplitude. Ground balance: the 1/t shape is projected out of each record (as the detector's ground balance does) and both raw and balanced
features are used. Classifier: softmax regression (numpy), 70 / 30 split; accuracy overall and by SNR.
usage: python3 rf2/rf2_decaylib.py -> data/decaylib/sim_v0_index.json, data/decaylib/sim_v0_samples.npz (40 example waveforms), rf2/results/rf2_decaylib.json"""
import os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "head"))
import rf2_zones as Z, rf2_coil_search as C
OUT = os.path.join(HERE, "results"); LIB = os.path.join(ROOT, "data", "decaylib"); mu0 = C.mu0; rng = np.random.default_rng(20261030)
T0, DT, NS = 13.5e-6, 0.5e-6, 1000; t = T0 + DT * np.arange(NS); SIGMA = 1.54e-9 * math.sqrt(1e6) / math.sqrt(100)
GATES = list(T0 * ((T0 + DT * NS) / T0) ** (np.arange(13) / 12)); RHO = dict(Au=19300, Ag=10490, Cu=8960, Al=2700, Pb=11340); SIG = dict(Au=4.1e7, Ag=6.3e7, Cu=5.96e7, Al=3.77e7, Pb=4.8e6)
CLASSES = ["compact_nonferrous", "ring_foil", "ferrous", "ground_viscous", "ground_conductive"]
def coupling(depth_m): return Z.I0 * float(Z.Bc((0, 0, -depth_m * 1e3))[0][2]) ** 2
def sphere(a, sigma, K, mur=1.0):
    tau = mu0 * mur * sigma * a ** 2 / math.pi ** 2; n = np.arange(1, 40)[:, None]; return K / tau * np.sum(np.exp(-(n ** 2) * t[None, :] / tau), axis=0), tau
def make(cls):
    meta = dict(cls=cls)
    if cls.startswith("ground"):
        A = SIGMA * 10 ** rng.uniform(1, 3.5)
        if cls == "ground_viscous": v = A * T0 / t; meta.update(amp_x_noise=round(A / SIGMA, 1))
        else: tau = rng.uniform(2e-6, 8e-6); v = A * np.exp(-(t - T0) / tau) + 0.05 * A * T0 / t; meta.update(tau_us=round(tau * 1e6, 2), amp_x_noise=round(A / SIGMA, 1))
        return v, meta
    d = rng.uniform(0.03, 0.5); c = coupling(d); meta.update(depth_mm=round(d * 1e3))
    if cls == "compact_nonferrous":
        m = rng.choice(list(SIG)); g = 10 ** rng.uniform(-1, math.log10(30)); a = (3 * g * 1e-3 / (4 * math.pi * RHO[m])) ** (1 / 3)
        K = (2 * math.pi * a ** 3 / mu0) * (6 / math.pi ** 2) * c; v, tau = sphere(a, SIG[m], K); meta.update(metal=m, mass_g=round(g, 3), tau_us=round(tau * 1e6, 2))
    elif cls == "ring_foil":
        tau = 10 ** rng.uniform(math.log10(3e-6), math.log10(300e-6)); a = 10 ** rng.uniform(-2.3, -1.7); K = (2 * math.pi * a ** 3 / mu0) * c
        v = K / tau * np.exp(-t / tau); meta.update(tau_us=round(tau * 1e6, 2), size_mm=round(a * 1e3, 1))
    else:
        g = 10 ** rng.uniform(0, 2); a = (3 * g * 1e-3 / (4 * math.pi * 7850)) ** (1 / 3); mur = rng.uniform(50, 200); K = (2 * math.pi * a ** 3 / mu0) * (6 / math.pi ** 2) * c
        v, tau = sphere(a, 6e6, K, mur); v = v + 0.2 * v[0] * T0 / t; meta.update(mass_g=round(g, 2), mu_r=round(mur), tau_us=round(tau * 1e6, 1))
    if rng.random() < 0.5:
        A = SIGMA * 10 ** rng.uniform(0.5, 2.5); v = v + A * T0 / t; meta["ground_bg_x_noise"] = round(A / SIGMA, 1)
    return v, meta
GB = T0 / t                                                                                   # viscous-ground shape (1/t) used for ground balance
def gate_feats(w):
    g = np.array([w[(t >= GATES[k]) & (t < GATES[k + 1])].mean() for k in range(12)]); amp = np.linalg.norm(g) + 1e-30
    shape = g / amp; lr = np.log(np.abs(g[1:]) + 1e-3 * amp) - np.log(np.abs(g[:-1]) + 1e-3 * amp)
    return np.r_[shape, lr, math.log10(amp / SIGMA)]
def features(w):
    """raw features + ground-balanced features (the 1/t ground shape projected out, as the detector's ground balance does) + the removed amount"""
    a = float(w @ GB / (GB @ GB)); r = w - a * GB
    return np.r_[gate_feats(w), gate_feats(r), math.copysign(math.log10(1 + abs(a) / SIGMA), a)]
if __name__ == "__main__":
    os.makedirs(LIB, exist_ok=True); N = 600; X, y, idx, keep = [], [], [], {}
    for ci, cls in enumerate(CLASSES):
        for k in range(N):
            v, meta = make(cls); w = v + rng.normal(0, SIGMA, NS); snr = float(np.max(np.abs(np.convolve(v, np.ones(20) / 20, "same"))) / (SIGMA / math.sqrt(20)))
            if cls not in ("ground_viscous", "ground_conductive") and snr < 3: continue           # undetectable entries are not useful to train on
            meta.update(id=f"sim0-{cls}-{k:04d}", source="simulated", snr_20sample=round(snr, 1)); X.append(features(w)); y.append(ci); idx.append(meta)
            if keep.get(cls, 0) < 8: keep[cls] = keep.get(cls, 0) + 1; np.savez_compressed if False else None; keep.setdefault("_w", []).append((meta["id"], w.astype(np.float32)))
    X = np.array(X); y = np.array(y); mu, sd = X.mean(0), X.std(0) + 1e-9; Xn = (X - mu) / sd
    p = rng.permutation(len(y)); ntr = int(0.7 * len(y)); tr, te = p[:ntr], p[ntr:]; W = np.zeros((Xn.shape[1], len(CLASSES))); b = np.zeros(len(CLASSES))
    Y = np.eye(len(CLASSES))[y]
    for it in range(3000):
        z = Xn[tr] @ W + b; z -= z.max(1, keepdims=True); P = np.exp(z); P /= P.sum(1, keepdims=True); G = (P - Y[tr]) / len(tr)
        W -= 0.5 * (Xn[tr].T @ G + 1e-3 * W); b -= 0.5 * G.sum(0)
    pred = np.argmax(Xn[te] @ W + b, 1); acc = float(np.mean(pred == y[te])); cm = np.zeros((len(CLASSES),) * 2, int)
    for a_, b_ in zip(y[te], pred): cm[a_, b_] += 1
    snr = np.array([idx[i]["snr_20sample"] if "snr_20sample" in idx[i] else 0 for i in te]); by = {}
    for lo, hi in ((3, 10), (10, 100), (100, 1e9)):
        m = (snr >= lo) & (snr < hi) & (y[te] < 3)
        if m.any(): by[f"targets, SNR {lo}-{hi:g}"] = round(float(np.mean(pred[m] == y[te][m])), 3)
    res = dict(status="SIMULATED library v0 + baseline softmax classifier; NOT field performance", entries=len(y), per_class={c: int(np.sum(y == i)) for i, c in enumerate(CLASSES)},
               test_accuracy=round(acc, 3), accuracy_by_snr=by, confusion_rows_true_cols_pred={CLASSES[i]: dict(zip(CLASSES, map(int, cm[i]))) for i in range(len(CLASSES))},
               receiver=dict(first_sample_us=13.5, dt_us=0.5, samples=NS, sigma_per_sample_uV=round(SIGMA * 1e6, 4)))
    json.dump(dict(schema="docs/DECAY_LIBRARY.md", version="sim_v0", entries=idx), open(os.path.join(LIB, "sim_v0_index.json"), "w"), indent=0)
    np.savez_compressed(os.path.join(LIB, "sim_v0_samples.npz"), t_us=(t * 1e6).astype(np.float32), **{i: w for i, w in keep["_w"]})
    json.dump(res, open(os.path.join(OUT, "rf2_decaylib.json"), "w"), indent=1); print(json.dumps(res, indent=1))
