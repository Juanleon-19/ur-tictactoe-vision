# Fabricación y ensamble físico

Esta carpeta contiene dos STL de fichas, seis DXF del tablero, la
[BOM.csv](BOM.csv) y `images/`, reservado para fotos reales.
Los ocho CAD se copiaron de los originales suministrados sin reparación,
reescalado ni modificación de geometría; se comprobó igualdad SHA-256.
Los originales de recepción quedan fuera de Git.

## Piezas y cantidades

| Elemento | Cantidad | Proceso | Archivo/Referencia |
|----------|----------|---------|--------------------|
| Ficha X | 5 | Impresión 3D | [ficha_X.stl](../hardware/pieces/ficha_X.stl) |
| Ficha O | 5 | Impresión 3D | [ficha_O.stl](../hardware/pieces/ficha_O.stl) |
| Base 1 | 1 | Corte láser | [base_1.dxf](../hardware/board/base_1.dxf) |
| Base 2 | 1 | Corte láser | [base_2.dxf](../hardware/board/base_2.dxf) |
| Horizontal central | 2 | Corte láser | [horizontal_central_x2.dxf](../hardware/board/horizontal_central_x2.dxf) |
| Horizontal lateral | 2 | Corte láser | [horizontal_lateral_x2.dxf](../hardware/board/horizontal_lateral_x2.dxf) |
| Vertical central | 2 | Corte láser | [vertical_central_x2.dxf](../hardware/board/vertical_central_x2.dxf) |
| Vertical lateral | 2 | Corte láser | [verticales_laterales_x2.dxf](../hardware/board/verticales_laterales_x2.dxf) |
| ArUco (IDs 10..18) | 9 | Impresión 2D | [generate_aruco.py](../scripts/generate_aruco.py) |
| Soporte de cámara | 1 | DISEÑO/ARCHIVO PENDIENTE DE PUBLICAR | Sin archivo publicado |
| Tornillería M5 / T-slot | POR CONFIRMAR | Ensamble | Longitudes POR CONFIRMAR |

Son **10 fichas y 10 piezas de corte láser**. El sufijo `x2` indica la cantidad
total requerida de ese elemento; revisar el contenido del DXF en el programa de
corte antes de multiplicar sus contornos.

## Unidades y preparación

Los seis DXF incluyen `$INSUNITS = 4`, que declara **milímetros**, según
[la referencia de Autodesk](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Core/files/GUID-A58A87BB-482B-4042-A00A-EEF55A2B4FD8.htm).
Comprobar que el programa de corte conserva la escala al importarlos.
El material y el espesor de cada base y separador están **POR CONFIRMAR**;
no se deducen del dibujo 2D. Confirmarlos antes de encargar el corte.

En ambos STL, las **dimensiones aproximadas** de la caja envolvente XYZ son
**59 × 59 × 50 unidades de coordenadas**, obtenidas leyendo sus vértices.
STL no declara unidades: no se certifica que esas cifras sean milímetros.
Confirmar la escala en el laminador y su correspondencia con tablero y pinza.
El **archivo CAD es la fuente de verdad** para la geometría; estas dimensiones
solo ayudan a comprobar la importación. Material de impresión, orientación,
relleno y tolerancias aún no están documentados.

## ArUco y ensamble

Preparar nueve marcadores **DICT_5X5_50**, uno por casilla:

```text
10 → CELL1    11 → CELL2    12 → CELL3
13 → CELL4    14 → CELL5    15 → CELL6
16 → CELL7    17 → CELL8    18 → CELL9
```

```powershell
python scripts/generate_aruco.py --ids 10 11 12 13 14 15 16 17 18
```

Ejecutar desde la raíz del repositorio con el entorno preparado. Los PNG quedan
en `assets/aruco/`. Imprimir cuadrados, con margen blanco y superficie sin reflejos.
El tamaño impreso, el adhesivo y la ubicación exacta dentro de cada casilla están
pendientes de acotar. Las dos fichas deben ocultar de forma repetible el marcador;
comprobar especialmente que la abertura de O no lo deje visible.

Montar bases y separadores para formar el tablero 3×3 y fijarlo sin movimiento
respecto al robot. Antes de fabricar en serie, comprobar encajes y orientación
de cada pieza con los CAD. Falta publicar un plano de ensamble acotado: no se
prescriben un orden entre bases, uniones ni tolerancias sin esa información.
Situar la cámara fija para observar los nueve marcadores completos con tablero vacío.

## Pendientes de publicación o confirmación

- Soporte de cámara: **1**, DISEÑO/ARCHIVO PENDIENTE DE PUBLICAR. El conjunto CAD publicado no incluye un soporte validado.
- Tornillería **M5 / T-slot**: cantidades, longitudes y referencias exactas **POR CONFIRMAR**.
- Material y espesor de corte láser; parámetros y escala física de impresión 3D.
- Plano de ensamble, tolerancias, fijaciones y cotas de colocación/tamaño de ArUco.
- Altura y fijación del soporte de cámara.
- Modelo exacto de pinza Robotiq y versión del URCap utilizado.
- Fotos reales y video: ver [material audiovisual pendiente](../docs/media.md).

La publicación permite acceder a los CAD originales; los datos pendientes deben
resolverse antes de reproducir fielmente el montaje. Seguir después la
[guía de construcción](../docs/build-from-scratch.md) para la puesta en marcha.
