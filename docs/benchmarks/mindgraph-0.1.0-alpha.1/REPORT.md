# MindGraph 0.1.0-alpha.1 reproducible graph benchmark

Measured on September 29–October 6, 2026 UTC on one dedicated BytePlus host. The candidate, its exact
ArcadeDB upstream control, and Neo4j Community were executed sequentially against the same source
datasets. Neo4j is a separately labeled competitor lane because its server/GDS execution surface
is not identical to the embedded MindGraph and upstream runners.

- MindGraph commit: `c7ffbdf3e1d154359c6b043b6f8bfdd325e50f55`
- Exact upstream commit: `50db74952c1ff1ac49bca7120f8ac51de6f2b40d`
- Harness commit: `02e1d824a2ff1bfc1574bbdda7cb9b3c2344bfff`
- Host: Intel Xeon 6986P-C, 8 logical CPUs, 31 GiB RAM, Ubuntu 24.04, OpenJDK 21.0.12.1
- JVM heap: 12 GiB
- Neo4j/GDS: `2026.09.0`/`2026.09.0`, official image pinned by digest, 12 GiB heap, 8 GiB page
  cache, and GDS Community concurrency explicitly set to 4

[Open the self-contained HTML dashboard](index.html) or inspect the
[normalized JSON](result.json) and [raw evidence manifest](evidence/manifest.json).

## Outcome

The result is `verified` for the two suites with correctness evidence:

- all six graph-algorithm output fingerprints matched across every measured MindGraph and upstream
  run;
- all six Neo4j graph algorithms passed complete-result semantic checks in every measured run;
- all nine LSQB SF1 query counts matched the official expected values for all three systems in
  every measured run; and
- all five synthetic banking query results were stable across five measured runs and identical
  between MindGraphDB and Neo4j.

MindGraph remains close to its exact upstream control. All nine LSQB medians are within 6% of the
control. Four graph-algorithm medians are within 9%; BFS and SSSP were about 20% slower in this run.
That difference is reported, not normalized away. Both embedded systems produced identical
fingerprints.

Neo4j is not uniformly faster or slower. On the graph workload it is faster for WCC, SSSP, and
CDLP, and slower for PageRank, BFS, and LCC. On LSQB it is faster for Q7 but slower for the other
eight queries in this specific dataset, query shape, edition, and configuration. These are measured
workload results, not a universal database ranking.

The synthetic banking lane reinforces that conclusion. MindGraphDB was faster on fund-flow
traversal and shared-device matching; Neo4j was faster on cycle detection and the two global
aggregation patterns. The results are shown as measured rather than mapped from LSQB.

### Graph algorithm execution

Public harness native load-once mode on `datagen-7_5-fb` (633,432 vertices and 34,185,747 edges).
One warm-up and five measured runs; lower is better.

| Algorithm | MindGraph median | Upstream median | Neo4j median | MindGraph delta vs upstream |
|---|---:|---:|---:|---:|
| PageRank | 0.472 s | 0.460 s | 4.253 s | +2.6% |
| WCC | 0.267 s | 0.292 s | 0.125 s | -8.6% |
| BFS | 0.309 s | 0.258 s | 0.847 s | +19.8% |
| LCC | 6.285 s | 6.368 s | 28.472 s | -1.3% |
| SSSP | 2.188 s | 1.827 s | 0.967 s | +19.8% |
| CDLP | 3.883 s | 3.895 s | 2.402 s | -0.3% |

The Neo4j graph database contained the same 633,432 vertices and 34,185,747 relationships. Bulk
import took 22.186 seconds and the undirected GDS projection took 12.956 server seconds; both are
preserved as setup evidence and excluded from algorithm timings.

### LSQB SF1

Nine Cypher pattern-matching queries on 3,947,829 vertices and 17,882,623 edges. MindGraph and
upstream use one data-load warm-up plus five measured runs. Neo4j uses one load/warm-up plus three
measured runs; the dashboard shows `n`, range, and coefficient of variation per value.

| Query | MindGraph median | Upstream median | Neo4j median | MindGraph delta vs upstream |
|---|---:|---:|---:|---:|
| Q1 | 0.666 s | 0.699 s | 9.426 s | -4.7% |
| Q2 | 0.436 s | 0.439 s | 2.714 s | -0.7% |
| Q3 | 0.257 s | 0.251 s | 18.448 s | +2.4% |
| Q4 | 7.948 s | 8.275 s | 10.053 s | -4.0% |
| Q5 | 0.453 s | 0.429 s | 9.756 s | +5.6% |
| Q6 | 0.465 s | 0.463 s | 50.086 s | +0.4% |
| Q7 | 19.492 s | 18.874 s | 13.833 s | +3.3% |
| Q8 | 0.190 s | 0.196 s | 25.630 s | -3.1% |
| Q9 | 2.275 s | 2.399 s | 474.131 s | -5.2% |

Neo4j's initial SF1 load took 438.17 seconds and is excluded from query timing. Q9 crossed 300
seconds in the measured set; the completed, count-validated timings are retained instead of being
censored. This makes the long tail visible and prevents a false-green comparison.

### Synthetic banking queries

Five exact Cypher queries on a deterministic synthetic graph containing 50,000 accounts, 10,000
devices, 500,000 transfers, and 50,000 account-to-device relationships. Both engines used the same
CSV files, query text, and parameters. Each engine ran one warm-up before five measured runs;
dataset loading and Neo4j index creation were excluded. Lower is better.

| Query | Pattern | MindGraph median | Neo4j median | Identical result |
|---|---|---:|---:|---:|
| B1 | Fund-flow traversal, 1–3 hops | 2.306 ms | 5.464 ms | 1,221 paths |
| B2 | Circular transfers, 2–5 hops | 99.447 ms | 51.666 ms | 7 cycles |
| B3 | Accounts sharing one device | 0.648 ms | 4.848 ms | 10 pairs |
| B4 | Small-transfer fan-in from at least five sources | 607.055 ms | 298.545 ms | 44,780 accounts |
| B5 | Maximum unique counterparties | 213.348 ms | 179.455 ms | 12 counterparties |

MindGraphDB leads B1 and B3; Neo4j leads B2, B4, and B5. This dataset was generated to exercise
the five graph shapes and is explicitly synthetic. It does not reproduce a bank's transaction
distribution, fraud rate, concurrency, retention period, or production service-level objectives,
so these numbers are not capacity-planning guidance.

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

The banking generator, exact queries, Neo4j runner, result validator, and report merger are in
[`banking_workload.py`](../../../benchmarks/industry-standard/banking_workload.py). The synthetic
dataset definition and hashes are preserved in
[`evidence/banking-dataset-manifest.json`](evidence/banking-dataset-manifest.json) and
[`evidence/banking-dataset-sha256.txt`](evidence/banking-dataset-sha256.txt); all ten measured logs,
warm-ups, import output, and runtime fingerprint are stored beside them.
