"""Release safety invariants for the scheduled production workflow."""
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/ngo-grants-ai.yml"

class ProductionFlagTests(unittest.TestCase):
    def test_live_delivery_hard_disabled_in_current_workflow(self):
        code = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("NGO_GRANTS_V59_LIVE_DELIVERY: 'false'",code)
        self.assertNotIn("vars.NGO_GRANTS_V59_LIVE_DELIVERY",code)

    def test_checkout_is_main_for_durable_checkpoint(self):
        code = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ref: main",code)
        self.assertIn("persist-credentials: true",code)

    def test_manual_reconciliation_is_separate_from_publication(self):
        code = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("inputs.v59_reconcile_order == ''",code)
        self.assertIn("--v59-reconcile-order",code)
        self.assertIn("inputs.v59_reconcile_order != ''",code)

if __name__ == "__main__":
    unittest.main()
