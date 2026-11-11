"""
==================================================================
COMPARAR RESULTADOS - ExpoU
==================================================================

Unifica los CSV de evaluacion existentes en una sola tabla para
comparar las configuraciones de un vistazo:

  - evaluacion_etapa2.csv       -> IA v1 (local, 3 niveles)
  - evaluacion_etapa2_v2.csv    -> IA v2 (local, 5 niveles)
  - evaluacion_coordinado.csv   -> IA coordinada (Etapa 4)

Cada CSV incluye su propio brazo 'baseline'. Como el baseline se corre
con las mismas semillas, debe ser muy parecido entre archivos; se
muestra el baseline de cada archivo para transparencia.

Hace dos cosas:
  1. Promedios por metrica para cada configuracion (baseline vs IA).
  2. Analisis par-a-par: en cuantas de las 5 semillas la IA supera al
     baseline (consistencia), que es lo que de verdad importa segun la
     Etapa 2.

Solo usa el modulo estandar csv (Pandas da problemas en este Windows).
No requiere SUMO; solo lee CSVs ya generados.

    python .\\comparar_resultados.py
==================================================================
"""

import os
import csv


ARCHIVOS = {
    "IA v1 (local, 3 niveles)": "evaluacion_etapa2.csv",
    "IA v2 (local, 5 niveles)": "evaluacion_etapa2_v2.csv",
    "IA coordinada (Etapa 4)": "evaluacion_coordinado.csv",
}

# Metricas a resumir: (columna, etiqueta, "mas" o "menos" = mejor)
METRICAS = [
    ("completados", "Completados", "mas"),
    ("espera_promedio", "Espera (s)", "menos"),
    ("duracion_promedio", "Duracion (s)", "menos"),
    ("timeloss_promedio", "Time loss (s)", "menos"),
    ("velocidad_promedio", "Velocidad (m/s)", "mas"),
    ("cola_promedio_suma_5tls", "Cola prom.", "menos"),
    ("teleports_total", "Teleports", "menos"),
    ("colisiones", "Colisiones", "menos"),
]


def leer_csv(ruta):
    with open(ruta, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def promedio(filas, columna):
    vals = [float(f[columna]) for f in filas if f.get(columna) not in (None, "")]
    return sum(vals) / len(vals) if vals else 0.0


def analizar(nombre, ruta):
    if not os.path.exists(ruta):
        print(f"\n[ {nombre} ]  (sin datos: falta {ruta})")
        return

    filas = leer_csv(ruta)
    base = [f for f in filas if f["brazo"] == "baseline"]
    ia = [f for f in filas if f["brazo"] == "ia"]

    print("\n" + "=" * 66)
    print(f"  {nombre}   ({ruta})")
    print("=" * 66)
    print(f"{'Metrica':<18}{'Baseline':>11}{'IA':>11}{'Delta':>11}  Mejor?")
    print("-" * 66)

    for col, etiqueta, sentido in METRICAS:
        b = promedio(base, col)
        i = promedio(ia, col)
        delta = i - b
        if sentido == "mas":
            mejor = "IA" if i > b else ("=" if i == b else "base")
        else:
            mejor = "IA" if i < b else ("=" if i == b else "base")
        print(f"{etiqueta:<18}{b:>11.3f}{i:>11.3f}{delta:>+11.3f}  {mejor}")

    # Consistencia par-a-par por semilla.
    print("\n  Consistencia par-a-par (semillas donde la IA supera al baseline):")
    semillas = sorted({f["semilla"] for f in filas})
    for col, etiqueta, sentido in METRICAS:
        gana = 0
        total = 0
        for s in semillas:
            fb = next((f for f in base if f["semilla"] == s), None)
            fi = next((f for f in ia if f["semilla"] == s), None)
            if not fb or not fi:
                continue
            total += 1
            b = float(fb[col]); i = float(fi[col])
            if sentido == "mas" and i > b:
                gana += 1
            elif sentido == "menos" and i < b:
                gana += 1
        print(f"    {etiqueta:<18} IA gana en {gana}/{total} semillas")


def main():
    print("=" * 66)
    print("COMPARACION DE CONFIGURACIONES - ExpoU")
    print("=" * 66)
    print("Recordatorio: comparar par-a-par (consistencia) importa mas que el")
    print("promedio; y los teleports son una limitacion de SUMO a vigilar.")

    hay_algo = False
    for nombre, ruta in ARCHIVOS.items():
        if os.path.exists(ruta):
            hay_algo = True
        analizar(nombre, ruta)

    if not hay_algo:
        print(
            "\nNo se encontro ningun CSV de evaluacion. Ejecuta primero:"
            "\n  python .\\evaluar_etapa2.py            (IA v1)"
            "\n  $env:VERSION_MODELO='v2'; python .\\evaluar_etapa2.py  (IA v2)"
            "\n  python .\\evaluar_coordinado.py        (IA coordinada)"
        )


if __name__ == "__main__":
    main()
