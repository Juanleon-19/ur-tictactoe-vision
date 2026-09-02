# Aplicación de escritorio MVP

La interfaz es una aplicación Windows con CustomTkinter sobre Tkinter. Mantiene esta separación:

```text
Tkinter GUI
    ↓ comandos y snapshots
GameApplication
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

## Modo real

```powershell
python main.py app
```

La pantalla y sus controles quedan disponibles, pero esta rama no abre hardware.
Las celdas no son clicables y el inicio informa `REAL_MODE_NOT_CONFIGURED`. La
integración posterior inyectará estas dos fronteras sin cambiar la GUI:

```text
Camera -> ArucoDetector -> BoardObserver -> PhysicalGameRuntime
ModbusClient -> UR
```

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
