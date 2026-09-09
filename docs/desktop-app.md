# Aplicación de escritorio MVP

La interfaz es una aplicación Windows con CustomTkinter sobre Tkinter. Mantiene esta separación:

```text
Tkinter GUI
    ↓ comandos y snapshots
GameApplication
    ↓
RealGameBackend (modo real)
    ↓
PhysicalGameRuntime
    ↓
GameSession / Modbus / PhysicalBoardState
```

La GUI no contiene Minimax, reglas, ArUco, observación física ni control Modbus.
Solo selecciona configuración, envía intenciones y representa snapshots.

## Controles de operación y ayuda offline

Abrir `python main.py app --simulate` y seleccionar **AYUDA / PUESTA EN MARCHA**
para consultar la ayuda sin hardware. Las seis secciones incluyen checklist,
solución contextual de problemas, mapa CELL1–9 / ID10–18, red y seguridad.
El estado general se actualiza desde el runtime; la simulación no acredita PASS físico.
Help es solo lectura: no tiene comandos de robot ni ejecuta el harness.

En **CÁMARA / DIAGNÓSTICO**, los perfiles Robusto, Reflejos y Estándar se conservan.
Los nuevos controles permiten seleccionar índice y AUTO/DSHOW/MSMF para esta sesión:

- **DETECTAR CÁMARAS** prueba 0–5 en segundo plano y libera cada captura de prueba.
  Reutiliza como evidencia el índice ya abierto con el mismo backend. Los índices
  no identifican marcas de cámara. No cambia la selección ni los YAML.
- **APLICAR CÁMARA** y **RECONECTAR CÁMARA** sustituyen únicamente la cámara,
  conservan Modbus y descartan la observación anterior para reacquirir el tablero.
- **REINICIAR OBSERVACIÓN** conserva cámara, detector y Modbus; limpia el estado
  temporal, IDs y preview. Esperar nuevamente la estabilización.

Estos controles se bloquean durante una partida física y mientras hay otra operación
de cámara pendiente. La apertura inicial también ocurre en segundo plano: se muestra
«Inicializando cámara...», sin timeout prematuro para los 50–60 s de la C920.
Una llamada del driver en curso no se puede cancelar desde Python; al cerrar la
ventana se solicita liberar los recursos cuando retorne. La detección puede tardar
varias aperturas, pero la ventana sigue atendiendo eventos.

El diagnóstico muestra cámara/backend, resolución capturada, FPS medidos entre ticks
de captura (limitados por el refresco de la GUI), perfil, IDs y estado del tablero.
La iluminación muestrea uno de cada ocho píxeles por eje, convierte a luminancia
y avisa si al menos 5 % alcanza 250/255. Es una recomendación visual aproximada:
un fondo blanco puede activarla. No altera el frame, perfiles, observer ni permisos
de inicio y no es un criterio de seguridad.

Al abrir la pestaña de ayuda se lee el archivo válido más reciente por modificación
en `reports/commissioning_*.json`. Se ignoran archivos corruptos y se muestran nombre
y estados del reporte elegido; no se combinan ensayos ni se modifican reportes.
Un paso ausente queda PENDIENTE. El checklist conserva solo PASS con evidencia;
FAIL/BLOCKED/SKIPPED se consultan literalmente en la sección Commissioning.
Los resultados son históricos y no certifican el hardware actual. C10–C14 siguen
sin implementación habilitada en el harness. C1–C4 físicos aprobados y C5 pendiente
no se modifican por estas mejoras de software.

Cerrar la aplicación, Ctrl+C o ABORT no garantiza detener un movimiento del UR.
COMMAND0 es acknowledgement, no emergency stop. Ante riesgo, usar parada física.

## Modo simulado

```powershell
python main.py app --simulate
```

No abre cámara, sockets ni conexiones UR. Los clics humanos producen un
`PhysicalBoardState` y atraviesan `PhysicalGameRuntime`. El transporte simulado
entrega `READY`, `BUSY` y `DONE` en actualizaciones distintas; después genera la
ocupación física esperada para que el runtime verifique la jugada robot. El ciclo
usa `Tkinter.after()` y no bloquea el hilo gráfico.

En simulación están disponibles:

- **Experto:** Minimax completo, sin errores estratégicos deliberados.
- **Intermedio:** victoria y bloqueo inmediatos; después usa búsqueda de un
  nivel, heurística posicional y variación reproducible entre alternativas
  próximas.
- **Pícaro:** humano y robot disponen de una sustitución por partida. El humano
  activa `USAR PÍCARO` y selecciona una ficha robot; el robot solo gasta su uso
  cuando su mejor reemplazo mejora estrictamente su mejor jugada normal.

Al seleccionar Pícaro se muestra `PÍCARO · SOLO SIMULACIÓN`.

## Modo real

```powershell
python main.py app
```

`RealGameBackend` encapsula `Camera`, `ArucoDetector`, `BoardObserver` y
`ModbusClient`. Construirlo no abre dispositivos. `open()` intenta abrir cámara y
conectar Modbus de forma independiente, `tick()` captura como máximo un frame y
actualiza la observación, y `close()` libera ambos recursos de forma idempotente.

```text
Camera -> ArucoDetector -> BoardObserver -> PhysicalGameRuntime
ModbusClient -> UR
```

La partida solo comienza cuando existe una observación `ready`, sin celdas
inciertas ni ocupadas. Estas condiciones se delegan en
`PhysicalGameRuntime.start()`. Durante la partida, DONE conduce a
`VERIFYING_ROBOT`; el movimiento lógico no se confirma ni se limpia COMMAND hasta
que la visión observa la celda esperada.

El observador usa exclusivamente IDs 10..18 y cuenta las capturas dentro de su
ventana temporal. No requiere marcadores de referencia geométrica. `AppConfig`
permite seleccionar `aruco_profile="default"` para diagnóstico; el valor
operacional es `robust`.

La GUI sigue consumiendo comandos y snapshots: no abre dispositivos ni interpreta
ArUcos. Las casillas no son clicables en modo real. Los estados distinguen cámara,
robot y tablero, y los fallos de apertura quedan en `last_error` sin cerrar la GUI.
Los tests inyectan cámaras, detectores, observers y clientes Modbus pequeños, sin
usar sockets ni hardware real.

En modo real Pícaro permanece deshabilitado. Una sustitución no cambia el estado
`FREE/OCCUPIED`, por lo que hará falta identificar el propietario físico mediante
X verde y O amarilla, e integrar posteriormente HSV y las acciones UR.

La C920 fue detectada y validada a 1280×720 @ 30 FPS. El perfil `robust`
mejoró la detección y es el predeterminado del backend real y de `AppConfig`.
Los IDs 10..18 se han observado 9/9; ID18 presenta más flicker.
La prueba end-to-end con C920, tablero físico y UR sigue pendiente.

Los valores iniciales de conexión están en `AppConfig` y se documentan en
`config/app.example.yaml`; no se guardan secretos ni parámetros físicos.

## Identidad institucional y recursos

El logo oficial es opcional y debe colocarse en:

```text
assets/javeriana_logo.png
```

Si no existe, la aplicación continúa normalmente y conserva el nombre de la
universidad en el pie. `desktop/assets.py` resuelve esta ruta tanto desde el árbol
de desarrollo como desde el directorio temporal `_MEIPASS` de una futura
aplicación PyInstaller. No se incluye ni se genera una imitación del escudo.

## Cámara / Diagnóstico

La pestaña comparte la única cámara y detección del `RealGameBackend`. Cada tick
captura como máximo un frame; consultar el snapshot o cambiar de pestaña no
captura ni decide jugadas. Presenta video RGB anotado con IDs 10..18, perfil,
resolución efectiva y estados FREE/OCCUPIED/UNCERTAIN. Sin cámara permanece
disponible y muestra CÁMARA NO DISPONIBLE. En simulación no abre dispositivos.

## Validación de Tcl/Tk

En esta sesión Python 3.12.10 y Tcl/Tk 8.6.15 funcionan fuera del contexto
aislado del asistente. Dentro de ese contexto Tk falla al localizar init.tcl,
aunque los archivos se pueden leer. No se modificó el intérprete ni se guardaron
variables TCL_LIBRARY/TK_LIBRARY globales. Ejecutar `python -m tkinter` y
`python -m pytest -q` desde una terminal normal del proyecto. La suite incluye
widgets Tk reales y necesita una sesión gráfica; no requiere cámara ni robot.
Los temporales locales `.gui-test-temp/` y `.gui-test-cache/` están ignorados.

## Branding académico

El encabezado conserva ROBOT TRIQUI y Sistema autónomo de juego, con el logo
oficial existente a 220×110 px, conservando la proporción 2:1 y el asset original
de 632×316 px para pantallas con escalado. El header compartido permanece visible
en inicio, partida y Cámara / Diagnóstico, sin duplicar el logo.
Añade Proyecto académico / Pontificia Universidad Javeriana, sin afirmar respaldo
institucional. El pie global muestra exactamente `By: Juan Esteban León Saiz`.

## Distribución Windows onedir

Desde PowerShell, con Python 3.12 y Tcl/Tk funcional:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
scripts\build_windows.ps1
dist\RobotTriqui\RobotTriqui.exe --simulate
dist\RobotTriqui\RobotTriqui.exe
```

El script verifica Tcl/Tk, dependencias y la suite completa antes de limpiar
únicamente los directorios generados de este producto y ejecutar PyInstaller.
`requirements-build.txt` fija el entorno de construcción; `robot_triqui.spec`
incluye logo, ejemplos YAML, CustomTkinter y dependencias de ejecución. Mantener
la carpeta **RobotTriqui completa**, incluido `_internal`; no distribuir solo el EXE.
No incluye tests, configuración local ni reportes. El build no ejecuta el robot.

La configuración externa se busca en `config/app.yaml` junto al EXE, o mediante
`--config ruta/al/app.local.yaml`. Copiar allí los ejemplos cuando se configure
hardware. `vision_config` se resuelve respecto al YAML de aplicación; si se omite,
se usa `config/vision.yaml` junto al EXE cuando existe, o el ejemplo empaquetado.
Sin configuración, el host es vacío: muestra robot NO CONFIGURADO y no conecta.
El perfil predeterminado es robust. En simulación no se abre cámara ni Modbus.

Acceptance automatizada: Experto con ambos inicios, Intermedio reproducible con
derrota de ambos jugadores, Pícaro independiente de humano/robot y reinicio;
widgets reales para logo, textos, colores, geometría 3×3, cancelación y diagnósticos
con fallos de hardware simulados. Las pruebas no usan cámara ni sockets reales.

El build onedir se completó. `scripts/smoke_windows.ps1` comprueba ambos modos
desde un directorio de trabajo vacío: ventana Robot Triqui que responde durante
10 segundos, cierre controlado con código 0, logs sin traceback y hash del logo
empaquetado idéntico al original. No permite configuración externa de robot en
la distribución de smoke. Las evidencias quedan en `reports/smoke_*`, ignorado.

Resultado: **SMOKE DE PROCESO = PASS** en simulación y real.
**SMOKE VISUAL = NOT CONFIRMED**: no se realizó inspección visual del EXE con
Computer Use. Los widgets y el resolver frozen sí tienen acceptance automatizada.
Esta limitación externa no bloquea el cierre de software autorizado. Video/detección
con cámara física y aceptación física del sistema siguen pendientes.

El harness se distribuye mediante el [entrypoint Python independiente](commissioning.md).
No se genera instalador ni un segundo EXE de commissioning en este cambio.
