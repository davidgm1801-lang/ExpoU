# Sistema de 19 intersecciones — Agente genérico (ExpoU)

## Qué es

Un diseño **robusto y general** que pone un agente Q-Learning en **todas** las
intersecciones controlables de la red, sin importar su estructura (2, 3 o más
grupos de verde). El objetivo: cubrir la red completa con un único mecanismo y
que solo tengas que **entrenar**.

## Por qué un agente genérico

La red tiene 19 semáforos con estructuras muy distintas (de 3 a 8 fases; de 1 a
3 grupos verdes). El agente de etapas anteriores solo manejaba 2 grupos (A/B).
Este sistema **generaliza a N grupos**, de modo que el mismo código sirve para
toda la red.

## Cómo funciona (robusto por diseño)

### 1. Autodetección (`autodetectar_semaforos.py`)
Lee la red y, para cada semáforo, detecta automáticamente:
- sus **fases verdes** (los grupos), y
- los **carriles de entrada** reales de cada grupo (filtrando carriles internos).

Guarda todo en `config_auto_semaforos.json`. **No configuras nada a mano.**
Descarta los semáforos sin al menos 2 grupos verdes (no hay decisión que tomar).

### 2. Agente genérico (`agents/generic_agent.py`)
- **Estado:** `(cola_grupo_activo, cola_max_otros, indice_grupo_activo)`.
  Tamaño acotado aunque el semáforo tenga muchos grupos.
- **Acción:** 0 = mantener el verde actual; 1 = avanzar al siguiente grupo
  (rotación cíclica). Decisión binaria → tabla Q pequeña y estable.

### 3. Entrenador (`train_generico.py`) y evaluador (`evaluar_generico.py`)
Un único script recorre todos los semáforos detectados, con la misma mecánica
para 2, 3 o más grupos. Respetan los tiempos mínimo/máximo de verde y las fases
amarillas originales.

## Garantías (y límites honestos)

**Lo que está garantizado:**
- El sistema **controla todas** las intersecciones controlables sin caerse, sea
  cual sea su número de fases.
- La configuración se genera **automáticamente** desde la red.
- Entrenamiento y evaluación **reproducibles** (semillas fijas).

**Lo que NO se puede garantizar de antemano:**
- Que *mejore* el tráfico en todas. Eso lo dice la evaluación. Como mostró la
  Etapa 6, el beneficio depende de la coordinación y de la estructura de
  corredores. Este sistema prioriza **cobertura y robustez**; la calidad se mide.

## Flujo de ejecución (tu Windows, .venv activo)

```powershell
# 1) AUTODETECTAR la configuracion de toda la red (genera el JSON)
python .\autodetectar_semaforos.py

# 2) ENTRENAR un agente por semaforo controlable (50 episodios por defecto)
python .\train_generico.py

# 3) EVALUAR las N intersecciones vs baseline (5 semillas)
python .\evaluar_generico.py
```

Genera `evaluacion_generico.csv`. Tráelo para analizar el resultado.

Parámetros útiles:
- `EPISODIOS_GEN` ajusta el número de episodios (p. ej. `$env:EPISODIOS_GEN=30`).

## Relación con lo anterior

- No reemplaza los modelos previos (usa prefijo `q_table_gen_`).
- Es la versión **cobertura total** del sistema. La versión **coordinada**
  (Etapa 4, 5 semáforos) sigue siendo la de mejor resultado medido hasta ahora.
- Paso futuro natural: añadir la señal de coordinación (presión de vecino)
  también al agente genérico, combinando cobertura + coordinación.
