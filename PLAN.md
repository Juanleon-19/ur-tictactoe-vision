# Plan de desarrollo

Este documento define el orden de implementación del proyecto. Cada fase debe cerrar con un resultado verificable antes de iniciar la siguiente.

## Fase 1 — Vision & ArUco

**Estado: validada experimentalmente con Logitech C920.**

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

## Fase 2 — Human Move Detection

**Estado: implementación lógica validada; validación física con cámara pendiente.**

### Objetivo

Detectar la jugada humana principalmente mediante la desaparición estable de un
marcador de celda y convertir su ID en una celda `1..9`.

### Entregables

- asociación fija `ID 10..18 ↔ celda 1..9`;
- estabilidad temporal/debounce;
- rechazo de oclusiones transitorias de mano, robot o fallos de detección;
- aceptación de una única jugada legal respecto al estado anterior.

La homografía no es requisito de V1 si la identificación por IDs es fiable.

---

## Fase 3 — Game Engine

### Objetivo

Implementar el juego de Triqui independientemente de cámara y robot.

### Entregables

- representación del tablero 3×3;
- validación de jugadas;
- detección de victoria y empate;
- Minimax;
- desempate agresivo únicamente entre opciones con el mismo valor óptimo;
- pruebas exhaustivas del motor lógico.

Esta fase se desarrolla anticipadamente porque no depende de cámara ni robot.

---

## Fase 4 — PolyScope

### Objetivo

Enseñar y validar manualmente las trayectorias físicas, en paralelo al software.

### Entregables

- HOME;
- PICK_APPROACH;
- PICK;
- PICK_EXIT;
- un único PICK fijo donde otra persona coloca la ficha;
- nueve destinos y subprogramas `Play_Cell_1 ... Play_Cell_9`;
- velocidades y aceleraciones verificadas;
- retorno seguro a HOME.

Python no generará estas trayectorias.

---

## Fase 5 — Modbus

### Objetivo

Enviar desde Python únicamente la celda elegida.

### Diseño inicial

```text
COMMAND_REGISTER = 128
STATUS_REGISTER  = 129

COMMAND: 0 idle; 1..9 -> PolyScope ejecuta Play_Cell_N
STATUS:  0 ready; 1 busy; 2 done; 3 error
```

El servidor UR usa direccionamiento base 0, escucha en TCP `502`, permite registros
generales `128..255` e ignora Unit Identifier/Slave ID. Los registros `128` y `129`
son la reserva explícita de este proyecto.

### Entregables

- cliente Modbus Python;
- escritura controlada de `COMMAND = 1..9`;
- lectura de `STATUS` y handshake `READY -> BUSY -> DONE/ERROR`;
- timeout y manejo de desconexión;
- prueba sin movimiento antes de habilitar trayectorias.

---

## Fase 6 — Integration

### Objetivo

Cerrar el flujo completo:

```text
Cámara -> jugada humana -> Game Engine -> movimiento 1..9 -> Modbus -> PolyScope
```

---

## Fase 7 — Validation / Optional robustness

### Objetivo

Validar el sistema completo y añadir técnicas geométricas solo si los ensayos las
justifican.

### Entregables

- homografía, pose 3D o calibración, únicamente si son necesarias;
- verificación adicional y métricas de partidas completas.

## Regla de avance

No se implementa una fase posterior para “ir adelantando” si su interfaz depende de una fase aún no validada. Las excepciones deben justificarse explícitamente en un issue o en la documentación.
