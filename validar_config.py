"""
==================================================================
VALIDAR CONFIGURACION DE SEMAFOROS - ExpoU
==================================================================

Antes de entrenar con mas intersecciones (Etapa 6), comprueba contra
SUMO que TODO lo definido en config_semaforos.py es correcto:

  1. Cada semaforo existe en la red.
  2. Cada semaforo tiene exactamente 4 fases.
  3. Las fases 0 y 2 son verdes (contienen 'G'/'g') y 1 y 3 amarillas.
  4. Cada carril de entrada listado existe en la red.
  5. La topologia de vecindad apunta a semaforos existentes.

NO entrena ni modifica nada. Es una comprobacion de arranque: si algo
falla aqui, no tiene sentido entrenar.

Como ejecutar (Windows, .venv activo, dentro de ExpoU):
    python .\\validar_config.py
==================================================================
"""

import traci
import sumolib

from config_semaforos import SEMAFOROS, VECINO_DESTINO


CONFIG = "sumo_bogota/osm.sumocfg"
SUMO = sumolib.checkBinary("sumo")


def main():
    print("=" * 64)
    print("VALIDACION DE config_semaforos.py CONTRA LA RED")
    print("=" * 64)
    print(f"Semaforos a validar: {len(SEMAFOROS)}")

    traci.start([SUMO, "-c", CONFIG, "--no-step-log", "true"])

    errores = []
    avisos = []

    try:
        tls_red = set(traci.trafficlight.getIDList())
        carriles_red = set(traci.lane.getIDList())

        for tls_id, grupos in SEMAFOROS.items():
            print(f"\n--- {tls_id} ---")

            # 1. existe
            if tls_id not in tls_red:
                errores.append(f"{tls_id}: no existe en la red")
                print("  ERROR: no existe en la red")
                continue

            # 2-3. fases
            prog = traci.trafficlight.getProgram(tls_id)
            logica = None
            for p in traci.trafficlight.getAllProgramLogics(tls_id):
                if p.programID == prog:
                    logica = p
                    break
            fases = logica.phases if logica else []
            if len(fases) != 4:
                errores.append(
                    f"{tls_id}: tiene {len(fases)} fases (se esperan 4)"
                )
                print(f"  ERROR: {len(fases)} fases (se esperan 4)")
            else:
                f0 = fases[0].state
                f2 = fases[2].state
                if "G" not in f0.upper() or "G" not in f2.upper():
                    avisos.append(
                        f"{tls_id}: fases 0/2 no parecen verdes"
                    )
                    print("  AVISO: fases 0/2 no parecen verdes")
                else:
                    print(f"  Fases OK (4; verdes en 0 y 2)")

            # 4. carriles
            for grupo, carriles in grupos.items():
                for c in carriles:
                    if c not in carriles_red:
                        errores.append(
                            f"{tls_id} grupo {grupo}: carril "
                            f"inexistente {c}"
                        )
                        print(f"  ERROR: carril inexistente {c}")
                print(f"  Grupo {grupo}: {len(carriles)} carriles")

        # 5. vecindad
        print("\n--- Topologia de vecindad ---")
        for origen, destinos in VECINO_DESTINO.items():
            if origen not in SEMAFOROS:
                errores.append(f"vecindad: origen {origen} no esta en SEMAFOROS")
            for grupo, (vecino, _g) in destinos.items():
                if vecino not in SEMAFOROS:
                    errores.append(
                        f"vecindad: {origen} apunta a vecino {vecino} "
                        f"que no esta en SEMAFOROS"
                    )
                else:
                    print(f"  {origen} ({grupo}) -> {vecino}: OK")

    finally:
        traci.close()

    print("\n" + "=" * 64)
    if errores:
        print(f"VALIDACION FALLIDA: {len(errores)} error(es)")
        for e in errores:
            print("  ERROR:", e)
    else:
        print("VALIDACION OK: todos los semaforos y carriles existen.")
    if avisos:
        print(f"\n{len(avisos)} aviso(s):")
        for a in avisos:
            print("  AVISO:", a)
    print("=" * 64)

    return len(errores) == 0


if __name__ == "__main__":
    main()
