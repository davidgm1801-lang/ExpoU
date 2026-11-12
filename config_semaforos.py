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

Como se eligieron los semaforos
--------------------------------
La red de Bogota tiene 19 semaforos; 9 tienen la estructura de 4 fases
(GGG/yyy alternas) que nuestros agentes saben controlar. Este archivo
incluye 10 cruces (los 5 originales validados en la Etapa 1 + 5 nuevos
de 4 fases, cuyos carriles de entrada se extrajeron de la red).

Los 5 nuevos se eligieron por conectar con el corredor existente y/o
con las zonas donde la Etapa 3 detecto mas teleports, para reducir la
"red no controlada".

Carriles por grupo
------------------
Grupo A = movimientos con verde en la fase 0 (GGG...).
Grupo B = movimientos con verde en la fase 2 (...GGG).
Para los 5 nuevos se incluyen TODOS los carriles de entrada del grupo
(la cola del grupo es la suma); esto mide la demanda real del grupo.

Topologia de vecindad
---------------------
Para los 5 originales la vecindad se valido manualmente en la Etapa 1.
Para los nuevos se derivo de las conexiones de la red. La senal de
coordinacion solo necesita saber si un semaforo vierte hacia un vecino
que puede congestionarse; ante ambiguedad se prefiere la relacion mas
clara.
==================================================================
"""

# ==================================================
# SEMAFOROS CONTROLADOS Y SUS CARRILES
# ==================================================

SEMAFOROS = {
    # ---- 5 originales (validados en Etapa 1) ----
    "262567760": {
        "A": ["1083001223#0_0", "1083001223#0_1"],
        "B": ["862794316#0_0", "862794316#0_1"],
    },
    "262567775": {
        "A": ["88757025#0_0", "88757025#0_1"],
        "B": ["1083001225#0_1", "1083001225#0_2"],
    },
    "262567777": {
        "A": ["1060493360#3_1", "1060493360#3_2"],
        "B": ["908369205#0_0", "908369205#0_1"],
    },
    "264377450": {
        "A": ["1083001233_0", "1083001233_1"],
        "B": ["1056806207#0_0", "1056806207#0_1"],
    },
    "265804326": {
        "A": ["88877450#2_0", "88877450#2_1"],
        "B": ["1083001234#0_0", "1083001234#0_1"],
    },
    # ---- 5 nuevos (Etapa 6, extraidos de la red) ----
    "317470710": {
        "A": ["-889995785#3_0", "889995785#0_0"],
        "B": ["88756920#0_0", "88756920#0_1"],
    },
    "GS_cluster_12519565096_12519565097": {
        "A": ["509352045#6_0", "509352046#0_0", "509352046#0_1"],
        "B": ["961101064#0_0", "961101064#0_1", "961101064#0_2"],
    },
    "cluster_261757164_261757167": {
        "A": ["175956267#1_0", "175956267#1_1",
              "672180642#0_0", "672180642#0_1"],
        "B": ["614556639#0_0", "614556639#0_1"],
    },
    "cluster_265804323_265804324": {
        "A": ["24421545#0_0", "24421545#0_1", "24421545#0_2",
              "908692396#0_0", "908692396#0_1", "908692396#0_2"],
        "B": ["24456444#4_0", "24456444#4_1"],
    },
    "cluster_7792538741_7792538742": {
        "A": ["242708697#0_0", "242708699#0_0"],
        "B": ["66953367#0_0", "66953367#0_1"],
    },
}


# ==================================================
# TOPOLOGIA DE VECINDAD
# ==================================================
# Para cada semaforo, por grupo (A/B), a que vecino (y su grupo) alimenta.
# Solo se incluyen relaciones claras hacia otro semaforo controlado.
#
#   262567760 grupo A --> 262567775            (validado Etapa 1)
#   262567777 grupo A --> 262567775            (validado Etapa 1)
#   264377450 grupo B --> 265804326            (validado Etapa 1)
#   265804326 grupo B --> cluster_7792538741_7792538742  (nuevo: via 66953367#0)

VECINO_DESTINO = {
    "262567760": {"A": ("262567775", "A")},
    "262567777": {"A": ("262567775", "B")},
    "264377450": {"B": ("265804326", "B")},
    "265804326": {"B": ("cluster_7792538741_7792538742", "B")},
}


# Archivos de modelo por version, derivados del conjunto SEMAFOROS.
def archivos_modelo(prefijo):
    """Devuelve {tls_id: 'prefijo<id>.pkl'} para el conjunto actual."""
    return {tls_id: f"{prefijo}{tls_id}.pkl" for tls_id in SEMAFOROS}
