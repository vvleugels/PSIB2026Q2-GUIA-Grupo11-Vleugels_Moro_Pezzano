"""Synthetic checks of masked texture and timestamp-based temporal estimates."""
import unittest
import numpy as np
import pandas as pd
from psib.features import descriptors
from psib.temporal import clean_curve, response_parameters


class Module3Tests(unittest.TestCase):
    def test_background_does_not_enter_glcm(self):
        rgb=np.zeros((15,15,3),np.uint8)
        mask=np.zeros((15,15),bool); mask[4:11,4:11]=True
        rgb[mask]=100
        f=descriptors(rgb,mask)
        self.assertEqual(f['R_glcm_contrast'],0)
        self.assertEqual(f['R_glcm_energy'],1)
        self.assertEqual(f['R_entropy_bits'],0)

    def test_gap_policy(self):
        table=pd.DataFrame({'timestamp_s':[0,.04,.08,.12,.3,.6,.64],
            'equivalent_diameter_px':[10]*7,'accepted':[True,False,True,True,False,True,False]})
        result=clean_curve(table,.15,.1)
        self.assertTrue(result.interpolated.iloc[1])
        self.assertTrue(np.isnan(result.diameter_clean_px.iloc[4]))
        self.assertTrue(np.isnan(result.diameter_clean_px.iloc[6]))

    def test_a_b_latency_and_scale(self):
        t=np.arange(0,3,.02)
        opts={'baseline_window_s':.5,'response_window_s':2,'min_baseline_frames':10,
              'relative_onset_threshold':.05,'noise_multiplier':3,'onset_hold_s':.1,'max_gap_s':.15}
        for kind,sign in [('A',-1),('B',1)]:
            d=100+sign*10*np.clip((t-1.2)/.5,0,1)
            table=pd.DataFrame({'timestamp_s':t,'diameter_smooth_px':d,'accepted':True})
            result=response_parameters(table,1,kind,opts,100)
            self.assertAlmostEqual(result['latency_s'],.46,delta=.03)
            self.assertAlmostEqual(result['response_amplitude_px'],10)
            self.assertAlmostEqual(result['response_amplitude_mm'],1)
            self.assertEqual(result['status'],'estimated_unvalidated')

    def test_missing_baseline(self):
        table=pd.DataFrame({'timestamp_s':[1,2,3],'diameter_smooth_px':[10.,9.,8.],'accepted':True})
        result=response_parameters(table,0,'A',{'baseline_window_s':1,'response_window_s':5,'min_baseline_frames':10})
        self.assertEqual(result['status'],'insufficient_data')
        self.assertTrue(np.isnan(result['latency_s']))

if __name__=='__main__': unittest.main()
