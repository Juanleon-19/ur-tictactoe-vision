# UR Tic-Tac-Toe Vision

Sistema de visión artificial para que un robot **Universal Robots** juegue Triqui (Tic-Tac-Toe) contra una persona.

Para instalar y usar Robot Triqui en Windows: [guía de instalación](docs/installation.md).

El prototipo usa **UR CB3 / PolyScope 3.14**, cámara fija, Python/OpenCV, ArUco y Modbus TCP. Python envía únicamente la celda. PolyScope calcula las posiciones desde cuatro Point Features de colocación y ejecuta el pick/place con Robotiq.

Estado físico comunicado por el operador: C6/C7 aprobados, Mode1 para grid seguro y Mode2 con recogida, colocación y HOME probados; C12 y varios ciclos de C13 funcionaron. La aproximación validada es **Tool Z -60 mm**. Falta completar la aceptación end-to-end con visión: C14 permite primero un turno guiado y después una partida completa. Los tests automáticos no validan hardware.

Antes del Script Node se requieren seis Assignments: `P1=CELL1_const`, `P3=CELL3_const`, `P7=CELL7_const`, `P9=CELL9_const`, `P_PICK=<Feature de recogida>` y `P_HOME=<Feature HOME/WAIT>`, seleccionados en PolyScope. P2/P4/P5/P6/P8 se derivan por promedios XYZ y todas las celdas usan la orientación P1. `Pn_UP = pose_trans(Pn, p[0,0,-0.060,0,0,0])`; +Tool Z baja, -Tool Z sube. Para recalibrar el tablero se editan sus cuatro Point Features. Ver [preparación exacta del programa](docs/polyscope-urscript.md).

## Objetivo

Construir un sistema modular capaz de:

1. observar un tablero 3×3 mediante los ArUco de sus nueve casillas;
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
Selección Pn / Pn_UP desde cuatro esquinas
  ↓
Pick & Place
```

### Responsabilidad de Python

Python será responsable de:

- adquisición de imagen;
- detección ArUco;
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
- secuencia PICK → celda → HOME con Robotiq.

## Diseño ArUco de la V1

La V1 utilizará **9 marcadores operacionales** del mismo diccionario:

- 9 marcadores internos, uno por cada casilla.

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

La homografía, la pose 3D y la calibración se añadirán solo si las pruebas de V1
demuestran que la identificación directa por IDs no es suficiente.

## Comunicación con el UR

Para preparar las pruebas de movimiento, consultar la
[guía de calibración física](docs/calibracion-fisica.md). El comando
`python main.py robot-test --host HOST --cell 5` rechaza la operación sin
`--allow-motion`. Solo envía la celda por Modbus; el modo y los parámetros físicos
se configuran en el UR. Ninguna prueba física se da por aprobada.

La interfaz V1 prevista es un comando Modbus mínimo:

Ejemplo conceptual:

```text
COMMAND = 1..9 -> PolyScope selecciona Pn y ejecuta el modo configurado
```

Los valores definitivos y las direcciones de registros se fijarán durante la fase de integración Modbus.

## Fases

1. **Vision & ArUco** — Logitech C920 y detección validada de los nueve IDs de celda.
2. **Human Move Detection** — desaparición estable del marcador e ID → celda `1..9`.
3. **Game Engine** — estado 3×3, reglas y Minimax.
4. **PolyScope** — cuatro esquinas, PICK fijo y HOME; celdas interpoladas en el UR.
5. **Modbus** — Python envía únicamente `COMMAND = 1..9`.
6. **Integration** — cámara → jugada → motor → Modbus → PolyScope.
7. **Validation / Optional robustness** — geometría avanzada solo con evidencia.

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
python -m pytest -q
```

`pytest.ini` mantiene los temporales en `.pytest-tmp/run` y la caché en
`.pytest-tmp/cache`, ambos ignorados por Git. No depende del directorio temporal
global de Windows. Pytest recrea su directorio `run` en cada ejecución; no guardar
archivos personales allí.

Generar los nueve marcadores ArUco iniciales:

```powershell
python scripts\generate_aruco.py
```

Generar una hoja digital 1920×1080 con los nueve marcadores para mostrarla a pantalla completa:

```powershell
python scripts\generate_aruco.py --board
```

Los PNG se guardarán en `assets/aruco/`. El tamaño físico definitivo se decidirá después de conocer cámara, altura, tamaño del tablero y campo de visión.

Ejecutar la visión en tiempo real:

```powershell
python main.py vision
python main.py vision --aruco-profile robust
```

Observar automáticamente el estado físico temporal del tablero, sin botones ni
confirmación manual:

```powershell
python main.py board-observe
python main.py board-observe --aruco-profile default
```

El comando muestra preview, FPS, perfil, readiness, ratios por celda y estados
`FREE`, `OCCUPIED` o `UNCERTAIN`. Al cerrar imprime la estabilidad de detección
de los nueve IDs de celda. Los parámetros experimentales de ventana, evaluación, histéresis,
umbrales y mínimo de muestras válidas están en `config/vision.example.yaml` y
pueden sobrescribirse en la configuración local ignorada por Git.

`board-observe`, `RealGameBackend` y la aplicación real utilizan `robust` por
defecto. `--aruco-profile default` conserva el perfil diagnóstico de OpenCV en
`board-observe`; `vision` mantiene `default` y permite seleccionar `robust`.

Validar con cámara la desaparición estable de un marcador de celda como jugada
humana, sin ejecutar el juego ni comunicarse con el robot:

```powershell
python main.py move-detect
python main.py move-detect --stable-frames 8
```

El modo usa la misma configuración de `vision.local.yaml`. Con los nueve ArUco
visibles debe indicar `Cell markers visible 9/9`. Al cubrir un
único marcador de celda durante el número configurado de frames, muestra e imprime
`HUMAN MOVE: CELL N`. Se cierra con `q` o `Esc`.

Jugar manualmente contra el motor, sin cámara ni robot:

```powershell
python main.py game --difficulty hard --seed 42
python main.py game --difficulty intermediate --seed 42
python main.py game --human-first --difficulty intermediate --seed 42
```

La dificultad predeterminada es `hard`. Este modo conserva el Minimax perfecto;
`intermediate` usa búsqueda limitada y puede cometer errores estratégicos de
horizonte. La representación, las reglas y ambos algoritmos se explican en
[`docs/game-engine.md`](docs/game-engine.md).

En Windows, listar la información PnP disponible y probar secuencialmente los índices `0..5` con los backends `AUTO`, `DSHOW` y `MSMF`:

```powershell
python main.py cameras
```

El nombre PnP es diagnóstico y no implica una correspondencia automática con un índice OpenCV. El backend (`AUTO`, `DSHOW` o `MSMF`) y el índice encontrados se configuran manualmente en `config/vision.local.yaml`.

Durante la Fase 1 la aplicación debe mostrar:

- IDs detectados;
- bordes y centros de cada marcador;
- FPS;
- número de marcadores de celda visibles de `9`;
- IDs de celda faltantes, sin inferir ocupación instantánea.

En Fase 1 un marcador interno ausente se reporta únicamente como **missing**; todavía no se clasifica automáticamente como una casilla ocupada.

Salir con `q` o `Esc`.

Si la cámara correcta no corresponde al índice `0`, editar únicamente `config/vision.local.yaml`. Ese archivo es local y está ignorado por Git.

## Estado actual

**Fase 3 — Game Engine, desarrollada anticipadamente con autorización explícita.**

La Fase 1 está validada experimentalmente. El motor se prueba sin cámara, robot,
Modbus ni red.

## Mejoras futuras

Los IDs 0..3 podrían incorporarse como referencia geométrica/homografía opcional.
No están disponibles ni forman parte del sistema operacional actual.
