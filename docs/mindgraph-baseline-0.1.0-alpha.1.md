# MindGraph DB Engine 0.1.0-alpha.1 baseline

This document records the first reproducible MindGraph DB Engine performance baseline. It is a
regression reference for future MindGraph changes, not a vendor comparison or production sizing
claim.

## Source provenance

- Run date: `2026-09-29` (UTC)
- MindGraph version: `0.1.0-alpha.1`
- Exact upstream source: ArcadeDB commit `50db74952c1ff1ac49bca7120f8ac51de6f2b40d`
  (`26.10.1-SNAPSHOT`)
- Stable upstream anchor: ArcadeDB `26.9.1`, commit
  `b6a92623554bb332d7564de19fbd9fdbc2d1d45e`
- Production engine delta for this baseline: none. `engine/src/main` is byte-for-byte unchanged
  relative to the exact upstream source commit.
- Test-only delta: the inherited `Issue7222StrictBooleanFromConfigurationSourceTest` now resets its
  mutable global setting before asserting the default, removing an order-dependent suite failure.
- Benchmark harness SHA-256:
  `ea22adef96a5711186f37db46ae5a96ea95611606c12b427b01869a903de641a`
- Aggregate result: [mindgraph-baseline-0.1.0-alpha.1.json](mindgraph-baseline-0.1.0-alpha.1.json)
- Raw measured results: [`docs/benchmarks/mindgraph-0.1.0-alpha.1/`](benchmarks/mindgraph-0.1.0-alpha.1/)

## Environment

The run used an otherwise idle BytePlus ECS virtual machine with only SSH publicly listening.

| Component | Value |
| --- | --- |
| Virtualization | KVM / OpenStack Nova |
| CPU | 8 vCPU, Intel Xeon 6986P-C, x86-64 |
| Memory | 30 GiB RAM, no swap |
| Storage | 200 GB virtual disk, ext4; 186 GB free before the run |
| OS | Ubuntu 24.04 LTS |
| Kernel | Linux 6.8.0-55-generic |
| Java | OpenJDK 21.0.12.1, Ubuntu build |
| JVM max heap | 8,283,750,400 bytes |

For context, a separate 30-second direct-I/O `fio` probe used 4 KiB random 70/30 read/write,
queue depth 32, and one job. It measured about 2,482 read IOPS and 1,060 write IOPS. Those numbers
describe the VM storage available to the run; they are not MindGraph performance claims.

## Workload and method

- Embedded engine, one client thread, local persistent database.
- Deterministic synthetic graph: 100,000 vertices and 400,000 light edges, seed `42`.
- Indexed lookup: 2,000 warm-up operations followed by 20,000 measured operations.
- One-hop outgoing traversal: 1,000 warm-up operations followed by 10,000 measured operations.
- One unmeasured whole-run warm-up followed by five measured whole runs.
- The database was recreated for every run. The operating-system page cache was not explicitly
  cleared, matching the warm local service profile this baseline is intended to track.
- Reported values are medians across the five measured runs. CV is the population coefficient of
  variation across those runs.

## Results

| Metric | Median | Observed range | CV |
| --- | ---: | ---: | ---: |
| Load 500,000 graph records | 5.412 s | 5.363–5.539 s | 1.11% |
| Load throughput | 92,379 records/s | 90,275–93,229 records/s | 1.09% |
| Database reopen | 9.933 ms | 9.876–11.426 ms | 5.87% |
| Indexed lookup throughput | 109,220 ops/s | 98,511–128,569 ops/s | 9.69% |
| Indexed lookup p50 | 0.008100 ms | 0.006728–0.009213 ms | 12.11% |
| Indexed lookup p95 | 0.012845 ms | 0.010270–0.013089 ms | 8.45% |
| Indexed lookup p99 | 0.025996 ms | 0.021480–0.028764 ms | 9.38% |
| One-hop traversal throughput | 121,135 ops/s | 106,273–128,031 ops/s | 6.06% |
| One-hop traversal p50 | 0.007689 ms | 0.007209–0.008350 ms | 4.77% |
| One-hop traversal p95 | 0.010078 ms | 0.009816–0.012659 ms | 9.95% |
| One-hop traversal p99 | 0.019423 ms | 0.017907–0.020165 ms | 4.29% |
| Database size | 23,660,626 bytes | 23,660,626–23,660,628 bytes | <0.01% |

The median process maximum resident set size was 1,080,504 KiB. The median JVM used-heap sample
captured after the measured operations was 110,832,520 bytes. These are different measurements:
RSS includes Maven, the JVM, native memory, mapped files, and other process overhead.

## Release rehearsal

The same VM completed the 20-module release build, Studio production build, archive assembly, and
CycloneDX 1.6 generation. The generated SBOM contained 279 components. The tar and zip archives
contained `MINDGRAPH_VERSION`, `UPSTREAM.md`, and `THIRD_PARTY_NOTICES.md`; every staged file passed
the generated SHA-256 manifest check.

## Interpretation and limits

The stable load results are suitable as a first regression guard. Lookup and traversal throughput
show normal cloud/JIT variation, so future changes should be evaluated against the full range and
CV, not only a single median.

This workload does not cover concurrent clients, remote protocols, HA replication, crash recovery,
vector search, complex SQL, or a production banking dataset. It also does not compare MindGraph
with Neo4j or any other database. Vendor or capacity claims require a separate, independently
reviewed benchmark with equivalent configuration, data, durability, and client workloads.

## Reproduce

Use an idle x86-64 host with JDK 21 and `jq`:

```bash
./scripts/mindgraph/verify-baseline.sh
./scripts/mindgraph/run-baseline-suite.sh
./scripts/mindgraph/stage-release.sh
```

The suite writes raw run JSON, Maven logs, process resource observations, and an aggregate summary
under `artifacts/benchmarks/`. The raw evidence archive produced for this run had SHA-256
`115e3c2fab87eaef0b30d3690b3741e52370d6a256004a3aad9241aaf49beb7c`.
