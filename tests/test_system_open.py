import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from subprocess import CompletedProcess
from psib.system_open import desktop_environment,open_folder


class SystemOpenTests(unittest.TestCase):
    def test_removes_opencv_libraries_but_preserves_other_settings(self):
        with patch.dict(os.environ,{'QT_QPA_FONTDIR':'/venv/cv2/fonts','QT_QPA_PLATFORM_PLUGIN_PATH':'/venv/cv2/plugins',
                                   'LD_LIBRARY_PATH':'/venv/cv2/../../lib64:/custom/libs'}):
            env=desktop_environment()
        self.assertNotIn('QT_QPA_FONTDIR',env)
        self.assertNotIn('QT_QPA_PLATFORM_PLUGIN_PATH',env)
        self.assertEqual(env['LD_LIBRARY_PATH'],'/custom/libs')

    def test_fallback_and_error_reporting(self):
        with tempfile.TemporaryDirectory() as folder,patch('psib.system_open.shutil.which',side_effect=lambda p:'/usr/bin/'+p),patch('psib.system_open.subprocess.run') as run:
            run.side_effect=[CompletedProcess([],1,stderr='failed'),CompletedProcess([],0)]
            self.assertEqual(open_folder(folder),Path(folder).resolve());self.assertEqual(run.call_count,2)
            run.side_effect=None;run.return_value=CompletedProcess([],1,stderr='no desktop handler')
            with self.assertRaisesRegex(RuntimeError,'no desktop handler'):open_folder(folder)

    def test_missing_folder(self):
        with self.assertRaises(FileNotFoundError):open_folder('/tmp/psib-folder-that-does-not-exist')
