# Arquitectura V1

## Principio de separación

La primera versión separa percepción/decisión y movimiento físico.

```text
PC / Python                              UR3 / PolyScope

Cámara
  ↓
OpenCV + ArUco
  └── 9 marcadores internos -> ID de celda / ocupación
  ↓
Tablero digital 3×3
  ↓
Reglas + Minimax
  ↓
Comando lógico 1..9  ── Modbus TCP ──>  Selector Pn / Pn_UP en URScript
                                             ↓
                                        Pick & Place
```

El PC indica **qué casilla** jugar. El UR determina **cómo moverse físicamente** porque sus trayectorias se enseñan previamente en PolyScope.

## Sistemas de referencia

En V1 existen dos referencias deliberadamente desacopladas:

1. **Identificación visual de casillas**: definida directamente por IDs 10..18.
2. **Referencia física del UR**: definida mediante posiciones enseñadas en PolyScope.

ArUco no modifica automáticamente las poses del UR durante V1.

Esta decisión reduce el riesgo de que un error de estimación visual produzca directamente una trayectoria cartesiana incorrecta.

## Tablero y contrato de IDs

La V1 utiliza exclusivamente nueve marcadores de celda, IDs 10..18.

```text
        ┌─────────┬─────────┬─────────┐
        │ ID 10   │ ID 11   │ ID 12   │
        │ CELL 1  │ CELL 2  │ CELL 3  │
        ├─────────┼─────────┼─────────┤
        │ ID 13   │ ID 14   │ ID 15   │
        │ CELL 4  │ CELL 5  │ CELL 6  │
        ├─────────┼─────────┼─────────┤
        │ ID 16   │ ID 17   │ ID 18   │
        │ CELL 7  │ CELL 8  │ CELL 9  │
        └─────────┴─────────┴─────────┘
```

### Cell markers

`10..18` corresponden uno a uno con las nueve casillas:

```text
10 -> 1    11 -> 2    12 -> 3
13 -> 4    14 -> 5    15 -> 6
16 -> 7    17 -> 8    18 -> 9
```

Su ausencia estable será una **señal candidata de ocupación**, no una confirmación inmediata.

## Modelo de ocupación previsto

`BoardObserver` trabaja únicamente con la historia de IDs 10..18. Cada captura
procesada aporta una muestra, incluso si no se detecta ningún marcador. Los IDs
ajenos a las celdas se ignoran. Un error de captura no aporta una muestra.

Se conservan `window_seconds=1.5`, `evaluation_period_seconds=0.25`,
`state_change_seconds=0.5`, `free_ratio=0.70`, `occupied_ratio=0.20` y
`min_valid_samples=3`. Este último indica el mínimo de muestras capturadas dentro
de la ventana; no existe un filtro por referencias geométricas.

`ready` indica que hay muestras suficientes, no que el tablero esté vacío o que
la imagen sea inequívoca. El inicio de partida exige además ausencia de celdas
`OCCUPIED` y `UNCERTAIN`. El flicker ocasional se absorbe mediante los ratios
temporales. Una oclusión prolongada aún puede parecer ocupación y requiere
validación física; no se incorpora otro clasificador de visión.

Durante una partida:

```text
VISIBLE -> FREE
MISSING transitorio -> historial temporal / UNCERTAIN
MISSING estable + validaciones -> OCCUPIED
```

La transición a `OCCUPIED` deberá considerar:

- persistencia durante varios frames;
- que no haya una oclusión transitoria causada por mano o robot;
- que la casilla estuviera libre en el estado lógico anterior;
- que el cambio sea coherente con el turno actual.

La V1 no depende de reconocer visualmente la forma X/O para saber a quién pertenece una jugada: inicialmente esa propiedad puede derivarse del turno y del estado lógico. Si las pruebas muestran que hace falta una segunda fuente de evidencia, se añadirá una clasificación visual específica en su fase correspondiente.

### Detección lógica de una jugada humana

La Fase 2 compara los IDs visibles con los marcadores que ya se esperan ausentes
porque sus celdas están ocupadas:

```text
IDs visibles -> nueva ausencia única -> N frames estables -> celda 1..9
```

Si aparecen varias ausencias nuevas, la candidata se
descarta. El detector solo produce el evento lógico; no decide el turno ni modifica
el tablero del Game Engine.

## Implicación mecánica

El principio `marker missing -> candidate occupied` requiere que **ambos tipos de pieza oculten el ArUco de su casilla de forma repetible**.

El diseño mecánico deberá garantizar una zona opaca común sobre el marcador. En particular, una pieza O con un agujero central no puede dejar el ArUco completamente visible cuando esté correctamente colocada.

## Fase 1

Componentes activos:

```text
main.py
  ↓
config.py
  ↓
vision/app.py
  ├── camera.py
  └── aruco.py
```

La Fase 1 solo valida detección y roles de IDs:

- contador de `10..18` visibles;
- listado de IDs de celda faltantes.

No se clasifica ocupación todavía.

No existe ninguna dependencia hacia módulos del robot.

## Game Engine

`game/engine.py` mantiene el tablero, valida celdas públicas `1..9` y aplica las
reglas. `game/minimax.py` explora el árbol completo sin depender de visión ni del
robot. El robot maximiza y el humano minimiza una puntuación terminal que favorece
victorias rápidas y retrasa derrotas. Entre jugadas con idéntico valor óptimo, se
prefiere la que deja menos respuestas humanas que conserven el mejor resultado
del humano; este criterio nunca degrada el resultado Minimax.

## Game Session

La sesión coordina una partida sin acoplar visión ni ejecución física:

```text
HumanMoveDetector -> human_move -> GameSession -> Game Engine / Minimax
                                             -> pending_robot_move
                                             -> futura confirmación Modbus
                                             -> confirm_robot_move()
```

`request_robot_move()` solo registra la intención elegida por Minimax. El tablero
se actualiza cuando `confirm_robot_move()` confirma que la acción externa terminó.
Una cancelación elimina la intención pendiente sin alterar el tablero.

## Flujo físico aprobado

PolyScope contiene cuatro Point Features de colocación CELL1/CELL3/CELL7/CELL9,
recogida y HOME/WAIT. Seis Assignments crean P1/P3/P7/P9/P_PICK/P_HOME antes del
Script Node. El UR deriva P2/P4/P5/P6/P8 por promedios XYZ, con orientación P1.
`pose_trans(Pn, p[0,0,-0.060,0,0,0])` eleva 60 mm sobre Tool Z; +Tool Z baja.
P_PICK tiene la misma aproximación y HOME conserva su pose enseñada.
Otra persona repone cada ficha en PICK. Python envía solo COMMAND=1..9,
nunca coordenadas. Recalibrar el tablero requiere editar solo cuatro Features.

La frontera de comunicación conserva separadas decisión y ejecución:

```text
GameSession -> pending_robot_move -> ModbusClient -> PolyScope
```

`ModbusClient` solo lee `STATUS` y escribe `COMMAND`; una capa de integración
externa verifica ocupación después de DONE y acusa con COMMAND0 antes de READY.
El runtime real conserva evidencia de entrega incierta ante errores y no reenvía.

La integración de software completa queda coordinada por ciclos no bloqueantes:

```text
C920/OpenCV -> HumanMoveDetector -> GameController -> GameSession
                                                   -> ModbusClient -> PolyScope
```

Actualmente esta cadena está validada con IDs visibles y transporte Modbus
simulados. `GameController` recibe sus componentes por inyección y no crea cámara,
conexiones ni direcciones IP.

## Evolución prevista

La arquitectura crecerá por responsabilidades:

```text
src/ur_tictactoe/
├── vision/          # Fases 1 y 2
├── game/            # Fase 3
└── communication/   # Contrato 128/129 y transporte Modbus
```

Estas carpetas futuras no deben crearse hasta que comience su fase correspondiente.

## Robustez opcional

### Observación física temporal

`BoardObserver` mantiene una ventana temporal de detecciones y solo calcula
ocupación con muestras que contienen los cuatro frame IDs. Produce un
`PhysicalBoardState` independiente de `GameSession`, sin propietario X/O:

```text
IDs ArUco -> BoardObserver -> FREE / OCCUPIED / UNCERTAIN / NOT_READY
```

La integración futura durante el turno humano será:

```text
PhysicalBoardState
  -> comparar con Board lógico
  -> new_cells = physical_occupied - logical_occupied
```

En modo normal se aceptará una jugada solo si aparece exactamente una celda
nueva y no desaparece ninguna ocupada. Ante cambios múltiples se esperará otro
estado estable o se invalidará la observación.

Después de un movimiento robot, `STATUS DONE` activará la observación y se
verificará que la celda esperada quedó `OCCUPIED` antes de llamar a
`confirm_robot_move()`. Esta integración está documentada, no implementada.

### Preparación del futuro modo PÍCARO

El observador actual maneja únicamente ocupación. Más adelante, las X físicas
verdes y los círculos amarillos sobre el tablero plateado podrán distinguirse
por color mediante HSV/ROI. No se prevé reconocer la geometría X/O y todavía no
existe código HSV.

### Distribución futura

El producto final será una aplicación de escritorio Windows, no una aplicación
web. Permitirá seleccionar modo de juego, quién inicia e iniciar una partida.
La ruta prevista es aplicación Python -> PyInstaller o equivalente -> aplicación
distribuible -> instalador `.exe` (por ejemplo, Inno Setup), incluyendo las
dependencias para no exigir una instalación manual de Python. No se implementa
GUI, empaquetado ni instalador en esta tarea.

La Fase 7 puede incorporar, solo con evidencia experimental:

```text
ArUco / ChArUco
  ↓
calibración de cámara
  ↓
pose 3D del tablero
  ↓
transformación cámara ↔ robot
  ↓
corrección automática de posiciones
```

Ese alcance no pertenece al MVP.

## Mejoras futuras

Los IDs 0..3 podrían incorporarse como referencia geométrica/homografía opcional.
No están disponibles ni forman parte del sistema operacional actual.
