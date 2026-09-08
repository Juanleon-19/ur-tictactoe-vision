# Entrega portable Windows x64

Desde PowerShell en el repositorio, con `.venv` y las dependencias de build:

```powershell
scripts/create_portable_release.ps1
```

El script ejecuta el build limpio existente (incluidos tests y pip check) y genera
`release/RobotTriqui_Windows_x64.zip`. No reutiliza una distribución que pueda
contener configuración personal. Incluye únicamente la carpeta `RobotTriqui/`
con EXE, `_internal/` completo y `README.txt` proveniente de
`packaging/README-portable.txt`. Se conserva el formato PyInstaller onedir.
El script rechaza archivos inesperados fuera de `_internal` o configuraciones
locales; el ZIP y la distribución generada están ignorados por Git.

## Prueba de la copia extraída

Después de generar el ZIP, el operador puede repetir el smoke sin robot:

```powershell
$portableDir = Join-Path ([System.IO.Path]::GetTempPath()) ("RobotTriquiPortable_" + [guid]::NewGuid())
Expand-Archive release/RobotTriqui_Windows_x64.zip -DestinationPath $portableDir
scripts/smoke_windows.ps1 -Product (Join-Path $portableDir "RobotTriqui/RobotTriqui.exe") -EvidenceRoot $portableDir
```

Se ejecuta el EXE extraído en simulación y real desde un directorio vacío dentro
del temporal, fuera del repositorio/build. El resolver frozen usa `_MEIPASS` en
la copia extraída; no usa el repositorio para cargar el logo. El script compara
el hash del logo incluido con el original como verificación de integridad, no
como fuente de assets para el proceso. Comprueba ventana que responde durante
10 segundos, logs sin traceback y cierre controlado con código 0.
Rechaza distribuciones con `config/app.yaml` externo para evitar conexiones a UR.

Las evidencias `smoke_*/results.json` y logs quedan en el temporal indicado.
El smoke de proceso no certifica inspección visual ni compatibilidad con otros
sistemas; el equipo probado usa Windows x64. La cámara puede estar ausente:
el modo real debe mantener la ventana y gestionar ese estado.

El launcher de commissioning requiere el entorno Python del repositorio y es
independiente de la GUI portable; consultar [la guía física](commissioning.md).
