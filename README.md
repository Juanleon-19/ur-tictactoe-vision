# UR Tic-Tac-Toe Vision

Sistema de visión artificial para que un robot **Universal Robots** juegue Triqui (Tic-Tac-Toe) contra una persona.

El primer prototipo utilizará un **UR3**, una cámara fija, Python, OpenCV, marcadores ArUco y comunicación Modbus TCP. El movimiento del robot no se generará dinámicamente desde Python: las posiciones y trayectorias se enseñarán y validarán directamente en PolyScope mediante subprogramas.

## Objetivo

Construir un sistema modular capaz de:

1. localizar visualmente un tablero 3×3 mediante marcadores ArUco externos;
2. identificar individualmente cada casilla mediante un ArUco propio;
3. detectar si una casilla pasa de libre a ocupada por la oclusión estable de su marcador;
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
4 ArUco externos -> referencia y alineación del tablero
9 ArUco internos -> identificación de celdas y ocupación
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
- referencia visual y alineación del tablero;
- asociación ID ArUco ↔ casilla lógica;
- detección temporal de casillas libres/ocupadas;
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

## Diseño ArUco de la V1

La V1 utilizará **13 marcadores** del mismo diccionario:

- 4 marcadores externos persistentes para la referencia visual del tablero;
- 9 marcadores internos, uno por cada casilla.

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

### Marcadores externos

Los IDs `0,1,2,3` permanecerán visibles durante toda la partida. Su función será:

- localizar el tablero;
- proporcionar una referencia geométrica estable;
- permitir rectificación/alineación en una fase posterior;
- detectar desplazamientos del tablero.

### Marcadores por casilla

Los IDs `10..18` identifican las casillas 1..9 respectivamente.

Contrato inicial:

```text
ID 10 -> celda 1
ID 11 -> celda 2
ID 12 -> celda 3
ID 13 -> celda 4
ID 14 -> celda 5
ID 15 -> celda 6
ID 16 -> celda 7
ID 17 -> celda 8
ID 18 -> celda 9
```

El principio previsto de ocupación será:

```text
marcador visible de forma estable    -> casilla libre
marcador deja de ser visible         -> candidata a casilla ocupada
```

La desaparición de un marcador **no se aceptará inmediatamente como jugada**. En fases posteriores se requerirá estabilidad temporal, ausencia de mano/robot en la zona y coherencia con el estado lógico previo.

### Requisito mecánico importante

Las piezas X y O deben diseñarse para **ocultar de forma fiable el marcador ArUco de la casilla** cuando están correctamente colocadas. Un O completamente abierto podría dejar visible un marcador situado en el centro, por lo que el diseño deberá incluir una zona opaca común, puente, base o geometría equivalente que garantice la oclusión del marcador sin perder la apariencia de la pieza.

Los cuatro ArUco externos permanecen visibles incluso cuando las casillas se ocupan; por eso la referencia del tablero no depende de que los marcadores internos sigan visibles.

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

1. **Foundation & ArUco** — Git, entorno Python, cámara y detección de los 13 marcadores.
2. **Board & Cell Mapping** — referencia del tablero y asociación robusta ID ↔ celda.
3. **Game Engine** — estado 3×3, reglas y Minimax.
4. **Occupancy & Human Move Detection** — detección temporal de ocupación mediante ArUco y validación de jugadas.
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

## Inicio rápido en Windows + VS Code

Clonar el repositorio y abrirlo en VS Code:

```powershell
git clone https://github.com/Juanleon-19/ur-tictactoe-vision.git
cd ur-tictactoe-vision
code .
```

Crear y activar un entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instalar dependencias:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Crear la configuración local a partir del ejemplo:

```powershell
Copy-Item config\vision.example.yaml config\vision.local.yaml
```

Ejecutar las pruebas automáticas:

```powershell
pytest -q
```

Generar los 13 marcadores ArUco iniciales:

```powershell
python scripts\generate_aruco.py
```

Los PNG se guardarán en `assets/aruco/`. El tamaño físico definitivo se decidirá después de conocer cámara, altura, tamaño del tablero y campo de visión.

Ejecutar la visión en tiempo real:

```powershell
python main.py vision
```

Durante la Fase 1 la aplicación debe mostrar:

- IDs detectados;
- bordes y centros de cada marcador;
- FPS;
- `FRAME READY` cuando estén visibles los IDs externos `0,1,2,3`;
- número de marcadores de celda visibles de `9`;
- `EMPTY BOARD READY` cuando estén visibles los cuatro marcadores externos y los nueve internos.

En Fase 1 un marcador interno ausente se reporta únicamente como **missing**; todavía no se clasifica automáticamente como una casilla ocupada.

Salir con `q` o `Esc`.

Si la cámara correcta no corresponde al índice `0`, editar únicamente `config/vision.local.yaml`. Ese archivo es local y está ignorado por Git.

## Estado actual

**Fase 1 — Foundation & ArUco.**

Primer objetivo verificable: abrir una cámara desde Python y detectar de forma estable los cuatro marcadores externos y los nueve marcadores de casilla en un tablero vacío, sin ninguna conexión con el robot.
