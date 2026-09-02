# Controlador URScript de Triqui

**Estado: PREPARADO PARA VALIDACIÓN FÍSICA. NO VALIDADO EN UN ROBOT.**

`triqui_controller.script` es un controlador V1 pequeño para PolyScope. Conserva
los registros `128 COMMAND` y `129 STATUS`, calcula las nueve celdas desde el
Feature Plane `TABLERO` y arranca con `MOTION_MODE = 0`, que no ejecuta movimientos.

## Antes de usarlo

No cambiar `MOTION_MODE` hasta verificar en el robot:

- modelo de robot y versión exacta de PolyScope/URScript;
- TCP, payload y herramienta;
- Feature Plane `TABLERO` enseñado físicamente;
- disponibilidad del símbolo URScript `TABLERO` dentro del Script node;
- `GRID_DX`, `GRID_DY`, `CELL1_X`, `CELL1_Y`, `Z_SAFE` y `Z_PLACE`, en metros;
- `CELL_RX`, `CELL_RY`, `CELL_RZ`, como vector de rotación relativo al Feature;
- HOME o posición inicial segura y recorrido libre hasta cada `CELL_N_SAFE`;
- solución de cinemática inversa y configuración articular para las nueve celdas;
- aceleración y velocidad iniciales bajo evaluación de riesgos.

Los valores geométricos `0.0` no representan posiciones reales. Los flags
`GEOMETRY_CONFIGURED` y `ORIENTATION_CONFIGURED` mantienen bloqueado el modo 1
hasta que una persona los complete conscientemente.

## Inclusión en PolyScope

En la Installation se espera configurar TCP, payload, Feature `TABLERO` y la
herramienta. En el Program se añade la inicialización necesaria y un **Script
node / File** que carga `triqui_controller.script`. Universal Robots documenta
que un Script node puede cargar archivos URScript y hacer disponibles sus
funciones y variables al programa. No se genera un archivo `.urp`.

La forma exacta de importación y el nombre resoluble del Feature deben verificarse
en la versión instalada. Si PolyScope inserta el archivo dentro de otro programa,
se debe confirmar si espera el programa completo o únicamente su cuerpo antes de
ejecutarlo.

Referencias oficiales:

- [UR Modbus Server](https://www.universal-robots.com/articles/ur/interface-communication/modbus-server/)
- [PolyScope Script node](https://www.universal-robots.com/manuals/EN/HTML/SW5_26/Content/prod-usr-man/software/PolyScope/content/AdvProgNodes/commandtab_script_en.htm)
- [PolyScope Features](https://www.universal-robots.com/manuals/EN/HTML/SW5_21/Content/prod-usr-man/software/PolyScope/content/installation_g5/installation_features_en.htm)
- [URScript manuals](https://www.universal-robots.com/developer/urscript/)
