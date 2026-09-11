# Aplicación de escritorio Robot Triqui

Para la recuperación del robot después de C14 y la comparación de tiempos
AUTO/DSHOW/MSMF, consultar [Recuperación y diagnóstico](recovery-diagnostics.md).

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
para consultar la ayuda sin hardware. **CÓMO JUGAR** presenta preparación,
turnos, problemas de robot/cámara/tablero y cierre con SALIR, sin requerir términos
del protocolo. **INFORMACIÓN TÉCNICA** conserva commissioning C0–C14, historial, mapa de IDs,
red y diagnóstico técnico. La información de desarrollo no domina la vista inicial.
El estado general se actualiza desde el runtime; la simulación no acredita PASS físico.
Help es solo lectura: no tiene comandos de robot ni ejecuta el harness.

En **CÁMARA / DIAGNÓSTICO** se separan selección de cámara, acciones, perfil,
preview y estado. Se conserva el índice editable porque puede variar. El botón
**CONFIGURACIÓN AVANZADA** despliega Camera N, AUTO/DSHOW/MSMF, DETECTAR y APLICAR; el backend efectivo sigue visible
en diagnóstico. El perfil usa botones segmentados **Robusto / Reflejos / Estándar**
y **APLICAR**, para esta sesión:

- **DETECTAR** prueba 0–5 en segundo plano y libera cada captura de prueba.
  Omite el índice ya abierto, incluso al seleccionar otro backend. Los índices
  no identifican marcas de cámara. No cambia la selección ni los YAML.
- **APLICAR** y **RECONECTAR CÁMARA** cierran antes de sustituir la cámara,
  conservan Modbus y descartan la observación anterior para reacquirir el tablero.
- **REINICIAR SISTEMA** en HOME cancela la partida, recupera explícitamente el
  robot y reinicia la observación temporal. La cámara conectada permanece abierta.
  Esperar nuevamente la estabilización antes de mostrar SISTEMA LISTO.

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

La presentación utiliza cards blancas, badges y texto Segoe UI. La configuración de
visión se agrupa sobre el preview, con una sola nota de sesión. El estado de visión
queda a su lado; **DETALLE** conserva IDs visibles, FPS de la GUI y códigos internos.
En simulación los controles físicos y aplicar perfil están deshabilitados; el
servicio de simulación y la pantalla JUEGO conservan su comportamiento.

En ayuda > **Avanzado** hay dos vistas de evidencia independientes y de solo lectura:

- **Última sesión**, en Commissioning: el último archivo válido por modificación,
  únicamente con los pasos que incluye y su archivo, timestamp y SHA.
- **Historial de validación física**, en Puesta en marcha: último resultado explícito
  de cada C0–C14 por timestamp del reporte (fecha de modificación si falta timestamp).
  Cada fila conserva archivo, fecha y SHA de origen. No se infieren resultados;
  los ausentes son PENDIENTE. PASS, FAIL, BLOCKED y SKIPPED conservan su significado.

Los JSON corruptos se ignoran y ningún reporte se modifica. El historial se etiqueta
como evidencia histórica que puede no representar el hardware actual; no es una
certificación. **Siguiente paso recomendado** toma el primer C1–C14 sin PASS;
C0 se muestra separadamente como evidencia de software. C1–C4 PASS recomienda C5,
y C5 PASS avanza a C6. **VER PROCEDIMIENTO** solo navega a la ayuda del paso.
Los resúmenes C1–C14 describen objetivo, preparación, observación, criterio y riesgo,
según el harness existente. C10/C11 registran evidencia manual; C12/C13 realizan ciclos confirmados.
C14 guía un turno humano+robot o una partida con aceptación visual y confirmación
HOME; requiere --allow-motion y autorizaciones desde el harness, nunca desde ayuda.

**Avanzado > Solucionar problema** ofrece siete opciones con estado runtime y acciones sugeridas.
Help usa scroll vertical y no ejecuta commissioning, terminales ni comandos de robot.
La geometría se comprueba con widgets reales a 900×620 y 1366×768; el logo y JUEGO
permanecen intactos. Las pruebas usan dispositivos falsos, sin validación física nueva.

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
comprobar Modbus de forma independiente, cerrando enseguida esa conexión. `tick()` captura como máximo un frame y
actualiza la observación, y `close()` libera ambos recursos de forma idempotente.

```text
Camera -> ArucoDetector -> BoardObserver -> PhysicalGameRuntime
ModbusClient -> UR
```

La partida solo comienza cuando existe una observación `ready`, sin celdas
inciertas ni ocupadas. Estas condiciones se delegan en
`PhysicalGameRuntime.start()`. Durante la partida, DONE conduce a
`VERIFYING_ROBOT`; el movimiento lógico no se confirma ni se limpia COMMAND hasta
que la visión observa la celda esperada. Después, `ACKNOWLEDGING_ROBOT` espera
READY y cierra la conexión. Se abre una conexión fresca por turno, ninguna queda
ociosa durante la espera humana. Movimiento, verificación y acuse disponen de
60 s por etapa; los ciclos físicos han excedido 15 s.

Un fallo de transporte se muestra como error de dominio y cierra la conexión,
sin reenviar COMMAND ni enviar COMMAND0. Ante una entrega incierta la GUI impide
iniciar otra partida con el comando sin resolver. Inspeccionar robot y Log antes
de recuperación manual. Cerrar aplicación no detiene movimiento físico.

**COMPARAR PERFILES** muestra las últimas muestras de Robusto y Reflejos (y
Estándar), con frames, duración, FPS y porcentaje de visibilidad de cada ID10..18.
Son conteos de las detecciones ya realizadas, sin captura adicional ni cambios
de BoardObserver. Compare al menos 10 s por perfil con tablero vacío y las mismas
condiciones; seleccionar un perfil inicia una muestra nueva para ese perfil.
Cambiar/reconectar cámara o un error de captura descarta la comparación.
Robusto sigue predeterminado. Reflejos es experimental y no se declara mejor
hasta tener evidencia física. Los FPS están limitados por el refresco de la GUI.

El observador usa exclusivamente IDs 10..18 y cuenta las capturas dentro de su
ventana temporal. No requiere marcadores de referencia geométrica. `AppConfig`
permite seleccionar `aruco_profile="default"` para diagnóstico; el valor
operacional es `robust`.

La GUI sigue consumiendo comandos y snapshots: no abre dispositivos ni interpreta
ArUcos. Las casillas no son clicables en modo real. Los estados distinguen cámara,
robot y tablero, y los fallos de apertura quedan en `last_error` sin cerrar la GUI.
Los tests inyectan cámaras, detectores, observers y clientes Modbus pequeños, sin
usar sockets ni hardware real.

En modo real Pícaro permanece deshabilitado; está disponible en simulación.
Como mejora opcional, P_DISCARD, retirada de ficha humana, colocación de ficha
robot y un nuevo contrato de acción requerirían validación física independiente.
No se implementan esas acciones ni se cambian velocidades productivas:
JOINT_A=0.20, JOINT_V=0.10, LINEAR_A=0.05, LINEAR_V=0.02.

La C920 fue detectada y validada a 1280×720 @ 30 FPS. El perfil `robust`
mejoró la detección y es el predeterminado del backend real y de `AppConfig`.
Los IDs 10..18 se han observado 9/9; ID18 presenta más flicker.
El operador confirmó C13 físico PASS y C14 end-to-end físico PASS para v1.0.0.
Consultar [validación física](physical-validation.md) para alcance y repetición.

Los valores iniciales de conexión están en `AppConfig` y se documentan en
`config/app.example.yaml`; no se guardan secretos ni parámetros físicos.

## Identidad institucional y recursos

El logo oficial es opcional y debe colocarse en:

```text
assets/javeriana_logo.png
```

Si no existe, la aplicación continúa normalmente. No se duplican el nombre de la
universidad ni textos académicos en encabezado o pie. `desktop/assets.py` resuelve esta ruta tanto desde el árbol
de desarrollo como desde el directorio temporal `_MEIPASS` de la
aplicación PyInstaller. No se incluye ni se genera una imitación del escudo.

## Cámara / Diagnóstico

La pestaña comparte la única cámara y detección del `RealGameBackend`. Cada tick
captura como máximo un frame; consultar el snapshot o cambiar de pestaña no
captura ni decide jugadas. Presenta video RGB anotado con IDs 10..18, perfil,
resolución efectiva y estados FREE/OCCUPIED/UNCERTAIN. Sin cámara permanece
disponible y muestra CÁMARA NO DISPONIBLE. En simulación no abre dispositivos.

## Validación de Tcl/Tk — nota histórica del entorno de desarrollo

En esta sesión Python 3.12.10 y Tcl/Tk 8.6.15 funcionan fuera del contexto
aislado del asistente. Dentro de ese contexto Tk falla al localizar init.tcl,
aunque los archivos se pueden leer. No se modificó el intérprete ni se guardaron
variables TCL_LIBRARY/TK_LIBRARY globales. Ejecutar `python -m tkinter` y
`python -m pytest -q` desde una terminal normal del proyecto. La suite incluye
widgets Tk reales y necesita una sesión gráfica; no requiere cámara ni robot.
Los temporales locales `.gui-test-temp/` y `.gui-test-cache/` están ignorados.

## Branding académico

El encabezado conserva ROBOT TRIQUI y Sistema autónomo de juego, con el logo
oficial existente a 260×130 px, conservando la proporción 2:1 y el asset original
de 632×316 px para pantallas con escalado. El header compartido permanece visible
en inicio, partida y Cámara / Diagnóstico, sin duplicar el logo.
El logo es la única identificación institucional. Se conserva el badge
SISTEMA REAL / SIMULACIÓN y el pie `By: Juan Esteban León Saiz`.
HOME presenta Experto, Intermedio, Pícaro, Robot y Humano; solo Cámara, Robot y
Tablero en estado del sistema y un único REINICIAR SISTEMA.

SALIR está visible en todas las pestañas. SALIR y la X comparten `shutdown_all()`:
cancelación local, bloqueo de acciones, espera de workers, release de cámara y
cierre independiente de Modbus/Dashboard antes de destruir Tk. No envían comandos
al robot. Si OpenCV sigue abriendo, se mantiene la ventana de cierre hasta liberar
el dispositivo; no queda un worker de esa sesión tras destruir la ventana.

## Distribución Windows onedir

La entrega instalable se genera desde la raíz con `scripts/build_release.ps1`,
usando `.venv/Scripts/python.exe`. Ejecuta pytest, pip check y diff --check antes
de limpiar únicamente build/, dist/ e installer/output/. Usa el spec versionado
`robot_triqui.spec`, conserva el logo y genera su ICO en build/assets/.

Los YAML locales se copian solo a dist/RobotTriqui/config/ como app.yaml y
vision.yaml. Se normaliza vision_config a vision.yaml únicamente en la copia.
Si falta un local se usa su example y el build avisa que requiere configuración.
La procedencia se registra sin IPs en build/stage-result.json.

Inno Setup debe estar instalado previamente; no se descarga automáticamente.
Se busca ISCC.exe en PATH y carpetas habituales, o se acepta `-IsccPath`.
Si falta, queda el onedir construido y el script termina con código distinto de
cero, sin afirmar que exista instalador. El fuente es installer/RobotTriqui.iss;
el resultado final es dist/release/RobotTriqui_Setup.exe, con tamaño y SHA256.
La versión inicial de distribución es 1.0.0; actualizar de forma coordinada el
recurso packaging/version_info.txt y la versión del .iss para futuras entregas.

El instalador es por usuario, no inicia la app y conserva configuración existente
al actualizar. No incluye reports ni archivos de desarrollo. El smoke es siempre
`RobotTriqui.exe --simulate`, aunque la distribución contenga configuración física.
Guía para el operador: [Instalación](installation.md).

Referencias del empaquetado: [spec de PyInstaller](https://pyinstaller.org/en/stable/spec-files.html)
y [modo sin administrador de Inno Setup](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm).

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
Esta limitación histórica del smoke no equivale a una validación física pendiente:
el operador confirmó C13 y C14 físicos PASS al cierre de v1.0.0. No se afirma
una nueva inspección visual automatizada del EXE.

El harness se distribuye mediante el [entrypoint Python independiente](commissioning.md).
El instalador publicado está disponible en [instalación](installation.md).
El harness de commissioning conserva su entrada Python independiente.
