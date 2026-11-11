import os
import csv
import matplotlib.pyplot as plt

# Ubicación del archivo CSV
carpeta = os.path.dirname(os.path.abspath(__file__))
archivo = os.path.join(carpeta, "metricas_fijas.csv")

# Listas para almacenar los datos
tiempo = []
vehiculos_activos = []
vehiculos_detenidos = []
espera_acumulada = []
vehiculos_llegados = []

# Leer el CSV sin utilizar Pandas
with open(archivo, "r", encoding="utf-8") as fichero:
    lector = csv.DictReader(fichero)

    for fila in lector:
        tiempo.append(float(fila["tiempo_s"]))
        vehiculos_activos.append(int(fila["vehiculos_activos"]))
        vehiculos_detenidos.append(int(fila["vehiculos_detenidos"]))
        espera_acumulada.append(float(fila["espera_acumulada_s"]))
        vehiculos_llegados.append(int(fila["vehiculos_llegados"]))

# Crear las cuatro gráficas
fig, graficas = plt.subplots(2, 2, figsize=(13, 8))

# Gráfica 1: vehículos activos
graficas[0, 0].plot(tiempo, vehiculos_activos)
graficas[0, 0].set_title("Vehículos activos")
graficas[0, 0].set_xlabel("Tiempo (s)")
graficas[0, 0].set_ylabel("Cantidad")

# Gráfica 2: vehículos detenidos
graficas[0, 1].plot(tiempo, vehiculos_detenidos)
graficas[0, 1].set_title("Vehículos detenidos")
graficas[0, 1].set_xlabel("Tiempo (s)")
graficas[0, 1].set_ylabel("Cantidad")

# Gráfica 3: espera acumulada
graficas[1, 0].plot(tiempo, espera_acumulada)
graficas[1, 0].set_title("Espera acumulada")
graficas[1, 0].set_xlabel("Tiempo (s)")
graficas[1, 0].set_ylabel("Vehículo-segundos")

# Gráfica 4: vehículos llegados
graficas[1, 1].plot(tiempo, vehiculos_llegados)
graficas[1, 1].set_title("Vehículos que han llegado")
graficas[1, 1].set_xlabel("Tiempo (s)")
graficas[1, 1].set_ylabel("Cantidad")

# Ajustar presentación
plt.tight_layout()

# Guardar imagen
salida = os.path.join(carpeta, "graficas_trafico.png")
plt.savefig(salida, dpi=150)

print("Gráficas creadas correctamente.")
print(f"Imagen guardada en: {salida}")

plt.show()

