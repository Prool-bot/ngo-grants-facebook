import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from ngo_grants_v59_checkpoint import durable_checkpoint

class Result:
    def __init__(self, stdout=""):
        self.stdout=stdout

class CheckpointTests(unittest.TestCase):
    @patch.dict(os.environ,{"GITHUB_ACTIONS":"true","NGO_GRANTS_V59_LIVE_DELIVERY":"true"})
    def test_commit_push_verify_before_return(self):
        calls=[]
        def fake(cmd,**kwargs):
            calls.append(cmd[1:])
            k=tuple(cmd[1:])
            if k==("rev-parse","--abbrev-ref","HEAD"):return Result("main")
            if k==("diff","--cached","--name-only"):return Result("ai_catalogs/state.json")
            if k==("rev-parse","HEAD"):return Result("abc123")
            if k==("ls-remote","origin","refs/heads/main"):return Result("abc123\trefs/heads/main")
            return Result()
        saved=[]
        durable_checkpoint({},save_local=lambda _:saved.append(True),
                           state_path=Path("ai_catalogs/state.json"),repo_root=Path("/tmp"),
                           runner=fake)
        self.assertTrue(saved)
        self.assertIn(["push","origin","HEAD:main"],calls)

    @patch.dict(os.environ,{"GITHUB_ACTIONS":"true","NGO_GRANTS_V59_LIVE_DELIVERY":"true"})
    def test_failed_push_prevents_delivery(self):
        def fail(cmd,**kwargs):
            if cmd[1]=="push":
                raise subprocess.CalledProcessError(1,cmd)
            if cmd[1:]==["rev-parse","--abbrev-ref","HEAD"]:return Result("main")
            return Result("ai_catalogs/state.json" if cmd[1]=="diff" else "")
        with self.assertRaisesRegex(RuntimeError,"checkpoint"):
            durable_checkpoint({},save_local=lambda _:None,
                state_path=Path("ai_catalogs/state.json"),repo_root=Path("/tmp"),runner=fail)

    @patch.dict(os.environ,{"GITHUB_ACTIONS":"true","NGO_GRANTS_V59_LIVE_DELIVERY":"true"})
    def test_wrong_branch_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"поза main"):
            durable_checkpoint({},save_local=lambda _:self.fail("saved"),
                state_path=Path("ai_catalogs/state.json"),repo_root=Path("/tmp"),
                runner=lambda cmd,**kw:Result("feature/test"))

    @patch.dict(os.environ,{"GITHUB_ACTIONS":"false","NGO_GRANTS_V59_LIVE_DELIVERY":"true"})
    def test_outside_actions_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"GitHub Actions"):
            durable_checkpoint({},save_local=lambda _:None,
                state_path=Path("ai_catalogs/state.json"))

    @patch.dict(os.environ,{"GITHUB_ACTIONS":"true","NGO_GRANTS_V59_LIVE_DELIVERY":"true"})
    def test_remote_mismatch_is_blocking(self):
        def fake(cmd,**kwargs):
            k=tuple(cmd[1:])
            if k==("rev-parse","--abbrev-ref","HEAD"):return Result("main")
            if k==("rev-parse","HEAD"):return Result("aaa")
            if k==("ls-remote","origin","refs/heads/main"):return Result("bbb\trefs/heads/main")
            return Result()
        with self.assertRaisesRegex(RuntimeError,"не підтверджено"):
            durable_checkpoint({},save_local=lambda _:None,
                state_path=Path("ai_catalogs/state.json"),repo_root=Path("/tmp"),runner=fake)

if __name__=="__main__":
    unittest.main()
