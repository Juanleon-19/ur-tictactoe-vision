# Controlador URScript de Robot Triqui

[triqui_controller.script](triqui_controller.script) es el controlador operacional
para UR3 CB3 / PolyScope 3.14. El operador confirmó C13 físico PASS y C14 end-to-end
físico PASS al cierre v1.0.0. Cada nuevo montaje debe realizar su propio commissioning.

## Preparación

Seguir [PolyScope y Assignments](../../docs/polyscope-urscript.md) y
[calibración física](../../docs/calibracion-fisica.md). Enseñar Point Features
CELL1/CELL3/CELL7/CELL9 de colocación, PICK y HOME/WAIT. Antes del Script Node,
crear P1=CELL1_const, P3=CELL3_const, P7=CELL7_const y P9=CELL9_const;
asignar P_PICK y P_HOME seleccionando sus Features reales.
Incluir funciones rq_activate_and_wait, rq_open_and_wait y rq_close_and_wait
mediante el URCap Robotiq, incluso para cargar Mode0. El modelo exacto de pinza
y versión del URCap quedan pendientes de documentar.

Cargar el archivo mediante Script > File después de los Assignments. El controlador
usa cuatro esquinas, promedios XYZ y orientación P1; no usa Plane Feature ni
Play_Cell. No publicar poses ni una Installation personal.

## Operación

- Mode0, predeterminado: handshake sin movimiento ni accionamiento de pinza.
- Mode1: aproximación a Pn_UP, sin descenso ni recogida.
- Mode2: PICK → PLACE → HOME mediante Robotiq.

APPROACH_DZ=-0.060 corresponde a −Z Tool, 60 mm de elevación con el TCP validado.
Conservar parámetros productivos; enseñar y verificar TCP, payload y recorridos
para el equipo real. El operador cambia el modo en el robot, nunca desde Python.
Tras editar Features, detener y reejecutar desde los Assignments.

COMMAND128: 0 reposo/acuse, 1..9 celda. STATUS129: 0 READY, 1 BUSY, 2 DONE, 3 ERROR.
El controlador limpia COMMAND al arrancar antes de READY. Ver
[contrato Modbus](../../docs/modbus-protocol.md) y
[commissioning C0–C14](../../docs/commissioning.md).

Timeout, ABORT, cierre de aplicación y COMMAND0 no detienen un movimiento iniciado.
Usar parada física ante riesgo. Los tests automáticos no compilan en CB3 ni
validan cinemática; no deben mover hardware.
