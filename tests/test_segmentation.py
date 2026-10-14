"""Local pupil extraction under distinct illumination conditions."""
import unittest
import cv2
import numpy as np
from psib.segmentation import local_pupil_mask, overlap_metrics


class LocalPupilTests(unittest.TestCase):
    def test_constant_image_does_not_invent_pupil(self):
        mask=local_pupil_mask(np.full((80,80,3),20,np.uint8),[40,40],15)
        self.assertFalse(mask.any())

    def test_dark_and_bright_iris(self):
        for iris,pupil in [(35,5),(130,25)]:
            image=np.full((100,100,3),200,np.uint8)
            cv2.circle(image,(50,50),30,(iris,iris,iris),-1)
            cv2.circle(image,(50,50),12,(pupil,pupil,pupil),-1)
            truth=np.zeros((100,100),np.uint8);cv2.circle(truth,(50,50),12,1,-1)
            mask=local_pupil_mask(image,[50,50],16)
            self.assertGreater(overlap_metrics(mask,truth)['IoU'],.8)

if __name__=='__main__':unittest.main()
