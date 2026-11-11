import gzip
import xml.etree.ElementTree as ET

archivo = "osm.net.xml.gz"

with gzip.open(archivo, "rb") as f:
    arbol = ET.parse(f)

raiz = arbol.getroot()

# Nodos identificados como semáforos
nodos = [
    nodo for nodo in raiz.findall("junction")
    if nodo.get("type") == "traffic_light"
]

# Controladores de semáforos
controladores = raiz.findall("tlLogic")

print("\n======= AUDITORÍA DE SEMÁFOROS =======")

print(f"Nodos físicos tipo traffic_light: {len(nodos)}")
print(f"Controladores SUMO (tlLogic): {len(controladores)}")

print("\nNODOS IDENTIFICADOS:")
for nodo in nodos:
    print(
        f"ID: {nodo.get('id')} | "
        f"X: {nodo.get('x')} | "
        f"Y: {nodo.get('y')}"
    )

print("\nAUDITORÍA FINALIZADA")