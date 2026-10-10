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
cd "$repository_root"
baseline_file="$repository_root/.mindgraph/baseline.properties"
harness_repository="https://github.com/ArcadeData/ldbc_graphalytics_platforms_arcadedb.git"
harness_commit="${MINDGRAPH_BENCHMARK_HARNESS_COMMIT:-02e1d824a2ff1bfc1574bbdda7cb9b3c2344bfff}"
run_id="${MINDGRAPH_BENCHMARK_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
run_root="${MINDGRAPH_INDUSTRY_RUN_DIR:-$repository_root/artifacts/industry-standard/$run_id}"
stages="${MINDGRAPH_BENCHMARK_STAGES:-setup,graphalytics,lsqb,olap,collect}"
force="${MINDGRAPH_BENCHMARK_FORCE:-0}"
heap_gib="${MINDGRAPH_BENCHMARK_HEAP_GIB:-12}"
graph_runs="${MINDGRAPH_GRAPH_RUNS:-5}"
lsqb_runs="${MINDGRAPH_LSQB_RUNS:-5}"
olap_vertices="${MINDGRAPH_OLAP_VERTICES:-500000}"
olap_edges_per_vertex="${MINDGRAPH_OLAP_EDGES_PER_VERTEX:-16}"

property() {
    local key="$1"
    sed -n "s/^${key}=//p" "$baseline_file" | head -n 1
}

mindgraph_version="$(property mindgraph.version)"
upstream_repository="$(property upstream.repository)"
upstream_commit="$(property upstream.baseCommit)"
maven_version="$(property upstream.mavenVersion)"
candidate_commit="$(git -C "$repository_root" rev-parse HEAD)"

case "$run_root" in
    / | "$HOME" | "$repository_root")
        echo "refusing unsafe benchmark run directory: $run_root" >&2
        exit 1
        ;;
esac

case "$heap_gib:$graph_runs:$lsqb_runs:$olap_vertices:$olap_edges_per_vertex" in
    *[!0-9:]* | :* | *:)
        echo "heap, run count, vertex count, and edge count must be positive integers" >&2
        exit 1
        ;;
esac
test "$heap_gib" -ge 4
test "$graph_runs" -ge 3
test "$lsqb_runs" -ge 3
test "$olap_vertices" -ge 1000
test "$olap_edges_per_vertex" -ge 1

has_stage() {
    case ",$stages," in
        *",$1,"*) return 0 ;;
        *) return 1 ;;
    esac
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "$1 is required" >&2
        exit 1
    }
}

for command_name in git java javac python3 sed awk; do
    require_command "$command_name"
done

mkdir -p "$run_root"/{sources,m2,harness,datasets,graphalytics,lsqb,olap,raw}
printf '%s\n' "$candidate_commit" > "$run_root/raw/mindgraph-commit.txt"
printf '%s\n' "$upstream_commit" > "$run_root/raw/upstream-commit.txt"
printf '%s\n' "$harness_commit" > "$run_root/raw/harness-commit.txt"

clone_at_commit() {
    local repository="$1"
    local commit="$2"
    local destination="$3"
    if test -d "$destination/.git"; then
        test "$(git -C "$destination" rev-parse HEAD)" = "$commit" || {
            echo "$destination exists at a different commit" >&2
            exit 1
        }
        return
    fi
    git clone --filter=blob:none --no-checkout "$repository" "$destination"
    git -C "$destination" fetch --depth 1 origin "$commit"
    git -C "$destination" checkout --detach "$commit"
}

install_engine() {
    local source="$1"
    local maven_repo="$2"
    local log="$3"
    if test -f "$maven_repo/com/arcadedb/arcadedb-engine/$maven_version/arcadedb-engine-$maven_version.jar" && test "$force" != 1; then
        return
    fi
    (
        cd "$source"
        ./mvnw -B -ntp -Dmaven.repo.local="$maven_repo" -DskipTests -pl engine -am install
    ) > "$log" 2>&1
}

prepare_harness() {
    local system_id="$1"
    local maven_repo="$2"
    local destination="$run_root/harness/$system_id"
    if test ! -d "$destination/.git"; then
        git clone --local "$run_root/sources/harness" "$destination"
        git -C "$destination" checkout --detach "$harness_commit"
    fi
    if test ! -f "$destination/target/graphalytics-platforms-arcadedb-0.1-SNAPSHOT-default.jar" || test "$force" = 1; then
        "$repository_root/mvnw" -B -ntp -f "$destination/pom.xml" \
            -Dmaven.repo.local="$maven_repo" \
            -Darcadedb.version="$maven_version" \
            -DskipTests package > "$run_root/raw/harness-$system_id-build.log" 2>&1
    fi
}

if has_stage setup; then
    clone_at_commit "$upstream_repository" "$upstream_commit" "$run_root/sources/upstream"
    clone_at_commit "$harness_repository" "$harness_commit" "$run_root/sources/harness"

    install_engine "$repository_root" "$run_root/m2/mindgraph" "$run_root/raw/mindgraph-engine-build.log"
    install_engine "$run_root/sources/upstream" "$run_root/m2/upstream" "$run_root/raw/upstream-engine-build.log"
    prepare_harness mindgraph "$run_root/m2/mindgraph"
    prepare_harness upstream "$run_root/m2/upstream"

    if test ! -x "$run_root/venv/bin/python"; then
        python3 -m venv "$run_root/venv"
        "$run_root/venv/bin/pip" install --disable-pip-version-check requests > "$run_root/raw/python-dependencies.log" 2>&1
    fi

    dataset_source="$run_root/sources/harness"
    if test ! -f "$dataset_source/datasets/datagen-7_5-fb/datagen-7_5-fb.e"; then
        (cd "$dataset_source" && "$run_root/venv/bin/python" datasets.py download datagen-7_5-fb) \
            > "$run_root/raw/graph-dataset-download.log" 2>&1
    fi
    if test ! -f "$dataset_source/datasets/social-network-sf1-merged-fk/Country.csv"; then
        (cd "$dataset_source" && "$run_root/venv/bin/python" datasets.py download lsqb-sf1 --format merged-fk) \
            > "$run_root/raw/lsqb-download.log" 2>&1
    fi
fi

run_graphalytics() {
    local system_id="$1"
    local harness="$run_root/harness/$system_id"
    local output="$run_root/graphalytics/$system_id"
    local runner_dir="$output/runner"
    if test -s "$output/run-$graph_runs.log" && test "$force" != 1; then
        return
    fi
    mkdir -p "$runner_dir"
    cp "$harness/ldbc-native/ArcadeDBEmbeddedBenchmark.java" "$runner_dir/"
    python3 - "$runner_dir/ArcadeDBEmbeddedBenchmark.java" \
        "$run_root/sources/harness/datasets/datagen-7_5-fb" \
        "$run_root/raw/$system_id-graph-database" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
dataset_path = sys.argv[2]
database_path = sys.argv[3]
text = source.read_text(encoding="utf-8")
text = text.replace(
    'static final String GRAPHS_DIR    = "../datasets/datagen-7_5-fb";',
    f'static final String GRAPHS_DIR    = "{dataset_path}";',
)
text = text.replace(
    'static final String DB_PATH       = "/tmp/arcadedb_benchmark";',
    f'static final String DB_PATH       = "{database_path}";',
)
validation_lines = {
    '    System.out.println("  PageRank time: " + prTime + "s");':
        '    System.out.println("  PageRank time: " + prTime + "s");\n    System.out.println("  VALIDATION PR: " + hashDoubles(pr));',
    '    System.out.println("  WCC time: " + wccTime + "s");':
        '    System.out.println("  WCC time: " + wccTime + "s");\n    System.out.println("  VALIDATION WCC: " + hashInts(wcc));',
    '    System.out.println("  BFS time: " + bfsTime + "s");':
        '    System.out.println("  BFS time: " + bfsTime + "s");\n    System.out.println("  VALIDATION BFS: " + hashInts(bfs));',
    '    System.out.println("  LCC time: " + lccTime + "s");':
        '    System.out.println("  LCC time: " + lccTime + "s");\n    System.out.println("  VALIDATION LCC: " + hashDoubles(lcc));',
    '    System.out.println("  SSSP time: " + ssspTime + "s");':
        '    System.out.println("  SSSP time: " + ssspTime + "s");\n    System.out.println("  VALIDATION SSSP: " + hashDoubles(sssp));',
    '    System.out.println("  CDLP time: " + cdlpTime + "s");':
        '    System.out.println("  CDLP time: " + cdlpTime + "s");\n    System.out.println("  VALIDATION CDLP: " + hashInts(cdlp));',
}
for original, replacement in validation_lines.items():
    if original not in text:
        raise SystemExit(f"benchmark source no longer contains expected line: {original}")
    text = text.replace(original, replacement)
marker = '  static int[] topK(double[] arr, int k) {'
helpers = '''  static long hashInts(int[] values) {
    long hash = 1125899906842597L;
    for (int value : values)
      hash = 31 * hash + value;
    return hash;
  }

  static long hashDoubles(double[] values) {
    long hash = 1125899906842597L;
    for (double value : values)
      hash = 31 * hash + Double.doubleToLongBits(value);
    return hash;
  }

'''
if marker not in text:
    raise SystemExit("benchmark source no longer contains topK marker")
text = text.replace(marker, helpers + marker)
source.write_text(text, encoding="utf-8")
PY
    local jar="$harness/target/graphalytics-platforms-arcadedb-0.1-SNAPSHOT-default.jar"
    (cd "$runner_dir" && javac --add-modules jdk.incubator.vector -cp "$jar" ArcadeDBEmbeddedBenchmark.java)
    if test ! -s "$output/warmup.log" || test "$force" = 1; then
        (
            cd "$runner_dir"
            java -Xms"${heap_gib}g" -Xmx"${heap_gib}g" --add-modules jdk.incubator.vector \
                -cp ".:$jar" ArcadeDBEmbeddedBenchmark
        ) > "$output/warmup.log" 2>&1
    fi
    local run=1
    while test "$run" -le "$graph_runs"; do
        if test ! -s "$output/run-$run.log" || test "$force" = 1; then
            (
                cd "$runner_dir"
                java -Xms"${heap_gib}g" -Xmx"${heap_gib}g" --add-modules jdk.incubator.vector \
                    -cp ".:$jar" ArcadeDBEmbeddedBenchmark
            ) > "$output/run-$run.log" 2>&1
        fi
        run=$((run + 1))
    done
}

if has_stage graphalytics; then
    run_graphalytics mindgraph
    run_graphalytics upstream
fi

run_lsqb() {
    local system_id="$1"
    local harness="$run_root/harness/$system_id"
    local output="$run_root/lsqb/$system_id"
    local runner_dir="$output/runner"
    if test -s "$output/run-$lsqb_runs.log" && test "$force" != 1; then
        return
    fi
    mkdir -p "$runner_dir"
    cp "$harness/lsqb/ArcadeDBEmbeddedLSQB.java" "$runner_dir/"
    python3 - "$runner_dir/ArcadeDBEmbeddedLSQB.java" "$run_root/raw/$system_id-lsqb-database" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
database_path = sys.argv[2]
text = source.read_text(encoding="utf-8")
text = text.replace('static final String DB_PATH  = "/tmp/arcadedb_lsqb";', f'static final String DB_PATH  = "{database_path}";')
source.write_text(text, encoding="utf-8")
PY
    local jar="$harness/target/graphalytics-platforms-arcadedb-0.1-SNAPSHOT-default.jar"
    (cd "$runner_dir" && javac -cp "$jar" ArcadeDBEmbeddedLSQB.java)
    local dataset="$run_root/sources/harness/datasets/social-network-sf1-merged-fk"
    if test ! -s "$output/warmup.log" || test "$force" = 1; then
        (
            cd "$runner_dir"
            java -Xms"${heap_gib}g" -Xmx"${heap_gib}g" --add-modules jdk.incubator.vector \
                -Ddataset.dir="$dataset" -cp ".:$jar" ArcadeDBEmbeddedLSQB --reset
        ) > "$output/warmup.log" 2>&1
    fi
    local run=1
    while test "$run" -le "$lsqb_runs"; do
        if test ! -s "$output/run-$run.log" || test "$force" = 1; then
            (
                cd "$runner_dir"
                java -Xms"${heap_gib}g" -Xmx"${heap_gib}g" --add-modules jdk.incubator.vector \
                    -Ddataset.dir="$dataset" -cp ".:$jar" ArcadeDBEmbeddedLSQB
            ) > "$output/run-$run.log" 2>&1
        fi
        run=$((run + 1))
    done
}

if has_stage lsqb; then
    run_lsqb mindgraph
    run_lsqb upstream
fi

run_olap() {
    local system_id="$1"
    local source="$2"
    local maven_repo="$3"
    local output="$run_root/olap/$system_id.log"
    if test -s "$output" && test "$force" != 1; then
        return
    fi
    (
        cd "$source"
        ./mvnw -B -ntp -Dmaven.repo.local="$maven_repo" -pl engine \
            -Dtest=performance.GraphOLAPBenchmark \
            -Dgroups=performance -DexcludedGroups= \
            -Darcadedb.olap.vertices="$olap_vertices" \
            -Darcadedb.olap.edgesPerVertex="$olap_edges_per_vertex" \
            test
    ) > "$output" 2>&1
}

if has_stage olap; then
    run_olap mindgraph "$repository_root" "$run_root/m2/mindgraph"
    run_olap upstream "$run_root/sources/upstream" "$run_root/m2/upstream"
fi

if has_stage collect; then
    evidence_dir="$run_root/evidence"
    mkdir -p "$evidence_dir"
    for system_id in mindgraph upstream; do
        cp "$run_root/graphalytics/$system_id/warmup.log" "$evidence_dir/graph-$system_id-warmup.txt"
        cp "$run_root/lsqb/$system_id/warmup.log" "$evidence_dir/lsqb-$system_id-warmup.txt"
        run=1
        while test "$run" -le "$graph_runs"; do
            cp "$run_root/graphalytics/$system_id/run-$run.log" "$evidence_dir/graph-$system_id-run-$run.txt"
            run=$((run + 1))
        done
        run=1
        while test "$run" -le "$lsqb_runs"; do
            cp "$run_root/lsqb/$system_id/run-$run.log" "$evidence_dir/lsqb-$system_id-run-$run.txt"
            run=$((run + 1))
        done
        cp "$run_root/olap/$system_id.log" "$evidence_dir/olap-$system_id.txt"
    done
    (
        cd "$run_root/sources/harness/datasets"
        find datagen-7_5-fb social-network-sf1-merged-fk -type f -print0 \
            | sort -z \
            | xargs -0 sha256sum
    ) > "$evidence_dir/dataset-sha256.txt"
    python3 - "$evidence_dir" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
files = []
for path in sorted(root.glob("*.txt")):
    digest = sha256(path.read_bytes()).hexdigest()
    files.append({"path": path.name, "bytes": path.stat().st_size, "sha256": digest})
(root / "manifest.json").write_text(
    json.dumps({"schemaVersion": 1, "files": files}, indent=2) + "\n",
    encoding="utf-8",
)
PY
    cpu_model="$(awk -F: '/model name/ {sub(/^[[:space:]]+/, "", $2); print $2; exit}' /proc/cpuinfo 2>/dev/null || true)"
    cpu_count="$(getconf _NPROCESSORS_ONLN)"
    memory_gib="$(awk '/MemTotal/ {printf "%.0f", $2 / 1024 / 1024}' /proc/meminfo)"
    os_name="$(. /etc/os-release && printf '%s' "$PRETTY_NAME")"
    java_version="$(java -version 2>&1 | head -n 1 | tr -d '"')"
    generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    python3 - "$run_root/metadata.json" <<PY
import json
import sys

metadata = {
    "title": "MindGraph reproducible graph benchmark",
    "subtitle": "MindGraph and its exact upstream control on one BytePlus host, with ArcadeDB's published numbers shown only as references.",
    "generatedAt": "$generated_at",
    "release": {
        "version": "$mindgraph_version",
        "commit": "$candidate_commit",
        "harnessCommit": "$harness_commit",
    },
    "environment": {
        "cpu": "$cpu_model",
        "cpuCount": int("$cpu_count"),
        "memoryGiB": int("$memory_gib"),
        "java": "$java_version",
        "os": "$os_name",
        "jvmHeapGiB": int("$heap_gib"),
    },
    "systems": [
        {"id": "mindgraph", "label": "MindGraph measured", "kind": "measured"},
        {"id": "upstream", "label": "ArcadeDB upstream control", "kind": "control"},
    ],
    "methodology": {
        "summary": [
            "MindGraph and the exact ArcadeDB upstream commit were built independently and executed sequentially on the same idle host.",
            "The graph algorithm comparison uses the harness native load-once mode on datagen-7_5-fb; LSQB uses SF1 merged-FK; OLAP speedup uses 500K vertices and approximately 8M edges by default.",
            "MindGraph and upstream graph outputs are fingerprinted outside the timed region and must match before the report is marked verified.",
            "Graph algorithm timing reports the median of $graph_runs measured runs after one full warm-up and data-load run.",
            "LSQB reports the median of $lsqb_runs measured query runs after one full warm-up and data-load run.",
        ],
        "disclosures": [
            "ArcadeDB published references came from arcadedb.com/benchmarks.html and were not measured on this host; its graph chart names graph500-22, so those values are context rather than an apples-to-apples comparison with datagen-7_5-fb.",
            "The graph algorithm section uses the public harness native load-once runner, not an official LDBC audited result or certification.",
            "Embedded results describe engine execution without network overhead and are not application TPS or production sizing claims.",
            "The inherited OLTP-to-OLAP benchmark uses randomized graph generation, so speedup is directional rather than a deterministic conformance value.",
        ],
    },
    "artifacts": [
        {"label": "Normalized result JSON", "path": "result.json"},
        {"label": "Run metadata", "path": "metadata.json"},
        {"label": "Raw evidence manifest", "path": "evidence/manifest.json"},
        {"label": "Dataset checksums", "path": "evidence/dataset-sha256.txt"},
    ],
}
with open(sys.argv[1], "w", encoding="utf-8") as stream:
    json.dump(metadata, stream, indent=2)
    stream.write("\n")
PY
    python3 "$repository_root/benchmarks/industry-standard/collect.py" "$run_root" "$run_root/result.json"
    python3 "$repository_root/benchmarks/industry-standard/dashboard.py" "$run_root/result.json" "$run_root/index.html"
fi

echo "benchmark evidence: $run_root"
