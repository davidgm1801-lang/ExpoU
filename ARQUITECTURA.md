# ExpoU — Arquitectura y objetivo del sistema

## Objetivo general

Construir un **sistema de IA multiagente** que **optimice el tráfico urbano** de
una red real de Bogotá (modelada en SUMO), controlando semáforos de forma
adaptativa, y demostrar —con evaluación rigurosa— que **mejora de forma
consistente** frente al control de tiempo fijo de SUMO.

## Qué nos enseñaron las etapas (y por qué el diseño es este)

| Etapa | Resultado | Consecuencia de diseño |
|---|---|---|
| 1. Diagnóstico | 264377450 está saturada; carriles de los 5 agentes verificados | Las diferencias entre agentes son por demanda, no por fallos |
| 2. Evaluación | La IA local es **inestable**: gana en 3/5 semillas, colapsa en 2/5 | El problema no es el nivel medio, es la varianza |
| 3A. Causa raíz | El colapso ocurre en la **red NO controlada**, disperso | Afinar agentes locales rinde poco a nivel global |
| 3B. Experimento | Estado más fino (5 niveles) **no** corrigió la inestabilidad | Confirma: el cuello de botella es estructural, no local |
| **4. Coordinación** | (en evaluación) agentes que observan a sus vecinos | Atacar el efecto de red: no inundar vecinos saturados |

**Conclusión que guía el proyecto:** cinco agentes locales aislados no bastan.
El valor está en **coordinar** (Etapa 4) y **escalar** (Etapa 6). Este repo ya
implementa la coordinación como primer paso hacia el sistema multiagente.

## Arquitectura (tres niveles del documento original)

```
Nivel 3  COORDINADOR CENTRAL         (futuro: objetivos de red)
            |
Nivel 2  COMUNICACION ENTRE AGENTES  <-- Etapa 4 (IMPLEMENTADO aqui)
            |
Nivel 1  AGENTES LOCALES Q-LEARNING  <-- Etapas 1-3 (base)
```

### Nivel 1 — Agente local (`agents/sumo_q_learning.py`)
- Estado: `(cola_A, cola_B, grupo_verde)`; colas discretizadas (umbrales
  configurables; por defecto 3 niveles).
- Acciones: mantener verde / pedir cambio. Q-Learning tabular, epsilon-greedy.

### Nivel 2 — Agente coordinado (`agents/coordinated_agent.py`)
- Extiende el estado con **`presion_vecino`**: ¿el vecino hacia el que apunta el
  grupo verde está congestionado?
- Estado: `(cola_A, cola_B, grupo_verde, presion_vecino)` → 3×3×2×2 = 36 estados.
- La recompensa penaliza servir verde hacia un vecino saturado (ver
  `train_coordinado.py`). Objetivo: no propagar atascos aguas abajo.

**Topología de vecindad** (derivada de `getControlledLinks`, Etapa 1):
```
262567760 (grupo A) --> 262567775
262567777 (grupo A) --> 262567775
264377450 (grupo B) --> 265804326
```

## Mapa de archivos

### Base (Nivel 1)
- `agents/sumo_q_learning.py` — agente local.
- `train_sumo_5.py` — entrena 5 agentes locales (v1).
- `train_sumo_5_v2.py` — variante v2 (estado de 5 niveles, Etapa 3B).

### Coordinación (Nivel 2)
- `agents/coordinated_agent.py` — agente con presión de vecino.
- `train_coordinado.py` — entrena los 5 agentes coordinados.
- `evaluar_coordinado.py` — evalúa coordinado vs baseline (5 semillas).

### Evaluación y diagnóstico
- `evaluar_etapa2.py` — evalúa baseline vs IA (v1/v2) con métricas rigurosas.
- `diagnostico_trafico_5.py` — demanda por intersección (control original).
- `localizar_teleports.py`, `ranking_bordes_teleports.py` — localizan teleports.
- `comparar_resultados.py` — unifica los CSV de evaluación en una tabla.

### Informes (evidencia)
- `DIAGNOSTICO_ETAPA1.md`, `EVALUACION_ETAPA2.md`, `ETAPA3_CAUSA_RAIZ.md`.

## Flujo de trabajo reproducible

```powershell
# (1) Entrenar coordinado (60 episodios por defecto; parametrizable)
python .\train_coordinado.py

# (2) Evaluar coordinado vs baseline (5 semillas emparejadas)
python .\evaluar_coordinado.py

# (3) Comparar las tres configuraciones en una tabla
python .\comparar_resultados.py
```

## Metodología de evaluación (resumen)
- 5 semillas emparejadas (42-46); mismo tráfico para baseline e IA.
- Métricas de `tripinfos.xml` (completados, espera, duración, time loss,
  velocidad) y `stats.xml` (teleports con desglose, colisiones).
- **Los teleports se reportan siempre** como limitación conocida de SUMO.
- Comparación par-a-par por semilla (no solo promedios).

## Próximos pasos
- Nivel 3 (coordinador central) y escalabilidad (más intersecciones).
- Integración de visión (YOLO) para conteos reales — fase futura.
