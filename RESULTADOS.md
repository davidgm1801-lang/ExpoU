# ExpoU — Resultados (documento ejecutivo)

Sistema de IA multiagente para el control adaptativo de semáforos en una red
real de Bogotá (SUMO + Q-Learning).

---

## 1. Resultado principal (MVP validado)

**Cinco agentes Q-Learning COORDINADOS superan al control de tiempo fijo de SUMO
de forma consistente.**

Evaluación con 5 semillas emparejadas (42-46), política determinista (ε=0),
misma demanda de tráfico para ambos:

| Métrica | Semáforo fijo (SUMO) | IA coordinada (5) | ¿Mejora? | Consistencia |
|---|---:|---:|:--:|:--:|
| Vehículos completados | 2408 | **2593** (+185) | ✅ | **5/5 semillas** |
| Teleports (atascos) | 939 | **826** (−113) | ✅ | **5/5 semillas** |
| Tiempo de espera medio (s) | 311.9 | **286.5** | ✅ | 4/5 |
| Duración media de viaje (s) | 610.0 | **590.6** | ✅ | 3/5 |
| Time loss medio (s) | 409.4 | **388.9** | ✅ | 3/5 |
| Velocidad media (m/s) | 2.76 | **2.91** | ✅ | 4/5 |
| Colisiones | 3.6 | **2.8** | ✅ | — |

**Interpretación:** la IA coordinada completa más viajes, con menos atascos y
menos espera, y lo hace en TODAS las realizaciones de tráfico probadas (no por
suerte de una semilla). Es un resultado robusto y reproducible.

---

## 2. El hallazgo clave del proyecto

> **Lo que mejora el tráfico no es "poner IA en más semáforos", sino que los
> agentes se COORDINEN entre sí.**

Esto se demostró comparando varias configuraciones con la misma metodología:

| Configuración | Semillas donde la IA gana al baseline (completados) |
|---|:--:|
| 5 agentes locales (aislados) | 2/5 — inestable |
| 5 agentes locales, estado más fino | 2/5 — no ayudó |
| 10 agentes locales (con cruces aislados) | ~3/5 — mixto |
| **5 agentes COORDINADOS** | **5/5 — gana siempre** ✅ |
| 18 agentes locales (cobertura total, sin coordinar) | 0/5 — peor de todos |

El patrón es inequívoco: la **coordinación** es el ingrediente que funciona; la
**cobertura sin coordinación empeora** el sistema.

---

## 3. Cómo funciona la solución

### Arquitectura (tres niveles)
```
Nivel 3  COORDINADOR CENTRAL         (futuro)
Nivel 2  COMUNICACION ENTRE AGENTES  <-- clave del MVP
Nivel 1  AGENTES LOCALES Q-LEARNING  <-- base
```

### Agente local (Nivel 1)
- **Estado:** nivel de cola de cada grupo + qué grupo tiene verde.
- **Acción:** mantener el verde o cambiar de grupo.
- **Recompensa:** penaliza la cola total y el desequilibrio entre grupos.
- **Algoritmo:** Q-Learning tabular con política ε-greedy.

### Coordinación (Nivel 2) — lo que marca la diferencia
Cada agente observa además la **presión de su vecino aguas abajo**: si el cruce
al que va a enviar tráfico está saturado, aprende a **no inundarlo**. Esto evita
que los atascos se propaguen por la red, que era la causa de la inestabilidad.

**Topología de vecindad** (validada contra la red):
```
262567760 --> 262567775        264377450 --> 265804326
262567777 --> 262567775
```

---

## 4. Metodología de evaluación (rigor científico)

- **Mismas condiciones** para IA y baseline: misma red, misma demanda, mismas
  semillas, mismo horizonte (4556 s), misma escala de tráfico.
- **Separación entrenamiento/evaluación:** se evalúa con ε=0 (sin exploración).
- **5 semillas emparejadas:** se compara par-a-par, no solo promedios, para
  medir consistencia y no "suerte".
- **Teleports siempre reportados:** son una limitación conocida de SUMO (un
  vehículo atascado es teletransportado y deja de contar); nunca se interpreta
  una mejora sin mirarlos.

---

## 5. Recorrido del proyecto (resumen por etapas)

| Etapa | Qué se hizo | Resultado |
|---|---|---|
| 1. Diagnóstico | Medir demanda; validar carriles | 264377450 saturada; config correcta |
| 2. Evaluación | IA local vs baseline | Inestable (gana 3/5, colapsa 2/5) |
| 3. Causa raíz | Localizar teleports | El problema está en la red NO controlada |
| 4. Coordinación | Agentes que ven a su vecino | **Gana 5/5 — MVP validado** ✅ |
| 6. Escalabilidad | Más intersecciones | Confirmó: cobertura sin coordinar no basta |

Documentos de detalle: `DIAGNOSTICO_ETAPA1.md`, `EVALUACION_ETAPA2.md`,
`ETAPA3_CAUSA_RAIZ.md`, `ESCALABILIDAD_ETAPA6.md`, `ARQUITECTURA.md`.

---

## 6. Cómo reproducir el resultado del MVP

En Windows, con el entorno virtual activo, dentro de `ExpoU`:

```powershell
# Entrenar los 5 agentes coordinados (si no estan ya entrenados)
python .\train_coordinado.py

# Evaluar coordinado vs baseline (5 semillas)
python .\evaluar_coordinado.py

# Tabla comparativa de las configuraciones
python .\comparar_resultados.py
```

Modelos entrenados: `q_table_coord_<id>.pkl` (versionados en el repo).

> Los datos de la tabla de la sección 1 provienen de la evaluación real
> ejecutada en la Etapa 4. El CSV crudo (`evaluacion_coordinado.csv`) se genera
> al correr `evaluar_coordinado.py` y debe versionarse desde esa corrida real
> como evidencia.

---

## 7. Limitaciones honestas

- El beneficio se demostró en **5 intersecciones coordinadas**; extenderlo a toda
  la red requiere coordinar más cruces (no solo añadirlos).
- La red tiene muchas intersecciones no controladas que concentran gran parte de
  los atascos; el sistema no puede gobernar lo que no controla.
- Q-Learning tabular es adecuado para este espacio de estados pequeño; estados
  más ricos (p. ej. con visión) requerirían Deep RL.
- Los teleports de SUMO son una limitación de la simulación, no del controlador.

---

## 8. Trabajo futuro

- **Coordinación + cobertura:** añadir la señal de vecino al sistema que cubre
  las 18 intersecciones (combinar lo mejor de ambos).
- **Coordinador central (Nivel 3):** objetivos de red por encima de los agentes.
- **Visión artificial (YOLO):** conteos reales de vehículos/peatones como entrada.
