# Calibración física — Robot Triqui

**PENDIENTE: ninguno de estos ensayos se da por aprobado.**
Preparación para UR3 CB3 / PolyScope 3.14; confirmar también el número de parche.
Python envía exclusivamente una celda 1..9 por Modbus, nunca coordenadas o poses.

## Antes de empezar

- Trabajar con una copia local del script y guardar la Installation/programa del UR.
  No incorporar poses, TCP, payload ni parámetros personales de movimiento a Git.
- Comprobar TCP, payload, herramienta, límites, área despejada y parada desde el
  teach pendant. Los flags del script no sustituyen la evaluación de recorridos.
- Arrancar en `MOTION_MODE=0`, con COMMAND 128=0. Confirmar el handshake sin
  movimiento mediante `modbus-check --host HOST --handshake 5`.
- Mantener una única aplicación cliente activa. Cerrar la app REAL antes de usar
  `robot-test`. El PC no puede leer ni seleccionar MOTION_MODE con este protocolo.

## Geometría y parámetros

Hueco 60,0 mm + separación 5,5 mm = **65,5 mm entre centros**.
`GRID_DX=GRID_DY=0.0655` m y `CELL1_X=CELL1_Y=0.0` m.

| Celda | X relativo (m) | Y relativo (m) |
|---|---:|---:|
| 1 | 0 | 0 |
| 2 | 0.0655 | 0 |
| 3 | 0.1310 | 0 |
| 4 | 0 | 0.0655 |
| 5 | 0.0655 | 0.0655 |
| 6 | 0.1310 | 0.0655 |
| 7 | 0 | 0.1310 |
| 8 | 0.0655 | 0.1310 |
| 9 | 0.1310 | 0.1310 |

El archivo distribuido utiliza listas vacías `[]` como **datos no enseñados**:

- `TABLERO_VALUES`: seis componentes de la pose del Plane TABLERO en base.
  En la copia local, después de verificar el nombre del Feature en el programa
  generado, reemplazar su asignación por
  `[TABLERO[0], TABLERO[1], TABLERO[2], TABLERO[3], TABLERO[4], TABLERO[5]]`.
  No usar una pose inventada. Releer el Feature después de reenseñarlo/reiniciar.
- `Z_SAFE=[valor_medido]`, `Z_PLACE=[valor_medido]`: una altura por lista,
  ambas relativas al eje Z del Plane, no a base ni a la punta actual.
- `CELL_ORIENTATION=[CELL_RX,CELL_RY,CELL_RZ]`: vector de rotación relativo
  al Plane, en radianes; **no ángulos Euler ni resta de vectores de rotación**.
- `HOME`, `PICK_APPROACH`, `PICK`, `PICK_EXIT`: cada uno contiene seis valores
  `[x,y,z,rx,ry,rz]` de una pose TCP enseñada en **base**, metros/radianes.
  `HOME` también sirve como WAIT. Nunca almacenar articulaciones en esas listas.
- `JOINT_MOTION=[aceleración,velocidad]`: rad/s² y rad/s.
  `LINEAR_MOTION=[aceleración,velocidad]`: m/s² y m/s. Enseñar/validar ambos.

Las listas no se rellenan automáticamente ni por Python. La conversión a pose
se realiza solo después de comprobar sus longitudes y los flags. El `TABLERO`
local de las funciones de movimiento es la pose reconstruida desde el Feature.
La transformación final siempre es `pose_trans(TABLERO, relative_pose)`.

## Secuencia de calibración

1. **Enseñar Plane TABLERO:** Origo en centro de celda 1, +X hacia celda 3,
   +Y hacia celda 7. Comprobar los ejes mostrados por PolyScope, no asumir el orden
   del asistente. Confirmar que +Z apunta fuera de la superficie. Si apunta hacia
   el soporte, detener la calibración y resolver esa incompatibilidad de ejes.
2. **Enseñar orientación TCP:** con la herramienta orientada para depositar,
   obtener en el UR `pose_trans(pose_inv(TABLERO), taught_tcp_pose_in_base)`.
   Introducir sus últimos tres componentes en `CELL_ORIENTATION` y validar
   `ORIENTATION_CONFIGURED`. No calcular esta transformación en Python.
3. **Definir Z_SAFE:** medir una altura libre sobre el tablero y validar TCP,
   payload, configuración articular y tasas de movimiento. Completar
   `TABLERO_VALUES`, `Z_SAFE`, `JOINT_MOTION`; solo entonces confirmar
   `GEOMETRY_CONFIGURED` y `MOTION_CONFIGURED`. Mantener Mode 2 bloqueado.
4. **Validar CELL5_SAFE:** seleccionar Mode 1 en la copia local y ejecutar
   `python main.py robot-test --host HOST --cell 5 --allow-motion`.
   Comprobar centro, orientación y altura sin descenso ni gripper.
5. **Validar 1..9 SAFE:** ensayar una celda por comando. Comprobar también el
   recorrido articular entre destinos: un destino elevado no garantiza una
   trayectoria libre. No hay barrido automático desde Python.
6. **Identificar Robotiq:** registrar modelo exacto, firmware, versión URCap,
   identificador del gripper y compatibilidad CB3/3.14. Verificar que sus funciones
   se incluyan realmente en el programa generado por PolyScope.
7. **Probar inicialización y open/close:** primero con la herramienta despejada,
   mediante la integración Robotiq validada. Adaptar `gripper_initialize/open/close` en la copia
   local y validar errores, activación, liberación y agarre. Candidatas previstas:
   `rq_reset()`, `rq_activate_and_wait()`, `rq_open_and_wait()`,
   `rq_close_and_wait()`. Verificar firmas/argumentos antes de activarlas.
   Solo entonces confirmar `ROBOTIQ_CONFIGURED`. Las funciones entregadas
   devuelven False incluso si se cambia el flag; no basta con cambiarlo a True.
8. **Enseñar HOME/WAIT:** pose segura y camino validado desde la posición inicial
   y desde el tablero. No es una recuperación automática ante errores.
9. **Enseñar PICK_APPROACH/PICK/PICK_EXIT:** un único PICK fijo. Validar aproximación
   y salida lineales, suministro de una ficha y confirmación de agarre antes de
   retirarse. Completar `LINEAR_MOTION` con valores comprobados.
10. **Definir Z_PLACE:** altura real de deposición relativa al Plane. Confirmar
    `Z_PLACE < Z_SAFE`, holguras y recorrido; validar `PICK_CONFIGURED` solo tras
    completar HOME, las tres poses PICK y la altura de deposición.
11. **Pick/place a CELL5:** con todos los bloqueos resueltos, seleccionar Mode 2
    y usar el mismo `robot-test`. Secuencia: HOME → PICK_APPROACH → PICK → PICK_EXIT
    → CELL_SAFE → CELL_PLACE → CELL_SAFE → HOME. `movej` en traslados amplios;
    `movel` en descensos/ascensos. Verificar que la ficha realmente se depositó:
    DONE del CLI no es verificación visual.
12. **Ampliar a varias celdas:** una por ensayo, comprobar repetibilidad, agarre,
    liberación, retorno HOME y ausencia de colisiones. Registrar PASS/FAIL y causa.

## Opciones de integración Robotiq pendientes

No se conoce todavía el modelo exacto ni la versión URCap. Elegir y verificar
una de estas opciones en el controlador antes de implementar los adaptadores:

- **A — URCap:** usar `rq_activate_and_wait()`, `rq_open_and_wait()` y
  `rq_close_and_wait()` si el URCap instalado proporciona esas funciones.
  Verificar también si la activación requiere previamente `rq_reset()`.
- **B — Plantilla Robotiq:** usar sus wrappers/subprogramas si la instalación CB3
  requiere cargar `rq_script.script` o subprogramas de la plantilla correspondiente.
  Confirmar archivos, nombres, firmas y orden de carga; no asumir disponibilidad.

Ambas opciones quedan completamente encapsuladas en `gripper_initialize()`,
`gripper_open()` y `gripper_close()`. El resto de Mode 2 conserva la misma secuencia
y solo consume éxito/fallo de esos adaptadores. `ROBOTIQ_CONFIGURED=False` y no
hay llamadas `rq_*` efectivas en el archivo entregado.

## Límites y parada

`robot-test` rechaza sin `--allow-motion` **antes de conectar**. Con permiso usa
el mismo handshake de `modbus-check`: READY → BUSY → DONE sostenido → COMMAND=0
→ READY. `--timeout SEGUNDOS` cambia la espera por estado (30 s por defecto en
robot-test, 3 s en modbus-check); elegirlo según el ciclo validado.

**Timeout o COMMAND=0 no detienen un movimiento ya iniciado.** No reenviar una
celda tras timeout sin detener/inspeccionar el estado real desde el pendant.
Un fallo del gripper interrumpe la secuencia, sin retorno HOME automático.
Protective stop, emergencia, errores IK o excepciones URCap pueden detener el
programa sin publicar STATUS_ERROR. La ruta de parada física es la del UR.

No está comprobada la carga/sintaxis del archivo en CB3 3.14 ni la disponibilidad
de símbolos de la Installation/URCap. Pytest solo revisa contratos estáticos y
Modbus simulado. `get_inverse_kin_has_solution` se incorporó en **3.14.3**;
no se utiliza suponiendo que cualquier instalación “3.14” lo tenga.

Fuentes oficiales consultadas:

- [UR: composición con un Feature](https://www.universal-robots.com/articles/ur/programming/urscript-move-with-respect-to-a-custom-featureframe/).
- [UR: notas CB3 3.14, incluida 3.14.3](https://www.universal-robots.com/articles/ur/release-notes/release-note-software-version-314xx/).
- [Robotiq: ejemplo documentado de API de control](https://assets.robotiq.com/website-assets/support_documents/document/online/Hand-E_Instruction_Manual_Web_20190329.zip/Hand-E_Instruction_Manual_Web/Content/4.%20Control.htm).
  Esta referencia ilustra nombres de funciones; **no identifica el modelo instalado**.
