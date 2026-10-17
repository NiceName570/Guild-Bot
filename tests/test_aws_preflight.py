"""Exercise the zero-spend gate with a fake AWS CLI. No AWS requests."""

import datetime as dt
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.name == "nt", "Windows PowerShell preflight")
class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.shell = shutil.which("pwsh") or shutil.which("powershell")
        if not self.shell:
            self.skipTest("PowerShell not installed")
        self.script = Path(__file__).resolve().parents[1] / "deploy/aws/preflight.ps1"
        (self.directory / "identity.json").write_text(
            json.dumps(
                {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:role/test-only"}
            )
        )
        (self.directory / "aws.cmd").write_text(
            '@echo off\nif "%1"=="sts" (\n'
            'type "%CLAN_TEST_IDENTITY%"\n) else (\n'
            'type "%CLAN_TEST_PLAN%"\n)\nexit /b 0\n'
        )
        self.plan = {
            "accountId": "123456789012",
            "accountPlanType": "FREE",
            "accountPlanStatus": "ACTIVE",
            "accountPlanRemainingCredits": {"amount": 50, "unit": "USD"},
            "accountPlanExpirationDate": (
                dt.datetime.now(dt.UTC) + dt.timedelta(days=10)
            ).isoformat(),
        }

    def tearDown(self):
        self.temp.cleanup()

    def run_gate(self):
        (self.directory / "plan.json").write_text(json.dumps(self.plan))
        env = dict(os.environ)
        env["PATH"] = str(self.directory) + os.pathsep + env["PATH"]
        env["CLAN_TEST_IDENTITY"] = str(self.directory / "identity.json")
        env["CLAN_TEST_PLAN"] = str(self.directory / "plan.json")
        return subprocess.run(
            [self.shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.script)],
            capture_output=True,
            text=True,
            env=env,
            timeout=20,
        )

    def test_accepts_verified_active_free_plan(self):
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FREE", result.stdout)
        self.assertIn("us-east-2", result.stdout)

    def test_rejects_paid_plan(self):
        self.plan["accountPlanType"] = "PAID"
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_rejects_expired_plan(self):
        self.plan["accountPlanExpirationDate"] = "2020-01-01T00:00:00Z"
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_rejects_no_credits(self):
        self.plan["accountPlanRemainingCredits"]["amount"] = 0
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_rejects_unknown_expiry(self):
        del self.plan["accountPlanExpirationDate"]
        self.assertNotEqual(self.run_gate().returncode, 0)

    def test_rejects_mismatched_project(self):
        self.plan["accountId"] = "999999999999"
        self.assertNotEqual(self.run_gate().returncode, 0)
