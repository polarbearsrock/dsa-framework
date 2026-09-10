#!/bin/bash
# usage: rtl-regress.sh <adg.json> [tag]
# Gate, build, compile and run the frozen regression set (vecadd matadd mv acc solver) on Verilator.
set -o pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd); HERE=$ROOT/scripts/regress
ADG=$(readlink -f "$1"); TAG=${2:-$(basename "$ADG" .json)}
OUT=${TMPDIR:-/tmp}/dsa-regress/$TAG; mkdir -p "$OUT"
# The conda and framework environment scripts reference unset variables, so source them before enabling -u.
source /etc/profile.d/conda.sh 2>/dev/null; source "$ROOT/setup.sh" >/dev/null 2>&1
set -u
export MAKEFLAGS=-j32; TS="taskset -c 0-31"
TESTS="vecadd matadd mv acc"; DSP="solver"
CY=$ROOT/chipyard; HW=$CY/generators/dsagen2/adg/$(basename "$ADG" .json)-hw.json
log() { echo "[$(date '+%H:%M:%S')] $*"; }
declare -A RES
# ---- 1. gate ----
log "gate: connection order"; python3 "$HERE/check-link-order.py" "$ADG" | tail -1 || exit 2
log "gate: hardware rules"; python3 "$HERE/validate-adg.py" "$HERE/reference-hw.json" "$ADG" | tail -1 || exit 2
log "gate: schedulability"
# The annealer is randomised and the compiler gives it 1024 iterations per DFG,
# so mirror that budget but allow a few seeds before declaring a DFG unschedulable.
sched_one() {  # <dir> <dfg>
  for seed in 1 2 3; do
    ( cd "$ROOT/dsa-apps/compiled/$1" && COUNT=1 $TS ss_sched --verbose --max-iters=1024 -b "$ADG" "$2" -e $seed > "$OUT/sched-$(basename "$2" .dfg).log" 2>&1 ) && return 0
  done
  return 1
}
for k in $TESTS; do sched_one Tests dfgs/$k/$(ls "$ROOT/dsa-apps/compiled/Tests/dfgs/$k" | head -1) || { log "  $k: not schedulable"; exit 2; }; done
sched_one Dsp dfgs/solver/solver_0_4_1.dfg || { log "  solver: not schedulable"; exit 2; }
# ---- 2. build ----
log "build: Verilator model for $(basename "$ADG")"
rm -rf "$CY/sims/verilator/generated-src/chipyard.TestHarness.DSAGenRocketConfig"
( cd "$CY" && $TS make -C sims/verilator CONFIG=DSAGenRocketConfig ADG="$ADG" ) > "$OUT/build.log" 2>&1 || { log "build failed, see $OUT/build.log"; exit 3; }
[ -f "$HW" ] || { log "print-back $HW missing"; exit 3; }
# ---- 3. compile ----
compile_one() {  # <dir> <kernel>   (same seed retry as the gate: SEED reaches ss_sched through the DSA pass)
  for seed in 1 2 3; do
    ( cd "$ROOT/dsa-apps/compiled/$1" && rm -f ss-$2.riscv ss-$2.o ss-$2.s ss-$2.ll $2.ll ${2}_*.dfg.bits.h ${2}_*.dfg.h &&
      SEED=$seed $TS make GEM5=0 BITSTREAM=1 COMPAT_ADG=0 COUNT=1 TEMPORAL_FALLBACK=1 SBCONFIG="$HW" ss-$2.riscv ) > "$OUT/compile-$2.log" 2>&1 && return 0
  done
  return 1
}
for k in $TESTS; do log "compile: $k"; compile_one Tests $k || { RES[$k]=COMPILE-FAIL; }; done
for k in $DSP; do log "compile: $k"; compile_one Dsp $k || { RES[$k]=COMPILE-FAIL; }; done
# ---- 4. run (in parallel, 30-minute cap each) ----
run_one() {  # <dir> <kernel>
  local bin=$ROOT/dsa-apps/compiled/$1/ss-$2.riscv
  ( cd "$CY" && timeout 1800 $TS make -C sims/verilator CONFIG=DSAGenRocketConfig ADG="$ADG" timeout_cycles=100000000 BINARY="$bin" run-binary-fast 2>&1 \
    | grep -vE "^\[UART|^make|^cd |^mkdir|^\(set -o|^$" ) > "$OUT/run-$2.log" 2>&1
}
pids=(); for k in $TESTS; do [ "${RES[$k]:-}" = COMPILE-FAIL ] || { log "run: $k"; run_one Tests $k & pids+=($!); }; done
for k in $DSP; do [ "${RES[$k]:-}" = COMPILE-FAIL ] || { log "run: $k"; run_one Dsp $k & pids+=($!); }; done
wait "${pids[@]}" 2>/dev/null
# ---- 5. verdicts ----
for k in $TESTS $DSP; do
  [ "${RES[$k]:-}" = COMPILE-FAIL ] && continue
  f="$OUT/run-$k.log"
  if grep -q "sanity check passed" "$f"; then RES[$k]=PASS
  elif grep -qE "Mismatch|did not pass|\*\*\* FAILED \*\*\* \(code" "$f"; then RES[$k]=FAIL
  elif grep -q "trace_count" "$f"; then RES[$k]=HANG
  else RES[$k]=HANG; fi
done
echo; echo "regression: $(basename "$ADG")  (logs: $OUT)"; rc=0
for k in $TESTS $DSP; do
  cyc=$(grep -oE "accelerator finished|csv, [0-9]+, [0-9]+, [0-9]+" "$OUT/run-$k.log" 2>/dev/null | tail -1 | sed -E 's/csv, [0-9]+, [0-9]+, //; s/accelerator finished//')
  printf "  %-8s %-13s %s\n" "$k" "${RES[$k]}" "${cyc:+${cyc} accel cycles}"; [ "${RES[$k]}" = PASS ] || rc=1
done
exit $rc
