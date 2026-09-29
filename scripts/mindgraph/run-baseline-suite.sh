#!/usr/bin/env bash
#
# Copyright © 2026 Mindwalker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# SPDX-License-Identifier: Apache-2.0
#

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
benchmark_script="$repository_root/scripts/mindgraph/run-baseline-benchmark.sh"
summary_script="$repository_root/scripts/mindgraph/summarize-baseline-benchmark.sh"
measured_runs="${MINDGRAPH_BENCHMARK_RUNS:-5}"
warmup_runs="${MINDGRAPH_BENCHMARK_WARMUP_RUNS:-1}"
suite_id="$(date -u +%Y%m%dT%H%M%SZ)"
suite_directory="${MINDGRAPH_BENCHMARK_SUITE_DIR:-$repository_root/artifacts/benchmarks/suite-$suite_id}"
runs_directory="$suite_directory/runs"

case "$measured_runs:$warmup_runs" in
    *[!0-9:]* | :* | *:) echo "run counts must be non-negative integers" >&2; exit 1 ;;
esac
test "$measured_runs" -ge 3 || {
    echo "MINDGRAPH_BENCHMARK_RUNS must be at least 3" >&2
    exit 1
}

mkdir -p "$runs_directory" "$suite_directory/warmups"

run=1
while test "$run" -le "$warmup_runs"; do
    echo "warming benchmark cache ($run/$warmup_runs)"
    "$benchmark_script" > "$suite_directory/warmups/warmup-$run.log" 2>&1
    run=$((run + 1))
done

run=1
while test "$run" -le "$measured_runs"; do
    run_directory="$runs_directory/run-$run"
    mkdir -p "$run_directory"
    date -u +%Y-%m-%dT%H:%M:%SZ > "$run_directory/started-at.txt"

    if /usr/bin/time -v true >/dev/null 2>&1; then
        /usr/bin/time -v -o "$run_directory/resource.txt" \
            "$benchmark_script" > "$run_directory/console.log" 2>&1
    else
        "$benchmark_script" > "$run_directory/console.log" 2>&1
    fi

    cp "$repository_root/artifacts/benchmarks/mindgraph-baseline.json" "$run_directory/result.json"
    cp "$repository_root/artifacts/benchmarks/mindgraph-baseline.log" "$run_directory/maven.log"
    echo "completed measured run $run/$measured_runs"
    run=$((run + 1))
done

"$summary_script" "$runs_directory" "$suite_directory/summary.json"
cp "$suite_directory/summary.json" "$repository_root/artifacts/benchmarks/mindgraph-baseline-summary.json"

echo "benchmark suite: $suite_directory"
