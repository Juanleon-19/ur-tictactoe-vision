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
| C8 CELL5 SAFE | Mode1 y Assignments confirmados; COMMAND5 termina en P5_UP, Tool Z -60 mm, sin descenso. |
| C9 GRID SAFE | COMMAND1..9 termina en Pn_UP. Confirmación antes de **cada** movimiento y evaluación posterior. |
| C10 ROBOTIQ | Confirmación de definiciones URCap cargadas y activación/open/close comprobados. Evidencia manual, sin I/O de robot. |
| C11 PICK | Confirmar ensayo manual PICK + close + retract a P_PICK_UP con agarre real. Sin comando PICK nuevo. |
| C12 PLACE CELL5 | Mode2: autorizar COMMAND5, handshake completo, confirmar ficha en CELL5 y retorno HOME. |
| C13 PLACE OTHER CELLS | Mode2: 1,3,7,9,2,4,6,8; autorización y evaluación individual por celda. |
| C14 END-TO-END | Un turno humano+robot o partida completa, con cámara y runtime productivos; autorización por movimiento, verificación visual antes del acuse y confirmación física de HOME. |

Para C7–C9 y C12–C14 hacen falta `--allow-motion` **y** confirmación interactiva YES.
C8–C9 confirman Mode1 y Assignments de cuatro esquinas; C12–C13 confirman Mode2,
los seis Assignments y evidencia C8–C11. Nunca se cambian modo ni poses desde PC.
C10/C11 solo registran evidencia manual explícita, sin conectar hardware.
Antes de cada colocación confirmar celda libre, ficha en PICK y zona sin manos.
C13 cubre las otras ocho celdas; CELL5 se verifica en C12.

```powershell
# Solo el operador, después de verificar el robot y disponer de parada física:
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C7 --allow-motion
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C8 --allow-motion
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C9 --allow-motion
```

`no` bloquea el siguiente comando del paso. `ABORT` en una pregunta o Ctrl+C
durante captura/espera detiene la sesión: pasos posteriores SKIPPED y cierre de
recursos. Un FAIL en C7–C9 o C12–C14 también detiene la sesión. No se reintenta ni se limpia
COMMAND automáticamente tras fallo/aborto; el operador debe inspeccionar el
estado físico y recuperar el controlador manualmente. COMMAND0 es un acuse,
no una parada de emergencia. **Ctrl+C/ABORT no detiene un robot que ya se mueve**;
usar la parada física. Una operación I/O en curso puede tardar hasta su timeout
en devolver el control. `--timeout` limita cada transición; `--done-hold` controla
la observación de DONE sostenido (predeterminado 1 s en C7–C9/C12–C13).
Sin override, C12/C13/C14 disponen de **60 s**; los pasos rápidos conservan **15 s**.
Un `--timeout` explícito tiene prioridad en todos los pasos. El ciclo físico excede
15 s: C13 produjo un falso timeout y funcionó con 60 s. No acelerar movimientos
para satisfacer el timeout. C14 mantiene DONE hasta la confirmación visual.

C8/C9/C12/C13 conectan después de cada autorización, realizan el handshake y
cierran en finally antes de preguntar el resultado físico. No se mantienen
sockets durante preguntas humanas. Una sesión ociosa puede perderse en CB3.

El programa devuelve 0 solo si todos los pasos seleccionados son PASS; 1 si hay
FAIL/BLOCKED/SKIPPED. Genera siempre un reporte de ejecución, incluso ante error
de configuración: `reports/commissioning_<timestamp UTC>.json`, y opcional TXT.
Incluye SHA base del checkout, timestamp, configuración mediante lista permitida,
duraciones, observaciones y confirmaciones manuales. Si hay cambios locales,
el SHA identifica la base, no certifica que el árbol esté limpio.
No incluye rutas de configuración ni IP del PC; el host del robot es un dato
local de sesión. No introducir secretos en el campo host. Reports está ignorado.

El operador confirmó C6 (cinco PASS consecutivos), C7, Assignments, Tool Z -60 mm,
Mode1 y Robotiq/Mode2. C12 y varios movimientos C13 funcionaron físicamente.
Completar la cobertura C13 y la aceptación C14. Esta iteración no ejecuta hardware.
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

## Comparar perfiles con reflejos

Los perfiles disponibles son `default`, `robust` y `robust_glare`. El default
operacional sigue siendo `robust`; no se cambia la configuración local al ensayar.
Commissioning usa `AppConfig.aruco_profile` en C2–C5, reporte y preview. El override
`--aruco-profile` afecta únicamente a la sesión y también se registra en el reporte.
`RealGameBackend` sigue usando el perfil configurado para la GUI.

`robust_glare` es experimental: ventanas adaptativas min=3, max=43, step=4;
conserva SUBPIX y ArUco3 cuando existen. `robust` mantiene todos sus parámetros
anteriores (ventanas 3..23, step=4). No se cambia adaptiveThreshConstant ni se
relajan errorCorrectionRate, maxErroneousBitsInBorderRate o
polygonalApproxAccuracyRate. No hay CLAHE ni otro preprocesamiento: ambos reciben
el frame original. El rango mayor puede reducir FPS y no recupera información
perdida por saturación especular; su beneficio físico todavía debe medirse.

Con cámara, tablero e iluminación en la misma posición:

```powershell
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C2 --aruco-profile robust --window 10 --text-report
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C2 --aruco-profile robust_glare --window 10 --text-report
```

Comparar `profile`, `frames`, `capture_elapsed_seconds`, `measured_fps`,
`visible_ids`, `visibility_percent` y `id18_visibility_percent`. El criterio PASS
sigue siendo cada ID observado al menos una vez; ≥70 % se evalúa manualmente.
El preview muestra `Profile: ...` y `Click preview for focus`: hacer clic dentro
del video antes de pulsar C/c o Q/q/Esc, no en PowerShell. El cierre con X queda
registrado como cancelación y no recrea la ventana ni inicia la medición.

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
| 7 Grupo original C0–C9 | `scripts/run_commissioning.ps1 -Group 7 -AllowMotion` | C0 C1 C2 C3 C4 C5 C6 C7 C8 C9 |

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
| C8 | MOTION_MODE=1 y P5_UP; verificar centro, orientación, elevación Tool Z -60 mm y trayecto antes de confirmar. |
| C9 | Celdas 1..9 una por una; confirmar antes y después de cada movimiento. |
| C10 | URCap cargado y activación/open/close comprobados; confirmación manual, sin I/O. |
| C11 | Confirmación manual de PICK + close + retract con agarre real. |
| C12 | COMMAND5 Mode2: ficha colocada en CELL5 y retorno a HOME. |
| C13 | Primero 1,3,7,9; después 2,4,6,8. Autorizar cada ciclo y confirmar resultado. |
| C14 | Turno humano+robot completo o partida: ocupación correcta por visión, retorno HOME confirmado y READY tras el acuse. El alcance queda registrado. |

## Configuración física vigente

Seguir [los seis Assignments previos al Script Node](polyscope-urscript.md).
Cuatro Point Features de colocación → P1/P3/P7/P9 → interpolación XYZ con
orientación P1 → Pn → Pn_UP por Tool Z -60 mm. P_PICK/P_HOME provienen de sus
Features respectivos. Para recalibrar el tablero editar solo las cuatro esquinas
y reiniciar desde los Assignments. No se usa Plane ni alturas relativas al tablero.

C10–C14 se seleccionan directamente desde el CLI; el launcher conserva sus grupos originales:

```powershell
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C10 C11
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C12 --allow-motion
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C13 --allow-motion
python -m ur_tictactoe.commissioning --config config/app.local.yaml --steps C14 --allow-motion --timeout 60
```

## C14: aceptación end-to-end guiada

Cerrar la GUI real y cualquier otro cliente Modbus. Verificar C1–C13, Mode2,
seis Assignments, URCap, suministro de fichas y parada física. El harness nunca
modifica el modo ni las poses. `--allow-motion` por sí solo no autoriza el movimiento.

1. Confirmar precondiciones. En la pregunta de alcance, responder **no** para
   validar primero un turno; **YES** selecciona una partida completa.
2. Retirar fichas y manos. La cámara debe observar tablero vacío estable durante
   la ventana. Se usan Camera, ArucoDetector y BoardObserver productivos.
3. Autorizar la observación humana, colocar una ficha y retirar la mano. El
   runtime acepta una única ocupación nueva estable; GameSession decide la respuesta.
4. Autorizar UN turno robot con ficha en PICK y zona despejada. Tras la pregunta
   se descartan tres frames y se vuelve a comprobar el tablero antes de conectar.
5. Conexión fresca → READY → COMMAND de la celda → BUSY → DONE. Mode2 termina
   en HOME. No hay reenvío automático si se pierde una respuesta.
6. La cámara debe confirmar exactamente las ocupaciones lógicas más la celda
   elegida. Solo entonces COMMAND0 → READY → cierre de socket → WAITING_HUMAN
   (o GAME_OVER). Si la visión no confirma dentro del timeout, FAIL sin acuse.
7. Con la conexión cerrada, confirmar que la ficha está en la celda indicada y
   el robot está físicamente en HOME. Los registros no pueden acreditar por sí
   solos agarre, colocación o posición. Responder no produce FAIL.

En alcance `one_turn`, PASS acredita únicamente ese turno. Después de confirmarlo,
el operador puede terminar o **continuar la misma partida**: el alcance cambia a
`full_game` y se repiten las autorizaciones individuales hasta resultado de
GameSession, conservando tablero, observer y cámara. No hay reset de juego
ni de robot automático. La observación humana tiene al menos 60 s; las preguntas
no consumen timeout de conexión. La cámara permanece abierta y conserva observer;
no hay captura en background.

El reporte incluye `scope`, `completed_robot_turns`, `turns` (celdas humana/robot,
observación previa, ocupación verificada y confirmación HOME), `modbus_events`
(intentos de COMMAND, STATUS y aperturas/cierres con tiempos), resultado y estado
final. Una escritura registrada como intentada no prueba entrega. Un PASS de los
unit tests con dobles no sustituye este ensayo físico. Ante fallo inspeccionar
Log y estado físico antes de recuperar manualmente; COMMAND0 no es parada.
