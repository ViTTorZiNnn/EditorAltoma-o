import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import picker

class PickerTests(unittest.TestCase):
    def tearDown(self): picker.WINDOW=None
    def test_native_owned_dialog_no_subprocess(self):
        picker.WINDOW=Mock();picker.WINDOW.create_file_dialog.return_value=('C:/Videos',)
        with patch.dict(sys.modules,{'webview':Mock(FOLDER_DIALOG=10,OPEN_DIALOG=20)}), patch.object(picker.subprocess,'run') as run:
            self.assertEqual(picker.choose('folder'),{'path':'C:/Videos'})
            run.assert_not_called()
            self.assertEqual(picker.WINDOW.create_file_dialog.call_args.args,(10,))
    def test_cancel_and_retry_after_error(self):
        picker.WINDOW=Mock();picker.WINDOW.create_file_dialog.side_effect=[RuntimeError('test'),None]
        with patch.dict(sys.modules,{'webview':Mock()}):
            with self.assertRaises(RuntimeError):picker.choose('audio')
            self.assertEqual(picker.choose('audio'),{'path':''})
    def test_double_click_rejected(self):
        picker._GATE.acquire()
        try:
            with self.assertRaisesRegex(ValueError,'Já existe'):picker.choose('folder')
        finally:picker._GATE.release()
    def test_invalid_kind(self):
        with self.assertRaises(ValueError):picker.choose('arbitrary')
    def test_browser_timeout_is_readable_and_releases_lock(self):
        with patch.object(picker.sys,'platform','win32'),patch.object(picker.subprocess,'run',side_effect=picker.subprocess.TimeoutExpired('powershell',120)):
            with self.assertRaisesRegex(ValueError,'2 minutos'):picker.choose('folder')
        self.assertTrue(picker._GATE.acquire(blocking=False));picker._GATE.release()
