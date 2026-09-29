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
distribution_directory="$repository_root/dist"

property() {
    local key="$1"
    awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); print; exit }' "$properties_file"
}

mindgraph_version="$(tr -d '[:space:]' < "$repository_root/MINDGRAPH_VERSION")"
maven_version="$(property upstream.mavenVersion)"
upstream_commit="$(property upstream.baseCommit)"

rm -rf "$distribution_directory"
mkdir -p "$distribution_directory"

(
    cd "$repository_root"
    ./mvnw -B -ntp clean package -DskipTests -pl package -am
    ./mvnw -B -ntp org.cyclonedx:cyclonedx-maven-plugin:2.9.3:makeAggregateBom -DskipTests -DschemaVersion=1.6 -DoutputFormat=all "-DoutputName=mindgraph-db-engine-$mindgraph_version-sbom"
)

source_prefix="$repository_root/package/target/arcadedb-$maven_version"
test -f "$source_prefix.tar.gz"
test -f "$source_prefix.zip"

cp "$source_prefix.tar.gz" "$distribution_directory/mindgraph-db-engine-$mindgraph_version.tar.gz"
cp "$source_prefix.zip" "$distribution_directory/mindgraph-db-engine-$mindgraph_version.zip"

for format in json xml; do
    sbom="$repository_root/target/mindgraph-db-engine-$mindgraph_version-sbom.$format"
    test -f "$sbom"
    cp "$sbom" "$distribution_directory/"
done

for legal_file in LICENSE NOTICE ATTRIBUTIONS.md THIRD_PARTY_NOTICES.md UPSTREAM.md; do
    cp "$repository_root/$legal_file" "$distribution_directory/"
done

{
    printf 'mindgraph.version=%s\n' "$mindgraph_version"
    printf 'source.commit=%s\n' "$(git -C "$repository_root" rev-parse HEAD)"
    printf 'upstream.commit=%s\n' "$upstream_commit"
    printf 'upstream.mavenVersion=%s\n' "$maven_version"
} > "$distribution_directory/BUILD-MANIFEST.properties"

(
    cd "$distribution_directory"
    : > SHA256SUMS
    for file in *; do
        test "$file" = SHA256SUMS && continue
        if command -v sha256sum >/dev/null 2>&1; then
            sha256sum "$file" >> SHA256SUMS
        else
            shasum -a 256 "$file" >> SHA256SUMS
        fi
    done

    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c SHA256SUMS
    else
        shasum -a 256 -c SHA256SUMS
    fi
)

echo "staged MindGraph DB Engine $mindgraph_version in $distribution_directory"
