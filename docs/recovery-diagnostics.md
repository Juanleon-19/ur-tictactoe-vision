# Recuperación y diagnóstico de la app real

El operador reportó **C13 y C14 PASS físicos**, con MOTION_MODE=2 funcionando.
Esta iteración no ejecuta hardware ni cambia parámetros de cámara, poses,
interpolación, velocidades o gripper. Refuerza únicamente el cierre de recursos.
Esta nota conserva el análisis de la iteración de recuperación y sus ensayos
específicos, que no se dan por repetidos. El estado de cierre v1.0.0 es C13 físico
PASS y C14 end-to-end físico PASS; ver [validación física](physical-validation.md).

## Arranque seguro del controlador

Se confirmó la ruta del fallo en el código: el controlador anterior publicaba
READY antes de leer COMMAND128, sin limpiarlo. Si retenía 1..9, el primer ciclo
podía llamar execute_cell() y mover el robot en Mode2 sin una orden nueva.
Esto demuestra el mecanismo posible; no es una traza del incidente físico.

Ahora, antes de publicar READY y entrar al loop operacional, ejecuta:

```text
write_port_register(COMMAND_REGISTER, COMMAND_IDLE)
global controller_status = STATUS_READY
write_port_register(STATUS_REGISTER, controller_status)
```

Se conservan COMMAND128, STATUS129, COMMAND_IDLE=0, estados, MOTION_MODE default=0,
APPROACH_DZ=-0.060 y todas las funciones físicas. El handshake operacional conserva
su test de hash anterior. No se añade ningún movimiento o reintento al arrancar.

## Consultar el robot sin moverlo

La consulta interna **ACTUALIZAR ESTADO** conserva cámara y última observación del tablero,
descarta la conexión Modbus anterior, crea un cliente fresco, conecta, lee
exclusivamente **STATUS129** y cierra. No captura un frame adicional ni reinicia
cámara/BoardObserver. El método interno reconnect_robot conserva esa semántica
de solo lectura. No hay botones de consulta o recuperación separados en HOME:
al abrir CÁMARA / DIAGNÓSTICO se consulta automáticamente cuando no hay partida activa.
El arranque también lee STATUS129; no basta con abrir TCP 502.

ACTUALIZAR ESTADO no escribe COMMAND128, incluido COMMAND0, reenvía jugadas ni
continúa una partida fallida. No conserva la conexión de diagnóstico para el turno.
Las consultas están bloqueadas durante partidas activas para no interferir con
el handshake, y disponibles sin partida, al terminarla o cuando está detenida
por error. Una operación en curso impide otra reconexión o partida simultánea.

CÁMARA / DIAGNÓSTICO muestra los resultados de la última consulta:

| Lectura | Modbus | Controlador | Resumen Robot |
| --- | --- | --- | --- |
| STATUS129 = 0 | CONECTADO | READY | LISTO |
| STATUS129 = 1 | CONECTADO | BUSY | EN MOVIMIENTO |
| STATUS129 = 2 | CONECTADO | DONE | REQUIERE RECUPERACIÓN |
| STATUS129 = 3 | CONECTADO | ERROR | REQUIERE RECUPERACIÓN |
| Fallo de conexión/lectura/respuesta/cierre | ERROR | DESCONOCIDO | ERROR DE CONEXIÓN |

CONECTADO describe una consulta válida, no un socket persistente. Una lectura
fresca READY elimina el error de disponibilidad anterior. Si una partida quedó
detenida, conserva su error, jugada pendiente y marca de entrega incierta:
la home indica REQUIERE RECUPERACIÓN por esa partida aunque Modbus ya responda.
Consultar no confirma el tablero físico ni autoriza movimientos.

## REINICIAR SISTEMA: reset explícito, nunca parada

El operador solicita esta única acción desde inicio. Se serializa con INICIAR
PARTIDA y las transiciones del runtime: espera a que termine una transición local
que ya esté enviando un comando, cancela la progresión de la partida y nunca
reenvía su jugada pendiente. Cancela también partidas con entrega incierta.

1. Cierra el cliente local viejo y conecta uno fresco.
2. Lee STATUS129. Ante BUSY no escribe nada y muestra:
   «Robot en movimiento. COMMAND0 no es parada. Espere o use la parada física.»
3. Ante READY, DONE o ERROR escribe exclusivamente COMMAND0 una sola vez.
4. Lee hasta READY durante una espera de 3 s, con sondeos separados 50 ms;
   las operaciones TCP conservan su timeout de transporte de 3 s. No reenvía
   el cero si se pierde la respuesta, vence el plazo o falla la conexión.
5. Cierra la conexión y consulta Dashboard de solo lectura.
6. Solo tras READY y cierre satisfactorios reinicia el historial temporal de
   BoardObserver, sin modificar su algoritmo ni reabrir la cámara conectada.
7. Espera nuevamente tablero estable, vacío y cámara conectada para mostrar
   **SISTEMA LISTO**. Si falta cámara, indica RECONECTAR CÁMARA; si hay fichas,
   pide retirarlas. Ante BUSY no reinicia observación ni escribe cero.

COMMAND0 es acknowledgement/reset del protocolo, **NO emergency stop**.
No se solicita ni reenvía pending_robot_move. Al aceptar la recuperación,
cualquier partida sin terminar queda cancelada, también si luego falla el reset:
se archivan tablero lógico, estado, error, causa, comando posiblemente entregado
y celda pendiente en DETALLE → historial de partidas canceladas de la sesión.
La instancia runtime anterior se retira; no puede volver a avanzar.

El ERROR pegado provenía de `_robot_status(RuntimeState.ERROR)` y de la prioridad
de `runtime.snapshot().last_error`, aun después de limpiar el error de transporte
en RealGameBackend. La recuperación distingue disponibilidad actual de esa
evidencia histórica. Conserva errores de cámara y no presenta la entrega incierta
como una jugada completada. La home queda LISTO al confirmar READY; se muestra
**PARTIDA CANCELADA · REQUIERE NUEVA PARTIDA** cuando corresponde.

INICIAR PARTIDA exige cámara conectada, observación lista/no incierta/tablero vacío
y una nueva consulta Modbus que confirme READY. Nunca escribe COMMAND0. Si
encuentra DONE o ERROR, permanece en inicio y ofrece REINICIAR SISTEMA. Una partida
incierta no puede sustituirse por otra hasta solicitar recuperación explícita.

## PolyScope CB3: diagnóstico opcional

La app real consulta automáticamente PolyScope durante el diagnóstico; HOME no
contiene checkbox ni estado PolyScope. Se usa el host del robot,
TCP 29999, biblioteca estándar, conexión fresca y plazo total de 2 s, sin retries.
Después de REINICIAR SISTEMA siempre se consulta Dashboard. Su ausencia no
convierte una recuperación Modbus válida en fallo.

El cliente envía únicamente `programState\n` y `robotmode\n`. La referencia
oficial [Dashboard Server CB-Series](https://www.universal-robots.com/articles/ur/dashboard-server-cb-series-port-29999/)
y su [tabla de comandos](https://s3-eu-west-1.amazonaws.com/ur-support-site/15690/Dashboard_Server_CB-Series.pdf)
documentan programState desde v1.8 y robotmode desde v1.6, anteriores a CB3 3.x.
PLAYING/STOPPED/PAUSED se muestran como EJECUTANDO/DETENIDO/PAUSADO.
Consultas no reconocidas producen DESCONOCIDO; timeout, desconexión, saludo
inválido o respuesta incompleta producen NO DISPONIBLE.

DETALLE incluye disponibilidad Dashboard, robot mode y respuestas recibidas.
Robot mode RUNNING no significa que el programa de juego esté ejecutándose.
Tampoco EJECUTANDO identifica el controlador requerido: confirmarlo en el pendant.
Dashboard es informativo, no participa en el handshake ni convierte un fallo de
29999 en fallo de Modbus. No se añade un requisito automático de Dashboard para
iniciar. No existe una API genérica para enviar comandos ni acciones remotas.

## Cámara: uso normal y configuración avanzada

- **RECONECTAR CÁMARA** cierra y reabre la cámara actual; no consulta al robot.
- **REINICIAR SISTEMA**, tras recuperar el robot, borra el historial temporal del
  BoardObserver; no reinicia cámara ni detector. El método interno de reset de
  observación mantiene esa separación, sin botón adicional en la vista normal.
- **CONFIGURACIÓN AVANZADA** contiene detectar cámaras, Camera N, AUTO/DSHOW/MSMF
  y aplicar cámara. Detectar enumera, sin cambiar selección ni configuración.
  Aplicar usa el índice/backend elegidos y reabre la captura.

Detectar mantiene hasta seis probes secuenciales OpenCV, liberando cada handle
incluso si falla. Omite el índice cuya captura ya posee la app, también al elegir
otro backend o después de un fallo de lectura. Los índices entre backends no
garantizan identidad física: confirmar visualmente la C920 al comparar.
No hay detección automática al arrancar.

## Investigación del arranque lento

Hallazgos verificables en el código previo:

- `Camera.open()` construía otro VideoCapture sin idempotencia ni exclusión entre
  open/read/release. Ahora captura y backend serializan esas operaciones; otro
  open sobre una cámara abierta reutiliza la captura.
- Un fallo de configuración de resolución/FPS antes de asignar `_capture` carecía
  de liberación explícita. Ahora libera el handle y propaga el error.
- Detectar con otro backend podía abrir el índice en uso. Ahora se omite.
- Arranque/aplicar/reconectar usan un worker; se bloquean solicitudes adicionales
  mientras vive. Shutdown impide nuevas operaciones; el worker libera recursos
  cuando retorna el driver. No se lanza una apertura de reemplazo por timeout.
- VideoCapture, los tres ajustes y la primera lectura pueden bloquear en el
  driver. Las lecturas siguen en el tick GUI: una lectura bloqueada puede congelar
  temporalmente la interfaz. No existe cancelación forzada de OpenCV.
- El sondeo inicial Modbus ocurre después de abrir cámara y antes del primer
  tick. Puede sumar su timeout al tiempo hasta el primer frame; USB/OpenCV no
  utiliza ni depende del puerto Modbus 502.

Estos riesgos **no demuestran la causa de los cinco minutos en el banco**.
OpenCV mantiene reportes de [arranque lento MSMF](https://github.com/opencv/opencv/issues/17687)
y [demora inicial al configurar resolución](https://github.com/opencv/opencv/issues/27917).
Son hipótesis compatibles, pendientes de medir en esta C920. También debe
comprobarse si otro proceso conserva el dispositivo. No se cambian backend
default, resolución, FPS, variables de entorno ni parámetros del driver.

DETALLE incluye:

| Métrica | Definición |
| --- | --- |
| camera_index / backend | Índice y backend solicitados; se conserva AUTO |
| backend efectivo | Nombre comunicado por OpenCV tras abrir |
| camera_open_seconds | Apertura y configuración, también si falla |
| capture_open_seconds | Duración del constructor VideoCapture |
| configure_seconds | Ajustes de ancho, alto y FPS |
| first_frame_seconds | Desde fin de apertura hasta primer frame válido; incluye espera del tick y sondeo Modbus inicial |
| first_frame_read_seconds | Duración de la lectura que entregó ese primer frame |
| Apertura en curso | Tiempo transcurrido mientras el driver no retorna |

Las métricas se reinician al abrir de nuevo, no al consultar estado ni reiniciar
observación. No se añaden retries ni loops de reapertura.

Siguiente ensayo manual: con el mismo dispositivo y condiciones, comparar AUTO,
DSHOW y MSMF desde Avanzado → Aplicar; registrar DETALLE y confirmar backend
efectivo. Guardar evidencia fuera de Git. Consultar CÁMARA / DIAGNÓSTICO para distinguir
Modbus de STATUS129 y PolyScope. Validar recuperación y tiempos antes de repetir
la partida física.

## Cierre completo

SALIR y la X llaman a la misma rutina `shutdown_all()`. Marca closing, cancela
el runtime local sin escribir registros y bloquea nuevas operaciones. Espera a
los workers de cámara y robot, libera Camera/VideoCapture, cierra Modbus y
Dashboard, y solo entonces destruye Tk. Cada recurso se intenta cerrar aunque
otro lance una excepción; el error se presenta al operador. La rutina es idempotente.

Si el robot figura BUSY o tiene entrega pendiente, avisa que cerrar no detiene
el movimiento. Un open nativo de OpenCV no admite cancelación segura: la ventana
permanece en «Esperando liberación de dispositivos» hasta que el driver retorne.
No se crea otro worker de apertura ni se declara cerrado dejando el anterior vivo.
