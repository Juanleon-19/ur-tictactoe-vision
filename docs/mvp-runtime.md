# Runtime físico MVP

Integrado en `feature/gameplay-polish`, usado por la GUI real y C14.
BoardObserver y Minimax conservan su lógica y umbrales existentes.

El runtime es una capa de aplicación independiente de GUI, cámara y robot. Recibe
una `GameSession`, un `ModbusClient` ya construido y estados estables
`PhysicalBoardState`. Su API pública es `start(initial_state)`,
`update_board(state)`, `poll_robot()` y `snapshot()`.

## Flujo humano

```text
BoardObserver -> PhysicalBoardState -> diferencia físico/lógico -> GameSession
```

Solo se acepta una ocupación nueva, sin celdas lógicas retiradas, con tablero
`ready` y sin `UNCERTAIN`. Los cambios múltiples o retiradas quedan esperando con
una razón diagnóstica; PÍCARO y piezas retiradas quedan post-MVP.

## Flujo robot

```text
GameSession -> Modbus -> UR -> DONE -> BoardObserver -> verificación
                                                    -> confirm_robot_move()
```

`READY` envía el comando una sola vez y `BUSY` suspende las decisiones visuales.
`DONE` solo indica que terminó el programa UR: el tablero lógico no cambia hasta
observar exactamente las ocupaciones anteriores más la celda esperada. Hasta
entonces el comando permanece distinto de cero y no hay reenvío ni reintento.

La aplicación mantiene la cámara abierta por encima del runtime y le
entrega observaciones estables. La GUI es otra capa superior que consulta
`RuntimeSnapshot`; no existe callback ni bus de eventos.

En hardware, `manage_connection=True` abre TCP al iniciar el turno robot y lee
READY inmediatamente. Exige BUSY antes de DONE; después de verificación visual,
COMMAND0 conduce a `ACKNOWLEDGING_ROBOT` hasta leer READY. Solo entonces cierra
y pasa a WAITING_HUMAN/GAME_OVER. No quedan sockets durante la espera humana.
La simulación conserva su ciclo anterior. Cada etapa real dispone de 60 s.
`stop()` y los errores cierran sin acuse ni reintento. Una escritura cuya respuesta
se perdió permanece registrada como posiblemente enviada; no se permite iniciar
otra partida desde la GUI con un comando sin resolver. No es parada física.

## Límite de Pícaro

El flujo físico normal no cambia. `confirm_simulated_robot_replacement()` y
`confirm_simulated_human_replacement()` existen solo para que la simulación
confirme una decisión `picaro` mediante estado lógico.
No debe utilizarse con hardware: sustituir una ficha conserva la casilla ocupada
y el observador V1 no distingue propietario. Pícaro real queda bloqueado hasta
disponer de clasificación verde/amarillo y validación física.

## Comprobación Modbus

`python main.py modbus-check --host <HOST_LOCAL>` conecta, lee una vez `STATUS` y
cierra sin escribir. Una escritura de desarrollo requiere simultáneamente
`--command 5 --allow-write` y anuncia que modifica `COMMAND_REGISTER=128`.
