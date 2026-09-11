# Plan de desarrollo

## Cierre de software desktop

- Diagnóstico integrado en una segunda pestaña, con una única captura/detección
  por tick y presentación de IDs 10..18 y estados temporales.
- Acceptance de widgets reales en procesos separados, sin hardware: navegación,
  logo, casillas vacías, cancelación Pícaro y errores de cámara/robot.
- Tcl/Tk funciona desde el intérprete del proyecto fuera del aislamiento;
  no se alteraron variables globales ni se ocultaron errores del intérprete.
- Packaging Windows onedir construido desde cero; smoke de proceso PASS en
  simulación y real, con cierre controlado. Smoke visual NOT CONFIRMED por falta
  de control de escritorio; no bloquea el cierre de software autorizado.
- Runner C0–C14: C6/C7 confirmados físicamente por el operador. C8/C9 usan
  cuatro Point Features y aproximación Tool Z -60 mm; C10/C11 registran evidencia
  manual, C12 y varios movimientos C13 funcionaron físicamente. C14 ejecuta una
  aceptación guiada de un turno o partida mediante cámara, GameSession y runtime;
  el operador confirmó C14 PASS físico. La recuperación/diagnóstico de la app
  posterior a ese ensayo requiere ahora validación física antes de repetir partida.
- Assignments, interpolación, aproximación y Robotiq/pick-place validados por
  el operador; C14 end-to-end PASS reportado por el operador.
- Modbus real: conexión fresca por turno, cierre tras READY y sin reenvíos ni
  resets automáticos ante entrega incierta. C12/C13/C14 tienen 60 s por defecto;
  los pasos rápidos conservan 15 s y --timeout permite override.
- C13/C14 PASS físicos reportados. Recuperación explícita: el controlador limpia
  COMMAND128 antes de publicar READY al arrancar; la GUI puede escribir un único
  COMMAND0 bajo solicitud del operador, nunca durante BUSY ni como parada física.
  Partidas inciertas se cancelan conservando historial; cámara congelada en esta
  iteración. Pendiente validación física de estos cambios de recuperación.
- Cámara y ayuda: selección separada de perfiles segmentados, comparación
  observacional por ID/FPS y procedimientos técnicos en Avanzado.

Este documento define el orden de implementación del proyecto. Cada fase debe cerrar con un resultado verificable antes de iniciar la siguiente.

## Fase 1 — Vision & ArUco

**Estado:** validada experimentalmente con Logitech C920.

### Objetivo

Crear una base reproducible en Python y validar la adquisición de cámara y la detección de **9 marcadores ArUco operacionales**:

- 9 marcadores de casilla: IDs `10..18`, asociados a las celdas `1..9`.

### Alcance

- estructura mínima del repositorio;
- entorno Python reproducible;
- configuración de cámara por YAML;
- apertura y cierre seguro de la cámara;
- detección de ArUco con OpenCV;
- visualización de borde, ID y centro de cada marcador;
- cálculo de FPS;
- conteo de marcadores de casilla visibles;
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
6. indicar cuántos de los nueve marcadores de celda están visibles;
7. reportar los IDs de celda faltantes sin inferir ocupación instantánea;
8. cerrar limpiamente con `q` o `Esc`.

La Fase 1 no debe inferir todavía que un ArUco ausente implica una jugada: durante esta fase se reporta únicamente como marcador faltante.

---

## Fase 2 — Human Move Detection

**Estado:** `BoardObserver` y la detección temporal están implementados y
validados por tests. La validación definitiva con el tablero físico real sigue
pendiente.

El tablero operacional usa exclusivamente IDs 10..18. `BoardObserver` conserva
ventana de 1.5 s, evaluación de 0.25 s, cambio de estado de 0.5 s, ratios 0.70/0.20
y mínimo de tres muestras. `board-observe` y el modo real usan `robust` por defecto;
`default` se conserva como diagnóstico. No se ajustan umbrales por el flicker de ID18.

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

**Estado:** implementación lógica completa y validada; Experto, Intermedio y
Pícaro simulado están integrados con `GameSession`.

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

**Estado:** arquitectura de cuatro Point Features y Assignments validada por
el operador en CB3 / PolyScope 3.14; Mode1, Mode2, C12 y varios ciclos C13 probados.
Completar cobertura de celdas; C14 con visión reportado PASS por el operador.

### Objetivo

Mantener las poses físicas en PolyScope: CELL1/CELL3/CELL7/CELL9 de colocación,
un PICK fijo y HOME/WAIT. El Script Node consume P1/P3/P7/P9/P_PICK/P_HOME creadas
por Assignment Nodes anteriores; no resuelve nombres de Features.

### Entregables

- promedios XYZ explícitos para las celdas derivadas y orientación fija P1;
- aproximación pose_trans(P, p[0,0,-0.060,0,0,0]): -Z Tool sube con el TCP probado;
- Mode1 solo Pn_UP; Mode2 PICK → PLACE → HOME con Robotiq;
- movej a=0.20, v=0.10; movel a=0.05, v=0.02, valores físicamente probados;
- recalibración editando únicamente los cuatro Point Features del tablero.

La arquitectura Plane Feature queda abandonada. Ver docs/polyscope-urscript.md.

Python no generará estas trayectorias.

---

## Fase 5 — Modbus

**Estado:** interfaz software y protocolo validados mediante transporte simulado.
En la red del ensayo: ping PASS, TCP 502 PASS, lectura de
STATUS 129 PASS y escritura/reset de COMMAND 128 PASS. C6 y el handshake Mode0 C7 fueron confirmados físicamente por el operador.

### Objetivo

Enviar desde Python únicamente la celda elegida.

### Diseño inicial

```text
COMMAND_REGISTER = 128
STATUS_REGISTER  = 129

COMMAND: 0 idle; 1..9 -> URScript procesa la celda paramétrica
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

**Estado:** `PhysicalGameRuntime` implementado y modo real desktop integrado por
software mediante `RealGameBackend`. C14 end-to-end físico reportado PASS por el
operador. Pendiente validar físicamente recuperación/diagnóstico de la app.

### Objetivo

Cerrar el flujo completo:

```text
Cámara -> jugada humana -> Game Engine -> movimiento 1..9 -> Modbus -> PolyScope
```

---

## Fase 7 — Validation / Optional robustness

**Estado:** pendiente.

### Objetivo

Validar el sistema completo y añadir técnicas geométricas solo si los ensayos las
justifican.

### Entregables

- homografía, pose 3D o calibración, únicamente si son necesarias;
- verificación adicional y métricas de partidas completas.

---

## Fase 8 — Desktop / Distribution

**Estado:** GUI desktop implementada; EXE onedir construido y smoke de proceso
PASS en ambos modos. Inspección visual del EXE no confirmada; aceptación física pendiente.

### Entregables

- aplicación CustomTkinter: implementada;
- ejecutable PyInstaller onedir: construido, smoke de proceso PASS;
- instalador: pendiente.

## Regla de avance

No se implementa una fase posterior para “ir adelantando” si su interfaz depende de una fase aún no validada. Las excepciones deben justificarse explícitamente en un issue o en la documentación.

## Mejoras futuras

Los IDs 0..3 podrían incorporarse como referencia geométrica/homografía opcional.
No están disponibles ni forman parte del sistema operacional actual.
