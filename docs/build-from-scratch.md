# Construir Robot Triqui desde cero

Esta guía conecta fabricación y puesta en marcha del sistema v1.0.0. El montaje
validado usa UR3 CB3, PolyScope 3.14, Logitech C920 y pinza Robotiq mediante URCap.
El modelo de pinza y versión del URCap están pendientes de documentar.
Consultar primero los [datos de fabricación pendientes](../hardware/README.md):
no encargar piezas sin confirmar material, espesor y escala. No se publican
poses, IPs ni instalaciones personales; deben configurarse en cada montaje.

Para generar ArUco y ejecutar commissioning, preparar una copia del repositorio
con Python 3.12 siguiendo [desarrollo desde código](../README.md#desarrollo-desde-código).
El instalador por sí solo permite jugar, pero no incluye el harness de commissioning.
Los comandos siguientes se ejecutan desde la raíz del repositorio, con `.venv` activa.

## 1. Fabricar fichas

Descargar [ficha_X.stl](../hardware/pieces/ficha_X.stl) y
[ficha_O.stl](../hardware/pieces/ficha_O.stl). Preparar **5 X y 5 O**.
Confirmar escala y material antes de imprimir; los STL no declaran unidades.
Revisar una muestra contra la casilla, la pinza y el área del ArUco antes de completar
el lote. No modificar los originales para corregir una importación de unidades.

## 2. Cortar tablero

Preparar Base 1 ×1, Base 2 ×1 y dos unidades de cada horizontal/vertical central
y lateral: **10 piezas**. Usar los seis DXF enlazados en la
[tabla de fabricación](../hardware/README.md). Declaran mm. Confirmar material,
espesor y encajes con el responsable del diseño antes del corte; no están documentados.

## 3. Generar e imprimir ArUco

```powershell
python scripts/generate_aruco.py --ids 10 11 12 13 14 15 16 17 18
```

Imprimir los nueve PNG de `assets/aruco/` del diccionario **DICT_5X5_50**,
sin deformación y con margen blanco. El tamaño físico final debe comprobarse
con cámara y fichas; 600 píxeles de imagen no determinan un tamaño en milímetros.
Evitar reflejos. Orden de montaje:

```text
10 → CELL1    11 → CELL2    12 → CELL3
13 → CELL4    14 → CELL5    15 → CELL6
16 → CELL7    17 → CELL8    18 → CELL9
```

## 4. Ensamblar tablero

Revisar los contornos CAD, presentar bases y separadores y comprobar las nueve
casillas antes de fijar el conjunto. Falta un plano acotado de ensamble; confirmar
uniones, orden de bases y tornillería M5/T-slot con el responsable del montaje.
No hay cantidades ni longitudes de tornillos publicadas.
Fijar cada ArUco en su casilla, visible en vacío y oculto por X y O al colocar.
Mantener tablero inmóvil respecto al robot y conservar el mismo mapa al enseñar Features.

## 5. Montar cámara

Fijar la C920 para observar los nueve ArUco sin recortes ni oclusiones de la
estructura. El diseño/archivo del soporte está pendiente de publicar; su altura
y fijaciones deben confirmarse. Comprobar iluminación uniforme y rigidez.
No enseñar posiciones definitivas del tablero hasta que esté fijado.

## 6. Preparar PolyScope

En el UR3 CB3 / PolyScope 3.14, preparar Installation, TCP y payload reales con
un operador capacitado. Configurar la pinza mediante su URCap y disponer de las
funciones `rq_activate_and_wait`, `rq_open_and_wait` y `rq_close_and_wait`.
Seguir [PolyScope](polyscope-urscript.md) y [calibración física](calibracion-fisica.md).
Comprobar parada física y recorridos; no copiar poses de otro equipo.

## 7. Enseñar CELL1 / CELL3 / CELL7 / CELL9

Crear cuatro **Point Features** en posiciones reales de colocación, sin elevarlas.
CELL1 define la orientación de todas las celdas. Las otras cinco se calculan por
promedios XYZ en el controlador. Comprobar correspondencia entre esquinas y ArUco.
La arquitectura operacional no usa Plane Feature.

## 8. Enseñar PICK

Enseñar el Feature real de recogida con la ficha en su posición repetible.
La secuencia usa un **único PICK fijo**; preparar el suministro de cada ficha.
Verificar agarre y retirada manualmente según C10/C11 antes de Mode2.

## 9. Enseñar HOME

Enseñar el Feature HOME/WAIT con posición y orientación reales. Verificar tanto
la espera como los recorridos hacia PICK y desde las celdas. No hay un traslado
inicial automático a HOME; iniciar desde un estado conocido y un recorrido validado.

## 10. Crear Assignments

Antes del Script Node, crear seis Assignment Nodes:

| Variable | Valor seleccionado en PolyScope |
|----------|---------------------------------|
| P1 | CELL1_const |
| P3 | CELL3_const |
| P7 | CELL7_const |
| P9 | CELL9_const |
| P_PICK | Pose del Feature real de recogida |
| P_HOME | Pose del Feature real HOME/WAIT |

P_PICK y P_HOME son variables; seleccionar los Features existentes, sin copiar
como código las descripciones de esta tabla. Tras editar Features, detener y
reejecutar el programa desde los Assignments.

## 11. Cargar triqui_controller.script

Añadir Script > File después de los Assignments y cargar
[triqui_controller.script](../robot/urscript/triqui_controller.script).
Incluir las definiciones Robotiq incluso para cargar Mode0. Comenzar con
`MOTION_MODE=0` y `COMMAND=0`. El operador cambia el modo en la copia del robot
durante commissioning, nunca desde Python. La aproximación validada es
`APPROACH_DZ=-0.060`: −Z Tool sube 60 mm con ese TCP; verificar el sentido en
el montaje propio. Conservar los parámetros productivos y consultar
[modos y secuencias](polyscope-urscript.md).

## 12. Configurar aplicación

En una copia nueva, crear archivos locales sin sobrescribir los existentes:

```powershell
if (!(Test-Path config/app.local.yaml)) { Copy-Item config/app.example.yaml config/app.local.yaml }
if (!(Test-Path config/vision.local.yaml)) { Copy-Item config/vision.example.yaml config/vision.local.yaml }
```

En `app.local.yaml`, completar `robot.host` con la dirección del UR de la red local,
mantener puerto `502`, `aruco_profile: robust` y añadir
`vision_config: vision.local.yaml` al nivel raíz. En `vision.local.yaml`, configurar
índice y backend de cámara, verificar 1280×720 / 30 FPS, **DICT_5X5_50** y
`cell_ids: [10,11,12,13,14,15,16,17,18]`. Conservar los umbrales del ejemplo.
Usar [los ejemplos versionados](../config/) como referencia; nunca publicar los YAML locales.

En la aplicación instalada, la configuración externa reside en `config/app.yaml`
y `config/vision.yaml` junto al EXE; usar `vision_config: vision.yaml`.
El instalador conserva archivos existentes y puede incluir ajustes de laboratorio:
revisarlos para el equipo nuevo antes de abrir el modo real. También se admite
`RobotTriqui.exe --config ruta/al/app.local.yaml`.
Ver [configuración desktop](desktop-app.md) e [instalación](installation.md).

## 13. Probar cámara

Con GUI y otros clientes cerrados, usar las herramientas de visión:

```powershell
python main.py cameras
python main.py vision --aruco-profile robust
python main.py board-observe
```

Ejecutar una herramienta cada vez y cerrarla con `q`/`Esc` antes de abrir otra.
Comprobar los nueve IDs con tablero vacío y que el observador alcance todas las
celdas FREE sin UNCERTAIN persistente. Cubrir y descubrir casillas permite revisar
la ocupación temporal sin mover el robot. No ajustar umbrales para ocultar un
problema de luz o montaje. Ver [validación física](physical-validation.md).

## 14. Commissioning

Seguir [commissioning C0–C14](commissioning.md) en orden y guardar evidencia local.
Preparar el import del módulo y la evidencia de software:

```powershell
$env:PYTHONPATH = (Join-Path $PWD "src")
python -m pytest -q --junitxml=reports/pytest.xml
python -m ur_tictactoe.commissioning --steps C0 --pytest-report reports/pytest.xml --text-report
```

Continuar C1–C5 (visión), C6 (lectura de red), C7 (Mode0), C8–C9 (Mode1),
C10/C11 (evidencia manual de pinza/PICK), C12/C13 (Mode2) y C14 (end-to-end).
La guía enlazada contiene los comandos y confirmaciones de cada paso.
Cerrar la aplicación mientras se usa el harness. El operador cambia los modos
en PolyScope y autoriza cada movimiento; no ejecutar toda la secuencia sin supervisión.
C12/C13/C14 disponen de 60 s por defecto; no acelerar movimientos para evitar timeout.

En el montaje original **C13 físico: PASS y C14 end-to-end físico: PASS**.
Cada réplica necesita su propia aceptación. Los reportes se guardan en `reports/`,
fuera de Git. Ante fallo, inspeccionar el estado físico antes de recuperar;
ABORT, Ctrl+C y COMMAND0 no detienen un robot en movimiento.

## 15. Ejecutar aplicación

Cerrar el harness. Abrir Robot Triqui instalado o, desde código:

```powershell
python main.py app --config config/app.local.yaml
```

Esperar Cámara CONECTADA, Robot LISTO y Tablero LISTO. Para practicar sin hardware,
usar `python main.py app --simulate`. La [guía de instalación](installation.md)
explica apertura y cierre; el diagnóstico se describe en [desktop](desktop-app.md).

## 16. Jugar

Retirar todas las fichas del tablero y preparar PICK en condiciones seguras.
Elegir dificultad, quién inicia e INICIAR PARTIDA. Colocar una sola ficha durante
el turno humano y retirar la mano. Esperar colocación, retorno HOME y verificación
antes de intervenir. Al terminar, retirar fichas solo con el robot en estado seguro.
Cerrar con SALIR. Ante riesgo, usar la parada física.

Para reconstruir el software distribuible más adelante, consultar
[empaquetado Windows](desktop-app.md) y [portable](portable-release.md).
La Release v1.0.0 y su instalador se conservan como binario validado de referencia;
esta guía no requiere reemplazarlos.
