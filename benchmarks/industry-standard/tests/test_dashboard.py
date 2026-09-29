import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "dashboard.py"
SPEC = importlib.util.spec_from_file_location("benchmark_dashboard", MODULE_PATH)
dashboard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(dashboard)


def fixture():
    return {
        "schemaVersion": 1,
        "title": "MindGraph benchmark",
        "subtitle": "Evidence",
        "generatedAt": "2026-09-29T00:00:00Z",
        "status": "verified",
        "release": {
            "version": "0.1.0-alpha.1",
            "commit": "abcdef123456",
            "harnessCommit": "123456abcdef",
        },
        "environment": {
            "cpu": "Test CPU",
            "cpuCount": 8,
            "memoryGiB": 30,
            "java": "21",
            "os": "Linux",
            "jvmHeapGiB": 12,
        },
        "methodology": {
            "summary": ["One warm-up and five measured runs."],
            "disclosures": ["Published references are not host measurements."],
        },
        "suites": [
            {
                "id": "graphalytics",
                "title": "Graphalytics",
                "description": "Six graph algorithms.",
                "unit": "seconds",
                "lowerIsBetter": True,
                "metrics": [{"id": "PR", "label": "PageRank"}],
                "series": [
                    {
                        "id": "mindgraph",
                        "label": "MindGraph measured",
                        "kind": "measured",
                        "values": {"PR": {"median": 0.12, "min": 0.1, "max": 0.14, "runs": [0.1, 0.12, 0.14]}},
                    },
                    {
                        "id": "reference",
                        "label": "ArcadeDB published",
                        "kind": "reference",
                        "values": {"PR": 0.1},
                    },
                ],
                "validation": {"passed": 1, "total": 1, "notes": ["Output matched."]},
            }
        ],
        "artifacts": [{"label": "Raw JSON", "path": "raw/result.json"}],
    }


class DashboardTest(unittest.TestCase):
    def test_renders_self_contained_dashboard(self):
        output = dashboard.render(fixture())
        self.assertIn("<!doctype html>", output)
        self.assertIn("MindGraph benchmark", output)
        self.assertIn("ArcadeDB published", output)
        self.assertIn("application/json", output)
        self.assertNotIn("https://cdn", output)

    def test_escapes_script_termination_in_data(self):
        data = fixture()
        data["title"] = "</script><script>alert(1)</script>"
        output = dashboard.render(data)
        payload = output.split('<script id="benchmark-data" type="application/json">', 1)[1].split("</script>", 1)[0]
        self.assertNotIn("</script>", payload)
        self.assertIn("\\u003c/script\\u003e", payload)

    def test_rejects_missing_metric_values(self):
        data = fixture()
        data["suites"][0]["series"][0]["values"] = {}
        with self.assertRaisesRegex(ValueError, "values.PR is required"):
            dashboard.validate(data)

    def test_cli_writes_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "result.json"
            target = root / "index.html"
            source.write_text(json.dumps(fixture()), encoding="utf-8")
            subprocess.run(
                [sys.executable, str(MODULE_PATH), str(source), str(target)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(target.read_text(encoding="utf-8").startswith("<!doctype html>"))


if __name__ == "__main__":
    unittest.main()
