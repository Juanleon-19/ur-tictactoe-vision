# UR Tic-Tac-Toe Vision

Sistema de visión artificial para que un robot **Universal Robots** juegue Triqui (Tic-Tac-Toe) contra una persona.

El primer prototipo utilizará un **UR3**, una cámara fija, Python, OpenCV, marcadores ArUco y comunicación Modbus TCP. El movimiento del robot no se generará dinámicamente desde Python: las posiciones y trayectorias se enseñarán y validarán directamente en PolyScope mediante subprogramas.

## Objetivo

Construir un sistema modular capaz de:

1. localizar visualmente un tablero 3×3 mediante marcadores ArUco;
2. rectificar la imagen y dividirla en nueve regiones de interés;
3. detectar la jugada realizada por una persona;
4. mantener el estado lógico de la partida;
5. seleccionar una respuesta mediante un algoritmo de juego, inicialmente Minimax;
6. enviar al UR únicamente el número de la casilla elegida;
7. ejecutar en PolyScope una trayectoria preenseñada de pick-and-place;
8. verificar visualmente que la jugada del robot se realizó correctamente.

## Arquitectura V1

```text
Cámara
  ↓
OpenCV + ArUco
  ↓
Detección del tablero y jugada humana
  ↓
Estado 3×3 + reglas + Minimax
  ↓
Comando de casilla 1..9
  ↓
Modbus TCP
  ↓
UR3 / PolyScope
  ↓
Subprograma preenseñado
  ↓
Pick & Place
```

### Responsabilidad de Python

Python será responsable de:

- adquisición de imagen;
- detección ArUco;
- rectificación del tablero;
- detección de cambios en las nueve celdas;
- lógica del juego;
- decisión de la jugada;
- comunicación Modbus;
- verificación posterior de la jugada.

Python **no calculará inicialmente las trayectorias cartesianas del UR**.

### Responsabilidad de PolyScope

PolyScope será responsable de:

- HOME;
- aproximación y retirada;
- punto de recogida de la pieza;
- accionamiento de la herramienta;
- posiciones de las nueve casillas;
- velocidades, aceleraciones y movimientos seguros;
- subprogramas de pick-and-place.

## Uso de ArUco en la V1

Los marcadores ArUco funcionarán como referencias visuales del tablero. Inicialmente se usarán cuatro marcadores alrededor de la matriz 3×3:

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

En esta versión ArUco se utilizará para:

- localizar el tablero en la imagen;
- obtener referencias geométricas estables;
- corregir perspectiva mediante homografía;
- definir las nueve regiones de interés;
- comprobar que el tablero no se haya desplazado fuera de tolerancia.

La estimación completa de pose 3D y la corrección automática de posiciones del robot se reservan para una versión futura.

## Comunicación con el UR

La interfaz prevista es Modbus TCP con un protocolo simple de comando/estado.

Ejemplo conceptual:

```text
COMMAND
0 = idle
1..9 = jugar en la casilla indicada

STATUS
0 = ready
1 = busy
2 = done
3 = error
```

Los valores definitivos y las direcciones de registros se fijarán durante la fase de integración Modbus.

## Fases

1. **Foundation & ArUco** — Git, entorno Python, cámara y detección de marcadores.
2. **Board Vision** — homografía, tablero rectificado y nueve ROI.
3. **Game Engine** — estado 3×3, reglas y Minimax.
4. **Human Move Detection** — detección robusta de nuevas jugadas.
5. **PolyScope** — HOME, PICK y subprogramas para las nueve casillas.
6. **Piece Handling** — recogida y liberación repetibles.
7. **Modbus** — protocolo COMMAND/STATUS entre Python y UR.
8. **Integration** — visión → decisión → Modbus → robot.
9. **Verification** — confirmación visual y recuperación de errores.
10. **Validation** — métricas, pruebas y documentación final.

El detalle de cada fase se mantiene en [`PLAN.md`](PLAN.md).

## Filosofía de desarrollo

- VS Code será el entorno principal de desarrollo.
- GitHub será la fuente de verdad del proyecto.
- Se trabajará por fases y ramas pequeñas.
- No se implementarán fases futuras antes de validar la actual.
- Los commits técnicos se escribirán en inglés.
- La documentación del proyecto se mantendrá principalmente en español.
- Ningún código automático debe mover el robot durante las primeras fases.
- Las posiciones reales del UR, IP, calibraciones y parámetros locales no se publicarán en el repositorio.

## Estado actual

**Fase 1 — Foundation & ArUco.**

Primer objetivo verificable: abrir una cámara desde Python, detectar los marcadores ArUco esperados y mostrar sus IDs y esquinas en tiempo real, sin ninguna conexión con el robot.
