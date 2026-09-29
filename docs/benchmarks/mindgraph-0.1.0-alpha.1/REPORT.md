# MindGraph 0.1.0-alpha.1 reproducible graph benchmark

Measured on September 29, 2026 UTC on one dedicated BytePlus host. The candidate and its exact
ArcadeDB upstream control were built independently, then executed sequentially with the same
datasets, heap, harness, and host.

- MindGraph commit: `c7ffbdf3e1d154359c6b043b6f8bfdd325e50f55`
- Exact upstream commit: `50db74952c1ff1ac49bca7120f8ac51de6f2b40d`
- Harness commit: `02e1d824a2ff1bfc1574bbdda7cb9b3c2344bfff`
- Host: Intel Xeon 6986P-C, 8 logical CPUs, 31 GiB RAM, Ubuntu 24.04, OpenJDK 21.0.12.1
- JVM heap: 12 GiB

[Open the self-contained HTML dashboard](index.html) or inspect the
[normalized JSON](result.json) and [raw evidence manifest](evidence/manifest.json).

## Outcome

The result is `verified` for the two suites with correctness evidence:

- all six graph-algorithm output fingerprints matched across every measured MindGraph and upstream
  run;
- all nine LSQB SF1 query counts matched the official expected values in every measured run.

MindGraph remains close to its exact upstream control. All nine LSQB medians are within 6% of the
control. Four graph-algorithm medians are within 9%; BFS and SSSP were about 20% slower in this run.
That difference is reported, not normalized away. Both systems produced identical fingerprints.

### Graph algorithm execution

Public harness native load-once mode on `datagen-7_5-fb` (633,432 vertices and 34,185,747 edges).
One warm-up and five measured runs; lower is better.

| Algorithm | MindGraph median | Upstream median | MindGraph delta |
|---|---:|---:|---:|
| PageRank | 0.472 s | 0.460 s | +2.6% |
| WCC | 0.267 s | 0.292 s | -8.6% |
| BFS | 0.309 s | 0.258 s | +19.8% |
| LCC | 6.285 s | 6.368 s | -1.3% |
| SSSP | 2.188 s | 1.827 s | +19.8% |
| CDLP | 3.883 s | 3.895 s | -0.3% |

### LSQB SF1

Nine Cypher pattern-matching queries on 3,947,829 vertices and 17,882,623 edges. One data-load
warm-up and five measured runs; lower is better.

| Query | MindGraph median | Upstream median | MindGraph delta |
|---|---:|---:|---:|
| Q1 | 0.666 s | 0.699 s | -4.7% |
| Q2 | 0.436 s | 0.439 s | -0.7% |
| Q3 | 0.257 s | 0.251 s | +2.4% |
| Q4 | 7.948 s | 8.275 s | -4.0% |
| Q5 | 0.453 s | 0.429 s | +5.6% |
| Q6 | 0.465 s | 0.463 s | +0.4% |
| Q7 | 19.492 s | 18.874 s | +3.3% |
| Q8 | 0.190 s | 0.196 s | -3.1% |
| Q9 | 2.275 s | 2.399 s | -5.2% |

### Graph Analytical View speedup

On the inherited 500,000-vertex/~8-million-edge workload, MindGraph's CSR-backed analytical path
was 3.5x to 258.4x faster than the OLTP path, depending on the operation. Its reported GAV memory
was 138.4 MB versus the benchmark's approximate 1.2 GB OLTP estimate, a 9.0x ratio.

This section is directional evidence, not a deterministic head-to-head result. The inherited test
uses unseeded random graph generation, and its 2-hop and 5-hop totals differed by one between OLTP
and OLAP in both measured systems. The dashboard therefore excludes these rows from the validated
output total and preserves the complete logs for review.

## Comparison with ArcadeDB's published page

The published values are rendered as a striped `reference` series, never as measurements from this
host. They are not directly comparable:

- the public page labels its graph chart as `graph500-22`, while the native Java runner available at
  the pinned harness commit uses `datagen-7_5-fb`;
- the page was last updated July 30, 2026 and its repository results identify ArcadeDB 26.4.1-era
  measurements, while this run tests the MindGraph and exact-upstream 26.10.1-SNAPSHOT sources;
- the page's hardware and raw run evidence are not specified in the HTML;
- the page's displayed `run-benchmark.sh graph500-22` and `native-comparison.sh` commands do not
  exist at the pinned public harness commit.

The large LSQB Q4/Q7 gap versus the published reference also occurs on the exact upstream control,
so this run does not attribute it to MindGraph changes. Enabling JVMCI in a diagnostic run did not
materially change those query times; that diagnostic was excluded from the five-run result set.

## Reproduce

On a dedicated Linux host with Java 21 and Python 3:

```bash
MINDGRAPH_INDUSTRY_RUN_DIR=/opt/mindgraph-benchmark/runs/0.1.0-alpha.1 \
  ./scripts/mindgraph/run-industry-benchmarks.sh
```

The runner is resumable per stage and per measured run. Dataset hashes are recorded in
[`evidence/dataset-sha256.txt`](evidence/dataset-sha256.txt); raw evidence file hashes and sizes are
recorded in [`evidence/manifest.json`](evidence/manifest.json).

