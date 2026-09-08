# Robot Triqui Commissioning / HIL Acceptance Runner

Runner independiente de `GameApplication`. Reutiliza `Camera`, `ArucoDetector`,
`BoardObserver`, `ModbusClient` y la aceptación de tablero vacío de
`PhysicalGameRuntime`. No cambia lógica del juego, umbrales, URScript ni poses.
El contrato operacional de estos ensayos es IDs 10..18; no requiere IDs 0..3.

Desde PowerShell en el repositorio, con el entorno preparado:

```powershell
.venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Join-Path $PWD "src")
python -m pytest -q --junitxml=reports/pytest.xml
python -m ur_tictactoe.commissioning --steps C0 --pytest-report reports/pytest.xml --text-report
```

Se documenta el entrypoint Python como distribución del harness; el EXE principal
es independiente y no incorpora commissioning. No hace falta un segundo build.

Copiar `config/app.example.yaml` a `config/app.local.yaml` y, si hace falta,
`config/vision.example.yaml` a `config/vision.local.yaml`. En el YAML de aplicación,
`vision_config: vision.local.yaml` se resuelve respecto de ese YAML. Introducir
el host real solo en configuración local. No versionarla.

```powershell
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C1 C2 C3 C4 C5 --window 10 --text-report
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C6
```

Sin `--steps` se selecciona C0–C6. La falta de evidencia pytest deja C0 BLOCKED;
no se ejecuta pytest desde el harness. El XML debe corresponder al código actual:
su procedencia la declara el operador, no constituye una certificación del SHA.

| Paso | Procedimiento y criterio |
|---|---|
| C0 SOFTWARE | Python, dependencias instaladas, configuración cargada y resultados del XML pytest. |
| C1 CAMERA | Solo Camera: apertura, ajustes, frames válidos durante ventana configurable, resolución y FPS declarado/efectivo/medido. Cierre garantizado; no crea detector ni observer. |
| C2 ARUCO | Preview en vivo: C confirma, Q/Esc cancela. Medición posterior de IDs 10..18; porcentaje por frame, ID18 explícito. FAIL si algún ID nunca se vio. PASS no significa visibilidad suficiente: revisar porcentajes. |
| C3 BOARD EMPTY | Confirmar tablero vacío; observer ready, nueve FREE y aceptación de `PhysicalGameRuntime.start`. Ningún I/O de robot. |
| C4 OCCUPANCY | Referencia vacía; confirmar ficha 5 y luego exactamente 1,5,9. Cada ventana debe terminar estable, sin UNCERTAIN ni ocupaciones adicionales. |
| C5 OCCLUSION | Referencia vacía; pasar mano tras YES durante captura; ventana adicional de recuperación sin reiniciar observer. Requiere pérdida observada y todas FREE al final. |
| C6 CONNECTIVITY | TCP y lectura de STATUS129 exclusivamente. Nunca escribe COMMAND. |
| C7 MODE0 | Operador confirma script y MOTION_MODE=0; READY → COMMAND5 → BUSY → DONE sostenido → COMMAND0 → READY, con tiempos. |
| C8 CELL5 SAFE | Mode1 confirmado físicamente, autorización de CELL5 y evaluación YES/NO de posición final a altura segura. |
| C9 GRID SAFE | 1..9, confirmación antes de **cada** movimiento y evaluación posterior. No se encadenan movimientos sin operador. |
| C10 ROBOTIQ | BLOCKED: modelo, URCap y adaptador initialize/open/close pendientes. No inventa funciones rq_*. |
| C11–C14 | PICK, PLACE CELL5, PLACE otras celdas, END-TO-END: declarados y BLOCKED. No existe vía para habilitarlos con un flag. |

Para C7–C9 hacen falta `--allow-motion` **y** confirmación interactiva YES.
Para C8–C9 además se confirma MOTION_MODE=1, GEOMETRY_CONFIGURED,
ORIENTATION_CONFIGURED y Z_SAFE configurados físicamente. Nunca se cambian desde PC.

```powershell
# Solo el operador, después de verificar el robot y disponer de parada física:
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C7 --allow-motion
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C8 --allow-motion
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C9 --allow-motion
```

`no` bloquea el siguiente comando del paso. `ABORT` en una pregunta o Ctrl+C
durante captura/espera detiene la sesión: pasos posteriores SKIPPED y cierre de
recursos. Un FAIL en C7–C9 también detiene la sesión. No se reintenta ni se limpia
COMMAND automáticamente tras fallo/aborto; el operador debe inspeccionar el
estado físico y recuperar el controlador manualmente. COMMAND0 es un acuse,
no una parada de emergencia. **Ctrl+C/ABORT no detiene un robot que ya se mueve**;
usar la parada física. Una operación I/O en curso puede tardar hasta su timeout
en devolver el control. `--timeout` limita cada transición; `--done-hold` controla
la observación de DONE sostenido (predeterminado 1 s).

El programa devuelve 0 solo si todos los pasos seleccionados son PASS; 1 si hay
FAIL/BLOCKED/SKIPPED. Genera siempre un reporte de ejecución, incluso ante error
de configuración: `reports/commissioning_<timestamp UTC>.json`, y opcional TXT.
Incluye SHA base del checkout, timestamp, configuración mediante lista permitida,
duraciones, observaciones y confirmaciones manuales. Si hay cambios locales,
el SHA identifica la base, no certifica que el árbol esté limpio.
No incluye rutas de configuración ni IP del PC; el host del robot es un dato
local de sesión. No introducir secretos en el campo host. Reports está ignorado.

Estos ensayos físicos **no se han ejecutado** durante el desarrollo del runner.
Los tests de pytest usan cámara, reloj, detección y transporte falsos; el
observador y la puerta de aceptación de runtime son los productivos.

C1 registra `camera_index`, `backend`, `resolution`, `configured_fps`, `camera_fps`,
`measured_fps`, `frames` y `elapsed_seconds`. La ventana y el FPS medido empiezan
después de abrir y consultar ajustes; la duración total del resultado incluye
apertura y cierre. PASS requiere al menos un frame y que todas las lecturas sean
válidas; no exige 30 FPS, ArUcos ni tablero listo. El tiempo de apertura/lectura
del controlador de cámara puede exceder la ventana: no es un timeout del driver.
Los errores incluyen `error_type` y una etiqueta fija `failure_stage`, como
`camera_open`, `camera_settings`, `camera_read`, `camera_close`, `aruco_detection`,
`observer`, `modbus_connect` o `modbus_read`. No se serializan mensajes arbitrarios.

En C2–C5, `--window` empieza después de abrir la cámara y consultar sus ajustes.
`capture_elapsed_seconds` y `measured_fps` corresponden a la adquisición;
`duration_seconds` incluye apertura, confirmaciones y cierre. Un driver que tarda
50–60 s en abrir no consume la ventana de captura.

C2 muestra video anotado, IDs visibles/9, missing IDs y FPS antes de medir.
Posicione cámara y tablero y pulse **C** con el foco en la ventana del preview.
Se cierra solo esa ventana y se mantiene la misma cámara abierta para medir.
Los frames y el tiempo del preview no cuentan en las estadísticas ni actualizan
BoardObserver. **Q/Esc** cancela, libera la ventana/cámara y deja los pasos
posteriores SKIPPED; no inicia la medición. C3–C5 conservan sus confirmaciones de
terminal, sin añadir previews entre cada adquisición. Los errores de la ventana
se identifican como `failure_stage: preview`; errores de lectura/detección
conservan `camera_read`/`aruco_detection`.

## Preparación rápida para el operador

El launcher es solo un menú; no implementa ensayos ni responde YES. Desde el
repositorio, `scripts/run_commissioning.ps1` permite seleccionar un grupo.
`-Group 1` evita el menú; `-DryRun` muestra argumentos sin arrancar Python ni hardware.
Usa `.venv/Scripts/python.exe`, configura temporalmente PYTHONPATH a `src`, busca
`config/app.local.yaml` y evidencia `reports/pytest.xml` cuando existen, y devuelve
el código de salida del runner. `-Python`, `-Config` y `-TestReport` permiten rutas
explícitas (las relativas se interpretan desde el repositorio).

| Grupo | Comando del launcher | Pasos existentes |
|---|---|---|
| 1 Software | `scripts/run_commissioning.ps1 -Group 1` | C0 |
| 2 Visión completa | `scripts/run_commissioning.ps1 -Group 2` | C1 C2 C3 C4 C5 |
| 3 Red UR | `scripts/run_commissioning.ps1 -Group 3` | C6 |
| 4 Mode0 | `scripts/run_commissioning.ps1 -Group 4 -AllowMotion` | C7 |
| 5 Cell5 SAFE | `scripts/run_commissioning.ps1 -Group 5 -AllowMotion` | C8 |
| 6 Grid SAFE | `scripts/run_commissioning.ps1 -Group 6 -AllowMotion` | C9 |
| 7 Todos disponibles | `scripts/run_commissioning.ps1 -Group 7 -AllowMotion` | C0 C1 C2 C3 C4 C5 C6 C7 C8 C9 |

Sin `-AllowMotion` nunca añade `--allow-motion`; C7–C9 quedan BLOCKED. Con el flag,
siguen siendo obligatorias todas las confirmaciones internas. En el grupo 7,
detenerse después de C7 para configurar Mode1 físicamente antes de confirmar C8;
el launcher no cambia modos. Un FAIL de movimiento o ABORT detiene la sesión.

El operador puede preparar los YAML (no se crean ni versionan en esta entrega):

```powershell
Copy-Item config/app.example.yaml config/app.local.yaml
Copy-Item config/vision.example.yaml config/vision.local.yaml
```

En `app.local.yaml`: rellenar `robot.host`, mantener `aruco_profile: robust` y
añadir `vision_config: vision.local.yaml`. En `vision.local.yaml`: verificar
`camera.index` y backend AUTO/DSHOW/MSMF si hace falta; resolución 1280×720;
mantener exclusivamente `cell_ids: [10,11,12,13,14,15,16,17,18]` y umbrales existentes.
No usar IDs 0..3. Antes de copiar, comprobar que no existen YAML locales para no
sobrescribir una configuración del operador.

## Hoja compacta de aceptación física

Estos objetivos prácticos son criterios del operador, **no nuevos umbrales del
runner ni cambios de BoardObserver**. Registrar observaciones en el reporte de
sesión y anotaciones locales adicionales cuando el objetivo práctico no se cumpla.

| Paso | Criterio de aceptación en el banco |
|---|---|
| C1 | Cámara abre, frame válido, resolución efectiva registrada, FPS observado; objetivo práctico ≥20 FPS. |
| C2 | Solo 10..18; todos observados durante ventana; revisar porcentaje por ID, objetivo práctico ≥70 % cada uno, especialmente ID18. |
| C3 | ready y celdas 1..9 FREE. |
| C4 | CELL5 produce exactamente {5}; CELL1,5,9 produce exactamente {1,5,9}. |
| C5 | Mano produce pérdida temporal; al retirarse no queda ocupación falsa persistente. |
| C6 | Modbus conecta y STATUS129 es válido. Solo lectura. |
| C7 | MOTION_MODE=0 confirmado; READY → BUSY → DONE held → READY. Confirmar que el robot NO se mueve. |
| C8 | MOTION_MODE=1 y CELL5_SAFE; operador verifica centro, orientación, altura y trayecto seguro antes de responder YES a la posición final. |
| C9 | Celdas 1..9 una por una; confirmar antes y después de cada movimiento. |
| C10 | BLOCKED hasta modelo/URCap e integración real. Futuro: 3 ciclos initialize/open/close sin error. |
| C11 | BLOCKED. Futuro: agarre repetible desde PICK fijo. |
| C12 | BLOCKED. Futuro: pick → place Cell5 → retreat → HOME. |
| C13 | BLOCKED. Futuro: probar primero 1,3,7,9 y después las demás. |
| C14 | BLOCKED. Futuro: una partida física completa. |

## Datos físicos que debe definir el operador

| Bloque | Dato | Definición o acción requerida |
|---|---|---|
| MODE0 | UR host | Dirección real en YAML local; sin valor preasignado. |
| MODE0 | Script cargado | Confirmar triqui_controller.script en el robot. |
| MODE0 | MOTION_MODE | 0, configurado por el operador en el robot. |
| MODE1 | Feature TABLERO | Enseñar y verificar físicamente. |
| MODE1 | TCP | Definir/verificar según herramienta real. |
| MODE1 | Payload | Definir/verificar según herramienta y carga reales. |
| MODE1 | Z_SAFE | Medir/enseñar altura segura, sin valor inventado. |
| MODE1 | CELL_ORIENTATION | Enseñar/verificar orientación real. |
| MODE1 | JOINT_MOTION | Definir/verificar parámetros seguros reales. |
| MODE1 | MOTION_MODE | 1, solo tras verificar protecciones y geometría. |
| TABLERO | Origo | Centro de Cell1. |
| TABLERO | +X | Cell1 → Cell3. |
| TABLERO | +Y | Cell1 → Cell7. |
| TABLERO | GRID | 0.0655 m, dato acordado; comprobar en tablero físico. |
| MODE2 adicional | Modelo Robotiq | Identificar modelo exacto; pendiente. |
| MODE2 adicional | Firmware | Registrar si está disponible; pendiente. |
| MODE2 adicional | Versión URCap | Identificar versión exacta; pendiente. |
| MODE2 adicional | HOME | Enseñar/verificar pose real. |
| MODE2 adicional | PICK_APPROACH | Enseñar/verificar pose real. |
| MODE2 adicional | PICK | Enseñar/verificar PICK fijo real. |
| MODE2 adicional | PICK_EXIT | Enseñar/verificar pose real. |
| MODE2 adicional | LINEAR_MOTION | Definir/verificar parámetros seguros reales. |
| MODE2 adicional | Z_PLACE | Medir/enseñar altura real de colocación. |

Esta tabla no habilita Mode2 ni ROBOTIQ_CONFIGURED. C10–C14 siguen BLOCKED;
ninguna función ficticia sustituye la implementación y validación físicas.
