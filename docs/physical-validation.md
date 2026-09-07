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

Prueba posterior. Red prevista: UR `192.168.1.10`; PC en la misma subred con IP
diferente. El servidor es UR Modbus TCP, puerto `502`. Contrato actual: registro
`128 COMMAND` y registro `129 STATUS`.

Sin habilitar movimiento: el PC escribe `COMMAND=5` y el UR lee `5`; el UR
escribe `STATUS=2` y el PC lee `2`.

## C. Feature Plane / cuadrícula

Prueba posterior y física. Crear en PolyScope el Feature Plane `TABLERO` con tres
puntos enseñados. El pitch ya medido es 0.0655 m en ambos ejes: hueco de
60 mm y separación de 5,5 mm. El origen es el centro de celda 1, +X hacia celda 3
y +Y hacia celda 7. URScript calcula las nueve celdas relativas al Feature;
Python no calcula ni transmite sus coordenadas.

La primera prueba no baja a la superficie: validar CELL5_SAFE y después cada
`CELL_N_SAFE` a una altura enseñada. Probar una celda por comando y verificar que
el TCP queda sobre el centro correcto sin riesgo de choque. Solo después se
define `CELL_N_PLACE` a la altura real. Si se mueve el tablero se reenseña el
Feature Plane, no las nueve celdas.

## D. Movimiento + Modbus

Solo después de B y C. Probar primero `CELL 5` y después las nueve celdas.

Seguir los doce pasos de [Calibración física](calibracion-fisica.md), incluyendo
Robotiq, HOME/PICK y Z_PLACE antes de Mode 2. Todos esos ensayos siguen pendientes.
