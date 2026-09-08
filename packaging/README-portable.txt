ROBOT TRIQUI — Windows x64
Proyecto académico
Pontificia Universidad Javeriana
By: Juan Esteban León Saiz

PARA EJECUTAR
1. Extraer RobotTriqui_Windows_x64.zip completamente.
2. Abrir la carpeta RobotTriqui extraída.
3. Ejecutar RobotTriqui.exe.

No requiere instalación manual de Python.
NO mover únicamente RobotTriqui.exe fuera de su carpeta: conservar _internal
y todas las dependencias incluidas. Ejecutar después de extraer, no dentro del ZIP.

Para probar sin hardware, desde PowerShell en esa carpeta:
  .\RobotTriqui.exe --simulate

La cámara y la conexión al UR requieren hardware y configuración correspondientes.
Sin host configurado no conecta al robot. La configuración real la prepara el
operador; esta entrega no contiene direcciones personales ni poses del robot.
Los ejemplos están en _internal/config. Para configuración externa, crear config
junto al EXE y copiar allí app.example.yaml como app.yaml y vision.example.yaml
como vision.yaml. Configurar robot.host y, si procede, camera.index/backend.
Mantener 1280x720, perfil robust e IDs de casilla 10..18.

Esta entrega es exclusivamente para Windows x64. No se promete compatibilidad
con otros sistemas operativos. Las pruebas físicas se realizan con el runner de
commissioning separado y un operador; no forman parte del inicio de esta GUI.
