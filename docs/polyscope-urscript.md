# PolyScope + URScript para el controlador físico

**Estado: PREPARADO PARA VALIDACIÓN FÍSICA. NO VALIDADO FÍSICAMENTE.**

Esta preparación incluye el controlador del UR y el CLI `robot-test`. No cambia
visión, GameSession, Minimax, GameController ni el protocolo Modbus 128/129.
La guía de enseñanza está en [Calibración física](calibracion-fisica.md).

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

- Origo: centro de celda 1;
- eje +X: dirección hacia celda 3;
- eje +Y: dirección hacia celda 7.

La regla de la mano derecha determina Z. Python no calcula ni actualiza este
plano. Debe comprobarse en el robot que el Feature nombrado `TABLERO` sea
referenciable con ese símbolo desde el archivo importado.

## Cuadrícula relativa

El pitch medido es `GRID_DX=GRID_DY=0.0655` m (60 mm + 5,5 mm).
`CELL1_X=CELL1_Y=0.0`, porque el origen es el centro de celda 1.
`Z_SAFE` y `Z_PLACE` siguen sin medir; se almacenan como listas de un valor
para distinguir explícitamente `[]` (pendiente) de una altura válida.
`CELL_ORIENTATION=[]` espera el vector `CELL_RX,CELL_RY,CELL_RZ` relativo al Plane.
`TABLERO_VALUES=[]` espera los seis componentes del Feature enseñado. Dentro de
las rutinas, `TABLERO` reconstruye esa pose; no es un plano calculado por Python.

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
cell_safe  = pose_trans(TABLERO, cell_relative_pose(cell, Z_SAFE[0]))
cell_place = pose_trans(TABLERO, cell_relative_pose(cell, Z_PLACE[0]))
```

Mode 1 solo usa `cell_safe`. Mode 2 contiene la secuencia completa y solo puede
alcanzar `cell_place` después de completar enseñanza, flags y adaptador Robotiq.

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
- `2 PICK AND PLACE` — HOME → PICK_APPROACH → PICK → PICK_EXIT → CELL_SAFE →
  CELL_PLACE → CELL_SAFE → HOME; traslados `movej`, aproximaciones/retiradas `movel`.

El PICK es único y fijo. HOME y las tres poses PICK se enseñan en base; sus listas
vacías no representan poses cero. No hay nueve poses de celda hardcodeadas.

Mode 1 exige `GEOMETRY_CONFIGURED`, `ORIENTATION_CONFIGURED`, `MOTION_CONFIGURED`
y datos completos de Plane, Z_SAFE, orientación y movimiento articular.
Mode 2 añade `PICK_CONFIGURED`, `ROBOTIQ_CONFIGURED`, HOME, las tres poses PICK,
Z_PLACE y tasas lineales validadas. Ningún flag se habilita en el archivo entregado.

`gripper_initialize()`, `gripper_open()` y `gripper_close()` aún devuelven False.
Los nombres `rq_reset`, `rq_activate_and_wait`, `rq_open_and_wait` y
`rq_close_and_wait` solo figuran en comentarios hasta confirmar el modelo,
la versión URCap, sus firmas y su disponibilidad en el programa generado.
Mode 2 falla antes de mover el brazo si inicialización no está implementada.

La integración futura puede usar las funciones del URCap instalado (opción A)
o wrappers/subprogramas de la plantilla Robotiq, cargando `rq_script.script` si
lo requiere ese CB3 (opción B). Toda adaptación queda dentro de las tres funciones
`gripper_*`; el resto de Mode 2 no depende de la opción elegida. Ver la guía de
calibración para la verificación previa. No se conoce todavía modelo ni versión.

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

El código activo de Mode 0 no referencia símbolos externos del Feature ni del
URCap. La carga completa sigue pendiente de comprobar en PolyScope. TCP/payload,
alturas, orientación y poses permanecen pendientes para los modos de movimiento.

### UR-1 — Modbus NO MOTION

Con `MOTION_MODE = 0`, el PC escribe COMMAND 128=5. El UR debe leer 5, publicar
BUSY, emitir `textmsg` para CELL 5 y publicar DONE. El PC escribe COMMAND=0 y el
UR vuelve a READY. PASS: handshake completo sin movimiento.

Una vez cargado y ejecutándose el controlador, lanzar manualmente desde el PC:

```powershell
python main.py modbus-check --host 192.168.1.10 --handshake 5
```

### UR-2 — Feature SAFE GRID

Con Feature `TABLERO` enseñado, flags/datos validados y `MOTION_MODE = 1`, probar
primero CELL 5 SAFE y después 1..9 SAFE. PASS: el TCP queda por encima de cada
centro, sin descenso ni colisión.

Usar `python main.py robot-test --host HOST --cell 5 --allow-motion`.
Sin el permiso explícito no conecta ni escribe. Reutiliza el handshake existente,
no envía coordenadas ni conoce el modo seleccionado en el UR.

### UR-3 — Recalibración

Mover físicamente el tablero, reenseñar únicamente `TABLERO` y repetir CELL 5
SAFE. PASS: el TCP vuelve a quedar sobre CELL 5 sin modificar las nueve posiciones
lógicas.

Estas pruebas no se ejecutan en esta tarea.

## Compatibilidad CB3 PolyScope 3.14

El archivo aún no ha sido compilado/cargado en el UR3 CB3 PolyScope 3.14.
No se afirma compatibilidad del archivo completo por pasar tests estáticos.
Queda por comprobar físicamente:

- carga del archivo completo mediante Script node/File;
- nombre generado/resoluble para el Feature `TABLERO` cuando se habilite modo 1;
- comportamiento ante una pose sin solución de cinemática inversa;
- cómo reflejar paradas y fallos del controlador en el protocolo de aplicación;
- disponibilidad y firmas del URCap Robotiq y tratamiento de errores de agarre;
- listas pendientes, ámbitos de variables y nombre real del Feature en Script/File.

El número de parche importa: UR añadió `get_inverse_kin_has_solution` en 3.14.3;
este controlador no depende de esa función. Ver fuentes y secuencia completa en
[Calibración física](calibracion-fisica.md). Un timeout del PC o COMMAND=0 no son
una parada física; no hay reintento automático.

La documentación oficial confirma registros generales 128..255, direccionamiento
base 0 y las funciones de acceso desde URScript. Los manuales oficiales también
documentan `pose_trans`, `movej`, `movel` y `get_inverse_kin`, pero advierten que
versiones antiguas o nuevas pueden comportarse de manera diferente.
