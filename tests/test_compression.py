"""Compression correctness, measurement pairing and transform isolation."""
import json
import struct
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import cv2
from psib.compression import encode_lossless, decode_lossless, jpeg_roundtrip
from psib.compression_study import compare_diameters, study_options, temporal_study
from psib.temporal import track_video


class CompressionTests(unittest.TestCase):
    def test_lossless_roundtrips_and_full_file_sizes(self):
        rng = np.random.default_rng(3)
        for image in [rng.integers(0, 256, (17, 13, 3), dtype=np.uint8),
                      rng.integers(0, 256, (15, 11), dtype=np.uint8),
                      np.zeros((9, 13), np.uint8), np.full((7, 11, 3), 255, np.uint8),
                      (rng.random((9, 7)) > .5).astype(np.uint8)*255]:
            for codec in ['huffman', 'rle_horizontal', 'rle_vertical']:
                with self.subTest(shape=image.shape, codec=codec):
                    data = encode_lossless(image, codec)
                    np.testing.assert_array_equal(decode_lossless(data), image)
                    header_size = struct.unpack('>I', data[5:9])[0]
                    self.assertGreater(len(data), 9+header_size)
        stripes = np.tile(np.arange(16, dtype=np.uint8)[:, None], (1, 32))
        self.assertLess(len(encode_lossless(stripes, 'rle_horizontal')),
                        len(encode_lossless(stripes, 'rle_vertical')))

    def test_malformed_and_unsupported(self):
        for codec in ['huffman', 'rle_horizontal', 'rle_vertical']:
            data = encode_lossless(np.arange(64, dtype=np.uint8).reshape(8, 8), codec)
            for broken in [b'', b'other'+data[5:], data[:-1], data+b'\x00']:
                with self.assertRaises(ValueError): decode_lossless(broken)
        for image in [np.zeros((8, 8)), np.zeros((8, 8, 4), np.uint8), np.zeros((0, 8), np.uint8)]:
            with self.assertRaises(ValueError): encode_lossless(image)
        with self.assertRaises(ValueError): encode_lossless(np.zeros((8, 8), np.uint8), 'unknown')
        # Zero-length RLE run and ambiguous Huffman prefix must be rejected.
        data = encode_lossless(np.zeros((8, 8), np.uint8), 'rle_horizontal')
        length = struct.unpack('>I', data[5:9])[0]; offset = 9+length
        with self.assertRaises(ValueError): decode_lossless(data[:offset]+b'\0'*5+data[offset+5:])
        header = dict(shape=[8, 8], dtype='uint8', codec='huffman', codes={'0':'0', '1':'01'}, bit_count=64)
        encoded_header = json.dumps(header).encode()
        with self.assertRaises(ValueError): decode_lossless(b'PSIC\x01'+struct.pack('>I',len(encoded_header))+encoded_header+b'\0'*8)

    def test_jpeg_channel_order_shape_and_quality(self):
        image = np.zeros((19, 23, 3), np.uint8); image[:] = [220, 50, 10]
        for q in [90, 50, 10, 5]:
            data, decoded = jpeg_roundtrip(image, q)
            self.assertEqual(decoded.shape, image.shape); self.assertEqual(decoded.dtype, np.uint8)
            self.assertGreater(decoded[..., 0].mean(), decoded[..., 2].mean()+100)
            self.assertTrue(data.startswith(b'\xff\xd8'))
        _, gray = jpeg_roundtrip(image[..., 0], 50)
        self.assertEqual(gray.shape, image.shape[:2])
        for q in [0, 101, 50.5, True]:
            with self.assertRaises(ValueError): jpeg_roundtrip(image, q)

    def test_pairing_missing_rejected_and_units(self):
        baseline = pd.DataFrame(dict(frame_index=[0,1,2],timestamp_s=[0.,.1,.2],accepted=[True,True,False],equivalent_diameter_px=[10.,20.,30.]))
        candidate = baseline.copy(); candidate['equivalent_diameter_px'] = [12.,np.nan,100.]
        stats = compare_diameters(baseline, candidate, 100)
        self.assertEqual(stats['n_paired'],1); self.assertEqual(stats['bias_px'],2)
        self.assertAlmostEqual(stats['MAE_mm'],.2)
        candidate['accepted'] = False
        stats = compare_diameters(baseline,candidate)
        self.assertEqual(stats['status'],'insufficient_paired_data'); self.assertNotIn('MAE_mm',stats)
        with self.assertRaises(ValueError): compare_diameters(baseline,candidate.iloc[:2])
        candidate.loc[0,'timestamp_s'] = 2
        with self.assertRaises(ValueError): compare_diameters(baseline,candidate)

    def test_options_legacy_and_validation(self):
        self.assertFalse(study_options({})['save_all_frames'])
        for values in [{'jpeg_qualities':[90]}, {'save_all_frames':'false'}, {'temporal_qualities':[50,10,10]}]:
            with self.assertRaises(ValueError): study_options({'module4':values})

    def test_temporal_transform_reference_observer_and_release(self):
        from psib.eye_tracking import EyeTracker
        rgb = np.full((60, 80, 3), 150, np.uint8); cv2.circle(rgb,(40,30),8,(10,10,10),-1)
        class Capture:
            def __init__(self): self.index=0; self.released=False
            def read(self):
                if self.index == 3: return False,None
                self.index+=1; return True,cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
            def get(self,key): return (self.index-1)*40.
            def release(self): self.released=True
        options=dict(tracking_method='local_otsu', min_area_px2=20,max_area_px2=2000,
                     morphology_radius=1,max_relative_diameter_step=.25,max_center_speed_px_s=300,
                     min_pupil_contrast=0,preview_stride=1,eye_tracking={'enabled':True})
        for roi, center in [((20,10,40,40),[20,20]),((0,0,80,60),[40,30])]:
            def run(transform=None, observer=None):
                cap=Capture()
                with patch('psib.temporal._open',return_value=cap), patch('psib.temporal.read_frame_at_time',return_value=(rgb,0,0)):
                    table,_=track_video('fake',roi,center,8,options,100,frame_transform=transform,frame_observer=observer)
                self.assertTrue(cap.released)
                return table
            baseline=run(); calls=[]; observed=[]
            def transform(image): calls.append(image.copy()); return image
            table=run(transform,lambda *args:observed.append(args[:2]))
            pd.testing.assert_frame_equal(table,baseline)
            self.assertEqual(len(calls),4);self.assertEqual(observed,[(0,0.),(1,.04),(2,.08)])
            self.assertIn('area_mm2',table)
            refs=[]
            def tracker(reference,*args): refs.append(reference.copy()); return EyeTracker(reference,*args)
            with patch('psib.temporal.EyeTracker',side_effect=tracker):
                run(lambda image: np.clip(image.astype(int)+1,0,255).astype(np.uint8))
            np.testing.assert_array_equal(refs[0],rgb+1)
            with self.assertRaises(ValueError): run(lambda image:image[:3])
            cap=Capture()
            with patch('psib.temporal._open',return_value=cap),patch('psib.temporal.read_frame_at_time',return_value=(rgb,0,0)):
                with self.assertRaises(RuntimeError):
                    track_video('fake',roi,center,8,options,frame_observer=lambda *a: (_ for _ in ()).throw(RuntimeError('stop')))
            self.assertTrue(cap.released)

    def test_temporal_retention_and_isolation(self):
        import matplotlib
        matplotlib.use('Agg')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'figures').mkdir()
            original=np.full((8,8,3),100,np.uint8)
            raw=pd.DataFrame(dict(frame_index=[0,1],timestamp_s=[0.,.1],accepted=[True,True],equivalent_diameter_px=[10.,11.]))
            def tracked(*args,frame_transform=None,frame_observer=None,**kw):
                if frame_transform:
                    frame_transform(original)
                    for i in range(2):
                        decoded=frame_transform(original)
                        frame_observer(i,i*.1,original,decoded)
                return raw.copy(),[]
            for save in [False,True]:
                out=root/str(save);out.mkdir();(out/'manifest.json').write_text('{}')
                study=dict(out=out,cfg={'_output_dir':root}, options=dict(temporal_qualities=[50,10],save_all_frames=save),
                           m3={'max_gap_s':.15,'smooth_window_s':.15},video='fake',roi=(0,0,8,8),
                           inits=[dict(center_xy=[4,4],radius_px=2)],scale=None,stimulus=0,kind='A')
                with patch('psib.compression_study.track_video',side_effect=tracked),patch('psib.compression_study.response_parameters',return_value={'status':'insufficient_data','latency_s':np.nan}):
                    summary,_=temporal_study(study)
                self.assertEqual(list(summary.n_paired),[2,2])
                self.assertEqual(len(list(out.rglob('*.jpg'))),4 if save else 0)
                self.assertFalse(any('mm' in c for c in pd.read_csv(out/'baseline_pupil_curve.csv')))
                metrics=pd.read_csv(out/'temporal_compression_metrics.csv')
                self.assertEqual(len(metrics),4)
                self.assertEqual(json.loads((out/'manifest.json').read_text())['status'],'complete')


if __name__=='__main__': unittest.main()
