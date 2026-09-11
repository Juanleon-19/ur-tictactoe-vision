# Protocolo Modbus V1

El servidor Modbus del controlador Universal Robots escucha en TCP `502`, usa
direccionamiento base 0 y permite utilizar los registros generales `128..255`.
La V1 reserva dentro de ese rango dos *holding registers*. Estas direcciones son
una decisión del proyecto y coinciden con la configuración validada de
PolyScope:

```text
COMMAND_REGISTER = 128
STATUS_REGISTER  = 129
```

`COMMAND` usa estos valores:

```text
0     IDLE
1..9  seleccionar P1..P9 según el modo configurado en PolyScope
```

`STATUS` usa estos valores:

```text
0  READY
1  BUSY
2  DONE
3  ERROR
```

## Handshake

Al iniciar una nueva ejecución del controlador UR, este escribe COMMAND128=0
**antes de publicar READY** y antes de leer órdenes en el loop. Así descarta
comandos 1..9 residuales de una ejecución anterior, sin ejecutar una celda.

```text
READY -> COMMAND=N -> BUSY -> DONE -> COMMAND=0 -> READY
```

Python espera `READY`, escribe la celda pendiente y mantiene el tablero lógico sin
cambios durante `BUSY`. Al recibir `DONE`, el runtime espera que la cámara confirme
exactamente las ocupaciones anteriores más la celda elegida. Entonces confirma
la jugada en `GameSession`, escribe COMMAND0 y espera READY antes de cerrar la conexión.
El programa UR publica DONE después de volver HOME; C14 exige además confirmación
del operador, porque los dos registros no acreditan la posición ni el agarre.

El modo real abre una conexión TCP fresca al comenzar cada turno del robot.
No deja un socket ocioso mientras espera al humano. La comprobación inicial de
disponibilidad también se cierra; no garantiza conectividad futura. C8/C9/C12/C13
conectan después de autorizar cada movimiento y cierran antes de preguntar su resultado.

Las excepciones de transporte se convierten en `ModbusConnectionError`, con causa
original. PyModbus se construye con `retries=0`: una respuesta perdida nunca
autoriza reenviar COMMAND n. Fallo, timeout o aborto detiene el avance y cierra
el socket sin COMMAND0, sin repetir movimiento y conservando la evidencia de
entrega incierta. Inspeccionar estado físico y Log antes de recuperar manualmente.
COMMAND0 es acknowledgement, **no emergency stop**; usar parada física ante riesgo.

La GUI distingue ACTUALIZAR ESTADO (solo lectura) de RECUPERAR ROBOT (acción
explícita del operador). Recuperar lee STATUS en una conexión fresca: BUSY aborta
sin escritura; READY/DONE/ERROR permiten un único COMMAND0 seguido de espera
corta de READY y cierre. Nunca reenvía celdas ni reanuda partidas inciertas; las
cancela conservando evidencia en el historial de sesión. INICIAR PARTIDA también
consulta STATUS fresco, pero no resetea COMMAND. Ver
[recuperación y diagnóstico](recovery-diagnostics.md).

El runtime real limita movimiento, verificación y espera del acuse a 60 s por
etapa. No consume ese tiempo durante el turno humano. C12/C13/C14 tienen 60 s
predeterminados; los pasos rápidos 15 s. `--timeout` del harness tiene prioridad.

El cliente usa Modbus TCP síncrono mediante `pymodbus>=3.14,<3.15`. Host, puerto
(por defecto `502`) y timeout son configurables; ninguna IP real se almacena en el
repositorio. El servidor UR ignora el campo Unit Identifier/Slave ID; no se añade
ninguna lógica especial alrededor de ese campo aunque PyModbus lo incluya al
construir la solicitud.
