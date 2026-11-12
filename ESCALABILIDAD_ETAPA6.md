# Etapa 6 — Escalabilidad y corredores (ExpoU)

## Motivación

La Etapa 3 mostró que el cuello de botella es la **red no controlada**. La
Etapa 4 mostró que la **coordinación** entre vecinos estabiliza y mejora. La idea
natural fue: controlar más intersecciones, coordinadas.

## Intento 1 — 10 semáforos "en crudo" (NO funcionó, y por qué)

Se añadieron 5 semáforos nuevos de 4 fases a los 5 originales. Resultado de la
evaluación (10 vs baseline): **empate/mixto**, muy por debajo del resultado de 5
coordinados (que ganaba 5/5 en completados y teleports).

**Diagnóstico con datos:** al analizar la conectividad de la red, 4 de los 5
semáforos nuevos están **topológicamente aislados** — no comparten tráfico con
ningún otro cruce controlado. Es decir, no pueden coordinarse y actúan como
agentes locales (inestables, Etapa 3). Escalamos la *cantidad* de agentes pero no
la *coordinación*.

**Lección:** lo que mejora el tráfico no es "más semáforos con IA", sino
semáforos con IA **bien conectados y coordinados**. Cobertura sin coordinación
no basta.

## Estructura real de la red

El análisis de conectividad de los 9 semáforos de 4 fases reveló **dos corredores
reales** y 4 cruces aislados:

```
Corredor 1 (confluencia):  262567760 --\
                                        >--> 262567775
                           262567777 --/

Corredor 2 (cadena):  264377450 --> 265804326 --> cluster_7792538741_7792538742

Aislados (sin conexion compatible): 317470710, GS_cluster_..096_097,
                                     cluster_261757164_..., cluster_265804323_...
```

## Intento 2 — 6 semáforos conectados (configuración actual)

`config_semaforos.py` define ahora **6 cruces**: los 5 originales +
`cluster_7792538741_7792538742` (único nuevo que **prolonga** un corredor, el 2).
**Todos tienen vecindad real** → todos pueden coordinar. Topología:

```
262567760 (A) --> 262567775
262567777 (B) --> 262567775
264377450 (B) --> 265804326
265804326 (A) --> cluster_7792538741_7792538742
```

Esta es la configuración correcta para demostrar que la coordinación **escala**
cuando se respeta la estructura de corredores.

## Flujo de ejecución (tu Windows, .venv activo)

```powershell
# 0) VALIDAR los 6 semaforos y sus carriles
python .\validar_config.py

# 1) ENTRENAR los 6 coordinados (prefijo propio para no pisar los de 5)
$env:PREFIJO_COORD="q_table_coord6_"; python .\train_coordinado.py

# 2) EVALUAR los 6 vs baseline (mismas 5 semillas)
$env:PREFIJO_COORD="q_table_coord6_"; python .\evaluar_coordinado.py
```

Genera `evaluacion_q_table_coord6.csv`.

## Cómo interpretar

- Si los 6 coordinados **superan al baseline de forma consistente** (par-a-par),
  se confirma que la coordinación escala al prolongar un corredor real.
- Comparar contra los 5 coordinados de la Etapa 4: el 6º agente debería ayudar al
  Corredor 2 (264377450 → 265804326 → nuevo), que incluye la intersección más
  congestionada (264377450).

## Límites honestos

- `cluster_7792538741_7792538742` agrupa pocos carriles; su cola es modesta.
- La red solo ofrece 2 corredores compatibles; para controlar más habría que
  incluir semáforos de otras estructuras de fase (más de 2 grupos), lo que
  requiere extender la arquitectura del agente — trabajo futuro.
- Los 4 semáforos aislados quedan fuera a propósito: añadirlos sin coordinación
  empeora el conjunto (Intento 1).
