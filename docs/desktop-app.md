# Aplicación de escritorio MVP

La interfaz es una aplicación Windows con CustomTkinter sobre Tkinter. Mantiene esta separación:

```text
Tkinter GUI
    ↓ comandos y snapshots
GameApplication
    ↓
RealGameBackend (modo real)
    ↓
PhysicalGameRuntime
    ↓
GameSession / Modbus / PhysicalBoardState
```

La GUI no contiene Minimax, reglas, ArUco, observación física ni control Modbus.
Solo selecciona configuración, envía intenciones y representa snapshots.

## Modo simulado

```powershell
python main.py app --simulate
```

No abre cámara, sockets ni conexiones UR. Los clics humanos producen un
`PhysicalBoardState` y atraviesan `PhysicalGameRuntime`. El transporte simulado
entrega `READY`, `BUSY` y `DONE` en actualizaciones distintas; después genera la
ocupación física esperada para que el runtime verifique la jugada robot. El ciclo
usa `Tkinter.after()` y no bloquea el hilo gráfico.

En simulación están disponibles:

- **Experto:** Minimax completo, sin errores estratégicos deliberados.
- **Intermedio:** victoria y bloqueo inmediatos; después usa búsqueda de un
  nivel, heurística posicional y variación reproducible entre alternativas
  próximas.
- **Pícaro:** humano y robot disponen de una sustitución por partida. El humano
  activa `USAR PÍCARO` y selecciona una ficha robot; el robot solo gasta su uso
  cuando su mejor reemplazo mejora estrictamente su mejor jugada normal.

Al seleccionar Pícaro se muestra `PÍCARO · SOLO SIMULACIÓN`.

## Modo real

```powershell
python main.py app
```

`RealGameBackend` encapsula `Camera`, `ArucoDetector`, `BoardObserver` y
`ModbusClient`. Construirlo no abre dispositivos. `open()` intenta abrir cámara y
conectar Modbus de forma independiente, `tick()` captura como máximo un frame y
actualiza la observación, y `close()` libera ambos recursos de forma idempotente.

```text
Camera -> ArucoDetector -> BoardObserver -> PhysicalGameRuntime
ModbusClient -> UR
```

La partida solo comienza cuando existe una observación `ready`, sin celdas
inciertas ni ocupadas. Estas condiciones se delegan en
`PhysicalGameRuntime.start()`. Durante la partida, DONE conduce a
`VERIFYING_ROBOT`; el movimiento lógico no se confirma ni se limpia COMMAND hasta
que la visión observa la celda esperada.

El observador usa exclusivamente IDs 10..18 y cuenta las capturas dentro de su
ventana temporal. No requiere marcadores de referencia geométrica. `AppConfig`
permite seleccionar `aruco_profile="default"` para diagnóstico; el valor
operacional es `robust`.

La GUI sigue consumiendo comandos y snapshots: no abre dispositivos ni interpreta
ArUcos. Las casillas no son clicables en modo real. Los estados distinguen cámara,
robot y tablero, y los fallos de apertura quedan en `last_error` sin cerrar la GUI.
Los tests inyectan cámaras, detectores, observers y clientes Modbus pequeños, sin
usar sockets ni hardware real.

En modo real Pícaro permanece deshabilitado. Una sustitución no cambia el estado
`FREE/OCCUPIED`, por lo que hará falta identificar el propietario físico mediante
X verde y O amarilla, e integrar posteriormente HSV y las acciones UR.

La C920 fue detectada y validada a 1280×720 @ 30 FPS. El perfil `robust`
mejoró la detección y es el predeterminado del backend real y de `AppConfig`.
Los IDs 10..18 se han observado 9/9; ID18 presenta más flicker.
La prueba end-to-end con C920, tablero físico y UR sigue pendiente.

Los valores iniciales de conexión están en `AppConfig` y se documentan en
`config/app.example.yaml`; no se guardan secretos ni parámetros físicos.

## Identidad institucional y recursos

El logo oficial es opcional y debe colocarse en:

```text
assets/javeriana_logo.png
```

Si no existe, la aplicación continúa normalmente y conserva el nombre de la
universidad en el pie. `desktop/assets.py` resuelve esta ruta tanto desde el árbol
de desarrollo como desde el directorio temporal `_MEIPASS` de una futura
aplicación PyInstaller. No se incluye ni se genera una imitación del escudo.

## Distribución futura

Después de validar el modo real, PyInstaller podrá producir el ejecutable Windows
y posteriormente Inno Setup el instalador `Setup.exe`. Deberán incluirse
`assets/javeriana_logo.png` y los archivos de datos de CustomTkinter. La guía
oficial de CustomTkinter recomienda actualmente una distribución `--onedir` en
Windows. Ninguna herramienta de packaging se instala o configura en esta fase.
