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
| C1 CAMERA | Captura durante ventana configurable; resolución, FPS declarado/efectivo/medido y perfil robust. Cierre garantizado. |
| C2 ARUCO | Solo IDs 10..18 en resultados; porcentaje por frame, ID18 explícito. FAIL si algún ID nunca se vio. PASS no significa visibilidad suficiente: revisar porcentajes. |
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
