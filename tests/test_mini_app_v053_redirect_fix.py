from unittest import TestCase
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from worker.patch_mini_app_v053_telegram_redirect_fix import patch, OLD, NEW, MARKER, FLAG

class TelegramRedirectHotfixTests(TestCase):
    def fixture(self):
        return ('NGO_MINI_APP_V052_503_CATEGORY_DIAGNOSTIC\n' +
                'NGO_MINI_APP_V051_D1_READBACK_STATUS_COMPATIBILITY\n' +
                FLAG + '\n' + OLD + '\n' + 'unrelated_live_bot_logic')

    def test_only_exact_telegram_fetch_option_changes(self):
        before=self.fixture()
        fixed=patch(before)
        self.assertEqual(fixed.count(MARKER),1)
        self.assertIn(NEW,fixed)
        self.assertNotIn(OLD,fixed)
        restored=fixed.replace('// '+MARKER+'\n','').replace(NEW,OLD)
        self.assertEqual(restored,before)
        with self.assertRaises(RuntimeError):patch(fixed)

    def test_unknown_current_worker_rejected(self):
        with self.assertRaises(RuntimeError):patch('some other script')
