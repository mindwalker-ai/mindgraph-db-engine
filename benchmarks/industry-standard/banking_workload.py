#!/usr/bin/env python3
"""Generate and run the reproducible synthetic banking query workload."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import statistics
import time
from pathlib import Path
from typing import Any


DEFAULT_ACCOUNTS = 50_000
DEFAULT_DEVICES = 10_000
DEFAULT_TRANSFERS = 500_000
DEFAULT_SEED = 20_260_930

BANKING_QUERIES: dict[str, dict[str, Any]] = {
    "B1": {
        "title": "Telusuri aliran dana",
        "question": "Dana dari satu rekening mengalir ke mana saja sampai tiga tingkat?",
        "pattern": "Traversal 1-3 tingkat",
        "query": (
            "MATCH (source:Account {accountNo: $accountNo})"
            "-[:TRANSFERRED_TO*1..3]->(destination:Account) "
            "RETURN count(*) AS result"
        ),
        "parameters": {"accountNo": "A000000"},
    },
    "B2": {
        "title": "Deteksi transaksi berputar",
        "question": "Apakah dana kembali lagi ke rekening asal melalui beberapa rekening?",
        "pattern": "Pencarian siklus 2-5 tingkat",
        "query": (
            "MATCH (account:Account {accountNo: $accountNo})"
            "-[:TRANSFERRED_TO*2..5]->"
            "(destination:Account {accountNo: $accountNo}) "
            "RETURN count(*) AS result"
        ),
        "parameters": {"accountNo": "A000000"},
    },
    "B3": {
        "title": "Rekening dengan perangkat yang sama",
        "question": "Berapa pasangan rekening yang menggunakan device yang sama?",
        "pattern": "Relasi melalui shared node",
        "query": (
            "MATCH (first:Account)-[:USES_DEVICE]->"
            "(device:Device {deviceId: $deviceId})<-[:USES_DEVICE]-(second:Account) "
            "WHERE first.accountNo < second.accountNo RETURN count(*) AS result"
        ),
        "parameters": {"deviceId": "D00000"},
    },
    "B4": {
        "title": "Banyak transaksi kecil ke satu rekening",
        "question": "Berapa rekening yang menerima transaksi kecil dari sedikitnya lima sumber?",
        "pattern": "Fan-in dan agregasi transaksi",
        "query": (
            "MATCH (source:Account)-[txn:TRANSFERRED_TO]->(target:Account) "
            "WHERE txn.timestamp >= $startTime AND txn.timestamp < $endTime "
            "AND txn.amount < $threshold "
            "WITH target, count(DISTINCT source) AS sourceCount "
            "WHERE sourceCount >= 5 RETURN count(*) AS result"
        ),
        "parameters": {
            "startTime": 0,
            "endTime": 9_999_999_999_999,
            "threshold": 5_000_000,
        },
    },
    "B5": {
        "title": "Counterparty paling sentral",
        "question": "Berapa jumlah counterparty unik tertinggi pada satu rekening?",
        "pattern": "Degree centrality sederhana",
        "query": (
            "MATCH (source:Account)-[:TRANSFERRED_TO]->(target:Account) "
            "WITH target, count(DISTINCT source) AS uniqueCounterparties "
            "RETURN max(uniqueCounterparties) AS result"
        ),
        "parameters": {},
    },
}

BANKING_RESULT_PATTERN = re.compile(
    r"^\s{2}(B[1-5]) time:\s*([0-9.]+)s \(result=(-?[0-9]+)\)$",
    re.MULTILINE,
)


def _account(index: int) -> str:
    return f"A{index:06d}"


def _device(index: int) -> str:
    return f"D{index:05d}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def update_evidence_manifest(evidence: Path) -> None:
    path = evidence / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entries = {entry["path"]: entry for entry in manifest["files"]}
    for artifact in sorted(evidence.glob("banking-*")):
        if artifact.is_file():
            entries[artifact.name] = {
                "path": artifact.name,
                "bytes": artifact.stat().st_size,
                "sha256": _sha256(artifact),
            }
    manifest["files"] = [entries[name] for name in sorted(entries)]
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def generate_dataset(
    output: Path,
    *,
    accounts: int = DEFAULT_ACCOUNTS,
    devices: int = DEFAULT_DEVICES,
    transfers: int = DEFAULT_TRANSFERS,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    if accounts < 10 or devices < 1 or transfers < 10:
        raise ValueError("dataset dimensions are too small")
    output.mkdir(parents=True, exist_ok=True)

    accounts_path = output / "accounts.csv"
    with accounts_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["accountNo:ID(Account)", ":LABEL"])
        for index in range(accounts):
            writer.writerow([_account(index), "Account"])

    devices_path = output / "devices.csv"
    with devices_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["deviceId:ID(Device)", ":LABEL"])
        for index in range(devices):
            writer.writerow([_device(index), "Device"])

    device_edges_path = output / "uses_device.csv"
    with device_edges_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([":START_ID(Account)", ":END_ID(Device)", ":TYPE"])
        for index in range(accounts):
            writer.writerow([_account(index), _device(index % devices), "USES_DEVICE"])

    special_edges = [(0, 1), (1, 0), (0, 2), (2, 3), (3, 0)]
    transfer_edges_path = output / "transfers.csv"
    with transfer_edges_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            ":START_ID(Account)",
            ":END_ID(Account)",
            "amount:long",
            "timestamp:long",
            ":TYPE",
        ])
        for edge_index in range(transfers):
            if edge_index < len(special_edges):
                source, target = special_edges[edge_index]
            else:
                source = edge_index % accounts
                round_index = edge_index // accounts
                target = (source * 7_919 + round_index * 104_729 + seed + 17) % accounts
                if target == source:
                    target = (target + 1) % accounts
            amount = 10_000 + ((edge_index * 48_271 + seed) % 9_000_000)
            timestamp = 1_767_225_600_000 + ((edge_index * 86_399 + seed) % 31_536_000_000)
            writer.writerow([
                _account(source),
                _account(target),
                amount,
                timestamp,
                "TRANSFERRED_TO",
            ])

    files = [accounts_path, devices_path, device_edges_path, transfer_edges_path]
    manifest = {
        "schemaVersion": 1,
        "kind": "synthetic-banking-graph",
        "seed": seed,
        "counts": {
            "accounts": accounts,
            "devices": devices,
            "transfers": transfers,
            "usesDevice": accounts,
        },
        "files": {path.name: _sha256(path) for path in files},
        "queries": BANKING_QUERIES,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def _driver():
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7689"),
        auth=(
            os.environ.get("NEO4J_USERNAME", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "benchmark-only"),
        ),
    )


def prepare_neo4j(driver) -> None:
    statements = [
        "CREATE CONSTRAINT account_number IF NOT EXISTS FOR (a:Account) REQUIRE a.accountNo IS UNIQUE",
        "CREATE CONSTRAINT device_id IF NOT EXISTS FOR (d:Device) REQUIRE d.deviceId IS UNIQUE",
        "CALL db.awaitIndexes(300)",
    ]
    with driver.session(database="neo4j") as session:
        for statement in statements:
            session.run(statement).consume()


def run_neo4j(*, prepare: bool = False) -> dict[str, int]:
    driver = _driver()
    results: dict[str, int] = {}
    try:
        driver.verify_connectivity()
        if prepare:
            prepare_neo4j(driver)
        for query_id, definition in BANKING_QUERIES.items():
            started = time.perf_counter()
            with driver.session(database="neo4j") as session:
                row = session.run(
                    definition["query"],
                    definition["parameters"],
                ).single(strict=True)
            elapsed = time.perf_counter() - started
            result = int(row["result"])
            results[query_id] = result
            print(f"  {query_id} time: {elapsed:.6f}s (result={result})", flush=True)
    finally:
        driver.close()
    return results


def _stats(values: list[float]) -> dict[str, Any]:
    mean = statistics.fmean(values)
    deviation = statistics.pstdev(values)
    return {
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "mean": mean,
        "standardDeviation": deviation,
        "coefficientOfVariationPercent": 0 if mean == 0 else deviation / mean * 100,
        "runs": values,
    }


def parse_banking_results(paths: list[Path]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    if not paths:
        raise ValueError("banking result paths must not be empty")
    timings: dict[str, list[float]] = {query_id: [] for query_id in BANKING_QUERIES}
    results: dict[str, set[int]] = {query_id: set() for query_id in BANKING_QUERIES}
    for path in paths:
        matches = BANKING_RESULT_PATTERN.findall(path.read_text(encoding="utf-8", errors="replace"))
        seen: set[str] = set()
        for query_id, seconds, result in matches:
            if query_id in seen:
                raise ValueError(f"{path} contains duplicate measured result for {query_id}")
            seen.add(query_id)
            timings[query_id].append(float(seconds))
            results[query_id].add(int(result))
        missing = set(BANKING_QUERIES).difference(seen)
        if missing:
            raise ValueError(f"{path} has no measured result for: {', '.join(sorted(missing))}")
    unstable = [query_id for query_id, values in results.items() if len(values) != 1]
    if unstable:
        raise ValueError(f"banking results changed between runs: {', '.join(unstable)}")
    return (
        {query_id: _stats(values) for query_id, values in timings.items()},
        {query_id: next(iter(values)) for query_id, values in results.items()},
    )


def summarize_banking(
    evidence: Path,
    source: Path,
    output: Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    data = json.loads(source.read_text(encoding="utf-8"))
    if generated_at:
        data["generatedAt"] = generated_at
    systems = {
        "mindgraph": sorted(evidence.glob("banking-mindgraph-run-*.txt")),
        "neo4j": sorted(evidence.glob("banking-neo4j-run-*.txt")),
    }
    parsed: dict[str, dict[str, dict[str, Any]]] = {}
    results: dict[str, dict[str, int]] = {}
    for system_id, paths in systems.items():
        parsed[system_id], results[system_id] = parse_banking_results(paths)
    if results["mindgraph"] != results["neo4j"]:
        raise ValueError("MindGraphDB and Neo4j returned different banking results")
    update_evidence_manifest(evidence)

    display = {
        "mindgraph": {"label": "MindGraphDB", "kind": "measured"},
        "neo4j": {"label": "Neo4j Community + GDS", "kind": "competitor"},
    }
    series = []
    for system_id in systems:
        series.append({
            "id": system_id,
            "label": display[system_id]["label"],
            "kind": display[system_id]["kind"],
            "values": parsed[system_id],
        })

    wins = {"mindgraph": 0, "neo4j": 0}
    for query_id in BANKING_QUERIES:
        winner = min(systems, key=lambda system_id: parsed[system_id][query_id]["median"])
        wins[winner] += 1

    suite = {
        "id": "banking",
        "title": "Query perbankan sintetis",
        "description": (
            "Five measured Cypher queries on the same deterministic synthetic graph: "
            "50,000 accounts, 10,000 devices, 500,000 transfers, and 50,000 device links."
        ),
        "plainDescription": "5 query pada 50 ribu rekening dan 500 ribu transaksi sintetis.",
        "takeaway": (
            f"MindGraphDB unggul pada {wins['mindgraph']} query; "
            f"Neo4j unggul pada {wins['neo4j']} query."
        ),
        "unit": "seconds",
        "lowerIsBetter": True,
        "metrics": [
            {
                "id": query_id,
                "label": definition["title"],
                "purpose": definition["question"],
                "query": definition["query"],
                "parameters": definition["parameters"],
            }
            for query_id, definition in BANKING_QUERIES.items()
        ],
        "series": series,
        "validation": {
            "passed": len(BANKING_QUERIES),
            "total": len(BANKING_QUERIES),
            "plainLabel": "5 dari 5 hasil query identik.",
            "plainNote": "MindGraphDB dan Neo4j mengembalikan nilai yang sama pada seluruh pengulangan.",
            "notes": [
                "All queries used the same deterministic synthetic dataset and parameters.",
                "Every scalar result was stable across five measured runs and identical across engines.",
                "Synthetic results demonstrate query behavior; they are not production sizing guidance.",
            ],
        },
    }
    data["suites"] = [item for item in data["suites"] if item["id"] != "banking"] + [suite]
    data.pop("bankingQueryExamples", None)
    presentation = data.setdefault("presentation", {})
    suite_ids = presentation.setdefault("suiteIds", [])
    if "banking" not in suite_ids:
        suite_ids.append("banking")
    data["audienceSummary"] = {
        "intro": "",
        "highlights": [
            {"title": "8 dari 9 LSQB", "detail": "MindGraphDB lebih cepat."},
            {
                "title": f"{wins['mindgraph']} vs {wins['neo4j']} query banking",
                "detail": "Pemenang bergantung pada pola query.",
            },
            {"title": "20/20 valid", "detail": "Semua hasil perhitungan benar."},
        ],
        "readingGuide": "Angka waktu yang lebih kecil berarti lebih cepat.",
    }
    banking_method = (
        "The synthetic banking comparison uses 50,000 accounts, 10,000 devices, "
        "500,000 transfers, five exact Cypher queries, one warm-up, and five measured runs."
    )
    banking_disclosure = (
        "The banking graph is deterministic and synthetic; it demonstrates query behavior, "
        "not a bank's production distribution, concurrency, or capacity requirement."
    )
    if banking_method not in data["methodology"]["summary"]:
        data["methodology"]["summary"].append(banking_method)
    if banking_disclosure not in data["methodology"]["disclosures"]:
        data["methodology"]["disclosures"].append(banking_disclosure)
    artifact_paths = {artifact["path"] for artifact in data["artifacts"]}
    for label, path in [
        ("Synthetic banking dataset manifest", "evidence/banking-dataset-manifest.json"),
        ("Synthetic banking dataset checksums", "evidence/banking-dataset-sha256.txt"),
        ("MindGraphDB banking run", "evidence/banking-mindgraph-run-1.txt"),
        ("Neo4j banking run", "evidence/banking-neo4j-run-1.txt"),
        ("Neo4j banking import", "evidence/banking-neo4j-import.txt"),
        ("Banking runtime fingerprint", "evidence/banking-runtime.txt"),
    ]:
        if path not in artifact_paths:
            data["artifacts"].append({"label": label, "path": path})
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("output", type=Path)
    generate.add_argument("--accounts", type=int, default=DEFAULT_ACCOUNTS)
    generate.add_argument("--devices", type=int, default=DEFAULT_DEVICES)
    generate.add_argument("--transfers", type=int, default=DEFAULT_TRANSFERS)
    generate.add_argument("--seed", type=int, default=DEFAULT_SEED)
    neo4j = subparsers.add_parser("neo4j")
    neo4j.add_argument("--prepare", action="store_true")
    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("evidence", type=Path)
    summarize.add_argument("source", type=Path)
    summarize.add_argument("output", type=Path)
    summarize.add_argument("--generated-at")
    args = parser.parse_args()
    if args.command == "generate":
        manifest = generate_dataset(
            args.output,
            accounts=args.accounts,
            devices=args.devices,
            transfers=args.transfers,
            seed=args.seed,
        )
        print(json.dumps(manifest["counts"], sort_keys=True))
    elif args.command == "neo4j":
        run_neo4j(prepare=args.prepare)
    else:
        summarize_banking(
            args.evidence,
            args.source,
            args.output,
            generated_at=args.generated_at,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
