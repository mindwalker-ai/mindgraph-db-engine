import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "banking_workload.py"
JAVA_RUNNER_PATH = Path(__file__).parents[1] / "BankingQueryBenchmark.java"
SPEC = importlib.util.spec_from_file_location("banking_workload", MODULE_PATH)
banking = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(banking)


class BankingWorkloadTest(unittest.TestCase):
    def test_java_and_neo4j_runners_use_the_same_queries(self):
        java_source = JAVA_RUNNER_PATH.read_text(encoding="utf-8")

        for definition in banking.BANKING_QUERIES.values():
            self.assertIn(definition["query"], java_source)

    def test_dataset_generation_is_deterministic(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_manifest = banking.generate_dataset(
                Path(first), accounts=20, devices=5, transfers=30, seed=123
            )
            second_manifest = banking.generate_dataset(
                Path(second), accounts=20, devices=5, transfers=30, seed=123
            )

        self.assertEqual(first_manifest["counts"], second_manifest["counts"])
        self.assertEqual(first_manifest["files"], second_manifest["files"])
        self.assertEqual(set(banking.BANKING_QUERIES), {"B1", "B2", "B3", "B4", "B5"})

    def test_parser_ignores_warmup_and_preserves_measured_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for run in range(2):
                lines = []
                for index in range(1, 6):
                    lines.append(f"  WARMUP B{index} time: 9.000000s (result={index})")
                    lines.append(f"  B{index} time: {0.1 * index + run:.6f}s (result={index})")
                path = Path(directory) / f"run-{run + 1}.txt"
                path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                paths.append(path)

            timings, results = banking.parse_banking_results(paths)

        self.assertEqual([0.1, 1.1], timings["B1"]["runs"])
        self.assertEqual(1, results["B1"])
        self.assertEqual(5, results["B5"])

    def test_parser_rejects_result_changes_between_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for run in range(2):
                lines = [
                    f"  B{index} time: 0.100000s (result={index + (1 if run and index == 3 else 0)})"
                    for index in range(1, 6)
                ]
                path = Path(directory) / f"run-{run + 1}.txt"
                path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                paths.append(path)

            with self.assertRaisesRegex(ValueError, "changed between runs: B3"):
                banking.parse_banking_results(paths)


if __name__ == "__main__":
    unittest.main()
