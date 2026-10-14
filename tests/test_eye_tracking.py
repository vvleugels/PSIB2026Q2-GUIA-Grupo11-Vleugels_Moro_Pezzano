"""Translation and loss tests independent of anatomical pupil segmentation."""
import unittest
import cv2
import numpy as np
from psib.eye_tracking import EyeTracker


class EyeTrackingTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(12)
        gray=rng.integers(0,256,(240,320),dtype=np.uint8)
        gray=cv2.GaussianBlur(gray,(3,3),.6)
        self.image=cv2.cvtColor(gray,cv2.COLOR_GRAY2RGB)
        self.roi=(80,60,120,100)

    def shifted(self,dx,dy):
        return cv2.warpAffine(self.image,np.array([[1,0,dx],[0,1,dy]],float),(320,240))

    def test_translation_does_not_resize(self):
        tracker=EyeTracker(self.image,self.roi,{'margin_px':10})
        for dx,dy in [(8,5),(16,10),(24,15)]:
            result=tracker.update(self.shifted(dx,dy))
            self.assertTrue(result.valid)
            np.testing.assert_allclose(result.shift_xy,[dx,dy],atol=1)
            self.assertEqual(result.roi[2:],(140,120))

    def test_tracking_back_to_first_frame(self):
        tracker=EyeTracker(self.shifted(10,8),(90,68,120,100),{'margin_px':0})
        result=tracker.update(self.image)
        self.assertTrue(result.valid)
        np.testing.assert_allclose(result.shift_xy,[-10,-8],atol=1)

    def test_loss_and_recovery(self):
        tracker=EyeTracker(self.image,self.roi)
        lost=tracker.update(np.zeros_like(self.image))
        self.assertFalse(lost.valid)
        recovered=tracker.update(self.shifted(8,5))
        self.assertTrue(recovered.valid)
        np.testing.assert_allclose(recovered.shift_xy,[8,5],atol=1)

    def test_blank_image_not_confident(self):
        tracker=EyeTracker(np.zeros_like(self.image),self.roi)
        self.assertFalse(tracker.update(np.zeros_like(self.image)).valid)

    def test_pupil_change_does_not_move_eye(self):
        ref=self.image.copy(); cv2.circle(ref,(140,110),20,(0,0,0),-1)
        tracker=EyeTracker(ref,self.roi,{'margin_px':0})
        frame=self.image.copy();cv2.circle(frame,(140,110),10,(0,0,0),-1)
        result=tracker.update(frame)
        self.assertTrue(result.valid)
        np.testing.assert_allclose(result.shift_xy,[0,0],atol=.7)


    def test_unsupported_rotation_rejected(self):
        tracker=EyeTracker(self.image,self.roi,{'margin_px':10})
        matrix=cv2.getRotationMatrix2D((140,110),12,1)
        rotated=cv2.warpAffine(self.image,matrix,(320,240))
        result=tracker.update(rotated)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason,'eye_scale_or_rotation_change')

    def test_template_recovery(self):
        tracker=EyeTracker(self.image,self.roi,{'margin_px':0})
        tracker.points=None
        result=tracker.update(self.shifted(12,7))
        self.assertTrue(result.valid)
        self.assertEqual(result.method,'template_recovery')
        np.testing.assert_allclose(result.shift_xy,[12,7],atol=1)

    def test_moving_crop_preserves_measurement_scale(self):
        from unittest.mock import patch
        from psib.temporal import track_video
        reference=self.image.copy()
        cv2.circle(reference,(140,110),12,(0,0,0),-1)
        frames=[cv2.warpAffine(reference,np.array([[1,0,d],[0,1,0]],float),(320,240)) for d in (0,8,16)]
        class Capture:
            index=0
            def read(self):
                if self.index==len(frames):return False,None
                frame=cv2.cvtColor(frames[self.index],cv2.COLOR_RGB2BGR);self.index+=1
                return True,frame
            def get(self,key):return (self.index-1)*40.0
            def release(self):pass
        options={'tracking_method':'snake','snake_iterations':10,'morphology_radius':1,
                 'min_area_px2':100,'max_area_px2':2000,'max_relative_diameter_step':.3,
                 'max_center_speed_px_s':30,'min_pupil_contrast':0,'preview_stride':1,
                 'eye_tracking':{'enabled':True,'margin_px':10},'roi_reference_time_s':0}
        with patch('psib.temporal._open',return_value=Capture()), \
             patch('psib.temporal.read_frame_at_time',return_value=(reference,0,0)), \
             patch('psib.temporal.segmentation.active_contour',side_effect=lambda image,contour,**kw:contour):
            table,_=track_video('synthetic',self.roi,[60,50],12,options,scale=100)
        self.assertTrue(table.accepted.all(),table.artifact_reason.tolist())
        self.assertEqual(table.roi_width_px.nunique(),1)
        np.testing.assert_allclose(table.area_mm2,table.area_mm2.iloc[0],atol=.05)
        np.testing.assert_allclose(table.centroid_full_x_px-table.centroid_full_x_px.iloc[0],[0,8,16],atol=1)
        self.assertTrue((table.centroid_anchor_x_px.max()-table.centroid_anchor_x_px.min())<1)
        with patch('psib.temporal._open',return_value=Capture()), \
             patch('psib.temporal.read_frame_at_time',return_value=(reference,0,0)), \
             patch('psib.temporal.segmentation.active_contour',side_effect=lambda image,contour,**kw:contour):
            full,_=track_video('synthetic',(0,0,320,240),[140,110],12,options,scale=100)
        self.assertTrue(full.accepted.all(),full.artifact_reason.tolist())
        self.assertTrue(full.roi_width_px.eq(320).all() and full.roi_height_px.eq(240).all())
        self.assertTrue(full.roi_x_px.eq(0).all() and full.roi_y_px.eq(0).all())
        np.testing.assert_allclose(full.area_mm2,full.area_mm2.iloc[0],atol=.05)
        np.testing.assert_allclose(full.centroid_full_x_px-full.centroid_full_x_px.iloc[0],[0,8,16],atol=1)


if __name__=='__main__':unittest.main()
