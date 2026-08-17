# Protocolo Modbus V1

El servidor Modbus del controlador Universal Robots escucha en TCP `502`, usa
direccionamiento base 0 y permite utilizar los registros generales `128..255`.
La V1 reserva dentro de ese rango dos *holding registers*. Estas direcciones son
una decisión del proyecto y deben coincidir con la configuración futura de
PolyScope:

```text
COMMAND_REGISTER = 128
STATUS_REGISTER  = 129
```

`COMMAND` usa estos valores:

```text
0     IDLE
1..9  ejecutar Play_Cell_1 .. Play_Cell_9
```

`STATUS` usa estos valores:

```text
0  READY
1  BUSY
2  DONE
3  ERROR
```

## Handshake

```text
READY -> COMMAND=N -> BUSY -> DONE -> COMMAND=0 -> READY
```

Python espera `READY`, escribe la celda pendiente y mantiene el tablero lógico sin
cambios durante `BUSY`. Al recibir `DONE`, la capa de integración confirma la
jugada en `GameSession` y limpia `COMMAND`. Si recibe `ERROR`, cancela la jugada
pendiente sin modificar el tablero.

El cliente usa Modbus TCP síncrono mediante `pymodbus>=3.14,<3.15`. Host, puerto
(por defecto `502`) y timeout son configurables; ninguna IP real se almacena en el
repositorio. El servidor UR ignora el campo Unit Identifier/Slave ID; no se añade
ninguna lógica especial alrededor de ese campo aunque PyModbus lo incluya al
construir la solicitud.
