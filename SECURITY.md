# MindGraph DB Engine security policy

Mindwalker takes vulnerabilities in MindGraph DB Engine and its inherited ArcadeDB components
seriously.

## Report a vulnerability

Do not open a public issue. Use
[GitHub private vulnerability reporting](https://github.com/mindwalker-ai/mindgraph-db-engine/security/advisories/new)
and include:

- affected MindGraph version, commit, and component;
- impact and expected attack prerequisites;
- minimal reproduction steps or a proof of concept;
- operating system, JVM, deployment mode, and relevant configuration; and
- logs or packet captures with credentials and customer data removed.

Mindwalker will coordinate inherited vulnerabilities with ArcadeDB or another upstream maintainer
when appropriate. Do not report a MindGraph deployment credential or customer incident to the
upstream project.

## Supported versions

Until a stable MindGraph release exists, only the newest tagged alpha baseline is eligible for
security fixes. Older alpha builds are unsupported and must be upgraded.

| Version | Status |
| --- | --- |
| Latest tagged MindGraph alpha | Best-effort security fixes |
| Untagged snapshots | Development only |
| Older alpha baselines | Unsupported |

Service-level response commitments will be published before general availability. This policy does
not promise a response SLA.

## Disclosure

Mindwalker follows coordinated disclosure. Please allow reasonable time to investigate and release
a fix before public disclosure. Do not access data or systems that you do not own or have explicit
authorization to test.

## Scope

Reports may cover the engine fork, MindGraph packaging, official container images, build and release
pipelines, and Mindwalker-authored modules in this repository. Third-party applications that merely
use MindGraph DB Engine are outside this repository's scope.
