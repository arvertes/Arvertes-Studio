import unittest
from arvertes_desktop.sentinel import evaluate_release, REQUIRED

SHA = "a" * 40

class SentinelTests(unittest.TestCase):
    def test_missing(self):
        for scope in REQUIRED:
            result = evaluate_release(scope, SHA, [])
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(result["installation_authorized"])

    def test_never_authorizes(self):
        scope = "desktop_diagnostic"
        evidence = [dict(check=k, commit=SHA, status="pass", reference="sintético") for k in REQUIRED[scope]]
        self.assertEqual(evaluate_release(scope, SHA, evidence)["status"], "human_review")
        self.assertFalse(evaluate_release(scope, SHA, evidence)["installation_authorized"])
        evidence[0]["commit"] = "b" * 40
        self.assertEqual(evaluate_release(scope, SHA, evidence)["blockers"][0]["reason"], "stale")

    def test_duplicate(self):
        item = dict(check="unit_tests", commit=SHA, status="pass", reference="sintético")
        with self.assertRaises(ValueError):
            evaluate_release("desktop_diagnostic", SHA, [item, item])
