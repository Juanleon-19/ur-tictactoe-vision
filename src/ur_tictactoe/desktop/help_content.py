"""Deterministic offline operator guidance; no hardware commands."""

from ur_tictactoe.desktop.commissioning_status import CommissioningStatus

SECTIONS = ("CÓMO JUGAR", "INFORMACIÓN TÉCNICA")
USER_HELP = (
    ("CÓMO JUGAR", "1. Preparar robot, tablero y fichas.\n"
     "2. Esperar Cámara conectada, Robot LISTO y Tablero LISTO.\n"
     "3. Elegir dificultad y quién inicia: Robot o Humano.\n"
     "4. Pulsar INICIAR PARTIDA.\n"
     "5. Colocar una sola ficha cuando sea turno humano.\n"
     "6. Retirar la mano.\n"
     "7. No tocar el tablero durante el movimiento del robot."),
    ("SI EL ROBOT NO ESTÁ LISTO", "Comprobar PolyScope y la conexión Ethernet.\n"
     "Usar REINICIAR SISTEMA. La partida anterior se cancela.\n"
     "Si el robot está en movimiento, esperar o usar la parada física ante riesgo."),
    ("SI LA CÁMARA NO FUNCIONA", "Comprobar USB. Usar RECONECTAR CÁMARA.\n"
     "Revisar que los 9 marcadores sean visibles."),
    ("SI EL TABLERO NO ESTÁ LISTO", "Retirar las manos. Comprobar los marcadores.\n"
     "Esperar estabilización. Para una partida nueva, retirar las fichas."),
    ("CÓMO CERRAR", "Usar SALIR y esperar la liberación de dispositivos.\n"
     "Cerrar la aplicación no detiene un movimiento del robot.\n"
     "Ante riesgo, usar la parada física."),
)
ADVANCED_SECTIONS = ("Puesta en marcha", "Commissioning", "Solucionar problema",
                     "Cámara y visión", "Red y robot", "Acerca del sistema")
SAFETY = (
    "Cerrar aplicación, Ctrl+C o ABORT no garantiza detener un movimiento ya iniciado del UR.\n"
    "COMMAND0 es acknowledgement, NO emergency stop.\n"
    "Ante riesgo: usar parada física del robot."
)
BOARD_MAP = "\n\n".join(
    "  ".join(f"CELL{i}" for i in range(start, start + 3)) + "\n"
    + "     ".join(f"ID{i + 9}" for i in range(start, start + 3))
    for start in (1, 4, 7)
)
STEPS = {
    "C0": "Software: dependencias, configuración y evidencia pytest.",
    "C1": "Cámara: apertura y captura.",
    "C2": "ArUco: visibilidad de IDs 10–18.",
    "C3": "Tablero: referencia vacía estable.",
    "C4": "Ocupación: fichas en 5 y luego 1, 5, 9.",
    "C5": "Oclusión: mano transitoria y recuperación.",
    "C6": "Red UR / Modbus: TCP y lectura STATUS, sin escrituras.",
    "C7": "Mode0: handshake; NO debe mover robot. Confirmación del operador.",
    "C8": "CELL5 a altura segura: movimiento con autorización y confirmación.",
    "C9": "Cuadrícula: confirmar cada movimiento seguro y su resultado.",
    "C10": "Robotiq: confirmar URCap cargado y activación/open/close comprobados.",
    "C11": "PICK: confirmar ensayo manual de recogida, cierre y retirada.",
    "C12": "PLACE CELL5: Mode2, COMMAND5 y confirmación de ficha y HOME.",
    "C13": "PLACE otras celdas: Mode2, autorización y evaluación individual.",
    "C14": "Aceptación guiada: un turno humano+robot o partida completa, visión y retorno HOME.",
}


def contextual_help(snapshot) -> str:
    tips = []
    if snapshot.simulation:
        tips.append("SIMULACIÓN: los estados simulados no acreditan validación física.")
    if snapshot.camera_status != "CONECTADA":
        tips.append("CÁMARA NO CONECTADA: verificar USB; cerrar otras apps que usen cámara; "
                    "detectar cámaras y probar reconectar. La C920 puede tardar 50–60 s en abrir.")
    if snapshot.board_status != "LISTO":
        tips.append("TABLERO NO LISTO: retirar manos; revisar IDs faltantes; reducir reflejos; "
                    "esperar estabilización. Probar perfil Reflejos si es necesario.")
    if snapshot.robot_status != "LISTO":
        tips.append("ROBOT NO CONFIGURADO O NO LISTO: configurar host local, conectar Ethernet, "
                    "verificar subred y usar commissioning C6.")
    return "\n\n".join(tips) or "Sistema listo. Mantenga despejada la zona de trabajo."


def start_explanation(snapshot) -> str:
    if snapshot.robot_status == "REQUIERE RECUPERACIÓN":
        return "Robot requiere recuperación. Pulse REINICIAR SISTEMA.\nNo se enviará una nueva jugada."
    if snapshot.robot_status == "EN MOVIMIENTO":
        return "Robot en movimiento. Espere o use la parada física."
    if snapshot.camera_status != "CONECTADA":
        reason = "Cámara no conectada. Use RECONECTAR CÁMARA en diagnóstico."
    elif snapshot.robot_status != "LISTO":
        reason = "Robot no conectado. Revise Ethernet y PolyScope; use REINICIAR SISTEMA."
    else:
        reason = "El tablero debe estar vacío y estable. Retire manos y fichas; espere estabilización."
    return "NO SE PUEDE INICIAR\n" + reason


def report_text(report: CommissioningStatus | None) -> str:
    if report is None:
        return "Sin resultados de commissioning disponibles."
    return (f"Último reporte válido: {report.source}\n{report.timestamp}\nSHA: {report.software_commit_sha}\nEvidencia histórica, no validación del estado actual.\n"
            + "\n".join(f"{step} {description.split(':')[0]}: {report.results.get(step, 'PENDIENTE')}"
                        for step, description in STEPS.items() if step in report.results))


def help_text(section: str, snapshot, report: CommissioningStatus | None) -> str:
    if section == "CÓMO JUGAR":
        return "\n\n".join(title + "\n" + body for title, body in USER_HELP)
    if section == "Antes de jugar":
        return ("Despeje el tablero y la zona del robot. Compruebe que hay fichas en recogida "
                "y que puede alcanzar la parada física.\n\n"
                "Seleccione SISTEMA REAL solo para hardware preparado y autorizado. "
                "Espere cámara conectada, tablero vacío LISTO y robot LISTO antes de iniciar. "
                "En simulación no se mueve hardware.\n\n"
                "Coloque una sola ficha y retire la mano. Espere a que el robot termine "
                "y la aplicación indique su próximo turno.\n\n" + SAFETY)
    if section == "Si la cámara no detecta":
        return ("Abra CÁMARA / DIAGNÓSTICO. Seleccione la cámara correcta; la C920 puede "
                "tardar 50–60 s en abrir. Cierre otras aplicaciones que usen la cámara.\n\n"
                "Retire manos, revise los IDs visibles y faltantes y reduzca reflejos. "
                "Espere a que el tablero se estabilice. No cambie perfiles durante la partida.\n\n"
                "Robusto es el perfil predeterminado. Reflejos es experimental. "
                "Use COMPARAR PERFILES con el mismo tablero vacío e iluminación, al menos "
                "10 s por perfil; compare visibilidad por ID y FPS antes de decidir.")
    if section == "Si el robot no responde":
        return ("Compruebe Ethernet, programa PolyScope en ejecución y ausencia de alarmas. "
                "El ciclo de recogida y colocación puede tardar más de 15 s.\n\n"
                "Si aparece error o timeout, no reinicie ni repita la jugada sin comprobar "
                "el estado físico y el Log del robot: el comando podría haberse recibido. "
                "No cambie de modo para eludir el error. Consulte al responsable de la instalación.\n\n" + SAFETY)
    if section == "Estado del sistema":
        return (f"Cámara: {snapshot.camera_status}\nTablero: {snapshot.board_status}\n"
                f"Robot: {snapshot.robot_status}\n\n"
                "LISTO describe disponibilidad; cada turno comprueba de nuevo la conexión. "
                "Los datos de simulación y el historial no acreditan el estado físico actual.\n\n"
                "Diagnóstico y ayuda son de consulta. Procedimientos y evidencia técnica "
                "están en Avanzado.\n\n" + SAFETY)
    if section == "Solucionar problema":
        return contextual_help(snapshot)
    if section == "Puesta en marcha":
        results = report.results if report else {}
        checklist = (("Software", "C0"), ("Cámara", "C1"), ("ArUco", "C2"),
                     ("Tablero", "C3"), ("Red UR", "C6"), ("Modbus", "C6"),
                     ("Mode0", "C7"), ("Movimiento seguro", "C9"),
                     ("Robotiq", "C10"), ("Juego físico", "C14"))
        return "Checklist según último reporte (no combina ensayos anteriores):\n\n" + "\n".join(
            f"{label}: " + ("PASS" if results.get(step) == "PASS" else
                           "ACEPTACIÓN PENDIENTE" if step == "C14" else "PENDIENTE")
            for label, step in checklist
        ) + ("\n\nSin resultados de commissioning disponibles." if not report else
             "\n\nFAIL/BLOCKED/SKIPPED se muestran como pendientes; ver Commissioning para detalle.")
    if section == "Cámara y visión":
        return ("Detectar cámaras no cambia la configuración. Seleccione índice y backend y aplique.\n"
                "Cambios solo para esta sesión. Reconectar conserva Modbus y exige reacquirir el tablero.\n"
                "Reiniciar observación conserva cámara y detector. Operaciones bloqueadas durante partida física.\n"
                "Iluminación es solo orientación visual; no altera detección ni seguridad.\n\n"
                + BOARD_MAP + "\n\nMarcador visible estable → FREE. Marcador oculto estable → OCCUPIED.\n"
                "El observer filtra mano/reflejo temporal; ausencia instantánea no implica ocupación.\n"
                "Consultar C5 en Historial de validación para comprobar la evidencia de oclusión.")
    if section == "Red y robot":
        return ("PC Ethernet ↔ UR: ambos deben estar en la misma subred.\n\n"
                "Wi-Fi puede permanecer activo. Puerto Modbus 502. Host real se configura localmente.\n"
                "Verificar conectividad mediante C6 desde el harness.\n\n" + SAFETY)
    if section == "Commissioning":
        return (report_text(report) + "\n\nEjecutar desde harness de commissioning.\n"
                "C1–C6: sin movimiento. C7: Mode0 sin movimiento. C8–C9 y C12–C13: movimiento y confirmaciones. "
                "C10–C11: evidencia manual. C14: aceptación guiada con movimiento autorizado.\n\n"
                + "\n".join(f"{step}: {description}" for step, description in STEPS.items()))
    return ("Robot Triqui · Pontificia Universidad Javeriana\n"
            "Python/OpenCV: visión y juego. PolyScope/UR: movimiento físico.\n"
            "Ayuda offline de consulta; no escribe COMMAND, MOTION_MODE, gripper ni URScript.\n\n"
            "Pícaro físico es una mejora opcional: requiere P_DISCARD, retirada de ficha humana, "
            "colocación de ficha robot y un nuevo contrato de acción con validación física independiente.\n\n" + SAFETY)
