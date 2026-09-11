# AGENTS.md

Instrucciones para asistentes de código que trabajen en este repositorio.

## Principio principal

Implementa únicamente la fase solicitada. No adelantes módulos de fases futuras salvo instrucción explícita.

El proyecto prioriza una arquitectura simple, verificable y fácil de depurar sobre soluciones excesivamente generales.

## Arquitectura acordada

La V1 separa responsabilidades de forma estricta:

- **Python/OpenCV**: cámara, ArUco, visión del tablero, lógica del juego, Minimax, Modbus y verificación.
- **PolyScope/UR**: posiciones físicas, trayectorias, pick-and-place y parámetros de movimiento.

Python no debe generar trayectorias cartesianas del UR en la V1.

## Contrato ArUco V1

La arquitectura operacional final utiliza **9 marcadores** DICT_5X5_50:
`cell_ids = [10,11,12,13,14,15,16,17,18]`, uno por celda lógica `1..9`.
Identifican casillas y sirven de señal primaria de ocupación por oclusión.
La ausencia aislada no equivale a OCCUPIED: conservar la validación temporal de
BoardObserver y la coherencia física/lógica del runtime.

El diseño original de 13 marcadores, incluidos `frame_ids = [0,1,2,3]`, es
histórico y fue sustituido con autorización explícita. No exigir esos IDs para
la operación ni reintroducirlos sin un alcance nuevo autorizado.

## Fases V1 aprobadas

Consultar `PLAN.md` antes de realizar cambios. La arquitectura vigente es:

- Fase 1: visión y los nueve ArUco operacionales, validada experimentalmente;
- Fase 2: detección temporal de la jugada humana por desaparición estable del marcador;
- Fase 3: motor 3×3 y Minimax implementados y validados;
- Fase 4: cuatro Point Features de colocación, PICK fijo y HOME en PolyScope;
- Fase 5: Modbus envía solamente `COMMAND = 1..9`;
- Fase 6: integración completa; C13 y C14 físicos PASS confirmados por el operador;
- Fase 7: robustez opcional, solo cuando exista evidencia experimental.

Restricciones históricas del desarrollo aislado de Fase 3 (no describen el estado final integrado):

- RTDE;
- URScript dinámico;
- Modbus;
- ROS/ROS2;
- clasificación de X/O;
- inferencia definitiva de ocupación;
- control del robot;
- pose 3D del tablero;
- calibración hand-eye.

La homografía, pose 3D y calibración no son requisitos de V1 mientras la
identificación directa por IDs resulte fiable.

## Reglas de desarrollo

1. Mantener módulos pequeños y con una responsabilidad clara.
2. No crear archivos vacíos para fases futuras.
3. Preferir configuración sobre constantes ocultas cuando el dato dependa del hardware.
4. No guardar IPs reales, rutas locales, calibraciones personales ni parámetros específicos del robot en Git.
5. Las pruebas automáticas nunca deben requerir ni mover un robot real.
6. Las pruebas de Fase 1 deben poder ejecutarse sin cámara física siempre que sea razonable.
7. Liberar siempre recursos de cámara y ventanas OpenCV al salir.
8. Manejar errores de cámara con mensajes claros; no usar excepciones silenciosas.
9. No añadir machine learning si una solución geométrica/determinista satisface el requisito.
10. Evitar dependencias que no tengan una necesidad demostrada.
11. Mantener el contrato operacional de nueve `cell_ids`; no añadir referencias externas sin autorización.
12. No inferir ocupación de una ausencia aislada; conservar la lógica temporal validada.

## Git

- `main` debe representar un estado utilizable.
- Trabajar en ramas para cambios funcionales.
- Commits en inglés, pequeños y descriptivos.
- Documentación principalmente en español.
- Revisar el diff antes de cada commit.
- No reescribir historial compartido sin autorización.

## Seguridad del robot

Conservar estas reglas en todas las tareas:

- ningún movimiento físico debe ejecutarse automáticamente como parte de tests;
- HOME, PICK y cuatro esquinas se enseñan en PolyScope; las otras celdas se derivan en el UR;
- velocidades, aceleraciones, TCP, payload y poses reales nunca se inventan;
- cualquier activación de movimiento debe tener una ruta clara de parada y un estado conocido;
- la visión no debe ordenar jugadas sin la condición de readiness del runtime; la alineación física se verifica en commissioning, no mediante marcadores externos.

## Criterio para añadir una dependencia

Antes de añadir una librería nueva, comprobar:

1. qué responsabilidad concreta resuelve;
2. si OpenCV, NumPy o la biblioteca estándar ya cubren esa necesidad;
3. si introduce complejidad de instalación desproporcionada.

## Entrega de cambios

Al finalizar una tarea, reportar:

- archivos modificados;
- comportamiento implementado;
- pruebas ejecutadas;
- limitaciones o hardware aún no validado;
- siguiente paso recomendado dentro de la fase actual.
