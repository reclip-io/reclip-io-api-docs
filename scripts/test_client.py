"""Deterministic client behavior checks; no live requests or credits."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

module_path = Path(__file__).resolve().parents[1] / "skills/reclip/scripts/reclip.py"
spec = importlib.util.spec_from_file_location("reclip", module_path)
reclip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reclip)

class FakeClient:
    def __init__(self, fail_first=False):
        self.submissions = []
        self.fail_first = fail_first
        self.key_id = "key-1"
    def request(self, method, path, data=None, idempotency=None):
        if path == "/me": return {"key_id": self.key_id, "workspace_id": "workspace-1"}
        if path == "/jobs/quote": return {"estimated_credits": 5, "affordable": True}
        if path == "/jobs":
            self.submissions.append((data, idempotency))
            if self.fail_first:
                self.fail_first = False
                raise RuntimeError("Unknown transport outcome")
            return {"id": "job-1"}
        if path == "/jobs/job-1": return {"id": "job-1", "status": "succeeded", "outputs": []}
        raise AssertionError(path)

class ClientTests(unittest.TestCase):
    def test_uncertain_submission_reuses_saved_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            client = FakeClient(True)
            with self.assertRaises(RuntimeError): reclip.run_job(client, {"tool": "example"}, path, 10)
            reclip.run_job(client, {"tool": "example"}, path, 10)
            self.assertEqual(client.submissions[0], client.submissions[1])
            self.assertNotIn("secret", path.read_text())
            reclip.run_job(client, {"tool": "example"}, path, 10)
            self.assertEqual(len(client.submissions), 2)
    def test_changed_key_or_payload_does_not_submit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            client = FakeClient()
            reclip.run_job(client, {"tool": "example"}, path, 10)
            with self.assertRaises(ValueError): reclip.run_job(client, {"tool": "other"}, path, 10)
            client.key_id = "key-2"
            with self.assertRaises(ValueError): reclip.run_job(client, {"tool": "example"}, path, 10)
            self.assertEqual(len(client.submissions), 1)
    def test_budget_denial_precedes_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient()
            with self.assertRaises(ValueError): reclip.run_job(client, {}, Path(directory) / "state.json", 4)
            self.assertFalse(client.submissions)
    def test_credentials_not_allowed_in_base_url(self):
        with self.assertRaises(ValueError): reclip.Client("https://user:pass@example.com/api/v1", "secret")
        with self.assertRaises(ValueError): reclip.Client("http://example.com/api/v1", "secret")

if __name__ == "__main__": unittest.main()
