"""
==================================================================
AUTODETECTOR DE SEMAFOROS - Sistema de 19 intersecciones (ExpoU)
==================================================================

Genera automaticamente la configuracion de TODOS los semaforos de la
red (sus fases verdes y los carriles de entrada de cada una), sin que
haya que escribir nada a mano. Asi el sistema cubre las 19
intersecciones aunque tengan distinto numero de grupos (1, 2 o 3+).

Como funciona
-------------
Se conecta a SUMO una vez (solo lectura) y para cada semaforo:
  1. Lee su programa y sus fases.
  2. Identifica las FASES VERDES: las que tienen 'G'/'g' y NO son
     amarillas (no contienen 'y'). Cada fase verde es un "grupo".
  3. Para cada fase verde, obtiene los carriles de ENTRADA reales
     (de getControlledLinks), descartando carriles internos (':').
  4. Guarda todo en 'config_auto_semaforos.json'.

El resultado lo consumen el entrenador y el evaluador genericos.

Robustez
--------
- Semaforos sin fases verdes utiles se descartan (se informan).
- Carriles internos y duplicados se filtran.
- No modifica la red ni ningun modelo.

Ejecutar (Windows, .venv activo, dentro de ExpoU):
    python .\\autodetectar_semaforos.py
==================================================================
"""

import json
import traci
import sumolib


CONFIG = "sumo_bogota/osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")
ARCHIVO_SALIDA = "config_auto_semaforos.json"


def es_fase_verde(estado):
    # Verde si tiene G/g y no es una fase de transicion (amarillo).
    return ("G" in estado or "g" in estado) and ("y" not in estado.lower())


def detectar():
    print("=" * 64)
    print("AUTODETECCION DE SEMAFOROS DE LA RED")
    print("=" * 64)

    traci.start([SUMO, "-c", CONFIG, "--no-step-log", "true"])

    config = {}
    descartados = []

    try:
        carriles_red = set(traci.lane.getIDList())
        tls_ids = traci.trafficlight.getIDList()
        print(f"Semaforos en la red: {len(tls_ids)}\n")

        for tls_id in tls_ids:
            programa = traci.trafficlight.getProgram(tls_id)
            logica = None
            for p in traci.trafficlight.getAllProgramLogics(tls_id):
                if p.programID == programa:
                    logica = p
                    break
            if logica is None:
                descartados.append((tls_id, "sin logica"))
                continue

            fases = logica.phases

            # Enlaces controlados: indice de senal -> lista de (entrada, salida, via)
            enlaces = traci.trafficlight.getControlledLinks(tls_id)

            grupos = []  # cada grupo: {"fase": i, "carriles": [...], "salidas": [...]}
            for i, fase in enumerate(fases):
                if not es_fase_verde(fase.state):
                    continue
                carriles = set()
                salidas = set()  # edges hacia los que vierte este grupo
                for idx, ch in enumerate(fase.state):
                    if ch in "Gg" and idx < len(enlaces):
                        for conexion in enlaces[idx]:
                            entrada = conexion[0]
                            salida = conexion[1]
                            # descartar carriles internos de interseccion
                            if entrada and not entrada.startswith(":"):
                                if entrada in carriles_red:
                                    carriles.add(entrada)
                            # edge de salida (sin el sufijo _carril)
                            if salida and not salida.startswith(":"):
                                salidas.add(salida.rsplit("_", 1)[0])
                if carriles:
                    grupos.append({
                        "fase": i,
                        "carriles": sorted(carriles),
                        "salidas": sorted(salidas),
                    })

            # Necesitamos al menos 2 grupos verdes para que el agente
            # tenga una decision real (servir uno u otro). Con 1 grupo
            # no hay nada que optimizar.
            if len(grupos) < 2:
                descartados.append(
                    (tls_id, f"{len(grupos)} grupo(s) verde(s) util(es)")
                )
                continue

            config[tls_id] = {
                "n_fases": len(fases),
                "grupos": grupos,
            }
            print(f"  {tls_id[:42]:<44} {len(grupos)} grupos, "
                  f"{len(fases)} fases")

    finally:
        traci.close()

    # ==================================================
    # CALCULAR VECINDAD (para coordinacion)
    # ==================================================
    # Para cada grupo de cada semaforo, ver si sus 'salidas' coinciden
    # con los carriles de ENTRADA de otro semaforo controlado. Si es
    # asi, ese grupo "alimenta" a ese vecino.
    #
    # edge de entrada -> tls que lo controla
    edge_entrada_de = {}
    for tid, datos in config.items():
        for g in datos["grupos"]:
            for carril in g["carriles"]:
                edge_entrada_de[carril.rsplit("_", 1)[0]] = tid

    n_relaciones = 0
    for tid, datos in config.items():
        for g in datos["grupos"]:
            vecinos = set()
            for edge_salida in g["salidas"]:
                vecino = edge_entrada_de.get(edge_salida)
                if vecino is not None and vecino != tid:
                    vecinos.add(vecino)
            # Guardar el vecino principal del grupo (si hay). Si vierte a
            # varios, se guarda el primero de forma estable; la senal de
            # coordinacion solo necesita "hay un vecino que puede saturarse".
            g["vecino"] = sorted(vecinos)[0] if vecinos else None
            if g["vecino"]:
                n_relaciones += 1
            # 'salidas' ya no se necesita en el JSON final
            del g["salidas"]

    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 64)
    print(f"Semaforos CONTROLABLES detectados: {len(config)}")
    print(f"Relaciones de vecindad detectadas (grupos con vecino): {n_relaciones}")
    print(f"Guardado en: {ARCHIVO_SALIDA}")
    if descartados:
        print(f"\nDescartados ({len(descartados)}):")
        for tid, motivo in descartados:
            print(f"  - {tid[:42]:<44} ({motivo})")
    print("=" * 64)
    print("\nAhora puedes entrenar con:  python .\\train_generico.py")


if __name__ == "__main__":
    detectar()
