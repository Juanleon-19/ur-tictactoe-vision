# Validación física del MVP

Estado: C920 detectada a 1280×720 @ 30 FPS; `robust` mejoró claramente
la detección frente a `default` y es el perfil operacional predeterminado.
Se observaron IDs 10..18 en 9/9, con mayor flicker en ID18.
La validación de ocupación y del ciclo físico completo sigue pendiente.

Estas pruebas se ejecutan manualmente y en orden. Los tests automáticos nunca
mueven el robot.

## A. Visión / ArUco

### A1 — Estabilidad

Con el tablero vacío y la cámara en su posición definitiva:

1. ejecutar 30 s con `python main.py board-observe --aruco-profile default`;
2. cerrar con `q` o `Esc` y anotar el resumen de los nueve IDs operacionales;
3. repetir 30 s con `python main.py board-observe --aruco-profile robust`;
4. comparar por ID el porcentaje detectado sobre todas las muestras.

PASS: no aparece ningún falso `OCCUPIED` y se elige el perfil con mayor
estabilidad. Registrar también FPS medio, iluminación y qué IDs bajan de 95 %.

### A2 — Ocupación

Partir del tablero vacío, colocar fichas en 1, 5 y 9 y verificar la detección
automática. Completar después el mapping físico 1..9.

PASS: se identifica la celda correcta, no hay eventos duplicados, la
confirmación ocurre en tiempo razonable y una mano u oclusión breve no genera
una ficha falsa.

## B. Modbus sin movimiento

C6 y C7 aprobados físicamente; C6 pasó cinco veces consecutivas. PC y UR en la
misma subred, configurada solo localmente. UR Modbus TCP, puerto `502`: registro
`128 COMMAND` y registro `129 STATUS`.

C6 solo lee STATUS. C7 exige verificar MOTION_MODE=0 y autorizar su handshake
COMMAND5 → BUSY → DONE sostenido → COMMAND0 → READY, sin movimiento.

## C. Cuatro Point Features / interpolación

Arquitectura validada por el operador: cuatro Point Features de colocación
CELL1/CELL3/CELL7/CELL9 y Assignments P1/P3/P7/P9 antes del Script Node.
Interpolar XYZ, conservar orientación P1 y elevar Pn mediante Tool Z -60 mm.
La selección de Features, aproximación y pick-place con Robotiq ya se probaron.

Aceptar el controlador integrado: C8 primero P5_UP, luego C9 P1_UP..P9_UP.
No bajar ni accionar pinza en Mode1. Para recalibrar, editar las cuatro esquinas
y reejecutar los Assignments; Python no calcula ni transmite coordenadas.

## D. Movimiento + Modbus

Seguir [Calibración física](calibracion-fisica.md): C10/C11 confirman Robotiq y
PICK manual; C12/C13 prueban colocación con Mode2 y confirmación individual.
C12 y varios ciclos C13 funcionaron; completar la cobertura restante. El pick/place
excede 15 s: se usa 60 s por defecto, sin cambiar velocidades. No dejar un socket
abierto durante espera humana ni repetir un comando de entrega incierta.
C14 ejecuta aceptación guiada de un turno primero o partida completa con visión;
la aceptación física de este nuevo flujo aún está pendiente.
C6/C7 fueron confirmados físicamente; su contrato 128/129 se conserva.
