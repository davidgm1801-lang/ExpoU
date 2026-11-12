"""
==================================================================
CONFIGURACION CENTRALIZADA DE SEMAFOROS - ExpoU
==================================================================

Un unico lugar que define:
  - SEMAFOROS       : los cruces controlados y sus carriles por grupo.
  - VECINO_DESTINO  : topologia de vecindad (que grupo alimenta a que vecino).

Objetivo: ESCALAR el sistema sin tocar la logica de los scripts. Para
controlar mas (o menos) intersecciones basta editar este archivo; los
entrenadores y evaluadores lo importan.

Por que ESTOS 6 semaforos (y no 10)
-----------------------------------
La red tiene 19 semaforos; 9 son de 4 fases (compatibles). Un primer
intento con 10 semaforos NO mejoro el trafico: 4 de los nuevos estaban
TOPOLOGICAMENTE AISLADOS (no comparten trafico con ningun otro cruce
controlado), asi que no podian coordinarse y actuaban como agentes
locales (inestables, segun la Etapa 3).

El analisis de conectividad de la red mostro que los semaforos de 4
fases forman DOS corredores reales:

  Corredor 1 (confluencia):  262567760 --\\
                                          >--> 262567775
                             262567777 --/

  Corredor 2 (cadena):  264377450 --> 265804326 --> cluster_7792538741_7792538742

Esta configuracion incluye exactamente esos 6 cruces: los 5 originales
+ 'cluster_7792538741_7792538742', que PROLONGA el Corredor 2. Todos
tienen vecindad real, que es la condicion para que la coordinacion
aporte valor (leccion de la Etapa 4 y del intento fallido de 10).

Carriles por grupo
------------------
Grupo A = movimientos con verde en la fase 0 (GGG...).
Grupo B = movimientos con verde en la fase 2 (...GGG).
Para el nuevo se incluyen todos los carriles de entrada del grupo.
==================================================================
"""

# ==================================================
# SEMAFOROS CONTROLADOS Y SUS CARRILES
# ==================================================

SEMAFOROS = {
    # ---- Corredor 1: confluencia hacia 262567775 ----
    "262567760": {
        "A": ["1083001223#0_0", "1083001223#0_1"],
        "B": ["862794316#0_0", "862794316#0_1"],
    },
    "262567777": {
        "A": ["1060493360#3_1", "1060493360#3_2"],
        "B": ["908369205#0_0", "908369205#0_1"],
    },
    "262567775": {
        "A": ["88757025#0_0", "88757025#0_1"],
        "B": ["1083001225#0_1", "1083001225#0_2"],
    },
    # ---- Corredor 2: cadena 264377450 -> 265804326 -> 7792538741/42 ----
    "264377450": {
        "A": ["1083001233_0", "1083001233_1"],
        "B": ["1056806207#0_0", "1056806207#0_1"],
    },
    "265804326": {
        "A": ["88877450#2_0", "88877450#2_1"],
        "B": ["1083001234#0_0", "1083001234#0_1"],
    },
    "cluster_7792538741_7792538742": {
        "A": ["242708697#0_0", "242708699#0_0"],
        "B": ["66953367#0_0", "66953367#0_1"],
    },
}


# ==================================================
# TOPOLOGIA DE VECINDAD
# ==================================================
# origen (grupo) -> (vecino, grupo del vecino). Derivada de las
# conexiones de la red (relacion dominante por numero de links).
#
#   Corredor 1:  262567760 (A) --> 262567775
#                262567777 (B) --> 262567775
#   Corredor 2:  264377450 (B) --> 265804326
#                265804326 (A) --> cluster_7792538741_7792538742
#
# Todos los cruces de esta configuracion participan en al menos una
# relacion de vecindad (como origen o destino): no hay agentes aislados.

VECINO_DESTINO = {
    "262567760": {"A": ("262567775", "A")},
    "262567777": {"B": ("262567775", "B")},
    "264377450": {"B": ("265804326", "B")},
    "265804326": {"A": ("cluster_7792538741_7792538742", "B")},
}


# Archivos de modelo por version, derivados del conjunto SEMAFOROS.
def archivos_modelo(prefijo):
    """Devuelve {tls_id: 'prefijo<id>.pkl'} para el conjunto actual."""
    return {tls_id: f"{prefijo}{tls_id}.pkl" for tls_id in SEMAFOROS}
