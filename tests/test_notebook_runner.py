"""Runner failure/progress/cancellation checks with a mocked kernel."""
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch,AsyncMock
import nbformat
import yaml
from psib.notebook_runner import execute_notebooks,RunCancelled


class NotebookRunnerTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'notebooks').mkdir()
        self.config=self.root/'config.yaml';self.config.write_text(yaml.safe_dump({'output_dir':str(self.root/'results')}))
        for name in ['one.ipynb','two.ipynb']:
            nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell('print(1)')]),self.root/'notebooks'/name)

    def tearDown(self):self.temp.cleanup()

    def test_failure_stops_next_notebook_and_reports_cell(self):
        events=[]
        class Client:
            def __init__(self,nb,**kw):self.nb=nb;self.kw=kw
            async def async_execute(self,**kwargs):
                self.kw['on_cell_start'](self.nb.cells[0],0)
                raise ValueError('bad cell')
        with patch('psib.notebook_runner.NotebookClient',Client),patch('psib.notebook_runner.KernelManager') as km:
            km.return_value.has_kernel=True
            result=execute_notebooks(self.root,['one.ipynb','two.ipynb'],emit=events.append)
            km.return_value.shutdown_kernel.assert_called_once()
        self.assertEqual(result['status'],'failed');self.assertEqual(result['cell'],0)
        self.assertEqual(sum(e['event']=='module_started' for e in events),1)
        self.assertTrue((self.root/'results/validation/one.ipynb').exists())
        self.assertFalse((self.root/'results/validation/two.ipynb').exists())

    def test_progress_and_sources_preserved(self):
        events=[];source=(self.root/'notebooks/one.ipynb').read_bytes()
        class Client:
            def __init__(self,nb,**kw):self.nb=nb;self.kw=kw
            async def async_execute(self,**kwargs):
                self.nb.cells[0].execution_count=1
                self.kw['on_cell_start'](self.nb.cells[0],0)
                self.kw['on_cell_executed'](self.nb.cells[0],0)
        with patch('psib.notebook_runner.NotebookClient',Client),patch('psib.notebook_runner.KernelManager'):
            result=execute_notebooks(self.root,['one.ipynb'],emit=events.append)
        self.assertEqual(result['status'],'complete');self.assertTrue(any(e['event']=='cell_completed' for e in events))
        self.assertEqual(source,(self.root/'notebooks/one.ipynb').read_bytes())
        self.assertTrue((self.root/'results/validation/one.html').exists())

    def test_cancellation_closes_kernel(self):
        with patch('psib.notebook_runner.NotebookClient') as client,patch('psib.notebook_runner.KernelManager') as km:
            client.return_value.async_execute=AsyncMock(side_effect=RunCancelled())
            km.return_value.has_kernel=True
            result=execute_notebooks(self.root,['one.ipynb','two.ipynb'])
            km.return_value.shutdown_kernel.assert_called_once()
        self.assertEqual(result['status'],'cancelled')
