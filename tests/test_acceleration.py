"""Optional OpenCL dispatch; mocked availability does not establish GPU execution."""
import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, Mock
import cv2
import numpy as np
import yaml
from psib import acceleration as A
from psib.filters import mean_filter, median_filter, gaussian_filter
from psib.frequency import fft2c, ifft2c, psd2d
from psib.gui_model import Setup,ProfileStore,effective_config
from psib.config import load_config


class AccelerationTests(TestCase):
    def tearDown(self):A.configure(False)

    def test_default_cpu_does_not_probe_and_preserves_math(self):
        with patch.object(A,'probe_gpu') as probe:
            A.configure(False);probe.assert_not_called()
        rng=np.random.default_rng(1);image=rng.integers(0,256,(31,43,3),np.uint8)
        np.testing.assert_array_equal(mean_filter(image,5),cv2.blur(image,(5,5)))
        np.testing.assert_array_equal(median_filter(image,5),cv2.medianBlur(image,5))
        np.testing.assert_array_equal(gaussian_filter(image,1.3),cv2.GaussianBlur(image,(0,0),1.3))
        np.testing.assert_array_equal(fft2c(image[...,0]),np.fft.fftshift(np.fft.fft2(image[...,0].astype(float))))

    def test_missing_runtime_falls_back_and_writes_honest_report(self):
        with tempfile.TemporaryDirectory() as temp,patch('psib.acceleration.cv2.ocl.haveOpenCL',return_value=False):
            A.configure(True,temp)
            image=np.arange(80,dtype=np.uint8).reshape(8,10)
            np.testing.assert_array_equal(mean_filter(image,3),cv2.blur(image,(3,3)))
            report=json.loads(next(Path(temp).glob('*.json')).read_text())
            self.assertTrue(report['requested']);self.assertFalse(report['available'])
            self.assertEqual(report['umat_attempts'],{});self.assertEqual(report['cpu_fallbacks']['mean_filter'],1)

    def test_probe_rejects_cpu_device_and_restores_thread_setting(self):
        device=Mock();device.type.return_value=cv2.ocl.Device_TYPE_CPU;device.available.return_value=True
        with patch('psib.acceleration.cv2.ocl.useOpenCL',side_effect=[False,True]),patch('psib.acceleration.cv2.ocl.haveOpenCL',return_value=True),patch('psib.acceleration.cv2.ocl.setUseOpenCL') as setting,patch('psib.acceleration.cv2.ocl.Device_getDefault',return_value=device):
            self.assertFalse(A.probe_gpu()['available']);self.assertFalse(setting.call_args.args[0])
        with patch('psib.acceleration.cv2.ocl.useOpenCL',side_effect=RuntimeError('bad driver')):
            self.assertIn('failed',A.probe_gpu()['message'])

    def test_umat_math_without_claiming_real_gpu(self):
        # Exercise the actual UMat code path on CPU here; hardware validation is separate.
        info=dict(available=True,device='mock GPU',double_precision=True,message='Mocked availability')
        with patch.object(A,'probe_gpu',return_value=info):A.configure(True)
        with patch('psib.acceleration.cv2.ocl.useOpenCL',return_value=True):
            rng=np.random.default_rng(2)
            for shape in [(32,40),(31,43),(1,16),(16,1)]:
                image=rng.integers(0,256,shape,dtype=np.uint8)
                np.testing.assert_allclose(A.fft2(image),np.fft.fft2(image),rtol=1e-10,atol=1e-8)
                spectrum=rng.random(shape)+1j*rng.random(shape)
                np.testing.assert_allclose(A.ifft2(spectrum),np.fft.ifft2(spectrum),rtol=1e-10,atol=1e-10)
                np.testing.assert_allclose(ifft2c(fft2c(image)),image,atol=1e-10)
                np.testing.assert_array_equal(mean_filter(image,3),cv2.blur(image,(3,3)))
                np.testing.assert_array_equal(median_filter(image,3),cv2.medianBlur(image,3))
                np.testing.assert_array_equal(gaussian_filter(image,1),cv2.GaussianBlur(image,(0,0),1))
            self.assertIn('fft2',A.status()['umat_attempts'])

    def test_precision_and_runtime_failure_fallback(self):
        info=dict(available=True,device='mock GPU',double_precision=False,message='mock')
        with patch.object(A,'probe_gpu',return_value=info):A.configure(True)
        with patch('psib.acceleration.cv2.dft') as transform:
            np.testing.assert_array_equal(A.fft2(np.ones((8,8))),np.fft.fft2(np.ones((8,8))))
            transform.assert_not_called()
        info['double_precision']=True
        with patch.object(A,'probe_gpu',return_value=info):A.configure(True)
        with patch('psib.acceleration.cv2.ocl.useOpenCL',return_value=True),patch('psib.acceleration.cv2.dft',side_effect=cv2.error('kernel failed')):
            np.testing.assert_array_equal(A.fft2(np.ones((8,8))),np.fft.fft2(np.ones((8,8))))
        self.assertIn('kernel failed',A.status()['last_fallback_reason'])
        with self.assertRaises(ValueError):A.configure('true')

    def test_profiles_config_and_cpu_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);video=root/'A_2.mp4';video.write_bytes(b'video')
            setup=Setup(str(video),100,80,6,ProfileStore.fingerprint(video),roi_enabled=False,
                        pupils=[{'center_xy':[30,30],'radius_px':8}]*2,use_gpu=True)
            base={'frames':{},'calibration':{},'module2':{},'module3':{}}
            cfg=effective_config(setup,base,root/'out',root)
            self.assertTrue(cfg['acceleration']['gpu'])
            store=ProfileStore(root/'profiles');store.save(setup);self.assertTrue(store.load(video).use_gpu)
            path=store.path(video);data=json.loads(path.read_text());del data['use_gpu'];path.write_text(json.dumps(data))
            self.assertFalse(store.load(video).use_gpu)
            config=root/'run.yaml';config.write_text(yaml.safe_dump(cfg))
            with patch.dict('os.environ',{},clear=True),patch.object(A,'probe_gpu',return_value=dict(available=False,device=None,double_precision=False,message='No GPU')):
                self.assertTrue(load_config(config)['acceleration']['gpu'])
            del cfg['acceleration'];config.write_text(yaml.safe_dump(cfg))
            with patch.dict('os.environ',{},clear=True):self.assertFalse(load_config(config)['acceleration']['gpu'])
            self.assertFalse(A.status()['requested'])
