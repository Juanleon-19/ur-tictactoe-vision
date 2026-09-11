# Instalar Robot Triqui en Windows

Robot Triqui funciona en Windows 10/11 de 64 bits. No necesita tener Python instalado.

1. Ejecutar **RobotTriqui_Setup.exe**.
2. Completar la instalación para el usuario actual. Puede elegir crear un acceso
   directo en el Escritorio. Normalmente no requiere permisos de administrador.
3. Abrir **Robot Triqui** desde el Menú Inicio o el acceso directo del Escritorio.
4. Preparar el robot, su programa en PolyScope, la cámara USB, el tablero y las fichas.
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

## Desinstalar

Cerrar Robot Triqui con **SALIR**. En Windows, abrir **Configuración → Aplicaciones
→ Aplicaciones instaladas**, buscar **Robot Triqui** y elegir **Desinstalar**.
Se eliminan los archivos instalados y sus accesos directos. La desinstalación no
conecta con el robot ni ejecuta la aplicación.
