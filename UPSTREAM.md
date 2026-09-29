# Upstream baseline and synchronization

MindGraph DB Engine is maintained as a controlled fork of
[ArcadeDB](https://github.com/ArcadeData/arcadedb). This document is the source of truth for the
upstream code represented by the first MindGraph baseline.

Machine-readable values are stored in [`.mindgraph/baseline.properties`](.mindgraph/baseline.properties).

## Baseline 0.1.0-alpha.1

| Item | Value |
| --- | --- |
| MindGraph version | `0.1.0-alpha.1` |
| Upstream repository | `https://github.com/ArcadeData/arcadedb.git` |
| Latest stable anchor at baseline time | `26.9.1` |
| Stable anchor commit | `b6a92623554bb332d7564de19fbd9fdbc2d1d45e` |
| Exact upstream source commit | `50db74952c1ff1ac49bca7120f8ac51de6f2b40d` |
| Upstream Maven version at that commit | `26.10.1-SNAPSHOT` |

The fork was created from upstream `main` after the `26.9.1` release. The exact source commit is
1,985 upstream commits after the stable anchor and is therefore intentionally released as a
MindGraph **alpha**, not represented as an ArcadeDB `26.9.1` build.

The MindGraph version and the embedded upstream Maven version are separate identifiers. This avoids
renaming upstream packages and artifacts before a compatibility policy exists.

The `0.1.0-alpha.1` baseline does not modify `engine/src/main`. Its only inherited engine-test
change resets mutable global configuration at the start of one assertion in
`Issue7222StrictBooleanFromConfigurationSourceTest`, preventing test order from changing the
result. MindGraph-owned benchmark code lives under `com.mindwalker.mindgraph.benchmark`.

## Remote configuration

Development checkouts should use:

```text
origin    https://github.com/mindwalker-ai/mindgraph-db-engine.git
upstream  https://github.com/ArcadeData/arcadedb.git
```

Add and verify the upstream remote:

```bash
git remote add upstream https://github.com/ArcadeData/arcadedb.git
git fetch --tags upstream
git remote -v
```

## Synchronization policy

1. Fetch upstream without rewriting published MindGraph history.
2. Review upstream release notes, breaking changes, security advisories, and license changes.
3. Create an `upstream-sync/<version-or-date>` branch from MindGraph `main`.
4. Merge the selected upstream commit. Do not squash upstream history.
5. Resolve fork-owned files deliberately, especially `.github/`, governance documents, packaging,
   and external product metadata.
6. Run the MindGraph pull-request, integration, benchmark, license, and compatibility checks.
7. Record the new exact commit in this file and `.mindgraph/baseline.properties`.
8. Merge through a reviewed pull request.

Published release tags are immutable. Never force-push a release tag or rebase a published release
line.

## Patch policy

- Generic correctness, performance, and security fixes should remain suitable for contribution to
  ArcadeDB whenever practical.
- Mindwalker-specific policy, enterprise, analytics, AI, and domain capabilities should be isolated
  in clearly named modules or services.
- Modifications to upstream files must retain applicable headers and include a prominent
  modification notice when required by Apache License 2.0.
- Broad internal namespace renames are prohibited until an explicit compatibility ADR approves
  them.

## Compatibility promise for the alpha baseline

The alpha baseline keeps upstream database files, configuration keys, Java packages, artifact
coordinates, APIs, and wire protocols unchanged. MindGraph does not yet promise compatibility
between alpha releases. Any intentional incompatibility must be documented in release notes and
covered by migration tests before a stable release.
