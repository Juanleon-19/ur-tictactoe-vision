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

## Estado actual

Consultar `PLAN.md` antes de realizar cambios. La fase activa inicial es:

**Fase 1 — Foundation & ArUco**.

Durante esta fase están prohibidas dependencias o implementaciones de:

- RTDE;
- URScript dinámico;
- Modbus;
- ROS/ROS2;
- Minimax;
- detección de X/O;
- control del robot;
- pose 3D del tablero;
- calibración hand-eye.

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

## Git

- `main` debe representar un estado utilizable.
- Trabajar en ramas para cambios funcionales.
- Commits en inglés, pequeños y descriptivos.
- Documentación principalmente en español.
- Revisar el diff antes de cada commit.
- No reescribir historial compartido sin autorización.

## Seguridad del robot

Aunque el robot no forma parte de la Fase 1, conservar estas reglas para fases posteriores:

- ningún movimiento físico debe ejecutarse automáticamente como parte de tests;
- HOME, PICK y las nueve posiciones de juego se enseñarán en PolyScope;
- velocidades, aceleraciones, TCP, payload y poses reales nunca se inventan;
- cualquier activación de movimiento debe tener una ruta clara de parada y un estado conocido;
- la visión no debe ordenar una jugada si el tablero está fuera de la condición de alineación establecida.

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
