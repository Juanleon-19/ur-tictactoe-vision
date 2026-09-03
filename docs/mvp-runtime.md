# Runtime físico MVP

`feature/mvp-runtime` depende temporalmente de
`origin/feature/robust-board-observer`. La dependencia se podrá retirar cuando
`BoardObserver` sea validado físicamente e integrado en la rama principal.

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

La aplicación futura mantendrá la cámara abierta por encima del runtime y le
entregará observaciones estables. La GUI será otra capa superior que consultará
`RuntimeSnapshot`; no existe callback ni bus de eventos.

## Límite de Pícaro

El flujo físico normal no cambia. `confirm_simulated_robot_replacement()` y
`confirm_simulated_human_replacement()` existen solo para que la simulación
confirme una decisión `picaro` mediante estado lógico.
No debe utilizarse con hardware: sustituir una ficha conserva la casilla ocupada
y el observador V1 no distingue propietario. Pícaro real queda bloqueado hasta
disponer de clasificación verde/amarillo y validación física.

## Comprobación Modbus

`python main.py modbus-check --host 192.168.1.10` conecta, lee una vez `STATUS` y
cierra sin escribir. Una escritura de desarrollo requiere simultáneamente
`--command 5 --allow-write` y anuncia que modifica `COMMAND_REGISTER=128`.
