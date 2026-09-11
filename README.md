# Robot Triqui

Sistema autónomo de Tic-Tac-Toe desarrollado para Universal Robots,
con OpenCV + ArUco, Minimax, Modbus TCP y una aplicación de escritorio.

## Descargar

### Windows — v1.0.0

**[⬇ Descargar RobotTriqui_Setup.exe](https://github.com/Juanleon-19/ur-tictactoe-vision/releases/download/v1.0.0/RobotTriqui_Setup.exe)**

Windows 10/11 x64. **No necesita Python** para usar el instalador.
SmartScreen puede advertir porque el instalador no está firmado.
[Ver la Release completa v1.0.0](https://github.com/Juanleon-19/ur-tictactoe-vision/releases/tag/v1.0.0).

## Demostración

> Foto del montaje real: pendiente de agregar.

> Video de funcionamiento: pendiente de agregar.

La [lista de material audiovisual](docs/media.md) está preparada para completar la demostración.

## Qué hace el sistema

Robot Triqui observa un tablero 3×3, identifica la jugada humana por la desaparición
estable del ArUco de una casilla y decide una respuesta. El UR recoge una ficha
en un PICK fijo, la coloca y vuelve a HOME. La cámara verifica la colocación antes
de continuar. El suministro de fichas en PICK requiere preparación del operador.

La aplicación ofrece Experto (Minimax), Intermedio y Pícaro, este último únicamente
en simulación. Permite elegir quién inicia y consultar el diagnóstico de cámara y robot.

## Configuración validada

- Universal Robots **UR3 CB3**.
- **PolyScope 3.14**.
- **Logitech C920**, adquisición configurada a 1280×720 y 30 FPS; los FPS efectivos dependen de la captura y la GUI.
- Pinza Robotiq mediante URCap — **modelo exacto pendiente de documentar**.

**C13 físico: PASS. C14 end-to-end físico: PASS**, según confirmación del operador
para el cierre del proyecto. Los tests automáticos no acreditan hardware ni sustituyen
el commissioning de otro montaje. Ver [validación física](docs/physical-validation.md).

## Cómo usarlo

1. [Instalar y abrir Robot Triqui](docs/installation.md) en un montaje configurado.
2. Preparar tablero vacío, fichas, cámara y programa PolyScope.
3. Esperar Cámara **CONECTADA**, Robot **LISTO** y Tablero **LISTO**.
4. Elegir dificultad e inicio y pulsar **INICIAR PARTIDA**.
5. Colocar una sola ficha en el turno humano y retirar la mano; mantener libre la zona durante el turno robot.
6. Al terminar, usar **SALIR** y esperar el cierre de dispositivos.

## Construir desde cero

Seguir la [guía de construcción completa](docs/build-from-scratch.md): fabricación,
ArUco, montaje, cámara, PolyScope, configuración local y commissioning C0–C14.
Los CAD y datos de fabricación están en [hardware](hardware/README.md), con
una [BOM descargable](hardware/BOM.csv). El soporte, la tornillería y ciertos datos
de fabricación siguen pendientes de documentar; se indican explícitamente.

## Tabla de fabricación

| Elemento | Cantidad | Proceso | Archivo/Referencia |
|----------|----------|---------|--------------------|
| Ficha X | 5 | Impresión 3D | [ficha_X.stl](hardware/pieces/ficha_X.stl) |
| Ficha O | 5 | Impresión 3D | [ficha_O.stl](hardware/pieces/ficha_O.stl) |
| Base 1 | 1 | Corte láser | [base_1.dxf](hardware/board/base_1.dxf) |
| Base 2 | 1 | Corte láser | [base_2.dxf](hardware/board/base_2.dxf) |
| Horizontal central | 2 | Corte láser | [horizontal_central_x2.dxf](hardware/board/horizontal_central_x2.dxf) |
| Horizontal lateral | 2 | Corte láser | [horizontal_lateral_x2.dxf](hardware/board/horizontal_lateral_x2.dxf) |
| Vertical central | 2 | Corte láser | [vertical_central_x2.dxf](hardware/board/vertical_central_x2.dxf) |
| Vertical lateral | 2 | Corte láser | [verticales_laterales_x2.dxf](hardware/board/verticales_laterales_x2.dxf) |
| ArUco (IDs 10..18) | 9 | Impresión 2D | [generate_aruco.py](scripts/generate_aruco.py) |
| Soporte de cámara | 1 | DISEÑO/ARCHIVO PENDIENTE DE PUBLICAR | Sin archivo publicado |
| Tornillería M5 / T-slot | POR CONFIRMAR | Ensamble | Longitudes POR CONFIRMAR |

## Arquitectura

```text
Cámara → OpenCV/ArUco → BoardObserver → GameSession/Minimax
                                             ↓ celda 1..9
                                         Modbus TCP
                                             ↓
                                   PolyScope → PICK → PLACE → HOME
                                             ↓
                                   Verificación visual → siguiente turno
```

Python gestiona percepción, estado temporal, juego, comunicación y verificación.
PolyScope conserva las posiciones, interpola las celdas y ejecuta los movimientos.
Python no genera trayectorias cartesianas. La visión usa IDs directamente, sin
homografía, pose 3D ni calibración hand-eye. Ver [arquitectura](docs/architecture.md).

## PolyScope

Enseñar Point Features **CELL1, CELL3, CELL7, CELL9, PICK y HOME/WAIT**.
Antes del Script Node, crear estos Assignments:

```text
P1 = CELL1_const
P3 = CELL3_const
P7 = CELL7_const
P9 = CELL9_const
P_PICK = Feature real de recogida
P_HOME = Feature HOME/WAIT
```

Las dos últimas expresiones describen las poses que se seleccionan en PolyScope;
no son nombres literales para copiar. Cargar
[robot/urscript/triqui_controller.script](robot/urscript/triqui_controller.script).
Las otras cinco celdas se derivan en el UR; la orientación de las celdas es P1.
**APPROACH_DZ = -0.060**: con el TCP validado, −Z Tool eleva 60 mm.
Las poses reales se enseñan en cada montaje y no se publican.

Seguir el [procedimiento completo de PolyScope](docs/polyscope-urscript.md),
incluidas funciones Robotiq, Assignments y modos de commissioning.

## Modbus

TCP `502`, direccionamiento base cero:

| Registro | Valores |
|----------|---------|
| 128 COMMAND | 0: reposo/acuse; 1..9: celda |
| 129 STATUS | 0: READY; 1: BUSY; 2: DONE; 3: ERROR |

READY → COMMAND de celda → BUSY → DONE → verificación visual → COMMAND0 → READY.
El PC envía solamente la celda como orden de juego. COMMAND0 no es una parada.
No hay reenvío automático tras entrega incierta. Ver [contrato Modbus](docs/modbus-protocol.md).

## Desarrollo desde código

Usar Windows con Python **3.12** y Tcl/Tk funcional para la suite GUI.

```powershell
git clone https://github.com/Juanleon-19/ur-tictactoe-vision.git
cd ur-tictactoe-vision
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
python -m pytest -q
python -m pip check
python main.py app --simulate
```

[requirements-build.txt](requirements-build.txt) fija las versiones del entorno
validado; [requirements.txt](requirements.txt) contiene los rangos de dependencias.
La simulación no abre cámara ni robot. La suite requiere una sesión gráfica y usa
dispositivos falsos. Para modo real, preparar los YAML de ejemplo según
[construir desde cero](docs/build-from-scratch.md).

Las instrucciones para reconstruir una distribución están en
[distribución desktop](docs/desktop-app.md) y [paquete portable](docs/portable-release.md).
La descarga oficial sigue siendo el binario validado v1.0.0; reconstruir localmente
no garantiza un ejecutable idéntico byte a byte ni actualiza esa Release.

## ArUco

Diccionario operacional: **DICT_5X5_50**, nueve marcadores:

```text
10 11 12
13 14 15
16 17 18
```

| ID | Celda | ID | Celda | ID | Celda |
|----|-------|----|-------|----|-------|
| 10 | CELL1 | 11 | CELL2 | 12 | CELL3 |
| 13 | CELL4 | 14 | CELL5 | 15 | CELL6 |
| 16 | CELL7 | 17 | CELL8 | 18 | CELL9 |

```powershell
python scripts/generate_aruco.py --ids 10 11 12 13 14 15 16 17 18
```

Los PNG se generan en `assets/aruco/`. Imprimir sin deformar, con margen blanco
y sin reflejos; confirmar tamaño físico con el montaje. Ambas fichas deben ocultar
su marcador al colocarse. Una ausencia aislada no equivale a ocupación: se valida
temporalmente y contra el estado del juego. Ver [preparación física](hardware/README.md).

## Estructura del repositorio

```text
hardware/          STL, DXF, BOM e imágenes pendientes
docs/              Instalación, construcción y procedimientos
config/            Ejemplos YAML; configuración personal ignorada
src/ur_tictactoe/   Visión, juego, comunicación, runtime y escritorio
robot/urscript/    Controlador ejecutado en PolyScope
scripts/           ArUco, commissioning y construcción de distribución
tests/             Pruebas sin hardware real
assets/            Recursos de la aplicación
installer/         Fuente del instalador
packaging/         Recursos de empaquetado
main.py            Entrada de aplicación y herramientas
```

## Documentación

- [Instalación Windows](docs/installation.md) y [construir desde cero](docs/build-from-scratch.md).
- [Fabricación y pendientes](hardware/README.md) y [material audiovisual](docs/media.md).
- [PolyScope](docs/polyscope-urscript.md) y [calibración física](docs/calibracion-fisica.md).
- [Commissioning C0–C14](docs/commissioning.md) y [validación física](docs/physical-validation.md).
- [Arquitectura](docs/architecture.md), [motor de juego](docs/game-engine.md) y [runtime](docs/mvp-runtime.md).
- [Modbus](docs/modbus-protocol.md), [aplicación desktop](docs/desktop-app.md) y [recuperación](docs/recovery-diagnostics.md).
- [Plan y cierre del proyecto](PLAN.md).

## Seguridad

Operar con zona despejada, estado físico conocido y parada física accesible.
Enseñar y comprobar TCP, payload, Features y recorridos en el equipo real.
Al mover tablero, cámara, PICK o herramienta, repetir las comprobaciones afectadas.
La identificación por IDs no acredita alineación mecánica ni corrige las poses.
No poner las manos en la zona mientras se mueve el UR; reponer PICK únicamente en
condiciones seguras. SALIR, Ctrl+C, ABORT, timeout y COMMAND0 no detienen un
movimiento ya iniciado. Los tests automáticos nunca deben mover hardware.

## Autor

Juan Esteban León Saiz — [Juanleon-19](https://github.com/Juanleon-19).
