"""Deterministic offline operator guidance; no hardware commands."""

from ur_tictactoe.desktop.commissioning_status import CommissioningStatus

SECTIONS = ("Puesta en marcha", "Solucionar problema", "Cámara y visión",
            "Red y robot", "Commissioning", "Acerca del sistema")
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
    "C10": "Robotiq: NO DISPONIBLE; modelo, URCap y adaptador pendientes.",
    "C11": "PICK: NO DISPONIBLE en el harness.",
    "C12": "PLACE CELL5: NO DISPONIBLE en el harness.",
    "C13": "PLACE otras celdas: NO DISPONIBLE en el harness.",
    "C14": "Juego físico end-to-end: NO DISPONIBLE en el harness.",
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
    rows = [("Cámara conectada", snapshot.camera_status == "CONECTADA"),
            ("Robot conectado", snapshot.robot_status == "LISTO"),
            ("Tablero listo", snapshot.board_status == "LISTO")]
    return ("NO SE PUEDE INICIAR\n" + "\n".join(
        f"{'✓' if ready else '✕'} {label}" for label, ready in rows
    ) + "\nRevise CÁMARA / DIAGNÓSTICO. El tablero debe estar vacío.\n"
        "Códigos internos disponibles en diagnóstico.")


def report_text(report: CommissioningStatus | None) -> str:
    if report is None:
        return "Sin resultados de commissioning disponibles."
    return (f"Último reporte válido: {report.source}\n{report.timestamp}\nSHA: {report.software_commit_sha}\nEvidencia histórica, no validación del estado actual.\n"
            + "\n".join(f"{step} {description.split(':')[0]}: {report.results.get(step, 'PENDIENTE')}"
                        for step, description in STEPS.items() if step in report.results))


def help_text(section: str, snapshot, report: CommissioningStatus | None) -> str:
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
                           "NO DISPONIBLE" if step in ("C10", "C14") else "PENDIENTE")
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
                "Ejemplo solamente, NO hardcode de producto:\n"
                "UR: 192.168.1.10\nPC: 192.168.1.20\nMask: 255.255.255.0\n\n"
                "Wi-Fi puede permanecer activo. Puerto Modbus 502. Host real se configura localmente.\n"
                "Verificar conectividad mediante C6 desde el harness.\n\n" + SAFETY)
    if section == "Commissioning":
        return (report_text(report) + "\n\nEjecutar desde harness de commissioning.\n"
                "C1–C6: sin movimiento. C7: Mode0 sin movimiento. C8–C9: movimiento y confirmaciones.\n\n"
                + "\n".join(f"{step}: {description}" for step, description in STEPS.items()))
    return ("Robot Triqui · Pontificia Universidad Javeriana\n"
            "Python/OpenCV: visión y juego. PolyScope/UR: movimiento físico.\n"
            "Ayuda offline de consulta; no escribe COMMAND, MOTION_MODE, gripper ni URScript.\n\n" + SAFETY)
