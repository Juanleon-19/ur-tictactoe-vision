# Arquitectura V1

## Principio de separación

La primera versión separa percepción/decisión y movimiento físico.

```text
PC / Python                              UR3 / PolyScope

Cámara
  ↓
OpenCV + ArUco
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

1. **Referencia visual del tablero**: definida por ArUco y utilizada por OpenCV.
2. **Referencia física del UR**: definida mediante posiciones enseñadas en PolyScope.

ArUco no modifica automáticamente las poses del UR durante V1.

Esta decisión reduce el riesgo de que un error de estimación visual produzca directamente una trayectoria cartesiana incorrecta.

## Tablero

Configuración conceptual:

```text
ID 0                         ID 1

        ┌─────┬─────┬─────┐
        │  1  │  2  │  3  │
        ├─────┼─────┼─────┤
        │  4  │  5  │  6  │
        ├─────┼─────┼─────┤
        │  7  │  8  │  9  │
        └─────┴─────┴─────┘

ID 2                         ID 3
```

Los IDs forman parte del contrato geométrico y no deben cambiarse sin actualizar configuración y documentación.

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

No existe ninguna dependencia hacia módulos del robot.

## Evolución prevista

La arquitectura crecerá por responsabilidades:

```text
src/ur_tictactoe/
├── vision/          # Fases 1, 2 y 4
├── game/            # Fase 3
├── communication/   # Fase 7
└── application/     # Integración posterior
```

Estas carpetas futuras no deben crearse hasta que comience su fase correspondiente.

## V2 potencial

Una versión futura puede incorporar:

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