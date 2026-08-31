# Game Engine

El motor representa el tablero como nueve celdas que contienen `X`, `O` o están
vacías. Su interfaz pública usa siempre los números familiares del tablero:

```text
1 | 2 | 3
--+---+--
4 | 5 | 6
--+---+--
7 | 8 | 9
```

`Board` valida que una jugada esté entre `1..9`, que la celda esté libre y que la
partida no haya terminado. También comprueba las tres filas, tres columnas y dos
diagonales para detectar victoria. Hay empate cuando nadie ganó y no quedan
movimientos legales.

## Minimax

Minimax simula un árbol de partidas posibles. El robot es **MAX** porque elige la
puntuación mayor; el humano es **MIN** porque elige la menor. En forma resumida:

```text
elegir(tablero, turno, profundidad):
    si hay victoria, derrota o empate: devolver puntuación terminal
    si se alcanzó el límite: devolver heurística
    simular cada movimiento legal
    si juega robot: devolver el máximo
    si juega humano: devolver el mínimo
```

La puntuación terminal de EXPERTO es `10 - profundidad` cuando gana el robot, `0`
para empate y `profundidad - 10` cuando gana el humano. Así una victoria rápida
vale más y una derrota inevitable se retrasa. La puntuación se propaga desde las
hojas del árbol hasta la jugada actual.

Cuando varias jugadas tienen exactamente el mismo resultado óptimo, el desempate
agresivo cuenta cuántas respuestas permiten al humano conservar su mejor
resultado. El robot prefiere dejar menos respuestas correctas, pero nunca cambia
una victoria por empate ni un empate por derrota.

## EXPERTO e INTERMEDIO

EXPERTO recorre el árbol completo hasta un estado terminal. Por eso conoce las
consecuencias de todas las jugadas y, en un tablero 3×3, es invencible.

INTERMEDIO limita la búsqueda a **2 plies**: una jugada del robot y una respuesta
humana. El valor permite defender amenazas cercanas sin anticipar todas las
combinaciones futuras. Antes de buscar, siempre toma una victoria inmediata o
bloquea una victoria humana inmediata.

Al alcanzar el límite, su heurística suma líneas abiertas del robot, resta líneas
abiertas del humano y concede valores pequeños al centro y las esquinas. Dos
marcas en una línea abierta pesan más que una. Esta evaluación produce jugadas
razonables, pero puede no ver forks que aparecen después del horizonte; por eso
INTERMEDIO es fuerte en tácticas inmediatas y aun así puede ser derrotado.

## Modos visibles en español y PÍCARO

**EXPERTO** usa el Minimax completo. **INTERMEDIO** conserva la búsqueda limitada y
la heurística, incluidas la victoria y el bloqueo inmediatos.

**PÍCARO** evalúa primero el juego normal con Minimax completo. Si el robot puede
forzar una victoria, juega como EXPERTO. Si el mejor resultado normal es empate o
derrota y hay fichas humanas, simula sustituir cada una por una ficha robot y elige
determinísticamente la sustitución con mejor resultado Minimax, suponiendo que el
turno siguiente es humano. Esta acción consume el turno y no agrega otra ficha.

La intención se representa mediante
`RobotDecision(action="normal" | "picaro", cell=N)`. Solicitarla no modifica el
tablero; `GameSession` solo aplica la jugada o sustitución al confirmarla.
`Board.make_move()` continúa rechazando sobrescrituras.

**Modo PÍCARO — Feature post-MVP.** La lógica de juego está implementada y
probada. La integración física con Modbus y PolyScope queda pendiente. No forma
parte del flujo normal actualmente integrado en `main`.
