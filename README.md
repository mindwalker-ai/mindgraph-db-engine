# MindGraph DB Engine

<p align="center">
  <strong>A high-performance, transactional multi-model database engine maintained by Mindwalker.</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-green.svg" alt="Apache License 2.0"></a>
  <a href="https://docs.oracle.com/en/java/javase/21/"><img src="https://img.shields.io/badge/Java-21-007396.svg" alt="Java 21"></a>
  <a href="https://github.com/mindwalker-ai/mindgraph-db-engine"><img src="https://img.shields.io/badge/maintained%20by-Mindwalker-3155F5.svg" alt="Maintained by Mindwalker"></a>
  <a href="https://github.com/ArcadeData/arcadedb"><img src="https://img.shields.io/badge/upstream-ArcadeDB-FF00A0.svg" alt="Upstream ArcadeDB"></a>
</p>

MindGraph DB Engine is Mindwalker's distribution of
[ArcadeDB](https://github.com/ArcadeData/arcadedb), maintained as a controlled fork under the
[Apache License 2.0](LICENSE). It preserves ArcadeDB's multi-model database capabilities while
providing the engine foundation for Mindwalker's graph intelligence products.

The project is currently at the **upstream-compatible baseline** stage. The repository retains
upstream APIs, artifact coordinates, configuration keys, wire protocols, and file formats while
Mindwalker establishes its own release, compatibility, security, and product-extension policies.

> **Current status:** `0.1.0-alpha.1` is the first defined MindGraph baseline. It remains a release
> candidate until its tag pipeline publishes the archives, SBOM, provenance, signature, and OCI
> image. References to `ArcadeDB`, `com.arcadedb`, and `ARCADEDB_*` are retained intentionally for
> upstream compatibility; they are not evidence of an incomplete repository migration.

The reproducible performance envelope for this candidate is documented in
[docs/mindgraph-baseline-0.1.0-alpha.1.md](docs/mindgraph-baseline-0.1.0-alpha.1.md).

The exact upstream source and stable-release anchor are documented in [UPSTREAM.md](UPSTREAM.md).

## Why MindGraph DB Engine

MindGraph DB Engine is intended to provide a stable, high-performance data plane for graph-centric
and AI-assisted workloads, especially in regulated enterprise environments. Mindwalker-specific
capabilities will be developed as isolated, versioned modules so that upstream fixes can continue
to be integrated safely.

The initial product direction includes:

- enterprise identity, authorization, and audit controls;
- governed ingestion, ontology, lineage, and entity resolution;
- temporal graph analytics and explainable scoring;
- permission-aware GraphRAG and AI tooling;
- operational tooling for private cloud, on-premise, and air-gapped environments; and
- domain packs for financial services and other regulated industries.

These items describe the product direction. They should not be treated as shipped functionality
until they appear in a tagged MindGraph release.

## Capabilities inherited from the upstream engine

MindGraph DB Engine starts with the complete upstream capability set rather than reimplementing a
database kernel. The baseline includes:

- ACID transactions, write-ahead logging, schema, indexes, and native graph relationships;
- graph, document, key/value, search, time-series, vector, and geospatial models;
- SQL, openCypher-compatible queries, Gremlin, GraphQL, and MongoDB query support;
- HTTP/JSON, PostgreSQL, Redis, MongoDB, Bolt, gRPC, and MCP interfaces;
- graph algorithms, full-text and vector search, materialized views, and parallel queries;
- embedded and client/server deployment modes;
- high availability based on Raft, backup/restore, metrics, and tracing; and
- Studio, console, Kubernetes, container, native-image, and client integration modules.

Some compatibility protocols intentionally implement only a subset of their upstream protocol.
Consult the [ArcadeDB documentation](https://docs.arcadedb.com/) for the behavior of the current
baseline. MindGraph-specific documentation will be published as its public interfaces diverge.

## Repository layout

The main modules include:

| Area | Modules |
| --- | --- |
| Core database | `engine`, `network`, `server`, `ha-raft` |
| Query and protocol adapters | `graphql`, `gremlin`, `postgresw`, `mongodbw`, `redisw`, `bolt`, `grpc` |
| Operations | `console`, `studio`, `metrics`, `tracing`, `k8s`, `package` |
| Integrations | `mcp`, `bindings/python`, `e2e-*` |
| Verification | unit, integration, end-to-end, load, and HA resilience suites |

## Build from source

### Prerequisites

- Git
- JDK 21
- Docker or Podman for container-based integration and end-to-end tests

The Maven Wrapper is included, so a separate Maven installation is not required.

Build all modules without running tests:

```bash
./mvnw clean install -DskipTests
```

Verify the MindGraph baseline metadata, notices, workflow policy, and Maven structure:

```bash
./scripts/mindgraph/verify-baseline.sh
```

Stage the release archives, CycloneDX SBOM, legal notices, build manifest, and checksums:

```bash
./scripts/mindgraph/stage-release.sh
```

Tagged releases publish the OCI image as
`ghcr.io/mindwalker-ai/mindgraph-db-engine:<mindgraph-version>`. Downstream applications should not
depend on the inherited `26.10.1-SNAPSHOT` Maven coordinates.

## Testing

Run the unit test suite:

```bash
./mvnw test
```

Run the faster unit-test subset:

```bash
./mvnw test -DexcludedGroups="slow,benchmark"
```

Run integration tests, which require Docker or a compatible container runtime:

```bash
./mvnw verify -Pintegration
```

Run only the black-box, load, and HA suites:

```bash
./mvnw verify -Pintegration -pl e2e,load-tests,e2e-ha
```

Run the deterministic MindGraph baseline benchmark:

```bash
./scripts/mindgraph/run-baseline-suite.sh
```

The default suite performs one warm-up and five measured runs. Environment variables documented by
the scripts can scale the dataset or select an isolated output directory.

| Suite | Scope |
| --- | --- |
| Unit | Storage, WAL, indexes, serialization, queries, schema, graph operations, and security |
| Integration | Server APIs, wire protocols, cross-module behavior, and embedded clustering |
| End-to-end | Black-box client behavior against a real containerized server |
| Load | Throughput, concurrency, stability, and data-integrity scenarios |
| HA | Failover, restart, network fault, replication, and cluster operation scenarios |

## Fork maintenance model

The repository uses two Git remotes during development:

```text
origin    https://github.com/mindwalker-ai/mindgraph-db-engine.git
upstream  https://github.com/ArcadeData/arcadedb.git
```

Confirm the remotes after cloning:

```bash
git remote -v
```

If `upstream` is missing, add it once:

```bash
git remote add upstream https://github.com/ArcadeData/arcadedb.git
```

Upstream changes are imported deliberately and must pass the MindGraph compatibility, security,
license, and regression checks before release. Avoid broad internal package renames or unrelated
formatting changes because they make upstream security updates harder to review and merge.

General-purpose engine fixes should remain suitable for contribution to ArcadeDB whenever
possible. Mindwalker product differentiation should live in clearly separated MindGraph modules.

## Contributing

Open a pull request in this repository for MindGraph-specific work. The public issue-management
policy will be documented before the first supported release. Changes inherited from or intended
for ArcadeDB should also follow the upstream
[contribution guide](https://github.com/ArcadeData/arcadedb/blob/main/CONTRIBUTING.md).

Before submitting a change:

1. keep upstream-derived and Mindwalker-owned changes easy to distinguish;
2. add tests for behavior changes;
3. preserve compatibility unless the pull request documents an intentional break; and
4. retain applicable license headers, notices, and third-party attribution.

## Security

Do not report security vulnerabilities in a public issue. Use
[GitHub private vulnerability reporting](https://github.com/mindwalker-ai/mindgraph-db-engine/security/advisories/new)
for vulnerabilities affecting this distribution. Issues confirmed to originate upstream will be
coordinated responsibly with the ArcadeDB maintainers.

## License and upstream attribution

The source currently contained in this repository is licensed under the
[Apache License 2.0](LICENSE). MindGraph DB Engine is derived from ArcadeDB and retains the
upstream copyright, license, patent, trademark, and third-party notices required by that license.

- [LICENSE](LICENSE) — Apache License 2.0
- [NOTICE](NOTICE) — required upstream and third-party notices
- [ATTRIBUTIONS.md](ATTRIBUTIONS.md) — detailed third-party acknowledgements
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — MindGraph distribution notice index
- [UPSTREAM.md](UPSTREAM.md) — exact upstream provenance and synchronization policy
- [LICENSES](LICENSES) — component license texts
- [ArcadeDB upstream repository](https://github.com/ArcadeData/arcadedb)

Mindwalker-authored modules may receive separately documented commercial terms in the future.
Nothing in this README changes the license of source already published in this repository.

---

Maintained by [Mindwalker](https://mindwalker.ai/). Powered by the open-source ArcadeDB engine and
its contributor community.
