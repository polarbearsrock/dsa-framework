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
  `supportBuffet` fields the current generator requires).
- a DSE overlay produced from `dsa-apps/compiled/Regress/dfgs.list`:

      cd dsa-apps/compiled/Regress
      taskset -c 0-31 ss_sched dfgs.list ../../adg/Mesh7x5-Full64-Full7I5O.json -x -f -m 200 --dse-timeout=300 -e 1
      cp viz/prunned-schedadg.json ../../../chipyard/generators/dsagen2/adg/dse/<tag>.json

`validate-adg.py <reference-hw.json> <adg.json>` and `check-link-order.py <adg.json>`
can be run on their own; they encode every hardware rule learned so far.
