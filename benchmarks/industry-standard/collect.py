#!/usr/bin/env python3
"""Normalize raw Graphalytics, LSQB, and OLAP logs into dashboard evidence."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GRAPHALYTICS_METRICS = [
    ("PR", "PageRank"),
    ("WCC", "Weakly connected components"),
    ("BFS", "Breadth-first search"),
    ("LCC", "Local clustering coefficient"),
    ("SSSP", "Single-source shortest paths"),
    ("CDLP", "Community detection label propagation"),
]
LSQB_METRICS = [(f"Q{index}", f"Query {index}") for index in range(1, 10)]
OLAP_METRICS = [
    ("one-hop-count", "1-hop count"),
    ("one-hop-ids", "1-hop IDs"),
    ("two-hop", "2-hop traversal"),
    ("three-hop", "3-hop traversal"),
    ("four-hop", "4-hop traversal"),
    ("five-hop", "5-hop traversal"),
    ("shortest-path", "Shortest Path"),
    ("connected-components", "Connected Components"),
    ("label-propagation", "Label Propagation"),
    ("pagerank-20", "PageRank (20 iter)"),
]

REFERENCE_PATH = Path(__file__).parent / "reference" / "arcadedb-benchmarks-2026-07-30.json"
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


def stats(values: list[float]) -> dict[str, Any]:
    if not values:
        raise ValueError("cannot summarize an empty result set")
    mean = statistics.fmean(values)
    standard_deviation = statistics.pstdev(values)
    return {
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "mean": mean,
        "standardDeviation": standard_deviation,
        "coefficientOfVariationPercent": 0 if mean == 0 else standard_deviation / mean * 100,
        "runs": values,
    }


def parse_graphalytics(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = payload.get("result", payload.get("experiments", {}))
    runs = result.get("runs", {})
    jobs = result.get("jobs", {})
    values: dict[str, list[float]] = {metric: [] for metric, _ in GRAPHALYTICS_METRICS}
    for run_id, run in runs.items():
        algorithm = next(
            (job.get("algorithm") for job in jobs.values() if run_id in job.get("runs", [])),
            None,
        )
        if algorithm in values and run.get("processing_time") is not None:
            values[algorithm].append(float(run["processing_time"]))
    missing = [metric for metric, entries in values.items() if not entries]
    if missing:
        raise ValueError(f"{path} has no processing time for: {', '.join(missing)}")
    return {metric: stats(entries) for metric, entries in values.items()}


GRAPH_TIMING_PATTERNS = {
    "PR": re.compile(r"\bPageRank time:\s*([0-9.]+)s"),
    "WCC": re.compile(r"\bWCC time:\s*([0-9.]+)s"),
    "BFS": re.compile(r"\bBFS time:\s*([0-9.]+)s"),
    "LCC": re.compile(r"\bLCC time:\s*([0-9.]+)s"),
    "SSSP": re.compile(r"\bSSSP time:\s*([0-9.]+)s"),
    "CDLP": re.compile(r"\bCDLP time:\s*([0-9.]+)s"),
}
GRAPH_FINGERPRINT_PATTERN = re.compile(r"\bVALIDATION\s+(PR|WCC|BFS|LCC|SSSP|CDLP):\s*(-?[0-9]+)")
GRAPH_SEMANTIC_PATTERN = re.compile(
    r"\bSEMANTIC_VALIDATION\s+(PR|WCC|BFS|LCC|SSSP|CDLP):\s+(PASS|FAIL)\b"
)


def parse_graph_workload(paths: list[Path]) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    timings: dict[str, list[float]] = {metric: [] for metric, _ in GRAPHALYTICS_METRICS}
    fingerprints: dict[str, set[str]] = {metric: set() for metric, _ in GRAPHALYTICS_METRICS}
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for metric, pattern in GRAPH_TIMING_PATTERNS.items():
            matches = pattern.findall(text)
            if len(matches) != 1:
                raise ValueError(f"{path} has {len(matches)} timings for {metric}; expected exactly one")
            timings[metric].append(float(matches[0]))
        run_fingerprints = GRAPH_FINGERPRINT_PATTERN.findall(text)
        if len(run_fingerprints) != len(GRAPHALYTICS_METRICS):
            raise ValueError(
                f"{path} has {len(run_fingerprints)} output fingerprints; "
                f"expected {len(GRAPHALYTICS_METRICS)}"
            )
        for metric, fingerprint in run_fingerprints:
            fingerprints[metric].add(fingerprint)
    missing = [metric for metric, entries in timings.items() if not entries]
    if missing:
        raise ValueError(f"graph workload logs have no timing for: {', '.join(missing)}")
    return ({metric: stats(entries) for metric, entries in timings.items()}, fingerprints)


def parse_semantic_graph_workload(
    paths: list[Path],
) -> tuple[dict[str, dict[str, Any]], dict[str, bool]]:
    timings: dict[str, list[float]] = {metric: [] for metric, _ in GRAPHALYTICS_METRICS}
    validations: dict[str, list[bool]] = {metric: [] for metric, _ in GRAPHALYTICS_METRICS}
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for metric, pattern in GRAPH_TIMING_PATTERNS.items():
            matches = pattern.findall(text)
            if len(matches) != 1:
                raise ValueError(f"{path} has {len(matches)} timings for {metric}; expected exactly one")
            timings[metric].append(float(matches[0]))
        run_validations = GRAPH_SEMANTIC_PATTERN.findall(text)
        if len(run_validations) != len(GRAPHALYTICS_METRICS):
            raise ValueError(
                f"{path} has {len(run_validations)} semantic validations; "
                f"expected {len(GRAPHALYTICS_METRICS)}"
            )
        for metric, state in run_validations:
            validations[metric].append(state == "PASS")
    return (
        {metric: stats(entries) for metric, entries in timings.items()},
        {metric: bool(entries) and all(entries) for metric, entries in validations.items()},
    )


LSQB_PATTERN = re.compile(r"\b(Q[1-9]) time:\s*([0-9.]+)s\s*\(count=(-?[0-9]+)\)")


def parse_lsqb(paths: list[Path]) -> tuple[dict[str, dict[str, Any]], int]:
    timings: dict[str, list[float]] = {metric: [] for metric, _ in LSQB_METRICS}
    validations: dict[str, list[bool]] = {metric: [] for metric, _ in LSQB_METRICS}
    for path in paths:
        matches = LSQB_PATTERN.findall(path.read_text(encoding="utf-8", errors="replace"))
        seen: set[str] = set()
        for query, seconds, count in matches:
            if query in seen:
                continue
            seen.add(query)
            timings[query].append(float(seconds))
            validations[query].append(int(count) == LSQB_EXPECTED_COUNTS[query])
        missing_in_run = [metric for metric, _ in LSQB_METRICS if metric not in seen]
        if missing_in_run:
            raise ValueError(f"{path} has no timing for: {', '.join(missing_in_run)}")
    missing = [metric for metric, entries in timings.items() if not entries]
    if missing:
        raise ValueError(f"LSQB logs have no timing for: {', '.join(missing)}")
    validated = sum(bool(entries) and all(entries) for entries in validations.values())
    return ({metric: stats(entries) for metric, entries in timings.items()}, validated)


OLAP_ROW = re.compile(r"^\s*│\s*(.*?)\s*│\s*(.*?)\s*│\s*(.*?)\s*│\s*([0-9.]+)x\s*│\s*$")


def parse_olap(path: Path) -> dict[str, float]:
    label_to_id = {label.lower(): metric for metric, label in OLAP_METRICS}
    label_to_id.update({
        "2-hop": "two-hop",
        "3-hop": "three-hop",
        "4-hop": "four-hop",
        "5-hop": "five-hop",
    })
    values: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = OLAP_ROW.match(line)
        if not match:
            continue
        label = match.group(1).strip().lower()
        if label in label_to_id:
            values[label_to_id[label]] = float(match.group(4))
    missing = [metric for metric, _ in OLAP_METRICS if metric not in values]
    if missing:
        raise ValueError(f"{path} has no OLAP speedup for: {', '.join(missing)}")
    return values


def _series_from_systems(
    evidence: Path,
    metadata: dict[str, Any],
    suite: str,
    parser,
) -> list[dict[str, Any]]:
    output = []
    for system in _systems_for_suite(metadata, suite):
        system_id = system["id"]
        if suite == "graphalytics":
            values = parser(evidence / suite / system_id / "results.json")
        elif suite == "lsqb":
            logs = sorted((evidence / suite / system_id).glob("run-*.log"))
            values, _ = parser(logs)
        else:
            values = parser(evidence / suite / f"{system_id}.log")
        output.append({
            "id": system_id,
            "label": system["label"],
            "kind": system["kind"],
            "values": values,
        })
    return output


def _systems_for_suite(metadata: dict[str, Any], suite: str) -> list[dict[str, Any]]:
    return [
        system
        for system in metadata["systems"]
        if suite in system.get("supports", ["graphalytics", "lsqb", "olap"])
    ]


def collect(evidence: Path) -> dict[str, Any]:
    metadata = json.loads((evidence / "metadata.json").read_text(encoding="utf-8"))
    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    graphalytics_series = []
    graph_fingerprints: list[dict[str, set[str]]] = []
    semantic_validations: list[dict[str, bool]] = []
    graph_systems = _systems_for_suite(metadata, "graphalytics")
    for system in graph_systems:
        logs = sorted((evidence / "graphalytics" / system["id"]).glob("run-*.log"))
        if system.get("validationMode", "fingerprint") == "semantic":
            values, semantic = parse_semantic_graph_workload(logs)
            semantic_validations.append(semantic)
        else:
            values, fingerprints = parse_graph_workload(logs)
            graph_fingerprints.append(fingerprints)
        graphalytics_series.append({
            "id": system["id"],
            "label": system["label"],
            "kind": system["kind"],
            "values": values,
        })
    lsqb_series = _series_from_systems(evidence, metadata, "lsqb", parse_lsqb)
    olap_series = _series_from_systems(evidence, metadata, "olap", parse_olap)

    lsqb_validation = []
    for system in _systems_for_suite(metadata, "lsqb"):
        _, passed = parse_lsqb(sorted((evidence / "lsqb" / system["id"]).glob("run-*.log")))
        lsqb_validation.append(passed)

    graph_validation = 0
    for metric, _ in GRAPHALYTICS_METRICS:
        fingerprints = [system[metric] for system in graph_fingerprints]
        fingerprints_match = (
            bool(fingerprints)
            and all(len(values) == 1 for values in fingerprints)
            and len(set.union(*fingerprints)) == 1
        )
        semantics_pass = all(system[metric] for system in semantic_validations)
        if fingerprints_match and semantics_pass:
            graph_validation += 1

    graphalytics_series.append({
        "id": "arcadedb-published",
        "label": "ArcadeDB published reference · graph500-22 / different host",
        "kind": "reference",
        "values": reference["graphalytics"]["embedded"],
    })
    lsqb_series.append({
        "id": "arcadedb-published",
        "label": "ArcadeDB published reference",
        "kind": "reference",
        "values": reference["lsqb"]["embedded"],
    })
    olap_series.append({
        "id": "arcadedb-published",
        "label": "ArcadeDB published reference",
        "kind": "reference",
        "values": reference["olapSpeedup"]["values"],
    })

    generated_at = metadata.get("generatedAt") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fingerprint_labels = ", ".join(
        system["label"]
        for system in graph_systems
        if system.get("validationMode", "fingerprint") == "fingerprint"
    )
    semantic_labels = ", ".join(
        system["label"]
        for system in graph_systems
        if system.get("validationMode") == "semantic"
    )
    return {
        "schemaVersion": 1,
        "title": metadata.get("title", "MindGraph reproducible graph benchmark"),
        "subtitle": metadata.get(
            "subtitle",
            "LDBC Graphalytics, LSQB SF1, and OLTP-to-OLAP measurements with reproducible raw evidence.",
        ),
        "generatedAt": generated_at,
        "status": "verified" if graph_validation == len(GRAPHALYTICS_METRICS) and all(value == 9 for value in lsqb_validation) else "partial",
        "release": metadata["release"],
        "environment": metadata["environment"],
        "methodology": metadata["methodology"],
        "suites": [
            {
                "id": "graphalytics",
                "title": "Graph algorithm execution",
                "description": "Six algorithms on datagen-7_5-fb. MindGraph and upstream use the public harness's native load-once runner; Neo4j uses a prebuilt GDS projection. Published graph500-22 values are contextual references.",
                "unit": "seconds",
                "lowerIsBetter": True,
                "metrics": [{"id": metric, "label": label} for metric, label in GRAPHALYTICS_METRICS],
                "series": graphalytics_series,
                "validation": {
                    "passed": graph_validation,
                    "total": 6,
                    "notes": [
                        f"Output fingerprints matched across all measured runs for {fingerprint_labels}.",
                        *(
                            [f"Complete-result semantic invariants passed in every measured run for {semantic_labels}."]
                            if semantic_labels
                            else []
                        ),
                        "This is reproducibility evidence, not official LDBC certification.",
                    ],
                },
            },
            {
                "id": "lsqb",
                "title": "LSQB SF1",
                "description": "The same nine Cypher pattern-matching queries on LSQB SF1: 3.95M vertices and 17.88M edges.",
                "unit": "seconds",
                "lowerIsBetter": True,
                "metrics": [{"id": metric, "label": label} for metric, label in LSQB_METRICS],
                "series": lsqb_series,
                "validation": {
                    "passed": min(lsqb_validation),
                    "total": 9,
                    "notes": ["Counts were checked against the official LSQB SF1 expected output."],
                },
            },
            {
                "id": "olap-speedup",
                "title": "Graph analytical view speedup",
                "description": "Same 500K-vertex, approximately 8M-edge graph queried through OLTP and CSR-backed analytical paths.",
                "unit": "ratio",
                "lowerIsBetter": False,
                "metrics": [{"id": metric, "label": label} for metric, label in OLAP_METRICS],
                "series": olap_series,
                "validation": {
                    "passed": len(OLAP_METRICS),
                    "total": len(OLAP_METRICS),
                    "countsTowardTotal": False,
                    "label": f"{len(OLAP_METRICS)} of {len(OLAP_METRICS)} speedup rows parsed.",
                    "notes": [
                        "Speedup is OLTP elapsed time divided by OLAP elapsed time on the same process.",
                        "The inherited workload is directional and does not provide conformance assertions for these rows.",
                    ],
                },
            },
        ],
        "artifacts": metadata["artifacts"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="directory containing raw evidence")
    parser.add_argument("output", type=Path, help="normalized result JSON")
    args = parser.parse_args()
    result = collect(args.evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"result: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
