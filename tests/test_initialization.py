"""Automatic pupil initialization and manual/automatic setup isolation."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from psib.initialization import estimate_pupil, estimate_comparison_pupils
from psib.gui_model import Setup, ProfileStore, effective_config, saved_overlays


class AutomaticInitializationTests(unittest.TestCase):
    def test_dark_pupil_with_reflection_and_border_distraction(self):
        image=np.full((120,160,3),170,np.uint8)
        cv2.circle(image,(80,60),26,(90,90,90),-1)
        cv2.circle(image,(80,60),14,(12,12,12),-1)
        cv2.circle(image,(83,57),2,(255,255,255),-1)
        cv2.rectangle(image,(0,0),(18,119),(0,0,0),-1)
        estimate=estimate_pupil(image)
        np.testing.assert_allclose(estimate['center_xy'],[80,60],atol=1.5)
        self.assertGreater(estimate['radius_px'],10);self.assertLess(estimate['radius_px'],18)

    def test_uninformative_and_ambiguous_images_require_correction(self):
        for image in [np.zeros((80,120,3),np.uint8),np.full((80,120,3),100,np.uint8),np.zeros((5,5,3),np.uint8)]:
            with self.assertRaises(ValueError):estimate_pupil(image)
        image=np.full((120,160,3),150,np.uint8)
        for x in [45,115]:cv2.circle(image,(x,60),12,(10,10,10),-1)
        with self.assertRaisesRegex(ValueError,'Multiple plausible'):
            estimate_pupil(image)

    def test_full_frame_support_maps_second_seed_without_resizing(self):
        image=np.full((200,300,3),150,np.uint8);crop=np.full((110,160,3),150,np.uint8)
        frames=[(image,1,30),(image,5,179)]
        crops=[(image,(0,0,300,200))]*2
        first={'center_xy':[100.,100.],'radius_px':10.}
        second={'center_xy':[25.,30.],'radius_px':6.}
        with patch('psib.initialization.estimate_pupil',side_effect=[first,second]),patch('psib.roi.tracked_frame_rois',return_value=[(crop,(20,45,160,110)),(crop,(65,70,160,110))]) as tracker:
            estimates=estimate_comparison_pupils(frames,crops,'video',{'enabled':True})
        self.assertEqual(estimates[1]['center_xy'],[90.,100.]);self.assertEqual(estimates[1]['radius_px'],6.)
        self.assertEqual(tracker.call_args.args[0][0][0].shape,(200,300,3))
        with patch('psib.initialization.estimate_pupil',return_value=first),patch('psib.roi.tracked_frame_rois',side_effect=RuntimeError('lost')):
            with self.assertRaisesRegex(RuntimeError,'lost'):estimate_comparison_pupils(frames,crops,'video',{})

    def test_crop_mode_preserves_local_coordinates(self):
        image=np.zeros((200,300,3),np.uint8);rgb=np.zeros((80,100,3),np.uint8)
        values=[{'center_xy':[40.,30.],'radius_px':10.},{'center_xy':[42.,32.],'radius_px':6.}]
        with patch('psib.initialization.estimate_pupil',side_effect=values),patch('psib.roi.tracked_frame_rois') as tracker:
            result=estimate_comparison_pupils([(image,1,0),(image,5,1)],[(rgb,(20,20,100,80)),(rgb,(30,25,100,80))],'video',{})
        tracker.assert_not_called();self.assertEqual(result,values)


class AutomaticSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.video=self.root/'video.mp4';self.video.write_bytes(b'video')
        self.manual=[{'center_xy':[20.,20.],'radius_px':8.}]*2
        self.automatic=[{'center_xy':[30.,25.],'radius_px':7.},{'center_xy':[32.,26.],'radius_px':5.}]
        self.setup=Setup(str(self.video),160,120,6,ProfileStore.fingerprint(self.video),roi=[20,10,100,80],pupils=self.manual.copy())
        self.base={'frames':{},'roi':{},'calibration':{},'module2':{},'module3':{}}

    def tearDown(self):self.temp.cleanup()

    def test_auto_requires_estimates_and_never_reuses_manual_seeds(self):
        self.setup.manual_pupils=False
        self.assertEqual(len(self.setup.missing()),2)
        with self.assertRaises(ValueError):effective_config(self.setup,self.base,self.root/'out',self.root)
        self.setup.automatic_pupils=self.automatic.copy()
        self.assertFalse(self.setup.missing())
        cfg=effective_config(self.setup,self.base,self.root/'out',self.root)
        self.assertEqual(cfg['module2']['initialization_mode'],'manual')
        self.assertEqual(cfg['module2']['initialization_source'],'automatic')
        self.assertEqual(cfg['module2']['initializations'],self.automatic)
        self.assertEqual(self.setup.pupils,self.manual)
        self.setup.manual_pupils=True
        cfg=effective_config(self.setup,self.base,self.root/'out',self.root)
        self.assertEqual(cfg['module2']['initialization_source'],'manual')
        self.assertEqual(cfg['module2']['initializations'],self.manual)

    def test_legacy_profile_defaults_and_auto_profile_restore(self):
        store=ProfileStore(self.root/'profiles');store.save(self.setup)
        path=store.path(self.video);data=json.loads(path.read_text())
        del data['manual_pupils'];del data['automatic_pupils'];path.write_text(json.dumps(data))
        restored=store.load(self.video);self.assertTrue(restored.manual_pupils)
        restored.manual_pupils=False;restored.automatic_pupils=self.automatic.copy();store.save(restored)
        restored=store.load(self.video)
        self.assertFalse(restored.manual_pupils);self.assertEqual(restored.active_pupils,self.automatic)

    def test_geometry_invalidates_both_modes_and_overlay_uses_active_values(self):
        self.setup.manual_pupils=False;self.setup.automatic_pupils=self.automatic.copy()
        circle=saved_overlays(self.setup,'pupil1')[0]
        self.assertEqual(circle[1],[[32.,26.],5.]);self.assertIn('Automatic',circle[2])
        self.assertEqual(saved_overlays(self.setup,None)[-1][1],[[50.,35.],7.])
        self.setup.change_geometry(times=[2,5])
        self.assertEqual(self.setup.pupils,[None,None]);self.assertEqual(self.setup.automatic_pupils,[None,None])
        self.setup.automatic_pupils=self.automatic.copy();self.setup.change_geometry(roi_enabled=False)
        self.assertEqual(self.setup.automatic_pupils,[None,None])
