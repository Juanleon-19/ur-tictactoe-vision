# Arquitectura de Robot Triqui — v1.0.0

## Separación de responsabilidades

Python gestiona cámara, ArUco, observación temporal, juego, Minimax, Modbus y
verificación. PolyScope ejecuta movimientos a partir de posiciones enseñadas.
El PC indica qué celda jugar; no calcula ni transmite trayectorias cartesianas.

```text
C920 → Camera → ArucoDetector → BoardObserver → PhysicalBoardState
                                                   ↓
GUI → GameApplication → RealGameBackend → PhysicalGameRuntime
                                                   ↓
                                             GameSession / Minimax
                                                   ↓
                                              ModbusClient
                                                   ↓
                                    UR / PolyScope → PICK → PLACE → HOME
                                                   ↓
                                      Observación visual y acuse
```

La GUI representa snapshots e intenciones; no implementa juego, visión ni protocolo.
El modo simulado usa dispositivos falsos. Ver [desktop](desktop-app.md) y
[runtime](mvp-runtime.md).

## Identificación y ocupación

El contrato operacional es **DICT_5X5_50**, nueve marcadores:

```text
10 → CELL1    11 → CELL2    12 → CELL3
13 → CELL4    14 → CELL5    15 → CELL6
16 → CELL7    17 → CELL8    18 → CELL9
```

BoardObserver mantiene una ventana temporal y produce ocupación sin propietario
X/O. Usa los IDs de celda; no exige marcadores externos. Una detección ausente
no se convierte inmediatamente en jugada. El runtime compara estado físico y
lógico, exige observación ready sin incertidumbre y acepta una única nueva
ocupación durante el turno humano. Las retiradas o cambios múltiples no se
interpretan como una jugada normal. El propietario se deriva del turno.

Las dos fichas deben ocultar el ArUco de forma repetible. Mano, robot, reflejos y
falta de foco pueden afectar la observación; el montaje se acepta mediante
[commissioning](commissioning.md). Perfil predeterminado: `robust`.
No se cambian umbrales para compensar una fijación o iluminación deficiente.

## Juego y verificación

[Game Engine](game-engine.md) implementa reglas y Minimax sin depender de hardware.
GameSession mantiene intención y tablero lógico. En modo real, DONE inicia la
verificación visual; la celda elegida debe aparecer ocupada junto con las ocupaciones
esperadas. Solo después se confirma y acusa la jugada con COMMAND0, se espera
READY y se cierra la conexión antes del siguiente turno.

La entrega incierta se conserva como error; no hay reenvío automático. Experto e
Intermedio están disponibles en modo real; Pícaro permanece solo en simulación.
Ver [recuperación](recovery-diagnostics.md).

## Referencia física y movimiento

La referencia visual por ID y la referencia física del UR están desacopladas.
La cámara no corrige poses ni acredita por sí sola la alineación del tablero.
Fijar el montaje y repetir las comprobaciones afectadas si se desplaza.

PolyScope recibe P1/P3/P7/P9/P_PICK/P_HOME mediante seis Assignments de Point
Features. El UR calcula las demás celdas por promedios XYZ con orientación P1.
`pose_trans(Pn, p[0,0,-0.060,0,0,0])` eleva 60 mm en −Z Tool con el TCP validado.
PICK es fijo y HOME conserva la pose enseñada. La reposición de fichas requiere
preparación del operador. Seguir [PolyScope](polyscope-urscript.md).

[Modbus](modbus-protocol.md) usa TCP 502, COMMAND128 (0 y 1..9) y STATUS129
(READY/BUSY/DONE/ERROR). El modo físico se selecciona en el robot; Python no
transmite poses ni selecciona modos. El cierre de la app no es parada física.

## Componentes y distribución

- `vision/`: cámara, ArUco y observación/detección temporal.
- `game/`: reglas, estrategias y sesión.
- `communication/`: transporte y contrato Modbus.
- El runtime integra estados físicos y juego; desktop coordina la aplicación Windows.
- PolyScope carga [triqui_controller.script](../robot/urscript/triqui_controller.script).

La aplicación se distribuye como instalador Windows que incluye Python y sus
dependencias. El harness de commissioning usa el entorno Python del repositorio.
Ver [instalación](installation.md) y [construcción completa](build-from-scratch.md).

## Validación e historia

El operador confirmó C13 físico PASS y C14 end-to-end físico PASS para el cierre
v1.0.0. La suite automática usa dobles y no valida movimientos reales.

El diseño inicial de 13 marcadores con IDs 0..3 externos y la referencia Plane
Feature son históricos. El flujo auxiliar HumanMoveDetector/GameController
se conserva en código y tests; la GUI real y C14 usan BoardObserver y
PhysicalGameRuntime. Homografía, pose 3D, hand-eye y reconocimiento X/O no son
requisitos de la arquitectura operacional. Ver [plan e historia](../PLAN.md).
