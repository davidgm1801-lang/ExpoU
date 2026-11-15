"""
Genera graficas para el poster a partir de los datos REALES de
evaluacion_coordinado.csv (5 agentes coordinados vs semaforo fijo).
Produce archivos PNG listos para insertar en el poster.

    python .\\generar_graficas_poster.py
"""

import csv
import matplotlib
matplotlib.use("Agg")  # sin ventana, solo guardar PNG
import matplotlib.pyplot as plt
import numpy as np

filas = list(csv.DictReader(open("evaluacion_coordinado.csv")))
base = [f for f in filas if f["brazo"] == "baseline"]
ia = [f for f in filas if f["brazo"] == "ia"]
semillas = [b["semilla"] for b in base]


def prom(rows, col):
    return sum(float(r[col]) for r in rows) / len(rows)


AZUL = "#4C72B0"   # fijo
VERDE = "#2CA02C"  # IA


# ======================================================
# GRAFICA 1: Barras comparativas de metricas clave (%)
# ======================================================
mets = [
    ("completados", "Vehiculos\ncompletados", "mas"),
    ("espera_promedio", "Espera\npromedio", "menos"),
    ("timeloss_promedio", "Time loss\npromedio", "menos"),
    ("teleports_total", "Teleports\n(atascos)", "menos"),
]
nombres = [m[1] for m in mets]
mejoras = []
for col, _, s in mets:
    b, i = prom(base, col), prom(ia, col)
    mejoras.append((i - b) / b * 100 if s == "mas" else (b - i) / b * 100)

fig, ax = plt.subplots(figsize=(8, 5))
barras = ax.bar(nombres, mejoras, color=VERDE, edgecolor="black")
for bar, v in zip(barras, mejoras):
    ax.text(bar.get_x() + bar.get_width() / 2, v + 0.2,
            f"+{v:.1f}%", ha="center", fontweight="bold", fontsize=12)
ax.set_ylabel("Mejora de la IA frente al semaforo fijo (%)", fontsize=11)
ax.set_title("IA coordinada vs semaforo fijo\n(5 agentes, promedio de 5 escenarios)",
             fontsize=13, fontweight="bold")
ax.set_ylim(0, max(mejoras) * 1.25)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("poster_mejoras.png", dpi=200)
plt.close()
print("Guardado: poster_mejoras.png")


# ======================================================
# GRAFICA 2: Vehiculos completados por semilla (barras pareadas)
# ======================================================
x = np.arange(len(semillas))
w = 0.38
b_comp = [int(r["completados"]) for r in base]
i_comp = [int(r["completados"]) for r in ia]

fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(x - w / 2, b_comp, w, label="Semaforo fijo", color=AZUL, edgecolor="black")
ax.bar(x + w / 2, i_comp, w, label="IA coordinada", color=VERDE, edgecolor="black")
ax.set_xticks(x)
ax.set_xticklabels([f"Esc. {s}" for s in semillas])
ax.set_ylabel("Vehiculos que completan su viaje", fontsize=11)
ax.set_title("Vehiculos completados por escenario de trafico\n"
             "(la IA gana en los 5)", fontsize=13, fontweight="bold")
ax.legend(fontsize=11)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("poster_completados.png", dpi=200)
plt.close()
print("Guardado: poster_completados.png")


# ======================================================
# GRAFICA 3: Teleports (atascos) por semilla
# ======================================================
b_tel = [int(r["teleports_total"]) for r in base]
i_tel = [int(r["teleports_total"]) for r in ia]

fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(x - w / 2, b_tel, w, label="Semaforo fijo", color=AZUL, edgecolor="black")
ax.bar(x + w / 2, i_tel, w, label="IA coordinada", color=VERDE, edgecolor="black")
ax.set_xticks(x)
ax.set_xticklabels([f"Esc. {s}" for s in semillas])
ax.set_ylabel("Teleports (vehiculos atascados)", fontsize=11)
ax.set_title("Atascos por escenario de trafico\n"
             "(menos es mejor; la IA reduce en los 5)",
             fontsize=13, fontweight="bold")
ax.legend(fontsize=11)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("poster_teleports.png", dpi=200)
plt.close()
print("Guardado: poster_teleports.png")

print("\nListo. 3 imagenes PNG generadas para el poster.")
