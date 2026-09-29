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
output_directory="$repository_root/artifacts/benchmarks"
output_file="$output_directory/mindgraph-baseline.json"
log_file="$output_directory/mindgraph-baseline.log"
benchmark_vertices="${MINDGRAPH_BENCHMARK_VERTICES:-100000}"
benchmark_edges="${MINDGRAPH_BENCHMARK_EDGES:-400000}"
lookup_warmup="${MINDGRAPH_BENCHMARK_LOOKUP_WARMUP:-2000}"
lookup_iterations="${MINDGRAPH_BENCHMARK_LOOKUP_ITERATIONS:-20000}"
traversal_warmup="${MINDGRAPH_BENCHMARK_TRAVERSAL_WARMUP:-1000}"
traversal_iterations="${MINDGRAPH_BENCHMARK_TRAVERSAL_ITERATIONS:-10000}"

mkdir -p "$output_directory"
rm -f "$output_file" "$log_file"

(
    cd "$repository_root"
    ./mvnw -B -ntp -pl engine \
        -Dtest=MindGraphBaselineBenchmark \
        -Dgroups=benchmark \
        -DexcludedGroups= \
        -Dmindgraph.benchmark.output="$output_file" \
        -Dmindgraph.benchmark.vertices="$benchmark_vertices" \
        -Dmindgraph.benchmark.edges="$benchmark_edges" \
        -Dmindgraph.benchmark.lookupWarmup="$lookup_warmup" \
        -Dmindgraph.benchmark.lookupIterations="$lookup_iterations" \
        -Dmindgraph.benchmark.traversalWarmup="$traversal_warmup" \
        -Dmindgraph.benchmark.traversalIterations="$traversal_iterations" \
        test
) 2>&1 | tee "$log_file"

test -s "$output_file" || {
    echo "benchmark did not produce $output_file" >&2
    exit 1
}

echo "benchmark result: $output_file"
echo "benchmark log: $log_file"
