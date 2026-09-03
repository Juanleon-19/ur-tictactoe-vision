# PolyScope + URScript para el controlador físico

**Estado: PREPARADO PARA VALIDACIÓN FÍSICA. NO VALIDADO FÍSICAMENTE.**

Esta arquitectura adelanta únicamente el controlador del UR. No cambia visión,
GameSession, Minimax, GameController ni el protocolo Modbus Python.

## Árbol previsto

```text
Installation
├── TCP
├── Payload
├── Feature Plane TABLERO
└── configuración de herramienta

Program
├── inicialización
└── Script controlador: robot/urscript/triqui_controller.script
```

No se genera `.urp`. El archivo se cargará mediante un Script node/File según la
versión de PolyScope disponible.

## Feature Plane TABLERO

`TABLERO` se enseña en PolyScope mediante tres puntos:

- P1: origen;
- P2: dirección X positiva;
- P3: dirección Y positiva.

La regla de la mano derecha determina Z. Python no calcula ni actualiza este
plano. Debe comprobarse en el robot que el Feature nombrado `TABLERO` sea
referenciable con ese símbolo desde el archivo importado.

## Cuadrícula relativa

Los parámetros pendientes, expresados en metros, son `GRID_DX`, `GRID_DY`,
`CELL1_X`, `CELL1_Y`, `Z_SAFE` y `Z_PLACE`. La orientación pendiente se expresa
como el vector de rotación `CELL_RX`, `CELL_RY`, `CELL_RZ` relativo a `TABLERO`.

```text
CELL 1 = (x0,        y0)
CELL 2 = (x0 + dx,   y0)
CELL 3 = (x0 + 2dx,  y0)
CELL 4 = (x0,        y0 + dy)
...
CELL 9 = (x0 + 2dx,  y0 + 2dy)
```

`cell_relative_pose(cell, z)` calcula una única pose relativa. Después:

```text
cell_safe  = pose_trans(TABLERO, cell_relative_pose(cell, Z_SAFE))
cell_place = pose_trans(TABLERO, cell_relative_pose(cell, Z_PLACE))
```

El script solo calcula y usa `cell_safe` en modo 1. `cell_place` documenta la
composición prevista, pero no se usa hasta validar altura, orientación y proceso
de colocación.

## Máquina de estados Modbus V1

```text
READY + COMMAND=0       -> READY
READY + COMMAND=1..9    -> BUSY -> una ejecución -> DONE
DONE  + COMMAND=1..9    -> DONE, sin repetir
DONE  + COMMAND=0       -> READY
COMMAND fuera de 0..9   -> ERROR
ERROR + COMMAND=0       -> READY
```

El UR lee `read_port_register(128)` y publica el estado con
`write_port_register(129, status)`. No existe registro ACTION.

`STATUS_ERROR` cubre comandos inválidos y errores lógicos detectados por este
programa. No implica que se detecten o comuniquen automáticamente protective
stops, emergency stops ni todos los fallos del controlador.

## Modos

- `0 NO MOTION` — predeterminado; registra la celda con `textmsg()` y completa
  BUSY/DONE sin llamar a `movej()` o `movel()`.
- `1 SAFE GRID ONLY` — calcula `CELL_N_SAFE` y usa
  `movej(get_inverse_kin(cell_safe))`. No desciende, no recoge y no usa gripper.
- `2 PICK AND PLACE` — estructura reservada, actualmente devuelve error.

`take_robot_piece()`, `open_gripper()` y `close_gripper()` son stubs sin señales
digitales ni comandos inventados. La alimentación futura será un Feature
`ALIMENTADOR` o un PICK fijo, según el hardware definitivo.

La arquitectura futura de PÍCARO podría reutilizar `cell_safe`, `cell_place` y
`TABLERO` para retirar o reemplazar una ficha. No se implementa esa lógica ni se
modifican los registros 128/129.

## Validación física pendiente

## Carga en UR3 CB3 con PolyScope 3.14

1. Copiar al USB exactamente `robot/urscript/triqui_controller.script`.
2. Insertar el USB en el controlador y crear o abrir un programa en PolyScope.
3. En **Program > Structure > Advanced**, añadir un nodo **Script**.
4. En el nodo Script, seleccionar **File**, buscar el USB y elegir
   `triqui_controller.script`.
5. Antes de Play, comprobar que `MOTION_MODE = 0`, COMMAND 128 vale 0, el área
   del robot está despejada y es posible detener el programa desde el teach pendant.

En modo 0 no hacen falta todavía el Feature `TABLERO`, TCP/payload definitivos,
geometría de cuadrícula, poses, alimentador ni gripper. Esos datos permanecen
bloqueados para los modos de movimiento posteriores.

### UR-1 — Modbus NO MOTION

Con `MOTION_MODE = 0`, el PC escribe COMMAND 128=5. El UR debe leer 5, publicar
BUSY, emitir `textmsg` para CELL 5 y publicar DONE. El PC escribe COMMAND=0 y el
UR vuelve a READY. PASS: handshake completo sin movimiento.

Una vez cargado y ejecutándose el controlador, lanzar manualmente desde el PC:

```powershell
python main.py modbus-check --host 192.168.1.10 --handshake 5
```

### UR-2 — Feature SAFE GRID

Con Feature `TABLERO` enseñado, dimensiones reales y `MOTION_MODE = 1`, probar
primero CELL 5 SAFE y después 1..9 SAFE. PASS: el TCP queda por encima de cada
centro, sin descenso ni colisión.

### UR-3 — Recalibración

Mover físicamente el tablero, reenseñar únicamente `TABLERO` y repetir CELL 5
SAFE. PASS: el TCP vuelve a quedar sobre CELL 5 sin modificar las nueve posiciones
lógicas.

Estas pruebas no se ejecutan en esta tarea.

## Compatibilidad CB3 PolyScope 3.14

Para el UR3 CB3 confirmado con PolyScope 3.14, la sintaxis usada de
`read_port_register`, `write_port_register`, `pose_trans`, `get_inverse_kin`,
`movej`, `sleep` y `textmsg` es compatible con el manual URScript de esa serie.
Queda por comprobar físicamente:

- carga del archivo completo mediante Script node/File;
- nombre generado/resoluble para el Feature `TABLERO` cuando se habilite modo 1;
- comportamiento ante una pose sin solución de cinemática inversa;
- cómo reflejar paradas y fallos del controlador en el protocolo de aplicación.

La documentación oficial confirma registros generales 128..255, direccionamiento
base 0 y las funciones de acceso desde URScript. Los manuales oficiales también
documentan `pose_trans`, `movej`, `movel` y `get_inverse_kin`, pero advierten que
versiones antiguas o nuevas pueden comportarse de manera diferente.
