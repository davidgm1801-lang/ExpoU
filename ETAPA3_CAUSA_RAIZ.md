# Etapa 3 — Causa raíz de la inestabilidad (ExpoU)

**Punto de partida (Etapa 2):** la política de IA es **inestable**: supera al
baseline en 3 de 5 semillas, pero **colapsa en 2** (semillas 42 y 44), con un
fuerte aumento de teleports por atasco y ~400 vehículos completados menos.

Este documento registra el diagnóstico que localizó la causa de ese colapso,
incluyendo las hipótesis que se **descartaron** por la evidencia.

---

## 1. Método de diagnóstico (sin reentrenar)

Dos herramientas, ambas de solo lectura (no modifican modelos):

1. `localizar_teleports.py` — atribuye cada teleport al **semáforo** cuyo carril
   de entrada coincide con la posición del vehículo, o a "otros".
2. `ranking_bordes_teleports.py` — registra el **borde exacto** de cada teleport
   y lo clasifica: SALIDA de TLS / ENTRADA de TLS / interno / red no controlada.

Ambas corren baseline e IA en las semillas 42 y 44 (colapso) y 45 (control).

---

## 2. Hipótesis 1 — "La IA rompe en 264377450" → DESCARTADA

264377450 era la intersección más congestionada (Etapa 1), así que se sospechó
que el colapso se concentraría ahí.

**Evidencia (`localizar_teleports.py`), teleports en los 5 semáforos vs "otros":**

| Semilla | 5 semáforos (base→IA) | "otros" (base→IA) |
|---|---|---|
| 42 | 8 → 4 | 1000 → **1269 (+269)** |
| 44 | 12 → 9 | 853 → **1231 (+378)** |
| 45 | 1 → 1 | 1061 → 812 (−249) |

Los cinco semáforos controlados concentran **muy pocos** teleports (4–9 con IA).
El aumento masivo está en "otros". **La hipótesis queda descartada:** el colapso
no se origina en los carriles de las intersecciones controladas.

---

## 3. Hipótesis 2 — "Spillover a las salidas de los TLS" → DESCARTADA

Segunda sospecha: la IA deja pasar más tráfico y satura las **salidas
inmediatas** de las intersecciones.

**Evidencia (`ranking_bordes_teleports.py`), teleports por clase de borde:**

| Semilla | SALIDA de TLS (base→IA) | Red no controlada (base→IA) |
|---|---|---|
| 42 | 7 → 13 (+6) | **154 → 206 (+52)** |
| 44 | 8 → 6 (−2) | **161 → 220 (+59)** |
| 45 | 6 → 0 (−6) | 169 → 118 (−51) |

El aumento de la IA está **abrumadoramente en la red no controlada**, no en las
salidas de los semáforos (que incluso bajan en la semilla 44). **Hipótesis
descartada:** no es un spillover directo a las salidas.

---

## 4. Causa raíz (respaldada por la evidencia)

Los bordes con más teleports bajo IA en las semillas malas están **dispersos por
toda la red no controlada** (p. ej. `23502426#0`, `88860991#0`, `915587469#5`),
no concentrados en un único cuello de botella.

Correlación clave observada entre los tres regímenes:
- Semillas **42, 44** (IA colapsa): los teleports en red no controlada **suben**
  (+52, +59).
- Semilla **45** (IA va bien): los teleports en red no controlada **bajan** (−51).

**Conclusión:** las decisiones de los 5 agentes alteran el **patrón temporal** con
que los vehículos se vierten al resto de la red. En ciertas realizaciones del
tráfico ese patrón provoca atascos en **puntos lejanos y dispersos de la red que
los agentes NO controlan**. Es un **efecto de red distribuido**, no un problema
local de ninguna intersección.

---

## 5. Implicación principal

> Con solo 5 semáforos inteligentes sobre una red urbana amplia, el rendimiento
> global está **dominado por la parte NO controlada** de la red, que concentra la
> gran mayoría de los teleports. Los agentes locales pueden mejorar sus propias
> intersecciones, pero no pueden evitar los atascos que se forman fuera de su
> alcance.

Esto tiene dos consecuencias directas:

1. **Afinar el estado o la recompensa local tiene rendimiento global esperado
   bajo**, porque el problema no está donde los agentes miran ni donde actúan.
   (La Parte B de la Etapa 3 lo comprueba experimentalmente.)
2. **Se justifica el plan a largo plazo de ExpoU:** para que la IA domine el
   resultado global hay que **controlar una fracción mucho mayor de la red**
   (Etapa 6, escalabilidad) y/o **coordinar** agentes (Etapas 4-5). Este es el
   verdadero cuello de botella del sistema.

---

## 6. Limitaciones honestas de este diagnóstico

- La atribución por borde solo cubre bordes con nombre; la mayoría de teleports
  ocurren en carriles internos de intersecciones (`:...`), no desglosados aquí.
  El análisis es sobre la **distribución** de los teleports con nombre, que es
  suficiente para distinguir "TLS vs red no controlada".
- Un borde puede ser salida de un TLS y entrada de otro; se priorizó la etiqueta
  "SALIDA de TLS".
- 3 semillas de diagnóstico; no se afirman resultados estadísticos, sí
  tendencias consistentes con la Etapa 2.

---

## 7. Qué sigue

- **Parte B (experimento de control):** probar una mejora local acotada (refinar
  la discretización de la cola), reentrenando con modelos de **nombre distinto**
  (los 5 modelos actuales se conservan como respaldo) y re-evaluando con
  `evaluar_etapa2.py`. Hipótesis a contrastar: la mejora local **no** corrige la
  inestabilidad global.
- Según el resultado de B, reorientar hacia **escalabilidad/coordinación**.
