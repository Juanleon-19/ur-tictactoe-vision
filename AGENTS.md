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

La arquitectura de visión utiliza **13 marcadores** del mismo diccionario:

- `frame_ids = [0,1,2,3]`: cuatro marcadores externos persistentes para referencia/alineación del tablero;
- `cell_ids = [10,11,12,13,14,15,16,17,18]`: uno por cada celda lógica `1..9` en ese mismo orden.

No sustituir este diseño por cuatro marcadores externos únicamente ni por nueve marcadores internos únicamente sin autorización explícita.

Los marcadores de celda tendrán doble función:

1. identificar de forma inequívoca cada casilla;
2. servir como señal primaria de ocupación cuando la pieza colocada ocluya el marcador.

La ausencia de un marcador de celda **no equivale automáticamente a OCCUPIED**. En la fase correspondiente deberá validarse temporalmente y descartarse oclusión por mano, robot, iluminación, desenfoque u otros fallos de detección.

Durante Fase 1 solo se reportan marcadores visibles/faltantes; no se implementa todavía la máquina de estados FREE/UNKNOWN/OCCUPIED.

## Fases V1 aprobadas

Consultar `PLAN.md` antes de realizar cambios. La arquitectura vigente es:

- Fase 1: visión y los 13 ArUco, validada experimentalmente;
- Fase 2: detección temporal de la jugada humana por desaparición estable del marcador;
- Fase 3: motor 3×3 y Minimax, autorizado para desarrollo anticipado porque no depende de hardware;
- Fase 4: trayectorias preenseñadas en PolyScope con un único PICK fijo;
- Fase 5: Modbus envía solamente `COMMAND = 1..9`;
- Fase 6: integración completa;
- Fase 7: robustez opcional, solo cuando exista evidencia experimental.

Durante la Fase 3 están fuera de alcance:

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
11. Mantener separados los roles de `frame_ids` y `cell_ids`.
12. No inferir que un marcador faltante es ocupación hasta implementar y validar la lógica temporal de Fase 2.

## Git

- `main` debe representar un estado utilizable.
- Trabajar en ramas para cambios funcionales.
- Commits en inglés, pequeños y descriptivos.
- Documentación principalmente en español.
- Revisar el diff antes de cada commit.
- No reescribir historial compartido sin autorización.

## Seguridad del robot

Aunque el robot no forma parte de la Fase 3, conservar estas reglas para fases posteriores:

- ningún movimiento físico debe ejecutarse automáticamente como parte de tests;
- HOME, PICK y las nueve posiciones de juego se enseñarán en PolyScope;
- velocidades, aceleraciones, TCP, payload y poses reales nunca se inventan;
- cualquier activación de movimiento debe tener una ruta clara de parada y un estado conocido;
- la visión no debe ordenar una jugada si los marcadores externos no confirman la condición de referencia/alineación establecida.

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
