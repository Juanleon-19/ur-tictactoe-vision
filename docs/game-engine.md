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

La puntuación terminal de HARD es `10 - profundidad` cuando gana el robot, `0`
para empate y `profundidad - 10` cuando gana el humano. Así una victoria rápida
vale más y una derrota inevitable se retrasa. La puntuación se propaga desde las
hojas del árbol hasta la jugada actual.

Cuando varias jugadas tienen exactamente el mismo resultado óptimo, el desempate
agresivo cuenta cuántas respuestas permiten al humano conservar su mejor
resultado. El robot prefiere dejar menos respuestas correctas, pero nunca cambia
una victoria por empate ni un empate por derrota.

## HARD e INTERMEDIATE

HARD recorre el árbol completo hasta un estado terminal. Por eso conoce las
consecuencias de todas las jugadas y, en un tablero 3×3, es invencible.

INTERMEDIATE limita la búsqueda a **1 ply**. Antes de evaluar, siempre toma una
victoria inmediata o bloquea una victoria humana inmediata. Después puntúa líneas
abiertas, centro y esquinas, y elige con `random.Random(seed)` entre movimientos
con puntuación óptima o a un punto de ella. Así conserva reproducibilidad y puede
cometer errores estratégicos sin convertirse en un jugador completamente aleatorio.

Al alcanzar el límite, su heurística suma líneas abiertas del robot, resta líneas
abiertas del humano y concede valores pequeños al centro y las esquinas. Dos
marcas en una línea abierta pesan más que una. Esta evaluación produce jugadas
razonables, pero puede no ver forks que aparecen después del horizonte; por eso
INTERMEDIATE es fuerte en tácticas inmediatas y aun así puede ser derrotado.

La secuencia humana fija `3, 7, 9, 8`, jugando primero contra robot `O` con seed
`42`, demuestra esa posibilidad en las pruebas.

## Pícaro simétrico

Una decisión del robot se representa con `RobotDecision(action, cell)`. El robot
compara el resultado Minimax de su mejor jugada normal con el de su mejor
reemplazo. Solo devuelve `picaro` si el reemplazo mejora estrictamente el resultado
esperado; de otro modo conserva el recurso y juega `normal`.

`GameSession` inicia con un uso disponible para el robot y otro para el humano.
Cada uno puede sustituir exactamente una ficha rival y su recurso queda consumido.
`play_human_picaro(cell)` valida turno, modo, disponibilidad y propietario antes de
realizar la sustitución. Esta regla solo está habilitada en simulación.
