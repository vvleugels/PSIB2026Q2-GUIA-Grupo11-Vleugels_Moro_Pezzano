"""Notebook execution with progress events, isolated configuration and reports."""
import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import inspect
import os
from pathlib import Path
import signal
import sys
import nbformat
from nbclient import NotebookClient as BaseNotebookClient
from nbconvert import HTMLExporter
from jupyter_client import AsyncKernelManager as KernelManager
from jupyter_client.kernelspec import KernelSpec
import yaml


class RunCancelled(Exception):pass


class NotebookClient(BaseNotebookClient):
    """Keep cancellation under the runner's control, not nbclient's signals."""
    @asynccontextmanager
    async def async_setup_kernel(self, **kwargs):
        try:
            if not self.km.has_kernel:
                await self.async_start_new_kernel(**kwargs)
            if self.kc is None:
                await self.async_start_new_kernel_client()
            yield
        finally:
            if self.km is not None:
                await self._async_cleanup_kernel()


async def run_client(client, env):
    task=asyncio.create_task(client.async_execute(env=env))
    loop=asyncio.get_running_loop()
    installed=False
    cancelled=False
    def cancel():
        nonlocal cancelled
        cancelled=True
        if not task.done() and not task.cancelling():task.cancel()
    try:
        try:
            loop.add_signal_handler(signal.SIGTERM,cancel)
            installed=True
        except (RuntimeError,NotImplementedError):pass
        await task
    except asyncio.CancelledError:
        raise RunCancelled()
    except Exception:
        if cancelled:raise RunCancelled()
        raise
    finally:
        if installed:loop.remove_signal_handler(signal.SIGTERM)


def execute_notebooks(project_root,paths,config_path=None,output_dir=None,emit=None):
    """Execute in order and return complete/failed/cancelled state.

    Relative notebook paths resolve under project_root/notebooks. output_dir
    controls executed copies/reports; configuration output_dir controls tables
    and figures. emit receives progress dictionaries with zero-based cell indices.
    Partial outputs survive errors; source notebooks are never rewritten here.
    """
    root=Path(project_root).resolve()
    config_path=Path(config_path).resolve() if config_path else root/'config.yaml'
    cfg=yaml.safe_load(config_path.read_text())
    results=Path(cfg['output_dir']);results=results if results.is_absolute() else root/results
    out=Path(output_dir) if output_dir else results/'validation'
    out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env['MPLBACKEND']='module://matplotlib_inline.backend_inline'
    if config_path!=root/'config.yaml':
        env['PSIB_RUN_CONFIG']=str(config_path)
        env['PSIB_NONINTERACTIVE']='1'
        for key in ('PSIB_VIDEO_PATH','PSIB_VIDEO_DIR'):env.pop(key,None)
    completed=[];state={'status':'running','completed':completed}
    log=out/'execution.jsonl'
    def event(kind,**values):
        item={'event':kind,**values}
        with log.open('a') as stream:stream.write(json.dumps(item,default=str)+'\n')
        if emit:emit(item)
    def status(**values):
        state.update(values);(out/'status.json').write_text(json.dumps(state,indent=2))
    status()
    try:
        for path in paths:
            path=Path(path);path=path if path.is_absolute() else root/'notebooks'/path
            nb=nbformat.read(path,as_version=4)
            for cell in nb.cells:
                if cell.cell_type=='code':cell.outputs=[];cell.execution_count=None
            total=sum(c.cell_type=='code' for c in nb.cells);count=0;active_cell=None
            status(notebook=path.name,cell=None)
            event('module_started',notebook=path.name,total=total)
            def started(cell,cell_index,**kwargs):
                nonlocal active_cell
                if cell.cell_type=='code':
                    active_cell=cell_index;event('cell_started',notebook=path.name,cell=cell_index)
            def executed(cell,cell_index,**kwargs):
                nonlocal count
                if cell.cell_type=='code':
                    count+=1;event('cell_completed',notebook=path.name,cell=cell_index,completed=count,total=total)
                    for output in cell.get('outputs',[]):
                        if output.output_type=='stream':event('log',notebook=path.name,text=output.text)
            km=KernelManager(kernel_name='python3')
            km._kernel_spec=KernelSpec(argv=[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],display_name='PSIB',language='python')
            client=NotebookClient(nb,km=km,timeout=300,resources={'metadata':{'path':str(root)}},
                                  on_cell_start=started,on_cell_executed=executed,shutdown_kernel="immediate")
            try:
                asyncio.run(run_client(client,env))
            except BaseException:
                status(cell=active_cell)
                raise
            finally:
                # Always close the kernel, even if saving/exporting fails.
                if km.has_kernel:
                    shutdown=km.shutdown_kernel(now=True)
                    if inspect.isawaitable(shutdown):asyncio.run(shutdown)
                nbformat.write(nb,out/path.name)
                try:
                    html,_=HTMLExporter(template_name='classic').from_notebook_node(nb)
                    (out/(path.stem+'.html')).write_text(html)
                except Exception as exc:event('log',text=f'HTML export failed: {exc}')
            completed.append(path.name)
            status(completed=completed)
            event('module_completed',notebook=path.name)
        status(status='complete',cell=None)
        event('complete',output_dir=str(out))
        return state
    except (RunCancelled,KeyboardInterrupt):
        status(status='cancelled');event('cancelled',notebook=state.get('notebook'),cell=state.get('cell'))
        return state
    except Exception as exc:
        status(status='failed',error=str(exc))
        event('failed',notebook=state.get('notebook'),cell=state.get('cell'),error=str(exc))
        return state


def main(project_root=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('notebooks',nargs='*')
    parser.add_argument('--config',type=Path)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--json-events',action='store_true')
    args=parser.parse_args()
    root=Path(project_root or Path(__file__).resolve().parents[2])
    paths=args.notebooks or sorted(p.name for p in (root/'notebooks').glob('*.ipynb'))
    def emit(item):
        print(json.dumps(item) if args.json_events else f"{item['event']}: {item.get('notebook','')} {item.get('text',item.get('error',''))}",flush=True)
    def cancel(signum,frame):
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
        raise RunCancelled()
    signal.signal(signal.SIGTERM,cancel)
    state=execute_notebooks(root,paths,args.config,args.output_dir,emit)
    return 0 if state['status']=='complete' else 130 if state['status']=='cancelled' else 1
