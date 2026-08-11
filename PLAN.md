# Plan de desarrollo

Este documento define el orden de implementación del proyecto. Cada fase debe cerrar con un resultado verificable antes de iniciar la siguiente.

## Fase 1 — Foundation & ArUco

### Objetivo

Crear una base reproducible en Python y validar la adquisición de cámara y la detección de cuatro marcadores ArUco.

### Alcance

- estructura mínima del repositorio;
- entorno Python reproducible;
- configuración de cámara por YAML;
- apertura y cierre seguro de la cámara;
- detección de ArUco con OpenCV;
- visualización de borde, ID y centro de cada marcador;
- cálculo de FPS;
- estado visual del tablero basado en los IDs esperados `0,1,2,3`;
- pruebas unitarias que no requieran cámara física.

### Fuera de alcance

- robot UR;
- RTDE;
- Modbus;
- PolyScope;
- Minimax;
- clasificación de X/O;
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
6. indicar `BOARD DETECTED` únicamente cuando estén presentes los cuatro IDs esperados;
7. cerrar limpiamente con `q` o `Esc`.

---

## Fase 2 — Board Vision

### Objetivo

Convertir la detección de marcadores en una representación normalizada del tablero.

### Entregables

- asociación estable ID ↔ esquina física;
- cálculo de homografía;
- imagen cenital rectificada;
- división automática en nueve ROI;
- comprobación de alineación del tablero;
- visualización de las nueve celdas.

No se detectarán todavía jugadas humanas.

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

## Fase 4 — Human Move Detection

### Objetivo

Detectar una nueva jugada física a partir de la cámara y convertirla en una celda lógica.

### Entregables

- comparación temporal del tablero;
- detección de cambio por ROI;
- rechazo de cambios ambiguos;
- validación contra el estado lógico previo;
- actualización de la partida únicamente después de confirmar una jugada válida.

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

Validar mecánicamente la recogida, transporte y liberación de piezas.

### Entregables

- punto fijo de recogida o magazine;
- herramienta final;
- repetibilidad del pick;
- repetibilidad del place;
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
visión -> jugada humana -> Minimax -> comando -> UR -> ejecución
```

---

## Fase 9 — Verification

### Objetivo

No asumir que una acción física fue correcta.

### Entregables

- verificación visual de la pieza colocada;
- detección de tablero desplazado;
- estados de error recuperables;
- bloqueo de nueva jugada mientras el robot esté ocupado.

---

## Fase 10 — Validation

### Objetivo

Medir el desempeño final del sistema.

### Métricas iniciales

- precisión de detección de jugadas;
- tasa de partidas completadas;
- tiempo de visión;
- tiempo de decisión;
- tiempo de ejecución del robot;
- tasa de errores de pick/place;
- tolerancia al desplazamiento del tablero;
- falsos positivos de visión.

## Regla de avance

No se implementa una fase posterior para “ir adelantando” si su interfaz depende de una fase aún no validada. Las excepciones deben justificarse explícitamente en un issue o en la documentación.