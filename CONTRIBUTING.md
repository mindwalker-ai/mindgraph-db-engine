# Contributing to MindGraph DB Engine

MindGraph DB Engine is a controlled fork of ArcadeDB. Contributions must preserve a reviewable
boundary between upstream-derived code and Mindwalker-owned product work.

## Before opening a pull request

1. Create a focused branch from the current MindGraph `main`.
2. Search both this repository and
   [ArcadeData/arcadedb](https://github.com/ArcadeData/arcadedb) for related work.
3. Decide whether the change is generic upstream work or MindGraph-specific differentiation.
4. Add or update tests at the same layer as the behavior being changed.
5. Retain required copyright, license, SPDX, NOTICE, and attribution information.
6. Run the relevant local checks described below.

Generic engine fixes should be proposed upstream whenever practical. MindGraph-specific
authorization, governance, analytics, AI, domain, and operational behavior should be isolated from
the database kernel.

## Local checks

Use JDK 21 and the included Maven Wrapper.

```bash
./scripts/mindgraph/verify-baseline.sh
./mvnw -B -ntp -pl engine -am test -DexcludedGroups=slow,benchmark
```

Container-based integration tests require Docker or a compatible container runtime:

```bash
./mvnw -B -ntp verify -Pintegration -pl '!e2e,!load-tests,!e2e-ha'
```

Run the reproducible MindGraph benchmark separately from ordinary unit tests:

```bash
./scripts/mindgraph/run-baseline-suite.sh
```

## Pull-request requirements

- Explain user-visible behavior and compatibility impact.
- Identify modified upstream files explicitly.
- Include tests and evidence proportionate to risk.
- Update `UPSTREAM.md` when importing upstream commits.
- Do not introduce credentials, private keys, customer data, or generated databases.
- Do not change public package names, database formats, or protocol behavior without an approved
  architecture decision record.

Formatting and implementation conventions inherited from ArcadeDB continue to apply where this
guide does not override them. See the
[upstream contribution guide](https://github.com/ArcadeData/arcadedb/blob/main/CONTRIBUTING.md) for
those details.
