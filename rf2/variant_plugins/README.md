# Variant plugins (multi-agent extension point for rf2/rf2_variants.py)

One file per domain, owned by one agent: `rf2/variant_plugins/<name>.py`. The engine loads every module here that defines `AXES` and `evaluate`.

```python
AXES = [dict(name="<axis>", help="...", options=[dict(id="...", desc="...", source="<study json / datasheet in DATASHEET_LOG / ASSUMED + reason>", today=True, p={...}), ...])]
def prepare(ctx): ...           # optional, once: load study JSONs, build caches (store under ctx.<name>)
def evaluate(ctx, P, m): ...    # per combination, fast (cache!): P = merged option params of every axis; m = metrics dict
```
- `m["_e"]`: the electrical model output for this combination (I_scan, I_boost, L_uH, R_coil, fall_us, W_TX_mm, Tj_switch_boost_C, E_pulse_mJ, ...).
- Adjust: `m["first_gate_us"]`, `m["depth_cm"][target]`, `m["runtime_boost_h"]`, `m["runtime_scan_h"]`, `m["P_boost_W"]`, `m["mass_delta_g"]`, `m["added_parts"]`.
- Rules: `m["rules"].append(dict(rule=..., value=..., limit=..., sense="<=" or ">=", where="<location>", kind="safety" or "target"))` (ok is recomputed).
- Extra metrics: `m["extra"]["<key>"] = value`.
- Exactly one option per axis has `today=True`; with today's options the plugin must leave m unchanged (today's machine stays the 1.0 reference).
- Test: `python3 rf2/rf2_variants.py --plugin-test <name>`; full run: `python3 rf2/rf2_variants.py`.
- Rules of the repo apply (CLAUDE.md): no fabricated datasheet values (cite data/datasheets + DATASHEET_LOG, or mark ASSUMED/UNVERIFIED); safety rules are reported, never relaxed; nothing is excluded.
