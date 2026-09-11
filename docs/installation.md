# Instalar Robot Triqui en Windows

## DESCARGAR

**[Descargar RobotTriqui_Setup.exe — v1.0.0](https://github.com/Juanleon-19/ur-tictactoe-vision/releases/download/v1.0.0/RobotTriqui_Setup.exe)**

[Release completa v1.0.0](https://github.com/Juanleon-19/ur-tictactoe-vision/releases/tag/v1.0.0).
SmartScreen puede advertir porque el instalador no está firmado.

## Instalar → abrir → sistema listo → jugar → SALIR

Robot Triqui funciona en Windows 10/11 de 64 bits. No necesita tener Python instalado.

1. Ejecutar **RobotTriqui_Setup.exe**.
2. Completar la instalación para el usuario actual. Puede elegir crear un acceso
   directo en el Escritorio. Normalmente no requiere permisos de administrador.
3. Abrir **Robot Triqui** desde el Menú Inicio o el acceso directo del Escritorio.
4. Usar un montaje configurado y aceptado mediante commissioning; preparar el robot,
   su programa en PolyScope, la cámara USB, el tablero y las fichas.
5. Esperar **Cámara CONECTADA**, **Robot LISTO** y **Tablero LISTO**.
6. Elegir dificultad y quién inicia; pulsar **INICIAR PARTIDA**. Colocar una sola
   ficha durante el turno humano y retirar la mano. No tocar el tablero mientras
   se mueve el robot.
7. Usar **SALIR** y esperar a que termine la liberación de dispositivos. La X
   de la ventana realiza el mismo cierre. Cerrar la app no detiene un movimiento
   del robot: ante riesgo, usar su parada física.

Si el robot no está listo, revisar PolyScope y Ethernet y usar **REINICIAR
SISTEMA**. Esto cancela la partida anterior. Si falla la cámara, revisar USB y
usar **RECONECTAR CÁMARA** en **CÁMARA / DIAGNÓSTICO**.

El instalador de laboratorio incluye la configuración preparada para ese equipo.
Si recibió una distribución genérica o cambia de equipo, solicitar al responsable
del laboratorio que revise la configuración antes de jugar. Una actualización
conserva la configuración que ya exista en la carpeta de instalación.

Para practicar sin dispositivos, se puede abrir `RobotTriqui.exe --simulate`.
Pícaro está disponible únicamente en simulación.

## Preparar otro montaje

Seguir [construir desde cero](build-from-scratch.md) para fabricar, configurar
PolyScope y software y ejecutar commissioning. C13 físico y C14 end-to-end físico
están confirmados PASS en el montaje original; una réplica necesita su aceptación.
Revisar los YAML externos antes del primer arranque real en otro equipo.
La configuración y los datos personales permanecen fuera de Git.

## Desinstalar

Cerrar Robot Triqui con **SALIR**. En Windows, abrir **Configuración → Aplicaciones
→ Aplicaciones instaladas**, buscar **Robot Triqui** y elegir **Desinstalar**.
Se eliminan los archivos instalados y sus accesos directos. La desinstalación no
conecta con el robot ni ejecuta la aplicación.
