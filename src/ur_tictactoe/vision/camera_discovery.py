from __future__ import annotations

import json
import platform
import subprocess

import cv2

from ur_tictactoe.config import CAMERA_BACKENDS


def _windows_capture_devices() -> list[dict[str, str]]:
    command = (
        "Get-PnpDevice -PresentOnly -ErrorAction Stop | "
        "Where-Object { $_.Class -in @('Camera','Image') -or "
        "($_.Class -eq 'MEDIA' -and "
        "$_.FriendlyName -match 'Camera|Webcam|Logitech|C920') } | "
        "Select-Object Class,FriendlyName,InstanceId | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        if not result.stdout.strip():
            return []
        devices = json.loads(result.stdout)
        return devices if isinstance(devices, list) else [devices]
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []


def _print_windows_devices() -> None:
    print("Windows capture devices")
    print("-----------------------")
    devices = _windows_capture_devices()
    if not devices:
        print("PnP camera information unavailable; continuing with OpenCV probe.")
    for device in devices:
        print(f"{device.get('Class', '?'):<7}: {device.get('FriendlyName', '?')}")


def _probe_combination(index: int, backend_id: int) -> str:
    capture = cv2.VideoCapture(index, backend_id)
    try:
        if not capture.isOpened():
            return f"index {index:<3} CLOSED"
        frame_ok, frame = capture.read()
        width = round(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_text = "yes" if frame_ok and frame is not None else "no"
        return (
            f"index {index:<3} OPEN    frame={frame_text:<3}   "
            f"{width}x{height} @ {fps:g}"
        )
    finally:
        capture.release()


def run_camera_discovery() -> int:
    if platform.system() == "Windows":
        _print_windows_devices()
        print()

    print("OpenCV capture probe")
    print("--------------------")
    for backend_name, backend_id in CAMERA_BACKENDS.items():
        print(f"\n{backend_name}")
        for index in range(6):
            try:
                print(_probe_combination(index, backend_id))
            except cv2.error as exc:
                print(f"index {index:<3} ERROR   {exc}")
    return 0
