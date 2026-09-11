# Plan y cierre de Robot Triqui

## Estado final v1.0.0

Proyecto funcional con aplicación Windows publicada, visión operacional con
**DICT_5X5_50, IDs 10..18**, juego, Modbus TCP y ejecución en UR3 CB3 / PolyScope 3.14.
El operador confirmó **C13 físico: PASS** y **C14 end-to-end físico: PASS**.
La descarga oficial es [RobotTriqui_Setup.exe v1.0.0](https://github.com/Juanleon-19/ur-tictactoe-vision/releases/download/v1.0.0/RobotTriqui_Setup.exe).
Esta pasada publica documentación y CAD sin cambiar software productivo, geometría,
poses ni parámetros de movimiento. No vuelve a ejecutar hardware ni reconstruye el instalador.

## Fases y resultados

| Fase | Resultado al cierre |
|------|---------------------|
| 1 — Visión y ArUco | Logitech C920 y nueve marcadores operacionales validados experimentalmente. |
| 2 — Jugada humana | BoardObserver temporal integrado; aceptación de jugada y verificación en el flujo físico C14 PASS. |
| 3 — Motor de juego | Reglas 3×3 y Minimax validados por tests; Experto e Intermedio disponibles, Pícaro solo simulado. |
| 4 — PolyScope | Cuatro Point Features de colocación, PICK fijo y HOME; Assignments e interpolación validados; C12/C13 físicos PASS. |
| 5 — Modbus | TCP 502, COMMAND128 y STATUS129; C6/C7 físicos aprobados y handshake integrado. |
| 6 — Integración | Cámara → BoardObserver → GameSession → Modbus → PolyScope → verificación visual; C14 end-to-end físico PASS. |
| 7 — Robustez opcional | Solo con evidencia experimental; no es un bloqueo del cierre V1. |
| 8 — Desktop y distribución | Aplicación Windows e instalador publicados en Release v1.0.0. |

## Arquitectura vigente

Python conserva cámara, detección, observación temporal, lógica, Minimax,
comunicación y verificación. PolyScope conserva posiciones, trayectorias,
accionamiento de pinza y parámetros físicos. Python no genera trayectorias cartesianas.

- Visión: nueve IDs de celda 10..18, en orden CELL1..CELL9; una ausencia aislada no es ocupación.
- Perfil operacional `robust`; umbrales y BoardObserver se conservan.
- CELL1/CELL3/CELL7/CELL9 son Point Features de colocación. Seis Assignments crean P1/P3/P7/P9/P_PICK/P_HOME.
- Las celdas derivadas usan promedios XYZ y orientación P1; aproximación Tool Z `APPROACH_DZ=-0.060`.
- Mode0 sin movimiento; Mode1 solo aproximación; Mode2 PICK → PLACE → HOME mediante Robotiq.
- Modbus abre una conexión por turno y la cierra tras READY. No reenvía ante entrega incierta.
- C12/C13/C14 usan 60 s por defecto; no se alteran velocidades para satisfacer un timeout.
- COMMAND0 es acuse/recuperación explícita, no parada física. El controlador limpia COMMAND128 antes de READY al arrancar.

Ver [arquitectura](docs/architecture.md), [PolyScope](docs/polyscope-urscript.md),
[commissioning](docs/commissioning.md) y [recuperación](docs/recovery-diagnostics.md).

## Historia de decisiones

El planteamiento inicial de **13 marcadores** incluía **IDs 0..3** externos.
Es un diseño histórico sustituido por la arquitectura operacional de nueve IDs
10..18. Los externos no forman parte del montaje final ni de su criterio de readiness.
También se abandonó Plane Feature en favor de cuatro Point Features enseñados.
El motor se desarrolló anticipadamente porque no dependía de hardware.

Los primeros ensayos documentaban C13 parcial y C14 pendiente; esos estados quedaron
superados por la confirmación física final del operador. Las notas históricas de
smoke de proceso no equivalen a una inspección visual automatizada del EXE.
La confirmación final no inventa métricas de partidas ni repite ensayos específicos
sobre recuperación o comparación de perfiles. Los informes personales quedan fuera de Git.

## Pendientes de reproducibilidad

- Publicar soporte de cámara y plano de ensamble; confirmar fijaciones y altura.
- Confirmar cantidades/longitudes M5 / T-slot, material y espesor de corte.
- Documentar escala y parámetros de impresión, tamaño/ubicación de ArUco y tolerancias.
- Documentar modelo Robotiq y versión del URCap.
- Añadir fotografías reales y video de partida completa.

La [guía desde cero](docs/build-from-scratch.md) y [hardware](hardware/README.md)
indican dónde se necesita esa información. Cada réplica debe ejecutar su propio
commissioning; una publicación documental no valida otro montaje.

## Evolución posterior

Homografía, pose 3D, hand-eye o clasificación visual adicional solo se considerarán
si hay una necesidad experimental demostrada. Pícaro físico requiere otro alcance
y validación. No se añade licencia ni CI en esta entrega; tampoco se modifica
v1.0.0 ni se crea una nueva Release.
