"""Selection interaction and coordinate mapping without opening desktop windows."""
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from psib.calibration import select_points, pixels_per_cm


class PointSelectionTests(unittest.TestCase):
    def run_selection(self, steps, **kwargs):
        callback = {}
        steps = iter(steps)
        def set_callback(title, function):
            callback['function'] = function
        def wait(ms):
            events, key = next(steps)
            for event,x,y in events:
                callback['function'](event,x,y,0,None)
            return key
        with patch('psib.calibration.prepare_gui_fonts'), \
             patch('psib.calibration.cv2.namedWindow'), \
             patch('psib.calibration.cv2.destroyWindow'), \
             patch('psib.calibration.cv2.imshow'), \
             patch('psib.calibration.cv2.getWindowProperty',return_value=1), \
             patch('psib.calibration.cv2.setMouseCallback',side_effect=set_callback), \
             patch('psib.calibration.cv2.waitKey',side_effect=wait):
            return select_points(np.zeros((50,100,3),np.uint8),**kwargs)

    def test_space_resets_and_zoom_preserves_ruler_scale(self):
        left=cv2.EVENT_LBUTTONDOWN
        points=self.run_selection([
            ([(left,100,100),(left,200,100)],32),
            ([(left,300,200),(left,700,200)],13)])
        np.testing.assert_allclose(points,[(30,20),(70,20)])
        self.assertEqual(pixels_per_cm(points),40)

    def test_undo_and_incomplete_enter(self):
        left=cv2.EVENT_LBUTTONDOWN
        points=self.run_selection([
            ([(left,100,100),(left,200,100)],8),
            ([],13),
            ([(left,400,100)],13)],preview_circle=True)
        np.testing.assert_allclose(points,[(10,10),(40,10)])

    def test_footer_click_is_ignored_and_right_click_undoes(self):
        left,right=cv2.EVENT_LBUTTONDOWN,cv2.EVENT_RBUTTONDOWN
        points=self.run_selection([
            ([(left,100,520),(left,100,100),(right,100,100)],13),
            ([(left,200,200),(left,400,200)],13)])
        np.testing.assert_allclose(points,[(20,20),(40,20)])

    def test_escape_cancels(self):
        with self.assertRaisesRegex(RuntimeError,'cancelled'):
            self.run_selection([([],27)])

if __name__=='__main__': unittest.main()
