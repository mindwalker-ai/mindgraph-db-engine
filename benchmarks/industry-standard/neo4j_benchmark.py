#!/usr/bin/env python3
"""Run the Neo4j lanes used by the MindGraph same-host benchmark."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

GRAPH_NODE_COUNT = 633_432
LSQB_EXPECTED_COUNTS = {
    "Q1": 221_636_419,
    "Q2": 1_085_627,
    "Q3": 753_570,
    "Q4": 14_836_038,
    "Q5": 13_824_510,
    "Q6": 1_668_134_320,
    "Q7": 26_190_133,
    "Q8": 6_907_213,
    "Q9": 1_596_153_418,
}


def _driver():
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7688"),
        auth=(
            os.environ.get("NEO4J_USERNAME", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "benchmark-only"),
        ),
    )


def _single(
    driver,
    query: str,
    *,
    timeout_seconds: float | None = None,
    **parameters: Any,
) -> dict[str, Any]:
    if timeout_seconds is not None:
        from neo4j import Query

        query = Query(query, timeout=timeout_seconds)
    with driver.session(database="neo4j") as session:
        record = session.run(query, parameters).single(strict=True)
        return dict(record)


def _timed(
    driver,
    query: str,
    *,
    timeout_seconds: float | None = None,
    **parameters: Any,
) -> tuple[float, dict[str, Any]]:
    started = time.perf_counter()
    result = _single(driver, query, timeout_seconds=timeout_seconds, **parameters)
    return time.perf_counter() - started, result


def _pass(metric: str, condition: bool, detail: str) -> None:
    state = "PASS" if condition else "FAIL"
    print(f"  SEMANTIC_VALIDATION {metric}: {state} {detail}")
    if not condition:
        raise RuntimeError(f"Neo4j {metric} semantic validation failed: {detail}")


def _ensure_projection(driver) -> None:
    exists = _single(driver, "CALL gds.graph.exists('bench') YIELD exists RETURN exists")["exists"]
    if exists:
        return
    elapsed, result = _timed(
        driver,
        """
        CALL gds.graph.project(
          'bench',
          'Node',
          {EDGE: {orientation: 'UNDIRECTED', properties: 'weight'}},
          {readConcurrency: 4}
        )
        YIELD nodeCount, relationshipCount, projectMillis
        RETURN nodeCount, relationshipCount, projectMillis
        """,
    )
    print(
        "  Projection: "
        f"nodes={result['nodeCount']} relationships={result['relationshipCount']} "
        f"server={result['projectMillis'] / 1000:.3f}s wall={elapsed:.3f}s"
    )
    if result["nodeCount"] != GRAPH_NODE_COUNT:
        raise RuntimeError(f"Neo4j projection has {result['nodeCount']} nodes")


def run_graph() -> None:
    driver = _driver()
    try:
        driver.verify_connectivity()
        neo4j = _single(
            driver,
            """
            CALL dbms.components() YIELD name, versions
            WHERE name = 'Neo4j Kernel'
            RETURN versions[0] AS version
            """,
        )["version"]
        gds = _single(driver, "RETURN gds.version() AS version")["version"]
        print(f"Neo4j version: {neo4j}")
        print(f"GDS version: {gds}")
        print("GDS concurrency: 4")
        _ensure_projection(driver)
        source = _single(
            driver,
            "MATCH (n:Node {id: 6}) RETURN id(n) AS nodeId",
        )["nodeId"]

        queries = [
            (
                "PR",
                "PageRank",
                """
                CALL gds.pageRank.stream('bench', {
                  dampingFactor: 0.85, maxIterations: 10, tolerance: 0.0,
                  concurrency: 4, logProgress: false
                })
                YIELD nodeId, score
                RETURN count(*) AS rows, sum(score) AS checksum, max(score) AS maximum
                """,
                lambda row: row["rows"] == GRAPH_NODE_COUNT and row["checksum"] > 0,
            ),
            (
                "WCC",
                "WCC",
                """
                CALL gds.wcc.stream('bench', {concurrency: 4, logProgress: false})
                YIELD nodeId, componentId
                RETURN count(*) AS rows, count(DISTINCT componentId) AS components
                """,
                lambda row: row["rows"] == GRAPH_NODE_COUNT and row["components"] == 1,
            ),
            (
                "BFS",
                "BFS",
                """
                CALL gds.bfs.stream('bench', {
                  sourceNode: $source, concurrency: 4, logProgress: false
                })
                YIELD nodeIds
                RETURN size(nodeIds) AS reached
                """,
                lambda row: row["reached"] == GRAPH_NODE_COUNT,
            ),
            (
                "LCC",
                "LCC",
                """
                CALL gds.localClusteringCoefficient.stream('bench', {
                  concurrency: 4, logProgress: false
                })
                YIELD nodeId, localClusteringCoefficient
                RETURN count(*) AS rows, sum(localClusteringCoefficient) AS checksum,
                       max(localClusteringCoefficient) AS maximum
                """,
                lambda row: row["rows"] == GRAPH_NODE_COUNT and 0 <= row["maximum"] <= 1,
            ),
            (
                "SSSP",
                "SSSP",
                """
                CALL gds.allShortestPaths.delta.stream('bench', {
                  sourceNode: $source, relationshipWeightProperty: 'weight',
                  delta: 2.0, concurrency: 4, logProgress: false
                })
                YIELD targetNode, totalCost
                RETURN count(*) AS reached, sum(totalCost) AS checksum,
                       max(totalCost) AS maximum
                """,
                lambda row: row["reached"] == GRAPH_NODE_COUNT and row["maximum"] >= 0,
            ),
            (
                "CDLP",
                "CDLP",
                """
                CALL gds.labelPropagation.stream('bench', {
                  maxIterations: 10, concurrency: 4, logProgress: false
                })
                YIELD nodeId, communityId
                RETURN count(*) AS rows, count(DISTINCT communityId) AS communities
                """,
                lambda row: row["rows"] == GRAPH_NODE_COUNT and row["communities"] >= 1,
            ),
        ]

        for metric, label, query, validator in queries:
            elapsed, result = _timed(driver, query, source=source)
            print(f"  {label} time: {elapsed:.3f}s")
            detail = " ".join(f"{key}={value}" for key, value in result.items())
            _pass(metric, validator(result), detail)
    finally:
        driver.close()


def _load_lsqb_queries(harness_root: Path) -> dict[str, str]:
    lsqb_root = harness_root / "lsqb"
    sys.path.insert(0, str(lsqb_root))
    try:
        from systems._common import CYPHER_QUERIES  # type: ignore[import-not-found]

        return dict(CYPHER_QUERIES)
    finally:
        sys.path.remove(str(lsqb_root))


def run_lsqb(harness_root: Path, timeout_seconds: float | None) -> None:
    queries = _load_lsqb_queries(harness_root)
    driver = _driver()
    try:
        driver.verify_connectivity()
        for index in range(1, 10):
            query_id = f"Q{index}"
            elapsed, result = _timed(
                driver,
                queries[query_id.lower()],
                timeout_seconds=timeout_seconds,
            )
            count = int(result["count"])
            print(f"  {query_id} time: {elapsed:.3f}s  (count={count})")
            if count != LSQB_EXPECTED_COUNTS[query_id]:
                raise RuntimeError(
                    f"{query_id} count {count} != {LSQB_EXPECTED_COUNTS[query_id]}"
                )
    finally:
        driver.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("graph")
    lsqb = subparsers.add_parser("lsqb")
    lsqb.add_argument("--harness-root", type=Path, required=True)
    lsqb.add_argument(
        "--query-timeout-seconds",
        type=float,
        help="optional server-enforced transaction timeout; omitted for the published run",
    )
    args = parser.parse_args()
    if args.command == "graph":
        run_graph()
    else:
        run_lsqb(args.harness_root, args.query_timeout_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
