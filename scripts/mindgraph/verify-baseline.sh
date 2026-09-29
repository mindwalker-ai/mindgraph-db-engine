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
properties_file="$repository_root/.mindgraph/baseline.properties"

fail() {
    echo "baseline verification failed: $*" >&2
    exit 1
}

property() {
    local key="$1"
    awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "$properties_file"
}

test -f "$properties_file" || fail "missing .mindgraph/baseline.properties"

mindgraph_version="$(property mindgraph.version)"
stable_tag="$(property upstream.stableTag)"
stable_commit="$(property upstream.stableCommit)"
base_commit="$(property upstream.baseCommit)"
upstream_maven_version="$(property upstream.mavenVersion)"
benchmark_harness_sha256="$(property benchmark.harnessSha256)"

test "$(tr -d '[:space:]' < "$repository_root/MINDGRAPH_VERSION")" = "$mindgraph_version" ||
    fail "MINDGRAPH_VERSION does not match baseline.properties"

actual_maven_version="$(
    cd "$repository_root"
    ./mvnw -q -DforceStdout help:evaluate -Dexpression=project.version
)"
test "$actual_maven_version" = "$upstream_maven_version" ||
    fail "root Maven version is $actual_maven_version, expected $upstream_maven_version"

git -C "$repository_root" cat-file -e "$base_commit^{commit}" 2>/dev/null ||
    fail "upstream base commit $base_commit is not available"
git -C "$repository_root" merge-base --is-ancestor "$base_commit" HEAD ||
    fail "upstream base commit $base_commit is not an ancestor of HEAD"
git -C "$repository_root" cat-file -e "$stable_commit^{commit}" 2>/dev/null ||
    fail "stable anchor commit $stable_commit is not available"
git -C "$repository_root" merge-base --is-ancestor "$stable_commit" "$base_commit" ||
    fail "stable anchor commit is not an ancestor of the exact upstream source"
git -C "$repository_root" diff --quiet "$base_commit" -- engine/src/main ||
    fail "engine/src/main differs from the declared upstream baseline"

if git -C "$repository_root" rev-parse --verify --quiet "$stable_tag^{}" >/dev/null; then
    resolved_stable_commit="$(git -C "$repository_root" rev-parse "$stable_tag^{}")"
    test "$resolved_stable_commit" = "$stable_commit" ||
        fail "stable tag $stable_tag resolves to $resolved_stable_commit, expected $stable_commit"
else
    echo "stable tag ref $stable_tag is not mirrored in this checkout; verified its recorded commit and ancestry"
fi

for required_path in LICENSE NOTICE ATTRIBUTIONS.md THIRD_PARTY_NOTICES.md UPSTREAM.md MINDGRAPH_VERSION; do
    test -e "$repository_root/$required_path" || fail "missing $required_path"
done

benchmark_harness="$repository_root/engine/src/test/java/com/mindwalker/mindgraph/benchmark/MindGraphBaselineBenchmark.java"
test -f "$benchmark_harness" || fail "missing MindGraph baseline benchmark harness"
if command -v sha256sum >/dev/null 2>&1; then
    actual_benchmark_sha256="$(sha256sum "$benchmark_harness" | awk '{ print $1 }')"
else
    actual_benchmark_sha256="$(shasum -a 256 "$benchmark_harness" | awk '{ print $1 }')"
fi
test "$actual_benchmark_sha256" = "$benchmark_harness_sha256" ||
    fail "benchmark harness checksum does not match baseline.properties"

if grep -R -n -E 'secrets\.(DOCKER_USERNAME|DOCKER_PASSWORD|MAVEN_CENTRAL_USERNAME|MAVEN_CENTRAL_PASSWORD|MAVEN_GPG_PRIVATE_KEY|MAVEN_GPG_PASSPHRASE|CLAUDE_CODE_OAUTH_TOKEN|CODACY_PROJECT_TOKEN|CODECOV_TOKEN)' "$repository_root/.github/workflows"; then
    fail "active workflows still reference upstream or unconfigured third-party release secrets"
fi

if grep -R -n -E 'uses: [^[:space:]@]+@(main|master|v[0-9]+([[:space:]]|$))' "$repository_root/.github/workflows"; then
    fail "GitHub Actions must be pinned to immutable commit SHAs"
fi

git -C "$repository_root" diff --check

(
    cd "$repository_root"
    ./mvnw -B -ntp -q -pl engine -am -DskipTests validate
)

echo "MindGraph DB Engine baseline $mindgraph_version verified"
echo "upstream stable anchor: $stable_tag ($stable_commit)"
echo "exact upstream source: $base_commit ($upstream_maven_version)"
