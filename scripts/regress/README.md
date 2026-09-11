# RTL regression set

Frozen set: `vecadd`, `matadd`, `mv`, `acc` (dsa-apps/compiled/Tests) and `solver`
(dsa-apps/compiled/Dsp), each with a data check against a CPU reference.

    scripts/regress/rtl-regress.sh <adg.json> [tag]

gates the ADG (dsagen2 connection order, hardware rules, schedulability of all
five DFGs), builds the Verilator model for it, compiles the kernels against the
hardware print-back the generator writes next to `chipyard/generators/dsagen2/adg/`,
runs them (30-minute cap each, all cores pinned to 0-31) and prints a PASS/FAIL/HANG
table. Logs go to `$TMPDIR/dsa-regress/<tag>/`. Exit status is non-zero on any failure.

Reference configurations:

- `seed-mesh.json`: the 7x5 seed mesh (`Mesh7x5-Full64-Full7I5O` plus the
  `supportBuffet` fields the current generator requires) with 512-byte vector
  ports. The compiler's recurrence streams (OVP -> recurrence engine -> IVP) need a
  port to hold the whole recurrence distance: 256 B for fir, 1 KB for mm at the
  default unroll, so 128-byte ports deadlock mm (dsagen2 `MAX_VP_BYTE` is 1024).
- `dse-overlay.json`: a DSE-pruned overlay explored from the same five kernels
  (9 PEs, 27 switches, all memory engines, stated output ports). Regenerate one
  from `dsa-apps/compiled/Regress/dfgs.list` when the DSE changes (different seeds
  give overlays of different tightness; keep one where all five DFGs pass the
  gate). The DSE seed with 512-byte ports is `scripts/regress/dse-seed.json` (copy it to `chipyard/generators/dsagen2/adg/`, which git ignores):

      cd dsa-apps/compiled/Regress
      taskset -c 0-31 ss_sched dfgs.list ../../adg/Mesh7x5-Full64-Full7I5O-d512.json -x -f -m 200 --dse-timeout=300 -e 3
      cp viz/prunned-schedadg.json ../../../chipyard/generators/dsagen2/adg/dse/<tag>.json

Reproducible builds: `rtl-regress.sh` exports `DSA_MAPPING_DIR=$TMPDIR/dsa-regress/<tag>/mappings`,
which makes `ss_sched` (through the DSA compiler pass) save each kernel's mapping as
`<dfg>.<adg>.<hash>.mapping.json` and reuse it on the next compile against the same
ADG, so two compiles yield identical bitstreams regardless of `SEED`. Set the same
variable by hand to pin a mapping outside the regression.

`validate-adg.py <reference-hw.json> <adg.json>` and `check-link-order.py <adg.json>`
can be run on their own; they encode every hardware rule learned so far.
