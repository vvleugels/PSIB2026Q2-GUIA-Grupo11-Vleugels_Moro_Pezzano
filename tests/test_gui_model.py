"""GUI setup state and per-video persistence without a display."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from psib.gui_model import Setup,ProfileStore,CanvasGeometry,effective_config
from psib.config import load_config
import yaml
import os


class GuiModelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.video=self.root/'A_2.mp4';self.video.write_bytes(b'video')
        self.setup=Setup(str(self.video),100,80,6,ProfileStore.fingerprint(self.video),roi=[10,10,60,50],
                         pupils=[{'center_xy':[25,25],'radius_px':10}]*2)
        self.base={'output_dir':'results','frames':{},'roi':{},'calibration':{},'module2':{},'module3':{}}

    def tearDown(self):self.temp.cleanup()

    def test_zoom_rectangle_and_letterbox(self):
        mapping=CanvasGeometry(100,80,4,(20,10))
        self.assertEqual(mapping.point(100,90),[20,20])
        self.assertIsNone(mapping.point(10,90))
        self.assertEqual(mapping.rectangle([80.1,60.1],[10.5,20.5]),[10,20,71,41])

    def test_geometry_invalidates_pupil_points(self):
        self.setup.ruler_points=[[1,1],[20,1]]
        self.setup.change_geometry(times=[2,5])
        self.assertEqual(self.setup.pupils,[None,None]);self.assertIsNone(self.setup.ruler_points)
        self.setup.pupils=[{},{}];self.setup.change_geometry(roi_enabled=False)
        self.assertEqual(self.setup.pupils,[None,None])

    def test_profile_restore_and_changed_video(self):
        store=ProfileStore(self.root/'profiles');store.save(self.setup)
        self.assertEqual(store.load(self.video).roi,self.setup.roi)
        self.video.write_bytes(b'changed video')
        self.assertIsNone(store.load(self.video))

    def test_arbitrary_filename_requires_type_and_persists_choice(self):
        video=self.root/'grabacion personal.MOV';video.write_bytes(b'video')
        self.setup.video=str(video);self.setup.fingerprint=ProfileStore.fingerprint(video)
        self.assertTrue(any('record type' in error for error in self.setup.missing()))
        self.setup.record_type='B'
        self.assertFalse(self.setup.missing())
        self.base['module3']['record_type']='A'
        cfg=effective_config(self.setup,self.base,self.root/'out',self.root)
        self.assertEqual(cfg['module3']['record_type'],'B')
        store=ProfileStore(self.root/'profiles');store.save(self.setup)
        self.assertEqual(store.load(video).effective_record_type,'B')

    def test_legacy_named_profile_infers_type_and_allows_override(self):
        store=ProfileStore(self.root/'profiles');store.save(self.setup)
        import json
        path=store.path(self.video);data=json.loads(path.read_text());del data['record_type']
        path.write_text(json.dumps(data))
        restored=store.load(self.video)
        self.assertEqual(restored.effective_record_type,'A')
        restored.record_type='B'
        self.assertEqual(effective_config(restored,self.base,self.root/'out',self.root)['module3']['record_type'],'B')

    def test_full_frame_and_calibration_off(self):
        self.setup.roi_enabled=False
        self.setup.ruler_points=[[0,0],[20,0]]
        cfg=effective_config(self.setup,self.base,self.root/'out',self.root)
        self.assertEqual(cfg['roi']['mode'],'full_frame')
        self.assertFalse(cfg['calibration']['enabled']);self.assertIsNone(cfg['calibration']['points_xy'])
        self.assertEqual(cfg['module2']['initialization_mode'],'manual')
        self.assertIsNone(cfg['module3']['manual_measurements_csv'])

    def test_calibration_on_requires_valid_points(self):
        self.setup.calibration_enabled=True
        with self.assertRaises(ValueError):effective_config(self.setup,self.base,self.root/'out',self.root)
        self.setup.ruler_points=[[0,0],[20,0]]
        self.assertFalse(self.setup.missing())

    def test_local_config_preferred_but_explicit_run_wins(self):
        cfg=effective_config(self.setup,self.base,self.root/'out',self.root)
        example=dict(cfg,video_path=str(self.root/'example.mp4'))
        main=self.root/'config.yaml';main.write_text(yaml.safe_dump(example))
        (self.root/'config.local.yaml').write_text(yaml.safe_dump(cfg))
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(load_config(main)['video_path'],str(self.video))
        with patch.dict(os.environ,{'PSIB_RUN_CONFIG':str(main)},clear=True):
            self.assertEqual(load_config(main)['video_path'],str(self.root/'example.mp4'))

    def test_explicit_run_ignores_old_video_env(self):
        cfg=effective_config(self.setup,self.base,self.root/'out',self.root)
        path=self.root/'run.yaml';path.write_text(yaml.safe_dump(cfg))
        with patch.dict(os.environ,{'PSIB_RUN_CONFIG':str(path),'PSIB_VIDEO_PATH':'wrong.mp4','PSIB_VIDEO_DIR':'wrong'}):
            loaded=load_config(self.root/'nonexistent.yaml')
        self.assertEqual(loaded['video_path'],str(self.video));self.assertEqual(loaded['_root'],self.root)

if __name__=='__main__':unittest.main()

class SavedOverlayTests(unittest.TestCase):
    def test_view_coordinates_and_disabled_settings(self):
        from psib.gui_model import saved_overlays
        s=Setup('example.mp4',200,100,6,'fake',roi=[20,10,100,70],calibration_enabled=True,
                ruler_points=[[0,90],[30,90]],pupils=[{'center_xy':[30,20],'radius_px':8},{'center_xy':[40,25],'radius_px':6}])
        full=saved_overlays(s,None)
        self.assertEqual(full[-1][1],[[50,30],8])
        self.assertEqual(saved_overlays(s,'pupil1')[0][1],[[40,25],6])
        self.assertEqual(saved_overlays(s,'roi')[0][0],'rectangle')
        self.assertEqual(saved_overlays(s,'ruler')[0][0],'line')
        s.calibration_enabled=False;s.roi_enabled=False
        self.assertEqual(saved_overlays(s,'roi'),[])
        self.assertEqual(saved_overlays(s,'ruler'),[])
