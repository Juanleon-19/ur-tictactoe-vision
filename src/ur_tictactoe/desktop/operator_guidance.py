"""Read-only procedure summaries from docs/commissioning.md and contextual tips."""

from ur_tictactoe.desktop.help_content import STEPS

STEP_TITLES = {
    "C0": "Software", "C1": "Cámara", "C2": "ArUco", "C3": "Tablero vacío",
    "C4": "Ocupación", "C5": "Oclusión", "C6": "Red / Modbus", "C7": "Mode0",
    "C8": "CELL5 seguro", "C9": "Cuadrícula segura", "C10": "Robotiq",
    "C11": "PICK", "C12": "PLACE CELL5", "C13": "PLACE otras celdas", "C14": "Juego físico",
}
HISTORY_NOTICE = "Evidencia histórica — puede no representar el estado actual del hardware."
PROCEDURES = {
    "C1": ("Conectar la cámara y cerrar aplicaciones que la usen.",
           "Revisar frames, resolución y FPS durante la ventana de captura.",
           "Al menos un frame válido y ninguna lectura fallida. La apertura no consume la ventana."),
    "C2": ("Colocar el tablero con IDs 10–18 y abrir el preview desde el harness.",
           "C confirma; Q/Esc cancela. Revisar porcentajes por ID, incluido ID18.",
           "Cada ID debe verse al menos una vez. PASS no garantiza visibilidad suficiente."),
    "C3": ("Retirar fichas y manos; confirmar tablero vacío.",
           "Esperar observer ready y nueve celdas FREE.",
           "Referencia vacía estable y aceptación del runtime, sin I/O del robot."),
    "C4": ("Partir de una referencia vacía estable.",
           "Confirmar ficha en 5; después exactamente en 1, 5 y 9.",
           "Cada ventana termina estable, sin UNCERTAIN ni ocupaciones adicionales."),
    "C5": ("Confirmar una referencia vacía estable desde el harness.",
           "Tras YES, pasar la mano durante la captura y retirarla. Observar la ventana adicional "
           "de recuperación sin reiniciar el observer.",
           "Debe registrarse pérdida de marcadores y todas las celdas deben volver a FREE al final."),
    "C6": ("Conectar PC Ethernet ↔ UR y verificar host local y subred.",
           "Comprobar TCP y lectura de STATUS129.",
           "Conectividad y lectura correctas. Nunca escribe COMMAND."),
    "C7": ("Verificar físicamente script y MOTION_MODE=0. El harness exige autorización "
           "--allow-motion y confirmación YES del operador.",
           "READY → COMMAND5 → BUSY → DONE sostenido → COMMAND0 → READY, con tiempos. "
           "NO debe mover robot.",
           "Handshake completo sin movimiento esperado. COMMAND0 es un acuse, no una parada."),
    "C8": ("Confirmar Mode1, Assignments P1/P3/P7/P9 y aproximación Tool Z -40 mm. Disponer de parada física "
           "y autorizar CELL5 en el harness.",
           "Evaluar la posición final P5_UP, sin descenso, y responder YES/NO.",
           "Movimiento seguro y evaluación afirmativa; no asumir poses ni parámetros."),
    "C9": ("Mismas verificaciones físicas de C8; confirmar cada movimiento desde el harness.",
           "Revisar cada Pn_UP de 1–9 y evaluar su resultado antes de continuar.",
           "Todas las posiciones confirmadas individualmente. No encadenar sin operador."),
    "C10": ("Confirmar definiciones rq_* del URCap cargadas en PolyScope.",
            "Registrar activación y open/close comprobados físicamente.",
            "Confirmación explícita del operador; el harness no conecta hardware."),
    "C11": ("Verificar P_PICK/P_HOME y Tool Z -40 mm en PolyScope.",
            "Confirmar ensayo manual PICK + close + retract con agarre real.",
            "Evidencia manual registrada; no existe comando PICK separado."),
    "C12": ("Mode2, seis Assignments, C8–C11 verificados y parada disponible; --allow-motion.",
            "Autorizar COMMAND5 y observar pick → place CELL5 → HOME.",
            "Handshake completo y confirmación de ficha en CELL5 y retorno HOME."),
    "C13": ("Mismos requisitos de C12; celda libre y ficha disponible en PICK antes de cada ciclo.",
            "Probar 1,3,7,9 y después 2,4,6,8, con autorización individual.",
            "Confirmar cada ficha y retorno HOME; no encadenar sin operador."),
    "C14": ("Confirmar evidencia C1–C13, tablero vacío estable y cliente Modbus exclusivo.",
            "Registrar precondiciones; el harness no ejecuta una partida.",
            "Aceptación runtime/visión/juego pendiente de adaptación separada."),
}


def procedure(step):
    number = int(step[1:])
    risk = ("SIN MOVIMIENTO" if number <= 6 else "HANDSHAKE SIN MOVIMIENTO ESPERADO"
            if number == 7 else "MOVIMIENTO FÍSICO" if number in (8, 9, 12, 13)
            else "EVIDENCIA MANUAL / SIN I/O" if number in (10, 11) else "PRECONDICIONES / PENDIENTE")
    preparation, observe, criterion = PROCEDURES.get(step, (
        "No habilitado en el harness actual. Robotiq requiere modelo, URCap y adaptador validados.",
        "No ejecutar este paso; revisar los prerrequisitos pendientes.",
        "Sin procedimiento ejecutable ni vía para habilitarlo mediante un flag.",
    ))
    return {"Objetivo": STEPS[step], "Preparación": preparation,
            "Qué observar": observe, "Criterio general": criterion, "Nivel de riesgo": risk}


PROBLEMS = ("Cámara no disponible", "Faltan marcadores", "Tablero incierto", "Reflejos",
            "Robot no configurado", "Robot no conecta", "No puedo iniciar partida")


def problem_guidance(problem, snapshot, diagnostic):
    missing = ", ".join(str(i) for i in range(10, 19) if i not in diagnostic.visible_ids) or "Ninguno"
    choices = {
        PROBLEMS[0]: (f"Cámara: {snapshot.camera_status}", "Verificar USB; cerrar otras apps; detectar cámaras; "
                      "seleccionar índice/backend y probar reconectar. La C920 puede tardar 50–60 s."),
        PROBLEMS[1]: (f"IDs faltantes: {missing}", "Revisar encuadre de IDs 10–18, retirar manos y reducir reflejos. "
                      "Esperar estabilización; un ID ausente no implica ocupación instantánea."),
        PROBLEMS[2]: (f"Tablero: {snapshot.board_status}", "Retirar manos, verificar el tablero y esperar estabilización. "
                      "Entre partidas puede reiniciar observación desde Diagnóstico."),
        PROBLEMS[3]: (f"Iluminación: {diagnostic.illumination}", "Reducir luz directa/reflejos y revisar IDs. Probar "
                      "Reflejos en SISTEMA REAL si hace falta. El indicador es orientativo, no de seguridad."),
        PROBLEMS[4]: (f"Robot: {snapshot.robot_status}", "Configurar el host real localmente, conectar Ethernet y "
                      "verificar subred. Consultar Red y robot y commissioning C6."),
        PROBLEMS[5]: (f"Robot: {snapshot.robot_status}", "Revisar cable Ethernet, host local, misma subred y puerto "
                      "Modbus 502. Usar C6 desde el harness; no escribir COMMAND para diagnosticar red."),
        PROBLEMS[6]: (f"Cámara: {snapshot.camera_status} · Robot: {snapshot.robot_status} · Tablero: {snapshot.board_status}",
                      "Revisar CÁMARA / DIAGNÓSTICO: cámara y robot conectados, tablero vacío y estable. "
                      "Consultar los códigos internos en Detalle técnico."),
    }
    return choices[problem]
