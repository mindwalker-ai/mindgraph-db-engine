# MindGraph DB Engine governance

MindGraph DB Engine is maintained by Mindwalker as a controlled Apache 2.0 fork of ArcadeDB.

## Principles

- Preserve upstream provenance, attribution, and patent notices.
- Keep upstream synchronization possible and reviewable.
- Prefer extensions over invasive engine changes.
- Require evidence for compatibility, performance, durability, and security claims.
- Never describe roadmap items as released capabilities.
- Treat database format, protocol, and security changes as architecture decisions.

## Decision ownership

Mindwalker maintainers approve repository policy, releases, compatibility guarantees, and
MindGraph-specific product direction. Changes to storage, WAL, replication, authentication,
authorization, encryption, public protocols, or database format require at least one documented
architecture decision and an explicit rollback or migration strategy.

Contributors may propose changes through pull requests. Security-sensitive decisions are discussed
privately until a coordinated disclosure is ready.

## Upstream relationship

ArcadeDB remains an independent upstream project. Mindwalker does not speak for Arcade Data Ltd or
the ArcadeDB community. Upstream imports follow [UPSTREAM.md](UPSTREAM.md), and inherited defects
should be coordinated upstream when responsible disclosure permits.

## Release governance

A MindGraph release must:

1. identify its exact upstream source commit;
2. pass the required CI, integration, license, and baseline checks;
3. include LICENSE, NOTICE, attribution, third-party notices, and an SBOM;
4. publish checksums and verifiable build provenance;
5. publish a signed OCI image under the Mindwalker namespace; and
6. document known incompatibilities, security limitations, and migration requirements.

Release tags are immutable. Alpha releases do not carry production support or compatibility
guarantees unless a separate commercial agreement states otherwise.

## Licensing boundary

Code already published in this repository remains under its applicable open-source license.
Mindwalker-authored modules may use separately documented terms in the future, but those terms must
not remove rights granted for upstream or previously published open-source code.
