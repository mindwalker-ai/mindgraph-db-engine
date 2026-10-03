# MindGraph industry-standard benchmarks

This directory turns raw benchmark evidence into a self-contained HTML report. It uses the public
ArcadeDB benchmark harness's native graph-algorithm and LSQB workloads while keeping host
measurements separate from published reference values. The release report also includes a
same-host Neo4j Community + Graph Data Science Community comparison as a distinct competitor
series.

The dashboard is presentation only. JSON evidence remains the source of truth.
Values transcribed from ArcadeDB's public page are pinned with their source date under
`reference/` and are always rendered as references, never as host measurements.

The current verified release evidence is published in
[`docs/benchmarks/mindgraph-0.1.0-alpha.1/`](../../docs/benchmarks/mindgraph-0.1.0-alpha.1/):
open the [self-contained dashboard](../../docs/benchmarks/mindgraph-0.1.0-alpha.1/index.html)
or read the [methodology and findings report](../../docs/benchmarks/mindgraph-0.1.0-alpha.1/REPORT.md).

## Evidence rules

- Pin the MindGraph commit, upstream ArcadeDB commit, benchmark-harness commit, datasets, JVM, and
  heap before a run.
- Execute MindGraph and the upstream control sequentially on the same otherwise-idle host.
- Compare untimed graph-output fingerprints across MindGraph and upstream, and validate LSQB result
  counts before reporting timing.
- Report warm-up policy, all measured runs, median, range, and coefficient of variation.
- Label values copied from a vendor page as `reference`; never merge them with values measured on
  the benchmark host.
- Keep embedded and container/server comparisons in separate series.
- Record each system's deployment surface, edition, image digest, concurrency ceiling, and sample
  count. A same-host result is not automatically an identical execution-mode result.
- Treat LSQB as a pattern-matching microbenchmark, not a production capacity estimate.

## Generate the report

```bash
python3 benchmarks/industry-standard/dashboard.py \
  artifacts/industry-standard/result.json \
  artifacts/industry-standard/index.html
```

The generated HTML has no runtime dependencies and can be opened directly from disk.

## Execute the full suite

Run this only on a dedicated, otherwise-idle Linux benchmark host with Java 21 and Python 3:

```bash
MINDGRAPH_INDUSTRY_RUN_DIR=/opt/mindgraph-benchmark/runs/0.1.0-alpha.1 \
  ./scripts/mindgraph/run-industry-benchmarks.sh
```

The runner builds the current MindGraph checkout and the exact upstream control into isolated
Maven repositories. It downloads the public datasets, runs both systems sequentially, validates
outputs, preserves raw logs, and generates `result.json` plus `index.html`. It is resumable: a
completed stage is not repeated unless `MINDGRAPH_BENCHMARK_FORCE=1` is set.

Stages can be selected explicitly:

```bash
MINDGRAPH_BENCHMARK_STAGES=setup,graphalytics \
  ./scripts/mindgraph/run-industry-benchmarks.sh
```

The default full-size OLAP workload creates 500,000 vertices and approximately 8 million edges.
For a smoke test only, lower `MINDGRAPH_OLAP_VERTICES`; never publish smoke-test numbers as the
full benchmark.

## Neo4j comparison lane

`neo4j_benchmark.py` runs the same six graph algorithms through Neo4j Graph Data Science and the
same nine LSQB Cypher queries imported from the pinned public harness. It expects the graph and
LSQB databases to have already been bulk-loaded from the same pinned datasets. Install the pinned
driver in an isolated environment and provide the benchmark-only connection values at runtime:

```bash
python3 -m venv artifacts/industry-standard/neo4j-venv
artifacts/industry-standard/neo4j-venv/bin/pip install neo4j==6.2.0

NEO4J_URI=bolt://127.0.0.1:7688 \
NEO4J_USERNAME=neo4j \
NEO4J_PASSWORD='<benchmark-only password>' \
  artifacts/industry-standard/neo4j-venv/bin/python \
  benchmarks/industry-standard/neo4j_benchmark.py graph
```

Run `lsqb --harness-root <pinned harness checkout>` against the separately loaded LSQB database.
`--query-timeout-seconds` is optional and uses Neo4j's server-enforced transaction timeout. The
published comparison deliberately omitted this limit because all completed query results were
required; the report discloses that Neo4j Q9 exceeded 300 seconds.

The Neo4j lane is useful competitor evidence, but not a perfectly symmetric engine microbenchmark:
MindGraph and upstream run embedded in the JVM, while Neo4j runs as a server over Bolt and the GDS
Community algorithms are capped at four concurrent workers. Import and GDS projection time are
excluded from the timed algorithm region, matching the load-once policy used by the other systems.

## Test the report generator

```bash
python3 -m unittest discover -s benchmarks/industry-standard/tests -p 'test_*.py'
```

## Public benchmark inputs

- ArcadeDB harness: `https://github.com/ArcadeData/ldbc_graphalytics_platforms_arcadedb`
- Graph algorithm dataset: `datagen-7_5-fb`, using the harness's native load-once runner
- LSQB dataset: `lsqb-sf1`, merged-FK representation
- Neo4j container: official `neo4j` image pinned by digest in the release metadata
- Neo4j GDS compatibility and Community concurrency limit:
  `https://neo4j.com/docs/graph-data-science/current/installation/`
- MindGraph source: the exact release commit under test
- Upstream control: the exact ArcadeDB commit recorded in `UPSTREAM.md`

The execution script and the resulting evidence manifest pin concrete commits instead of following
moving branches.

ArcadeDB's public page labels its graph chart as `graph500-22`, while the public native Java runner
at the pinned harness commit uses `datagen-7_5-fb`. The dashboard therefore labels the page values
as context from a different dataset and host rather than presenting them as an apples-to-apples
comparison. The native runner is not an official LDBC audited or certified result.
