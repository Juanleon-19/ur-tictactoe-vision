# Calibración física — Robot Triqui

CB3 / PolyScope 3.14. El operador validó Assignments desde Point Features,
aproximación Tool Z -40 mm, Robotiq open/close y la secuencia
PICK → close → UP → CELL5_UP → CELL5 → open → UP. C6/C7 también están validados.
La integración completa debe aceptarse mediante C8–C14; esta entrega no movió hardware.

## Configuración enseñada

Usar Installation, TCP y payload validados. Enseñar cuatro Point Features
CELL1, CELL3, CELL7 y CELL9 en las posiciones reales de colocación.
Enseñar también recogida y HOME/WAIT. Las poses están en base,
posición en metros y vector de rotación en radianes.

Antes del Script Node: P1=CELL1_const, P3=CELL3_const, P7=CELL7_const,
P9=CELL9_const. Asignar P_PICK y P_HOME seleccionando sus Features reales.
Ver [orden del programa](polyscope-urscript.md). No rellenar listas ni inventar
poses. La interpolación solo usa XYZ y orientación de P1; recogida/HOME
conservan sus orientaciones propias.

Con el TCP probado, +Z Tool baja y -Z Tool sube.
APPROACH_DZ=-0.040 eleva 40 mm mediante pose_trans(P, p[0,0,APPROACH_DZ,0,0,0]).
No aplicar esa distancia sobre Z base. Conservar movej a=0.20, v=0.10 y
movel a=0.05, v=0.02; no optimizar todavía.

## Secuencia de aceptación

1. Guardar Installation y programa localmente. Verificar TCP/payload, posición
   inicial conocida, recorrido libre y parada física. Un solo cliente Modbus activo.
2. Reejecutar los seis Assignments antes del Script Node e incluir las definiciones
   rq_* del URCap Robotiq instalado.
3. Mantener Mode0 y COMMAND0 al inicio; conservar la evidencia C6/C7.
4. Seleccionar Mode1 manualmente y ejecutar C8: COMMAND5 termina en P5_UP,
   sin bajar ni accionar pinza.
5. C9: 1..9 con autorización y confirmación individual. Verificar posiciones y
   recorridos articulares, no solo destinos.
6. C10 registra confirmación explícita de URCap cargado y activación/open/close
   comprobados. No envía acciones al brazo ni a la pinza.
7. C11 registra ensayo manual de PICK + close + retract, con agarre real.
   No existe comando PICK independiente.
8. Mode2 manualmente. C12 autoriza COMMAND5: pick → place CELL5 → HOME.
   Confirmar físicamente ficha y retorno.
9. C13: primero 1,3,7,9 y después 2,4,6,8. Antes de cada comando confirmar
   celda libre, ficha en PICK y zona despejada; después confirmar colocación
   y HOME. CELL5 ya está cubierta por C12.
10. C14 registra precondiciones de la partida final. Falta adaptar el procedimiento
    runtime/visión/juego; no confundir precondiciones con PASS end-to-end.

DONE acredita finalización del script, no agarre/colocación. Confirmar esos
resultados físicamente y, en C14, con visión.

## Recalibración y parada

Tras mover el tablero, reenseñar solo sus cuatro Point Features, reiniciar desde
los Assignments y repetir C8/C9. Si cambia recogida o HOME, actualizar su Feature.

--allow-motion y las confirmaciones no sustituyen el control de la zona.
Timeout, Ctrl+C, ABORT y COMMAND0 no son paradas físicas. Ante un fallo, parar e
inspeccionar desde el pendant; no reenviar comandos automáticamente.
Errores URCap/IK o protective stops pueden impedir publicar ERROR/DONE.
La sintaxis completa y recorridos del controlador integrado requieren aceptación
en CB3; los tests del repositorio nunca mueven hardware.
