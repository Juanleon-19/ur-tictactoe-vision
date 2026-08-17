# Arquitectura V1

## Principio de separación

La primera versión separa percepción/decisión y movimiento físico.

```text
PC / Python                              UR3 / PolyScope

Cámara
  ↓
OpenCV + ArUco
  ├── 4 marcadores externos -> referencia del tablero
  └── 9 marcadores internos -> ID de celda / ocupación
  ↓
Tablero digital 3×3
  ↓
Reglas + Minimax
  ↓
Comando lógico 1..9  ── Modbus TCP ──>  Selector de subprograma
                                             ↓
                                        Pick & Place
```

El PC indica **qué casilla** jugar. El UR determina **cómo moverse físicamente** porque sus trayectorias se enseñan previamente en PolyScope.

## Sistemas de referencia

En V1 existen dos referencias deliberadamente desacopladas:

1. **Referencia visual del tablero**: definida por cuatro ArUco externos y utilizada por OpenCV.
2. **Referencia física del UR**: definida mediante posiciones enseñadas en PolyScope.

ArUco no modifica automáticamente las poses del UR durante V1.

Esta decisión reduce el riesgo de que un error de estimación visual produzca directamente una trayectoria cartesiana incorrecta.

## Tablero y contrato de IDs

La V1 utiliza dos grupos de marcadores con responsabilidades diferentes.

```text
ID 0                                             ID 1

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

ID 2                                             ID 3
```

### Frame markers

`0,1,2,3` son marcadores persistentes. Deben permanecer visibles mientras el sistema esté habilitado y se usarán para:

- localizar el tablero;
- verificar orientación;
- detectar desplazamientos;
- confirmar que la referencia visual requerida permanece disponible.

La identificación directa por IDs es suficiente para V1 mientras las pruebas sean
fiables; la homografía no es un requisito inicial.

### Cell markers

`10..18` corresponden uno a uno con las nueve casillas:

```text
10 -> 1    11 -> 2    12 -> 3
13 -> 4    14 -> 5    15 -> 6
16 -> 7    17 -> 8    18 -> 9
```

Su ausencia estable será una **señal candidata de ocupación**, no una confirmación inmediata.

## Modelo de ocupación previsto

Durante una partida:

```text
VISIBLE -> FREE
MISSING transitorio -> UNKNOWN / OCCLUDED
MISSING estable + validaciones -> OCCUPIED
```

La transición a `OCCUPIED` deberá considerar:

- persistencia durante varios frames;
- que la referencia externa del tablero siga válida;
- que no haya una oclusión transitoria causada por mano o robot;
- que la casilla estuviera libre en el estado lógico anterior;
- que el cambio sea coherente con el turno actual.

La V1 no depende de reconocer visualmente la forma X/O para saber a quién pertenece una jugada: inicialmente esa propiedad puede derivarse del turno y del estado lógico. Si las pruebas muestran que hace falta una segunda fuente de evidencia, se añadirá una clasificación visual específica en su fase correspondiente.

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

- `FRAME READY` cuando `0,1,2,3` son visibles;
- contador de `10..18` visibles;
- `EMPTY BOARD READY` cuando los 13 marcadores son visibles.

No se clasifica ocupación todavía.

No existe ninguna dependencia hacia módulos del robot.

## Game Engine

`game/engine.py` mantiene el tablero, valida celdas públicas `1..9` y aplica las
reglas. `game/minimax.py` explora el árbol completo sin depender de visión ni del
robot. El robot maximiza y el humano minimiza una puntuación terminal que favorece
victorias rápidas y retrasa derrotas. Entre jugadas con idéntico valor óptimo, se
prefiere la que deja menos respuestas humanas que conserven el mejor resultado
del humano; este criterio nunca degrada el resultado Minimax.

## Flujo físico aprobado

PolyScope contiene `HOME`, `PICK_APPROACH`, un único `PICK` fijo, `PICK_EXIT` y
`Play_Cell_1 ... Play_Cell_9`. Otra persona coloca cada ficha del robot en PICK.
No hay magazine automático y Python nunca genera trayectorias. En integración,
Python enviará solamente `COMMAND = 1..9` por Modbus.

## Evolución prevista

La arquitectura crecerá por responsabilidades:

```text
src/ur_tictactoe/
├── vision/          # Fases 1 y 2
├── game/            # Fase 3
└── communication/   # Fase 5, aún no creada
```

Estas carpetas futuras no deben crearse hasta que comience su fase correspondiente.

## Robustez opcional

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
