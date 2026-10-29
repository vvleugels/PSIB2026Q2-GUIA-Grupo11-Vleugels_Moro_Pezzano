# PSIB — Pupillary light reflex analysis

Eye video → pupil segmentation → area/diameter curve → exploratory response
estimates, following the Biomedical Signal and Image Processing practical guide.

**[Read the project documentation](documentation.md)** for architecture,
configuration precedence, algorithms, output formats and maintenance notes.

## Current status

| Module | Status |
| --- | --- |
| 0 — Acquisition | Inventory, timestamp/lighting checks and selected-video image preview implemented |
| 1 — Image fundamentals | Sampling, color, enhancement, filters, edges, Fourier and quality comparisons implemented |
| 2 — Segmentation | Multiple methods, morphology and optional reference-mask comparison implemented |
| 3 — Features and dynamics | Shape/texture, moving eye ROI, temporal curves and exploratory response estimates implemented |
| 4 — Compression | Huffman, horizontal/vertical RLE, JPEG quality comparisons and whole-video diameter effects implemented |

Modules 0–4 run on the available examples. **Execution success is not measurement
accuracy.** Some pupil boundaries remain incorrect; manual annotations and further
recordings are needed to validate them. Written discussion answers and fully
automatic handling of unseen recordings are also pending.

## Install and open the desktop app

Python 3.12 is the tested version. Tkinter comes from the operating system or the
Python installer, not pip.

### Linux

Run commands from the repository root.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python gui.py
```

Tkinter is provided by `python3-tk` on Debian/Ubuntu. Use a desktop session.
Folder opening needs the system's `xdg-open` or `gio`.

### Windows

**Quick start (recommended)**

1. Install **64-bit Python 3.12** with pip, the Python launcher (`py`), and
   **Tcl/Tk and IDLE** enabled. See the [Python Windows installation guide](https://docs.python.org/3.12/using/windows.html).
2. Download the repository: on its GitHub page, click **Code → Download ZIP**.
   Right-click the downloaded ZIP and choose **Extract All**. Open the extracted
   folder until you can see `gui.py`, `requirements.txt` and `PSIB.bat`.
3. **Double-click `PSIB.bat`.**

The first launch creates the `.venv` environment and installs `requirements.txt`.
This needs an internet connection and can take a few minutes; the command window
shows setup progress and application output. Later launches reuse the environment
and open the app directly. Keep the command window open while using the app.

Choose your video with **Choose video…**; recordings are not bundled with the
repository.

What `PSIB.bat` does, in order:

1. Moves to its own folder, so it works from a shortcut too.
2. If `.venv\Scripts\python.exe` is missing, creates the environment with
   `py -3.12` and installs the requirements. Dependency installation failure
   removes the incomplete environment so the next launch can retry.
3. Runs `gui.py` with the environment's Python. Setup failures and application
   errors leave a message in the console and wait for a key before closing.

**Optional: desktop shortcut.** Right-click `PSIB.bat` → **Show more options** →
**Send to** → **Desktop (create shortcut)**. You can change the shortcut's icon in
its **Properties**.

**If something goes wrong**

| Message or symptom | What to do |
| --- | --- |
| Environment creation fails (`No se pudo crear el entorno`) | Python 3.12 or the `py` launcher is missing. Reinstall Python with the options in step 1 |
| Dependency installation fails (`Fallo la instalacion de las dependencias`) | Read the console output, check your internet connection and launch `PSIB.bat` again |
| The console shows "Press any key to continue" after the app closes | The app exited with an error. Read the message above it |
| A Tkinter / `_tkinter` error | Modify the Python installation to include **Tcl/Tk and IDLE**; do not install it through pip |
| You changed `requirements.txt` or the environment is broken | Delete the `.venv` folder and launch `PSIB.bat` again |

**Manual setup (alternative)**

Use this if you prefer to run the commands yourself, for example during
development. Use **Command Prompt (CMD)**, run one command at a time and press
**Enter** after each. Open CMD in the folder containing `gui.py`: click the
**address bar** in File Explorer, type `cmd` and press Enter.

```cmd
py -3.12 --version
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python gui.py
```

`py -3.12 --version` should print `Python 3.12.x`. Creating `.venv` and installing
packages are one-time steps. In a new CMD window, run only
`.venv\Scripts\activate.bat` and `python gui.py`; you should see **`(.venv)`** at
the start of the command line. Type `deactivate` to leave the environment.

**Optional: open the notebooks in JupyterLab**

With `(.venv)` visible in CMD, install the optional notebook interface once:

```cmd
python -m pip install -r requirements-notebooks.txt
```

Then start it with:

```cmd
python -m jupyterlab
```

The regular GUI does not require JupyterLab. Advanced terminal execution, also
from the activated environment, uses a prepared configuration with numeric pupil
initializations:

```cmd
python validate_notebooks.py --config "C:/path/to/run_config.yaml"
```

Replace `C:/path/to/run_config.yaml` with the actual path to your configuration.
For manual YAML configuration, use forward slashes in Windows paths, for example
`video_path: "C:/Users/YourName/Videos/A_2.mp4"`. Keep machine-specific settings in
`config.local.yaml`. Create a new Windows environment rather than copying a Linux
`.venv` folder. See Python's [virtual environment documentation](https://docs.python.org/3.12/library/venv.html).

**Windows notes**

- **Results folder** opens the run's directory in File Explorer. HTML reports
  open in your browser.
- **Cancel run** ends the notebook runner and its kernels with `taskkill`. This has
  not been systematically validated on Windows (Linux is the tested platform). If a
  `python.exe` process stays alive after cancelling, end it from Task Manager.
- Closing the window is blocked while a run or frame preparation is active. Cancel
  the run first and wait for it to finish.

## Run an analysis

Video filenames are unrestricted (MP4, MOV, AVI or MKV). Under **Record type**,
choose **A — Dark to light** or **B — Light to dark**. Names starting with `A_`
or `B_` preselect that type; you can change it. The choice is saved per video.
For manual notebook runs with other names, set `module3.record_type: A` or `B`.

New to the app? Follow the [step-by-step GUI walkthrough](documentation.md#3-desktop-workflow-a-guided-walkthrough).
The documentation also maps [each button to its Python functions](documentation.md#51-functions-behind-the-buttons).
See the [frontend guide](documentation.md#55-frontend-structure-and-layout) for widgets, layout, events and image rendering.

The left panel groups video selection, comparison timestamps and measurement
settings into cards. The **Steps** checklist uses teal check marks for completed
steps, an amber numbered step for the next action, and outlined numbers for
pending steps. Steps that do not apply, such as the ruler when Calibration is
off, are marked with –. A hint below the list explains the current step;
**Go to next step ▶** opens its tool, and clicking a step does the same. Start
analysis with **Run all notebooks (0–4)** when the checklist is complete.

Use **Hide panel** / **Show panel** in the header to give the image more space or
restore the settings. **Advanced options** expands the manual pupil-selection
and OpenCL controls. Hover over controls for short explanations. The status line
above the progress bar says what is missing.

1. Choose a video and confirm its **Record type** (A or B). Enter the
   primary/secondary timestamps in seconds and click **Apply / load frames**.
2. Enable **Select eye ROI** to draw a crop; disable it for full-frame measurements.
3. Enable **Calibration** to select two ruler marks a known distance apart,
   normally 1 cm. Disable it for pixel-only measurements.
4. Under **Advanced options**, leave **Select pupils manually** on to select a
   center and boundary point in each comparison frame. Turn it off to estimate
   both pupils automatically. Use
   **Primary estimate** / **Secondary estimate** to review the blue dashed circles.
5. Confirm any manual selections, then click **Run all notebooks (0–4)**.
6. In **Results & log**, use **Next ▶** / **◀ Prev** to browse plots, **Fit** and
   zoom controls to inspect them, and drag to pan. Select a notebook report and
   click **Open report**, or click **Results folder** to browse saved files. The
   execution log is hidden by default; use **Show log** to display it. It opens
   automatically when a run fails or is cancelled.

Use Zoom/Fit and scrollbars. Space resets a draft selection; Backspace/right click
undoes a point; Enter confirms. **Show saved presets** displays previous selections
as blue dashed overlays. Presets are remembered per video in the ignored
`.psib_gui/` folder. Changing video/timestamps/ROI requires new dependent selections.

The app runs notebooks without additional selection windows. Progress and Cancel
are available; the status line names the current module and completed cells. Each
run gets its own `results/gui/<video>_<run id>/` directory,
including configuration, CSVs, figures, notebooks, HTML reports and execution status.
Failed/cancelled runs retain labelled partial outputs. Source notebooks and prior
results are preserved.

An eye ROI is recommended for automatic mode. Automatic initialization is a
heuristic, not a validated pupil boundary. If it
cannot find an unambiguous candidate, Run stays disabled: select a tighter eye ROI
or turn manual selection back on. Full-frame mode follows a local eye region to
estimate the second pupil, while keeping measurement frames full-size. Manual
points and automatic estimates are stored separately in the per-video profile.

## Figure explanations

The **Results & log** tab shows an explanation above each plot. Edit
[`figure_notes.yaml`](figure_notes.yaml) in the project folder to add or revise
these texts. Use the PNG filename without `.png` as the key and `|` for multiple
lines, for example:

```yaml
m0_brightness_vs_time: |
  Shows how image brightness changes over time.
  Compare brightness changes with the selected comparison timestamps.
"m4_*": |
  Module 4 compares original and compressed images.
```

An exact filename takes precedence over a trailing `*` prefix pattern. If several
patterns match, the longest prefix wins. Save the file and press **Next ▶** or
**◀ Prev** to reload the explanations without restarting the app. Figures with
no explanation show their key and a prompt to add it. The supplied file covers
all 55 figures in the current calibrated Modules 0–4 workflow. See the
[figure-note guide](documentation.md#37-editing-figure-explanations) for naming,
fallback behavior and the distinction between GUI notes and HTML reports.

## Optional GPU processing

1. Start the app (`PSIB.bat` on Windows, or `python gui.py` from the activated
   virtual environment).
2. Expand **Advanced options** and tick **Request GPU (OpenCL)**, below the
   pupil-selection toggle.
3. Read the message beside it. **OpenCL GPU available** means supported steps
   can request the GPU. **GPU unavailable … using CPU** means the run will still
   work, using the CPU instead.
4. Choose the video, finish your selections, and run the notebooks normally.
   Leave the checkbox off to use the original CPU paths.

This option applies to mean/median/Gaussian filters and Fourier transforms in
Module 1. Pupil segmentation, eye tracking, JPEG compression and the remaining
steps stay on the CPU. Fourier operations require GPU float64 support; otherwise
those operations also use CPU. OpenCV may silently run individual supported
operations on the CPU, and small images can be slower with GPU transfers.

The option is remembered per video. No extra pip packages are needed, but a
working **OpenCL GPU runtime and driver** must be installed on the computer.
The app does not install or change drivers. If the unavailable message appears,
leave the checkbox off to continue normally. AMD GPUs use OpenCL here, not CUDA.

Each run records availability, device, UMat dispatch attempts and explicit CPU
fallbacks in `acceleration/process_*.json` under the run's results folder. These
reports do not prove that individual GPU kernels ran. See the
[OpenCV OpenCL notes](https://github.com/opencv/opencv/wiki/OpenCL-optimizations)
for its automatic per-operation fallback behavior.

## Configuration and other entry points

- `config.yaml`: portable example settings.
- `config.local.yaml`: optional ignored machine-specific settings, preferred by
  ordinary notebook runs and the GUI.
- GUI-generated run configurations override old video-path environment variables.
- Videos in `data/` are ignored. Inputs may also live outside the repository.

To use notebooks manually, install the optional interface first:

```bash
python -m pip install -r requirements-notebooks.txt
python -m jupyterlab
```

Open it from the repository root and run
`notebooks/00_acquisition.ipynb` through `04_compression.ipynb` in order.
Restart the kernel after code changes. For terminal execution:

```bash
python validate_notebooks.py
python validate_notebooks.py 02_segmentation_morphology.ipynb
python validate_notebooks.py --config /absolute/path/run_config.yaml --json-events
```

Prepared configurations must include numeric pupil initializations (manual or
GUI-estimated), a manual/full-frame ROI, and manual ruler points when calibration
is enabled. With arbitrary filenames, set `module3.record_type` explicitly.
Kernel execution needs local ports. See the
[terminal execution guide](documentation.md#23-notebooks-and-terminal-execution)
for prepared-run configuration and report paths.

## Verify changes

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pip check
```

On Windows CMD, open the project folder and activate the environment first.
These checks are for development; they are not needed to launch the app:

```cmd
.venv\Scripts\activate.bat
set "PYTHONPATH=src"
python -m unittest discover -s tests -v
python -m pip check
set "PYTHONPATH="
```

Synthetic tests check processing and workflow behavior, not anatomical accuracy.
Inspect overlays and compare with manually annotated frames before interpreting
latency, amplitude or speed. Equivalent diameter comes from mask area, not an
anatomical circle fit. Ruler calibration assumes a suitable plane and stable
camera distance.

## Repository contents

`src/psib/` contains reusable processing and GUI code; `notebooks/` contains the
experiments; `tests/` contains focused checks. `gui.py` starts the desktop app.
`PSIB.bat` installs the environment on first launch and starts the app on Windows
with console output visible.
`src/psib/theme.py` defines the GUI styles and checklist; `assets/logo.png` supplies
the app branding, and `figure_notes.yaml` holds editable plot explanations.

The application creates `results/` locally for generated figures, measurements,
executed notebooks and reports. This entire directory is ignored and is not part
of the repository. Source notebooks are committed without saved cell outputs or
execution counts. Clear those outputs before committing notebooks that you ran manually; GUI runs already write executed
copies under the ignored results directory.

Videos, environments, presets, local settings and caches are also ignored. Older
Git commits may still contain previously published results; removing them from the current tree does not rewrite repository history.

The source code is small compared with generated reports. See the documentation's
maintenance section for the debloat audit and approved cleanup decisions.

## Compression study

Module 4 compares Huffman, horizontal/vertical RLE and JPEG Q=90/50/10/5 on the
selected frames and segmented regions. It also reruns the whole video at JPEG
Q=50/10 to compare diameter curves, rejection rates and exploratory response
parameters against uncompressed processing. This adds two JPEG passes and an
independent baseline to execution time. These are differences from the existing
pipeline, not anatomical accuracy scores.

Selected-frame compressed files, CSVs and figures are retained. Temporal JPEGs
are processed in memory by default. Set `module4.save_all_frames: true` in your
configuration to save every temporal JPEG for a future example recording; these
bulk files are ignored by Git. The example video and publication set will be
chosen separately. No additional packages are required.

# PSIB — Análisis del reflejo pupilar a la luz

Video del ojo → segmentación de la pupila → curva de área/diámetro → estimaciones
exploratorias de la respuesta, siguiendo la guía práctica de Procesamiento de
Señales e Imágenes Biomédicas.

**[Leer la documentación del proyecto](documentation.md)** para conocer la arquitectura,
la precedencia de la configuración, los algoritmos, los formatos de salida y las
notas de mantenimiento.

## Estado actual

| Módulo | Estado |
| --- | --- |
| 0 — Adquisición | Inventario, verificación de marcas de tiempo e iluminación, y vista previa de imágenes del video seleccionado implementados |
| 1 — Fundamentos de imágenes | Muestreo, color, realce, filtros, bordes, Fourier y comparaciones de calidad implementados |
| 2 — Segmentación | Múltiples métodos, morfología y comparación opcional con máscara de referencia implementados |
| 3 — Características y dinámica | Forma/textura, ROI ocular móvil, curvas temporales y estimaciones exploratorias de la respuesta implementados |
| 4 — Compresión | Huffman, RLE horizontal/vertical, comparaciones de calidad JPEG y efectos sobre el diámetro en el video completo implementados |

Los módulos 0–4 se ejecutan sobre los ejemplos disponibles. **Que la ejecución
sea exitosa no significa que la medición sea precisa.** Algunos bordes de pupila
siguen siendo incorrectos; se necesitan anotaciones manuales y más grabaciones para
validarlos. Además, siguen pendientes las respuestas escritas a las preguntas de
discusión y el manejo totalmente automático de grabaciones nuevas.

## Instalar y abrir la aplicación de escritorio

Python 3.12 es la versión probada. Tkinter viene con el sistema operativo o con el
instalador de Python, no con pip.

### Linux

Ejecutá los comandos desde la raíz del repositorio.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python gui.py
```

Tkinter se obtiene con el paquete `python3-tk` en Debian/Ubuntu. Usá una sesión de
escritorio. Para abrir carpetas se necesita `xdg-open` o `gio` del sistema.

### Windows

**Inicio rápido (recomendado)**

1. Instalá **Python 3.12 de 64 bits** con pip, el lanzador de Python (`py`) y
   **Tcl/Tk e IDLE** habilitados. Consultá la [guía de instalación de Python en Windows](https://docs.python.org/3.12/using/windows.html).
2. Descargá el repositorio: en su página de GitHub, hacé clic en **Code → Download ZIP**.
   Hacé clic derecho sobre el ZIP descargado y elegí **Extraer todo**. Abrí la carpeta
   extraída hasta que veas `gui.py`, `requirements.txt` y `PSIB.bat`.
3. **Hacé doble clic en `PSIB.bat`.**

El primer inicio crea el entorno `.venv` e instala `requirements.txt`. Esto requiere
conexión a internet y puede tardar unos minutos; la ventana de comandos muestra el
progreso de la instalación y la salida de la aplicación. Los inicios posteriores
reutilizan el entorno y abren la aplicación directamente. Mantené abierta la ventana
de comandos mientras uses la aplicación.

Elegí tu video con **Choose video…**; las grabaciones no se incluyen en el
repositorio.

Qué hace `PSIB.bat`, en orden:

1. Se mueve a su propia carpeta, por lo que también funciona desde un acceso directo.
2. Si falta `.venv\Scripts\python.exe`, crea el entorno con `py -3.12` e instala los
   requisitos. Si falla la instalación de dependencias, elimina el entorno incompleto
   para que el siguiente inicio pueda reintentar.
3. Ejecuta `gui.py` con el Python del entorno. Los errores de instalación y de la
   aplicación dejan un mensaje en la consola y esperan una tecla antes de cerrarse.

**Opcional: acceso directo en el escritorio.** Clic derecho sobre `PSIB.bat` → **Mostrar más opciones** →
**Enviar a** → **Escritorio (crear acceso directo)**. Podés cambiar el ícono del acceso
directo en sus **Propiedades**.

**Si algo sale mal**

| Mensaje o síntoma | Qué hacer |
| --- | --- |
| Falla la creación del entorno (`No se pudo crear el entorno`) | Falta Python 3.12 o el lanzador `py`. Reinstalá Python con las opciones del paso 1 |
| Falla la instalación de dependencias (`Fallo la instalacion de las dependencias`) | Leé la salida de la consola, revisá tu conexión a internet y volvé a ejecutar `PSIB.bat` |
| La consola muestra "Press any key to continue" después de cerrar la aplicación | La aplicación terminó con un error. Leé el mensaje que aparece arriba |
| Un error de Tkinter / `_tkinter` | Modificá la instalación de Python para incluir **Tcl/Tk e IDLE**; no lo instales con pip |
| Modificaste `requirements.txt` o el entorno está dañado | Eliminá la carpeta `.venv` y volvé a ejecutar `PSIB.bat` |

**Instalación manual (alternativa)**

Usala si preferís ejecutar los comandos vos mismo, por ejemplo durante el desarrollo.
Usá el **Símbolo del sistema (CMD)**, ejecutá un comando a la vez y presioná
**Enter** después de cada uno. Abrí CMD en la carpeta que contiene `gui.py`: hacé clic
en la **barra de direcciones** del Explorador de archivos, escribí `cmd` y presioná Enter.

```cmd
py -3.12 --version
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python gui.py
```

`py -3.12 --version` debería mostrar `Python 3.12.x`. Crear `.venv` e instalar los
paquetes son pasos que se hacen una sola vez. En una nueva ventana de CMD, ejecutá
solamente `.venv\Scripts\activate.bat` y `python gui.py`; deberías ver **`(.venv)`** al
comienzo de la línea de comandos. Escribí `deactivate` para salir del entorno.

**Opcional: abrir los notebooks en JupyterLab**

Con `(.venv)` visible en CMD, instalá una sola vez la interfaz opcional de notebooks:

```cmd
python -m pip install -r requirements-notebooks.txt
```

Luego iniciala con:

```cmd
python -m jupyterlab
```

La GUI normal no requiere JupyterLab. La ejecución avanzada por terminal, también
desde el entorno activado, usa una configuración preparada con inicializaciones
numéricas de la pupila:

```cmd
python validate_notebooks.py --config "C:/path/to/run_config.yaml"
```

Reemplazá `C:/path/to/run_config.yaml` por la ruta real de tu configuración.
Para la configuración manual en YAML, usá barras normales (`/`) en las rutas de Windows,
por ejemplo `video_path: "C:/Users/YourName/Videos/A_2.mp4"`. Guardá los ajustes
específicos de tu máquina en `config.local.yaml`. Creá un entorno nuevo en Windows en
lugar de copiar una carpeta `.venv` de Linux. Consultá la [documentación de entornos virtuales](https://docs.python.org/3.12/library/venv.html) de Python.

**Notas sobre Windows**

- **Results folder** abre el directorio de la ejecución en el Explorador de archivos.
  Los informes HTML se abren en tu navegador.
- **Cancel run** finaliza el ejecutor de notebooks y sus kernels con `taskkill`. Esto no
  fue validado sistemáticamente en Windows (Linux es la plataforma probada). Si un
  proceso `python.exe` sigue activo después de cancelar, finalizalo desde el
  Administrador de tareas.
- Cerrar la ventana está bloqueado mientras haya una ejecución o una preparación de
  frames activa. Cancelá la ejecución primero y esperá a que termine.

## Ejecutar un análisis

El video puede tener cualquier nombre (MP4, MOV, AVI o MKV). En **Record type**,
elegí **A — Dark to light** (oscuro → luz) o **B — Light to dark** (luz → oscuro).
Los nombres que empiezan con `A_` o `B_` preseleccionan el tipo; podés cambiarlo.
La elección se guarda por video. Para ejecutar notebooks manualmente con otros
nombres, configurá `module3.record_type: A` o `B`.

¿Es tu primera vez con la aplicación? Seguí la [guía paso a paso de la GUI](documentation.md#3-desktop-workflow-a-guided-walkthrough).
La documentación también relaciona [cada botón con sus funciones de Python](documentation.md#51-functions-behind-the-buttons).
Consultá la [guía del frontend](documentation.md#55-frontend-structure-and-layout) para ver widgets, diseño, eventos y renderizado de imágenes.

El panel izquierdo agrupa en tarjetas la selección de video, las marcas de tiempo de
comparación y los ajustes de medición. La lista **Steps** usa marcas verdes azulado
para los pasos completados, un número ámbar para la siguiente acción y números con
contorno para los pasos pendientes. Los pasos que no aplican, como la regla cuando
Calibration está desactivada, se marcan con –. Una indicación debajo de la lista
explica el paso actual; **Go to next step ▶** abre su herramienta, y hacer clic en un
paso hace lo mismo. Iniciá el análisis con **Run all notebooks (0–4)** cuando la lista
esté completa.

Usá **Hide panel** / **Show panel** en el encabezado para darle más espacio a la
imagen o restaurar los ajustes. **Advanced options** despliega los controles de
selección manual de la pupila y de OpenCL. Pasá el cursor sobre los controles para ver
explicaciones breves. La línea de estado sobre la barra de progreso indica qué falta.

1. Elegí un video y confirmá su **Record type** (A o B). Ingresá las marcas de
   tiempo primaria/secundaria en segundos y hacé clic en **Apply / load frames**.
2. Activá **Select eye ROI** para dibujar un recorte; desactivalo para mediciones de
   cuadro completo.
3. Activá **Calibration** para seleccionar dos marcas de una regla separadas por una
   distancia conocida, normalmente 1 cm. Desactivalo para mediciones solo en píxeles.
4. En **Advanced options**, dejá **Select pupils manually** activado para seleccionar un
   centro y un punto del borde en cada frame de comparación. Desactivalo para estimar
   ambas pupilas automáticamente. Usá
   **Primary estimate** / **Secondary estimate** para revisar los círculos azules
   punteados.
5. Confirmá las selecciones manuales y hacé clic en **Run all notebooks (0–4)**.
6. En **Results & log**, usá **Next ▶** / **◀ Prev** para recorrer los gráficos, los
   controles **Fit** y de zoom para inspeccionarlos, y arrastrá para desplazarte.
   Seleccioná un informe de notebook y hacé clic en **Open report**, o hacé clic en
   **Results folder** para explorar los archivos guardados. El registro de ejecución
   está oculto por defecto; usá **Show log** para mostrarlo. Se abre automáticamente
   cuando una ejecución falla o se cancela.

Usá Zoom/Fit y las barras de desplazamiento. Espacio reinicia una selección en curso;
Retroceso/clic derecho deshace un punto; Enter confirma. **Show saved presets** muestra
las selecciones anteriores como superposiciones azules punteadas. Los presets se
recuerdan por video en la carpeta ignorada `.psib_gui/`. Cambiar el video, las marcas de
tiempo o el ROI requiere nuevas selecciones dependientes.

La aplicación ejecuta los notebooks sin ventanas de selección adicionales. El progreso
y la cancelación están disponibles; la línea de estado indica el módulo actual y las
celdas completadas. Cada ejecución obtiene su propio directorio
`results/gui/<video>_<run id>/`, que incluye la configuración, CSVs, figuras,
notebooks, informes HTML y el estado de ejecución. Las ejecuciones fallidas o
canceladas conservan salidas parciales etiquetadas. Los notebooks fuente y los
resultados previos se preservan.

Se recomienda un ROI ocular para el modo automático. La inicialización automática es
una heurística, no un borde de pupila validado. Si no puede encontrar un candidato
inequívoco, Run queda deshabilitado: seleccioná un ROI ocular más ajustado o volvé a
activar la selección manual. El modo de cuadro completo sigue una región local del ojo
para estimar la segunda pupila, manteniendo los frames de medición a tamaño completo.
Los puntos manuales y las estimaciones automáticas se almacenan por separado en el
perfil de cada video.

## Explicaciones de las figuras

La pestaña **Results & log** muestra una explicación sobre cada gráfico. Editá
[`figure_notes.yaml`](figure_notes.yaml) en la carpeta del proyecto para agregar o
revisar estos textos. Usá el nombre del archivo PNG sin `.png` como clave y `|` para
varias líneas, por ejemplo:

```yaml
m0_brightness_vs_time: |
  Shows how image brightness changes over time.
  Compare brightness changes with the selected comparison timestamps.
"m4_*": |
  Module 4 compares original and compressed images.
```

Un nombre de archivo exacto tiene precedencia sobre un patrón de prefijo con `*` al
final. Si coinciden varios patrones, gana el prefijo más largo. Guardá el archivo y
presioná **Next ▶** o **◀ Prev** para recargar las explicaciones sin reiniciar la
aplicación. Las figuras sin explicación muestran su clave y una invitación a
agregarla. El archivo provisto cubre las 55 figuras del flujo de trabajo calibrado
actual de los módulos 0–4. Consultá la
[guía de notas de figuras](documentation.md#37-editing-figure-explanations) para ver
la nomenclatura, el comportamiento de respaldo y la diferencia entre las notas de la
GUI y los informes HTML.

## Procesamiento opcional con GPU

1. Iniciá la aplicación (`PSIB.bat` en Windows, o `python gui.py` desde el entorno
   virtual activado).
2. Desplegá **Advanced options** y marcá **Request GPU (OpenCL)**, debajo del
   interruptor de selección de pupilas.
3. Leé el mensaje junto a la opción. **OpenCL GPU available** significa que los pasos
   compatibles pueden solicitar la GPU. **GPU unavailable … using CPU** significa que
   la ejecución funcionará igual, usando la CPU.
4. Elegí el video, completá tus selecciones y ejecutá los notebooks normalmente.
   Dejá la casilla desactivada para usar las rutas originales en CPU.

Esta opción se aplica a los filtros de media/mediana/gaussiano y a las transformadas
de Fourier del Módulo 1. La segmentación de la pupila, el seguimiento del ojo, la
compresión JPEG y el resto de los pasos permanecen en la CPU. Las operaciones de
Fourier requieren soporte de float64 en la GPU; de lo contrario, también usan la CPU.
OpenCV puede ejecutar silenciosamente en la CPU operaciones individuales compatibles, y
las imágenes pequeñas pueden ser más lentas por las transferencias a la GPU.

La opción se recuerda por video. No se necesitan paquetes pip adicionales, pero debe
haber un **runtime y driver de OpenCL para GPU** funcionando en la computadora. La
aplicación no instala ni modifica drivers. Si aparece el mensaje de no disponibilidad,
dejá la casilla desactivada para continuar normalmente. Las GPU AMD usan OpenCL aquí,
no CUDA.

Cada ejecución registra la disponibilidad, el dispositivo, los intentos de despacho
UMat y los respaldos explícitos a CPU en `acceleration/process_*.json` dentro de la
carpeta de resultados de la ejecución. Estos reportes no prueban que se hayan ejecutado
kernels individuales en la GPU. Consultá las
[notas de OpenCL de OpenCV](https://github.com/opencv/opencv/wiki/OpenCL-optimizations)
para conocer su comportamiento automático de respaldo por operación.

## Configuración y otros puntos de entrada

- `config.yaml`: ajustes de ejemplo portables.
- `config.local.yaml`: ajustes opcionales específicos de la máquina, ignorados por Git,
  preferidos por las ejecuciones ordinarias de notebooks y por la GUI.
- Las configuraciones de ejecución generadas por la GUI tienen prioridad sobre las
  variables de entorno antiguas con la ruta del video.
- Los videos en `data/` se ignoran. Las entradas también pueden estar fuera del
  repositorio.

Para usar los notebooks manualmente, instalá primero la interfaz opcional:

```bash
python -m pip install -r requirements-notebooks.txt
python -m jupyterlab
```

Abrila desde la raíz del repositorio y ejecutá
`notebooks/00_acquisition.ipynb` hasta `04_compression.ipynb` en orden.
Reiniciá el kernel después de cambiar el código. Para la ejecución por terminal:

```bash
python validate_notebooks.py
python validate_notebooks.py 02_segmentation_morphology.ipynb
python validate_notebooks.py --config /absolute/path/run_config.yaml --json-events
```

Las configuraciones preparadas deben incluir inicializaciones numéricas de la pupila
(manuales o estimadas por la GUI), un ROI manual/de cuadro completo y puntos de
regla manuales si la calibración está activada. Con nombres libres, configurá
`module3.record_type` explícitamente. El kernel necesita puertos locales.
Consultá la [guía de ejecución por terminal](documentation.md#23-notebooks-and-terminal-execution)
para preparar la configuración y elegir la carpeta de informes.

## Verificar cambios

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pip check
```

En CMD de Windows, abrí la carpeta del proyecto y activá primero el entorno. Estas
verificaciones son para desarrollo; no se necesitan para iniciar la aplicación:

```cmd
.venv\Scripts\activate.bat
set "PYTHONPATH=src"
python -m unittest discover -s tests -v
python -m pip check
set "PYTHONPATH="
```

Las pruebas sintéticas verifican el procesamiento y el comportamiento del flujo de
trabajo, no la precisión anatómica. Inspeccioná las superposiciones y compará con
frames anotados manualmente antes de interpretar la latencia, la amplitud o la
velocidad. El diámetro equivalente surge del área de la máscara, no de un ajuste de
círculo anatómico. La calibración con regla supone un plano adecuado y una distancia
estable de la cámara.

## Contenido del repositorio

`src/psib/` contiene el código reutilizable de procesamiento y de la GUI; `notebooks/`
contiene los experimentos; `tests/` contiene verificaciones puntuales. `gui.py` inicia
la aplicación de escritorio. `PSIB.bat` instala el entorno en el primer inicio y abre
la aplicación en Windows con la salida de consola visible.
`src/psib/theme.py` define los estilos de la GUI y la lista de pasos; `assets/logo.png`
aporta la marca de la aplicación, y `figure_notes.yaml` contiene las explicaciones
editables de los gráficos.

La aplicación crea localmente `results/` para las figuras generadas, mediciones,
notebooks ejecutados e informes. Todo este directorio se ignora y no forma parte del
repositorio. Los notebooks fuente se versionan sin salidas de celdas guardadas ni
contadores de ejecución. Limpiá esas salidas antes de hacer commit de notebooks que
hayas ejecutado manualmente; las ejecuciones de la GUI ya escriben copias ejecutadas
en el directorio de resultados ignorado.

Los videos, entornos, presets, ajustes locales y cachés también se ignoran. Los
commits antiguos de Git podrían contener resultados publicados anteriormente; quitarlos
del árbol actual no reescribe el historial del repositorio.

El código fuente es pequeño comparado con los informes generados. Consultá la sección
de mantenimiento de la documentación para ver la auditoría de depuración y las
decisiones de limpieza aprobadas.

## Estudio de compresión

El Módulo 4 compara Huffman, RLE horizontal/vertical y JPEG con Q=90/50/10/5 sobre los
frames seleccionados y las regiones segmentadas. También vuelve a ejecutar el video
completo con JPEG Q=50/10 para comparar las curvas de diámetro, las tasas de rechazo y
los parámetros exploratorios de respuesta contra el procesamiento sin comprimir. Esto
agrega dos pasadas JPEG y una línea base independiente al tiempo de ejecución. Se
trata de diferencias respecto del pipeline existente, no de puntajes de precisión
anatómica.

Los archivos comprimidos de los frames seleccionados, los CSVs y las figuras se
conservan. Los JPEG temporales se procesan en memoria por defecto. Configurá
`module4.save_all_frames: true` en tu configuración para guardar todos los JPEG
temporales de una futura grabación de ejemplo; estos archivos voluminosos son ignorados
por Git. El video de ejemplo y el conjunto de publicación se elegirán por separado. No
se requieren paquetes adicionales.
