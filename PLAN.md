# Plan de desarrollo

Este documento define el orden de implementación del proyecto. Cada fase debe cerrar con un resultado verificable antes de iniciar la siguiente.

## Fase 1 — Foundation & ArUco

### Objetivo

Crear una base reproducible en Python y validar la adquisición de cámara y la detección de **13 marcadores ArUco**:

- 4 marcadores externos persistentes: IDs `0,1,2,3`;
- 9 marcadores de casilla: IDs `10..18`, asociados a las celdas `1..9`.

### Alcance

- estructura mínima del repositorio;
- entorno Python reproducible;
- configuración de cámara por YAML;
- apertura y cierre seguro de la cámara;
- detección de ArUco con OpenCV;
- visualización de borde, ID y centro de cada marcador;
- cálculo de FPS;
- separación lógica entre marcadores externos y marcadores de casilla;
- estado `FRAME READY` basado en `0,1,2,3`;
- conteo de marcadores de casilla visibles;
- estado `EMPTY BOARD READY` cuando los 13 marcadores sean visibles;
- pruebas unitarias que no requieran cámara física.

### Fuera de alcance

- robot UR;
- RTDE;
- Modbus;
- PolyScope;
- Minimax;
- clasificación de X/O;
- decisión definitiva libre/ocupada;
- filtrado temporal de ocupación;
- homografía definitiva;
- pose 3D;
- calibración intrínseca;
- movimiento físico.

### Definition of Done

Debe poder ejecutarse:

```bash
python main.py vision
```

El programa debe:

1. abrir la cámara configurada;
2. mostrar el video en tiempo real;
3. detectar marcadores del diccionario configurado;
4. dibujar sus esquinas e IDs;
5. mostrar FPS;
6. indicar si los cuatro marcadores externos están visibles;
7. indicar cuántos de los nueve marcadores de celda están visibles;
8. indicar `EMPTY BOARD READY` cuando estén visibles los trece marcadores;
9. cerrar limpiamente con `q` o `Esc`.

La Fase 1 no debe inferir todavía que un ArUco ausente implica una jugada: durante esta fase se reporta únicamente como marcador faltante.

---

## Fase 2 — Board & Cell Mapping

### Objetivo

Convertir los marcadores ArUco en una referencia geométrica estable del tablero y en una asociación determinista entre marcador y casilla.

### Entregables

- referencia visual basada en los cuatro marcadores externos;
- comprobación de orientación del tablero;
- homografía/rectificación cuando sea necesaria;
- asociación fija `ID 10..18 ↔ celda 1..9`;
- validación geométrica de que cada ArUco interno aparece en la celda esperada;
- visualización del tablero lógico y de sus nueve marcadores;
- detección de tablero desplazado o referencia externa incompleta.

No se aceptarán todavía jugadas humanas.

---

## Fase 3 — Game Engine

### Objetivo

Implementar el juego de Triqui independientemente de cámara y robot.

### Entregables

- representación del tablero 3×3;
- validación de jugadas;
- detección de victoria y empate;
- Minimax;
- pruebas exhaustivas del motor lógico.

---

## Fase 4 — Occupancy & Human Move Detection

### Objetivo

Detectar una nueva jugada física usando principalmente el estado de visibilidad de los ArUco de cada casilla.

### Principio inicial

```text
ArUco de celda visible de forma estable -> libre
ArUco deja de ser visible               -> candidata a ocupada
```

La ausencia de un marcador no será suficiente por sí sola para aceptar una jugada.

### Entregables

- seguimiento temporal de los nueve IDs de celda;
- ventana de estabilidad/debounce para cambios de visibilidad;
- rechazo de oclusiones transitorias producidas por mano o robot;
- detección de exactamente una nueva casilla candidata;
- validación contra el estado lógico previo;
- confirmación antes de actualizar la partida;
- estrategia de recuperación si un marcador deja de detectarse por iluminación, desenfoque o perspectiva;
- pruebas con X y O reales verificando que ambas piezas ocultan el marcador correspondiente.

La identificación de X/O puede apoyarse inicialmente en el turno y el estado lógico. Una clasificación visual adicional solo se añadirá si resulta necesaria experimentalmente.

---

## Fase 5 — PolyScope

### Objetivo

Construir y validar en el UR3 todas las trayectorias preenseñadas, sin depender de Python.

### Entregables

- HOME;
- PICK_APPROACH;
- PICK;
- PICK_EXIT;
- nueve posiciones de colocación;
- nueve subprogramas de jugada;
- velocidades y aceleraciones verificadas;
- retorno seguro a HOME.

Python no generará estas trayectorias.

---

## Fase 6 — Piece Handling

### Objetivo

Validar mecánicamente la recogida, transporte, colocación y oclusión fiable del ArUco de cada casilla.

### Entregables

- punto fijo de recogida o magazine;
- herramienta final;
- repetibilidad del pick;
- repetibilidad del place;
- diseño de X y O que cubra de forma fiable el marcador de celda;
- manejo de ausencia de pieza cuando sea posible.

---

## Fase 7 — Modbus

### Objetivo

Crear un protocolo simple y robusto entre Python y PolyScope.

### Diseño inicial

```text
COMMAND
0    idle
1..9 jugar en la celda indicada

STATUS
0 ready
1 busy
2 done
3 error
```

Las direcciones de registros se fijarán durante esta fase y se documentarán explícitamente.

### Entregables

- cliente Modbus Python;
- lectura/escritura controlada;
- handshake COMMAND/STATUS;
- timeout y manejo de desconexión;
- prueba sin movimiento antes de habilitar trayectorias.

---

## Fase 8 — Integration

### Objetivo

Cerrar el flujo completo:

```text
ArUco por celda -> jugada humana -> Minimax -> comando -> UR -> ejecución
```

---

## Fase 9 — Verification

### Objetivo

No asumir que una acción física fue correcta.

### Entregables

- verificación visual de que la celda ordenada queda ocupada;
- comprobación continua de los cuatro marcadores externos;
- detección de tablero desplazado;
- estados de error recuperables;
- bloqueo de nueva jugada mientras el robot esté ocupado.

---

## Fase 10 — Validation

### Objetivo

Medir el desempeño final del sistema.

### Métricas iniciales

- precisión de detección libre/ocupada por casilla;
- precisión de detección de jugadas;
- tasa de partidas completadas;
- tiempo de visión;
- tiempo de decisión;
- tiempo de ejecución del robot;
- tasa de errores de pick/place;
- tasa de falsos `occupied` por pérdida de ArUco;
- tolerancia al desplazamiento del tablero;
- falsos positivos de visión.

## Regla de avance

No se implementa una fase posterior para “ir adelantando” si su interfaz depende de una fase aún no validada. Las excepciones deben justificarse explícitamente en un issue o en la documentación.
