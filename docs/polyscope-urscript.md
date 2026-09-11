# PolyScope + URScript: cuatro Point Features

Arquitectura vigente para CB3 / PolyScope 3.14. El operador confirmó físicamente
los Assignments, interpolación, Tool Z y recogida/colocación con Robotiq.
Estado final v1.0.0 comunicado por el operador: **C13 físico: PASS** y
**C14 end-to-end físico: PASS**. Mode1, Mode2 y C12 también fueron probados.
Cada nuevo montaje requiere su propio commissioning; no se infiere PASS de software.

## Preparar Installation y programa

1. Abrir la Installation validada y verificar TCP y payload.
2. En Installation > Features, enseñar cuatro **Point Features**: CELL1, CELL3,
   CELL7 y CELL9. Son las poses reales de **colocación**, no poses elevadas.
   Todas las celdas usarán la orientación de CELL1.
3. Conservar un Point Feature para recogida y otro para HOME/WAIT con sus poses
   reales enseñadas. No copiar coordenadas físicas al repositorio.
4. Antes del Script Node, añadir seis Assignment Nodes, seleccionando el Feature
   desde PolyScope como en la prueba física validada:

   | Variable | Expresión seleccionada en Assignment |
   |---|---|
   | P1 | CELL1_const |
   | P3 | CELL3_const |
   | P7 | CELL7_const |
   | P9 | CELL9_const |
   | P_PICK | Feature real de recogida seleccionado en PolyScope |
   | P_HOME | Feature real HOME/WAIT seleccionado en PolyScope |

   P_PICK y P_HOME son variables de programa; los nombres de sus Features dependen
   de la Installation. Seleccionar sus poses, no escribir nombres ficticios.
5. Incluir las definiciones rq_activate_and_wait, rq_open_and_wait y
   rq_close_and_wait del URCap Robotiq instalado en el programa generado.
   Deben estar disponibles para cargar el archivo completo incluso en Mode0.
   No sustituirlas por IO.
6. Después de los seis Assignments, añadir Script > File y cargar
   robot/urscript/triqui_controller.script. Solo consume las seis variables:
   no resuelve directamente nombres de Features.
7. Arrancar con MOTION_MODE=0 y COMMAND=0. El modo se cambia manualmente en la
   copia del controlador cargada en el robot, nunca desde Python.

El Script Node contiene el bucle del controlador. Tras editar Features, detener
el programa y volver a ejecutar desde los Assignments antes del Script Node.
No se actualizan poses durante una jugada.

## Interpolación y aproximación

```text
CELL1  CELL2  CELL3
CELL4  CELL5  CELL6
CELL7  CELL8  CELL9

4 Point Features → Assignments → interpolación XYZ → Pn → Pn_UP
```

P2 promedia XYZ de P1/P3; P4 de P1/P7; P5 de las cuatro esquinas;
P6 de P3/P9 y P8 de P7/P9. Se calculan una vez con aritmética explícita;
XYZ de las esquinas se conserva. No hay función bilineal genérica en el controlador.
Todas las poses seleccionadas usan P1[3], P1[4], P1[5].
No se interpolan vectores de rotación. Selección 1..9 mediante if/elif explícitos.

Con el TCP validado, +Z Tool baja y -Z Tool sube:

```text
APPROACH_DZ = -0.060
Pn_UP = pose_trans(Pn, p[0,0,APPROACH_DZ,0,0,0])
P_PICK_UP = pose_trans(P_PICK, p[0,0,APPROACH_DZ,0,0,0])
```

Son 60 mm a lo largo del eje Tool de cada pose, no de Z base.
Conservar movej a=0.20 rad/s², v=0.10 rad/s y movel a=0.05 m/s², v=0.02 m/s.

La arquitectura de Plane Feature TABLERO está abandonada. Para recalibrar el
tablero, editar solo sus cuatro Point Features y reejecutar los Assignments.
PICK y HOME no cambian si sus ubicaciones no cambiaron.

## Modos

- Mode0, predeterminado: textmsg de celda y sleep(0.1); sin evaluar poses ni
  accionar brazo/pinza. Conserva el comportamiento C7.
- Mode1: seleccionar Pn, calcular Pn_UP y un único movej a Pn_UP.
  Sin descenso, recogida ni Robotiq. C8 prueba 5; C9 prueba 1..9.
- Mode2: activar Robotiq en el primer ciclo de la ejecución del programa;
  abrir → movej(P_PICK_UP) → movel(P_PICK) → cerrar → movel(P_PICK_UP) →
  seleccionar Pn → calcular Pn_UP → movej(Pn_UP) → movel(Pn) → abrir →
  movel(Pn_UP) → movej(P_HOME) → retornar True → DONE.
  No se reactiva cada turno ni se hace reset automático.

Los movej usan get_inverse_kin con la pose seleccionada. P_PICK y P_HOME
conservan sus orientaciones propias. No hay traslado inicial extra a HOME:
el operador parte de una posición conocida con recorrido validado.

## Contrato Modbus intacto

COMMAND_REGISTER=128: 0 IDLE, 1..9 CELL.
STATUS_REGISTER=129: 0 READY, 1 BUSY, 2 DONE, 3 ERROR.

READY → COMMAND n → BUSY → ejecución → DONE sostenido → COMMAND0 → READY.
Un COMMAND no cero mientras DONE no repite movimiento.
Al reiniciar el controlador se borra COMMAND128 con COMMAND_IDLE antes de
publicar READY y entrar al loop. Esta limpieza inicial descarta una orden
residual; no modifica las poses, movimientos ni el handshake de una orden nueva.
Un comando fuera de 0..9 produce ERROR; COMMAND0 permite volver a READY.
No se añaden registros, comandos PICK ni selección remota de modo.

C6/C7 fueron confirmados físicamente por el operador. Seguir
[commissioning](commissioning.md) y [calibración física](calibracion-fisica.md).

El pick/place tarda más de 15 s. C12/C13 usan 60 s por defecto, configurable con
--timeout. El PC abre una conexión por movimiento autorizado, sin espera humana
dentro del socket. En runtime real/C14 se verifica ocupación antes de COMMAND0,
se espera READY y se cierra la conexión antes del siguiente turno humano.

## Límites

Comprobar la carga del archivo integrado en CB3 3.14 con sus Assignments y URCap.
Pytest comprueba contratos, aritmética y secuencias con dobles; no compila URScript
ni valida cinemática o recorridos. No se usa get_inverse_kin_has_solution.

Un destino elevado no garantiza un traslado articular libre. Timeout, ABORT y
COMMAND0 no detienen movimiento iniciado: usar la parada física.
Errores IK/URCap o protective stops pueden detener el programa sin publicar
STATUS_ERROR. No hay reintento ni retorno HOME automático tras esos fallos.
