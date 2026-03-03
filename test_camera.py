#!/usr/bin/env python3
"""
Script de diagnóstico mínimo para probar la cámara en macOS.

Abre la cámara SIN forzar resolución ni FPS, muestra lo que la cámara
realmente entrega, y reporta estadísticas frame a frame.

Uso:
    python test_camera.py

Presiona 'q' para salir.
"""

import platform
import time
import cv2
import numpy as np

IS_MACOS = platform.system() == "Darwin"
print(f"Sistema: {platform.system()} | macOS: {IS_MACOS}")
print(f"OpenCV: {cv2.__version__}")
print(f"Backends disponibles: {[cv2.videoio_registry.getBackendName(b) for b in cv2.videoio_registry.getBackends()]}")
print()

# ── Abrir cámara ──
print("Abriendo cámara...")
if IS_MACOS:
    cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
    print("  Backend: CAP_AVFOUNDATION")
else:
    cap = cv2.VideoCapture(0)
    print("  Backend: auto")

if not cap.isOpened():
    print("ERROR: No se pudo abrir la cámara.")
    print("Verifica permisos en Ajustes del Sistema > Privacidad > Cámara")
    exit(1)

# ── NO forzar resolución — leer lo que la cámara da nativamente ──
native_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
native_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
native_fps = cap.get(cv2.CAP_PROP_FPS)
buf_size = cap.get(cv2.CAP_PROP_BUFFERSIZE)

print(f"  Resolución nativa: {native_w}x{native_h}")
print(f"  FPS nativo: {native_fps}")
print(f"  Buffer size: {buf_size}")
print()

# ── Warmup: leer frames y reportar ──
print("Warmup: leyendo primeros 30 frames...")
warmup_start = time.time()

for i in range(30):
    ret, frame = cap.read()
    if ret and frame is not None:
        mean_val = np.mean(frame)
        is_black = mean_val < 5.0
        status = "NEGRO" if is_black else "OK"
        print(f"  Frame {i+1:02d}: ret={ret} | shape={frame.shape} | mean={mean_val:.1f} | {status}")
    else:
        print(f"  Frame {i+1:02d}: ret={ret} | FALLO")
    time.sleep(0.033)  # ~30 FPS

warmup_time = time.time() - warmup_start
print(f"\nWarmup completado en {warmup_time:.2f}s")
print()

# ── Loop principal con ventana ──
print("Mostrando video en ventana... Presiona 'q' para salir.")
frame_count = 0
fail_count = 0
black_count = 0
start_time = time.time()

try:
    while True:
        ret, frame = cap.read()

        if not ret:
            fail_count += 1
            if fail_count > 30:
                print(f"\nDemasiados fallos consecutivos ({fail_count}). Saliendo.")
                break
            continue

        fail_count = 0  # Reset
        frame_count += 1

        # Detectar frame negro
        mean_val = np.mean(frame)
        if mean_val < 5.0:
            black_count += 1

        # Overlay info
        elapsed = time.time() - start_time
        fps = frame_count / max(elapsed, 0.001)
        info = f"FPS: {fps:.1f} | Frames: {frame_count} | Negros: {black_count} | Fallos: {fail_count}"
        cv2.putText(frame, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.imshow("Test Camera - Press 'q' to quit", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    print("\nInterrumpido por el usuario.")

# ── Estadísticas finales ──
elapsed = time.time() - start_time
print(f"\n{'='*50}")
print(f"Estadísticas finales:")
print(f"  Duración: {elapsed:.1f}s")
print(f"  Frames exitosos: {frame_count}")
print(f"  Frames negros: {black_count}")
print(f"  FPS promedio: {frame_count / max(elapsed, 1):.1f}")
print(f"{'='*50}")

cap.release()
cv2.destroyAllWindows()
print("Cámara cerrada.")
