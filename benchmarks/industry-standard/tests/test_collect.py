import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "collect.py"
SPEC = importlib.util.spec_from_file_location("benchmark_collect", MODULE_PATH)
collect = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(collect)


class CollectTest(unittest.TestCase):
    def test_stats_uses_median_and_preserves_runs(self):
        result = collect.stats([3.0, 1.0, 2.0])
        self.assertEqual(2.0, result["median"])
        self.assertEqual(1.0, result["min"])
        self.assertEqual(3.0, result["max"])
        self.assertAlmostEqual(40.824829, result["coefficientOfVariationPercent"], places=5)
        self.assertEqual([3.0, 1.0, 2.0], result["runs"])

    def test_parses_graphalytics_report(self):
        jobs = {}
        runs = {}
        for index, (metric, _) in enumerate(collect.GRAPHALYTICS_METRICS):
            run_id = f"run-{index}"
            jobs[f"job-{index}"] = {"algorithm": metric, "runs": [run_id]}
            runs[run_id] = {"processing_time": index + 0.25}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps({"result": {"jobs": jobs, "runs": runs}}), encoding="utf-8")
            parsed = collect.parse_graphalytics(path)
        self.assertEqual(0.25, parsed["PR"]["median"])
        self.assertEqual(5.25, parsed["CDLP"]["median"])

    def test_parses_native_graph_runs_and_fingerprints(self):
        timing_labels = {
            "PR": "PageRank",
            "WCC": "WCC",
            "BFS": "BFS",
            "LCC": "LCC",
            "SSSP": "SSSP",
            "CDLP": "CDLP",
        }
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for run in range(1, 4):
                lines = []
                for index, (metric, _) in enumerate(collect.GRAPHALYTICS_METRICS, start=1):
                    lines.append(f"  {timing_labels[metric]} time: {index + run / 10}s")
                    lines.append(f"  VALIDATION {metric}: {1000 + index}")
                path = Path(directory) / f"run-{run}.log"
                path.write_text("\n".join(lines), encoding="utf-8")
                paths.append(path)
            parsed, fingerprints = collect.parse_graph_workload(paths)
        self.assertEqual(1.2, parsed["PR"]["median"])
        self.assertEqual({"1001"}, fingerprints["PR"])

    def test_rejects_graph_run_without_complete_fingerprints(self):
        timing_labels = {
            "PR": "PageRank",
            "WCC": "WCC",
            "BFS": "BFS",
            "LCC": "LCC",
            "SSSP": "SSSP",
            "CDLP": "CDLP",
        }
        lines = [
            f"{timing_labels[metric]} time: 0.1s"
            for metric, _ in collect.GRAPHALYTICS_METRICS
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-1.log"
            path.write_text("\n".join(lines), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "output fingerprints"):
                collect.parse_graph_workload([path])

    def test_parses_semantic_graph_runs(self):
        timing_labels = {
            "PR": "PageRank",
            "WCC": "WCC",
            "BFS": "BFS",
            "LCC": "LCC",
            "SSSP": "SSSP",
            "CDLP": "CDLP",
        }
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for run in range(1, 3):
                lines = []
                for index, (metric, _) in enumerate(collect.GRAPHALYTICS_METRICS, start=1):
                    lines.append(f"  {timing_labels[metric]} time: {index + run / 10}s")
                    lines.append(f"  SEMANTIC_VALIDATION {metric}: PASS rows=633432")
                path = Path(directory) / f"run-{run}.log"
                path.write_text("\n".join(lines), encoding="utf-8")
                paths.append(path)
            parsed, validations = collect.parse_semantic_graph_workload(paths)
        self.assertEqual(1.15, parsed["PR"]["median"])
        self.assertTrue(all(validations.values()))

    def test_semantic_graph_validation_requires_every_run_to_pass(self):
        timing_labels = {
            "PR": "PageRank",
            "WCC": "WCC",
            "BFS": "BFS",
            "LCC": "LCC",
            "SSSP": "SSSP",
            "CDLP": "CDLP",
        }
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for run in range(1, 3):
                lines = []
                for metric, _ in collect.GRAPHALYTICS_METRICS:
                    state = "FAIL" if run == 2 and metric == "BFS" else "PASS"
                    lines.append(f"  {timing_labels[metric]} time: 0.1s")
                    lines.append(f"  SEMANTIC_VALIDATION {metric}: {state} rows=633432")
                path = Path(directory) / f"run-{run}.log"
                path.write_text("\n".join(lines), encoding="utf-8")
                paths.append(path)
            _, validations = collect.parse_semantic_graph_workload(paths)
        self.assertFalse(validations["BFS"])
        self.assertTrue(validations["PR"])

    def test_parses_and_validates_lsqb_logs(self):
        lines = []
        for query, expected in collect.LSQB_EXPECTED_COUNTS.items():
            lines.append(f"  {query} time: 0.12s  (count={expected})")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run-1.log"
            path.write_text("\n".join(lines), encoding="utf-8")
            parsed, passed = collect.parse_lsqb([path])
        self.assertEqual(9, passed)
        self.assertEqual(0.12, parsed["Q6"]["median"])

    def test_lsqb_validation_requires_correct_count_in_every_run(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for run in range(2):
                lines = []
                for query, expected in collect.LSQB_EXPECTED_COUNTS.items():
                    count = expected + 1 if run == 1 and query == "Q6" else expected
                    lines.append(f"  {query} time: 0.12s  (count={count})")
                path = Path(directory) / f"run-{run + 1}.log"
                path.write_text("\n".join(lines), encoding="utf-8")
                paths.append(path)
            _, passed = collect.parse_lsqb(paths)
        self.assertEqual(8, passed)

    def test_parses_olap_summary(self):
        rows = []
        for index, (_, label) in enumerate(collect.OLAP_METRICS, start=1):
            rows.append(f"│ {label} │ 10 ms │ 5 ms │ {index}.0x │")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "olap.log"
            path.write_text("\n".join(rows), encoding="utf-8")
            parsed = collect.parse_olap(path)
        self.assertEqual(1.0, parsed["one-hop-count"])
        self.assertEqual(10.0, parsed["pagerank-20"])

    def test_parses_compact_hop_labels_from_benchmark_table(self):
        labels = {
            "one-hop-count": "1-hop count",
            "one-hop-ids": "1-hop IDs",
            "two-hop": "2-hop",
            "three-hop": "3-hop",
            "four-hop": "4-hop",
            "five-hop": "5-hop",
            "shortest-path": "Shortest Path",
            "connected-components": "Connected Components",
            "label-propagation": "Label Propagation",
            "pagerank-20": "PageRank (20 iter)",
        }
        rows = [f"│ {label} │ 10 ms │ 5 ms │ 2.0x │" for label in labels.values()]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "olap.log"
            path.write_text("\n".join(rows), encoding="utf-8")
            parsed = collect.parse_olap(path)
        self.assertEqual(set(labels), set(parsed))


if __name__ == "__main__":
    unittest.main()
