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
runs_directory="${1:-$repository_root/artifacts/benchmarks/standard-runs}"
output_file="${2:-$repository_root/artifacts/benchmarks/mindgraph-baseline-summary.json}"

command -v jq >/dev/null 2>&1 || {
    echo "jq is required to summarize benchmark results" >&2
    exit 1
}

result_files=()
for result_file in "$runs_directory"/*/result.json; do
    test -f "$result_file" && result_files+=("$result_file")
done
test "${#result_files[@]}" -ge 3 || {
    echo "expected at least 3 measured runs in $runs_directory" >&2
    exit 1
}

jq -e -s '
  def stable_environment:
    {
      javaVersion,
      javaVendor,
      osName,
      osVersion,
      architecture,
      availableProcessors,
      maxHeapBytes
    };
  .[0] as $baseline
  | all(.[1:][];
      .dataset == $baseline.dataset
      and .measurement == $baseline.measurement
      and (.environment | stable_environment) == ($baseline.environment | stable_environment)
    )
' "${result_files[@]}" >/dev/null || {
    echo "benchmark runs do not share the same dataset, measurement, and stable environment" >&2
    exit 1
}

mkdir -p "$(dirname "$output_file")"

jq -s '
  def stats:
    sort as $values
    | length as $count
    | (add / $count) as $mean
    | ((map((. - $mean) * (. - $mean)) | add / $count) | sqrt) as $standardDeviation
    | {
        min: $values[0],
        median: (
          if ($count % 2) == 1 then
            $values[($count / 2 | floor)]
          else
            (($values[$count / 2 - 1] + $values[$count / 2]) / 2)
          end
        ),
        max: $values[-1],
        mean: $mean,
        standardDeviation: $standardDeviation,
        coefficientOfVariationPercent: (
          if $mean == 0 then 0 else ($standardDeviation / $mean * 100) end
        )
      };

  {
    schemaVersion: 1,
    benchmark: "mindgraph-baseline-suite",
    measuredRuns: length,
    dataset: .[0].dataset,
    measurement: .[0].measurement,
    environment: {
      javaVersion: .[0].environment.javaVersion,
      javaVendor: .[0].environment.javaVendor,
      osName: .[0].environment.osName,
      osVersion: .[0].environment.osVersion,
      architecture: .[0].environment.architecture,
      availableProcessors: .[0].environment.availableProcessors,
      maxHeapBytes: .[0].environment.maxHeapBytes
    },
    metrics: {
      loadSeconds: ([.[].storage.loadSeconds] | stats),
      recordsPerSecond: ([.[].storage.recordsPerSecond] | stats),
      reopenMillis: ([.[].storage.reopenMillis] | stats),
      databaseBytes: ([.[].storage.databaseBytes] | stats),
      indexedLookupThroughputOpsPerSecond: ([.[].indexedLookup.throughputOpsPerSecond] | stats),
      indexedLookupP50Millis: ([.[].indexedLookup.p50Millis] | stats),
      indexedLookupP95Millis: ([.[].indexedLookup.p95Millis] | stats),
      indexedLookupP99Millis: ([.[].indexedLookup.p99Millis] | stats),
      oneHopTraversalThroughputOpsPerSecond: ([.[].oneHopTraversal.throughputOpsPerSecond] | stats),
      oneHopTraversalP50Millis: ([.[].oneHopTraversal.p50Millis] | stats),
      oneHopTraversalP95Millis: ([.[].oneHopTraversal.p95Millis] | stats),
      oneHopTraversalP99Millis: ([.[].oneHopTraversal.p99Millis] | stats),
      usedHeapBytes: ([.[].environment.usedHeapBytes] | stats)
    }
  }
' "${result_files[@]}" > "$output_file"

echo "benchmark summary: $output_file"
