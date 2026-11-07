"""Real git integration test against a LOCAL bare remote, no external network."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ngo_grants_v59_checkpoint import durable_checkpoint

def git(cwd,*args):
    return subprocess.run(["git",*args],cwd=str(cwd),check=True,
                          text=True,capture_output=True).stdout.strip()

class RealGitCheckpointTests(unittest.TestCase):
    @patch.dict(os.environ,{"GITHUB_ACTIONS":"true","NGO_GRANTS_V59_LIVE_DELIVERY":"true"})
    def test_git_checkpoint_pushed_to_local_bare_remote(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            remote=root/"origin.git"
            work=root/"work"
            work.mkdir()
            subprocess.run(["git","init","--bare","--initial-branch=main",str(remote)],
                           check=True,capture_output=True)
            git(work,"init","-b","main")
            git(work,"config","user.name","CI")
            git(work,"config","user.email","ci@example.test")
            git(work,"remote","add","origin",str(remote))
            statefile=work/"ai_catalogs"/"state.json"
            statefile.parent.mkdir(parents=True)
            statefile.write_text(json.dumps({"schema_version":1}),encoding="utf-8")
            git(work,"add","--","ai_catalogs/state.json")
            git(work,"commit","-m","initial")
            git(work,"push","-u","origin","main")

            changed={"schema_version":1,"v59_deliveries":{
                "101":{"documents":[{"status":"sending"}]}}}
            durable_checkpoint(changed,
                save_local=lambda state:statefile.write_text(
                    json.dumps(state),encoding="utf-8"),
                state_path=Path("ai_catalogs/state.json"),repo_root=work)
            self.assertEqual(
                git(work,"rev-parse","HEAD"),
                git(work,"ls-remote","origin","refs/heads/main").split()[0])
            remote_state=git(work,"show","HEAD:ai_catalogs/state.json")
            self.assertIn('"sending"',remote_state)
            self.assertEqual("main",git(work,"rev-parse","--abbrev-ref","HEAD"))

if __name__=="__main__":
    unittest.main()
