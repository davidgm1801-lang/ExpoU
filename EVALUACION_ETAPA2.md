# Evaluación — Etapa 2 (ExpoU)

**Objetivo:** comparar, en condiciones idénticas y reproducibles, el controlador
original de SUMO (**baseline**) contra los cinco agentes Q-Learning entrenados
(**IA**), para determinar si la política aprendida mejora, empeora o iguala al
control de referencia.

---

## 1. Diseño experimental

| Elemento | Valor |
|---|---|
| Brazos | **baseline** (programa fijo de SUMO) vs **IA** (5 agentes, ε=0) |
| Modelos IA | `q_table_independiente_<id>.pkl` (uno por semáforo) |
| Política IA | Determinista (ε=0, sin exploración) |
| Semillas | 42, 43, 44, 45, 46 (emparejadas entre brazos) |
| Duración | 4556 s por corrida | 
| Escala de tráfico | 2 |
| Modo | Headless (`sumo` sin GUI) |
| Corridas totales | 10 (5 semillas × 2 brazos) |
| Script | `evaluar_etapa2.py` |
| Datos crudos | `evaluacion_etapa2.csv` |

El emparejamiento por semilla garantiza que baseline e IA de una misma semilla
ven **exactamente la misma demanda de vehículos**; así, su diferencia aísla el
efecto del controlador.

**Regla metodológica:** las tablas Q no se modificaron ni se reentrenaron. El
evaluador solo las lee.

---

## 2. Resultados promedio (sobre las 5 semillas)

| Métrica | Baseline | IA | Δ (IA−base) | Sentido |
|---|---:|---:|---:|---|
| Vehículos completados | 2408.4 | 2331.6 | −76.8 | más = mejor |
| Espera promedio (s) | 311.9 | 300.8 | −11.1 | menos = mejor |
| Duración promedio (s) | 610.0 | 592.3 | −17.7 | menos = mejor |
| Time loss promedio (s) | 409.4 | 393.6 | −15.8 | menos = mejor |
| Velocidad promedio (m/s) | 2.761 | 2.785 | +0.024 | más = mejor |
| Cola prom. (suma 5 TLS) | 16.64 | 15.21 | −1.43 | menos = mejor |
| Cola máxima global | 34.2 | 31.0 | −3.2 | menos = mejor |
| Teleports total | 939.0 | 1031.2 | +92.2 | menos = mejor |
| Colisiones | 3.6 | 2.8 | −0.8 | menos = mejor |

**Advertencia:** estos promedios, por sí solos, dan una impresión engañosa
(leve mejora de fluidez con menos completados y más teleports). El análisis
par-a-par de abajo muestra que la realidad es distinta.

---

## 3. Análisis par-a-par por semilla (lo importante)

Comparando IA vs baseline **dentro de cada semilla**:

| Semilla | Completados (base→IA) | Espera | Duración | Teleports (base→IA) | Veredicto |
|---|---|---|---|---|---|
| 42 | 2418 → 2021 (**−397**) | peor | peor | 972 → 1237 (**+265**) | ❌ IA peor en todo |
| 43 | 2628 → 2616 (−12) | mejor | mejor | 800 → 840 (+40) | ✅ IA mejor (salvo teleports) |
| 44 | 2510 → 2073 (**−437**) | peor | ≈ | 829 → 1204 (**+375**) | ❌ IA peor en casi todo |
| 45 | 2260 → 2704 (**+444**) | mejor | mejor | 1026 → 777 (**−249**) | ✅✅ IA mejor en TODO |
| 46 | 2226 → 2244 (+18) | mejor | mejor | 1068 → 1098 (+30) | ✅ IA mejor (salvo teleports) |

---

## 4. Hallazgo principal: comportamiento bimodal e inestable

El resultado **no es una mejora uniforme pequeña**: es **bimodal**.

- En **3 semillas (43, 45, 46)** la IA es claramente mejor (menos espera y
  duración; en la 45 incluso más completados y menos teleports).
- En **2 semillas (42, 44)** la IA **se descompensa**: pierde ~400 vehículos
  completados y dispara los teleports (+265 y +375), con fuerte aumento de los
  teleports por **jam** (atasco) y **yield**.

Los promedios de la Sección 2 son la mezcla de estos dos regímenes opuestos, y
por eso resultan engañosos. **El problema central de la política aprendida no es
su nivel medio, sino su alta varianza frente a distintas realizaciones del
tráfico.**

---

## 5. Hipótesis sobre la causa (fundada, no confirmada)

En las semillas malas (42, 44) se disparan los teleports por **jam**, lo que
sugiere que, en ciertas realizaciones, la política **mantiene el verde en un
grupo mientras otro se satura** hasta provocar atascos que terminan en
teletransporte.

Un sospechoso concreto es la **representación del estado**: la cola se discretiza
en solo 3 niveles (0 / 1–3 / >3). Una vez la cola supera 3 vehículos, el agente
**no distingue** entre "4" y "28". En una intersección ya saturada (264377450,
caracterizada en la Etapa 1), esa ceguera puede impedir que el agente reaccione a
tiempo a una cola creciente.

**Pendiente de confirmar:** localizar en qué semáforo se concentran los teleports
en las semillas 42 y 44. El evaluador actual cuenta teleports globales, no por
intersección. Esta medición se abordará al inicio de la Etapa 3.

---

## 6. Conclusiones (honestas)

- ❌ **No** se puede afirmar que la IA mejore el tráfico de forma global:
  completa menos viajes y genera más teleports en promedio.
- ❌ Tampoco es correcto decir que la IA es "peor": mejora espera, duración,
  colas y colisiones en la mayoría de las semillas.
- ✅ Afirmación respaldada por la evidencia: **la política aprendida es
  inestable** — supera al baseline en 3 de 5 semillas, pero colapsa en 2 de 5.
  La inconsistencia es el problema a resolver.

**Límite estadístico:** con 5 semillas no se afirman resultados estadísticamente
significativos. El análisis par-a-par sí permite observar consistencia y
magnitud.

**Límite de SUMO (teleports):** un vehículo atascado es teletransportado y deja
de contar en los promedios de vehículos completados. Por eso un número menor de
"completados" junto a más teleports (semillas 42 y 44) indica que esos brazos
perdieron precisamente los casos difíciles; no deben leerse los promedios de
espera/duración de forma aislada.

---

## 7. Implicaciones para la Etapa 3

Objetivos medibles derivados de esta evaluación:

1. **Localizar la inestabilidad:** medir teleports y ocupación **por semáforo**
   en las semillas malas (42, 44) para confirmar dónde se rompe la política.
2. **Revisar la representación del estado:** la discretización de cola a 3
   niveles es candidata principal (probar más niveles o umbrales distintos).
3. **Revisar la función de recompensa:** evaluar si penalizar solo cola total y
   desequilibrio basta, o si debe incorporar señales que desincentiven la
   saturación extrema que lleva a teleports.
4. Volver a evaluar con esta misma metodología tras cada cambio, para comparar
   de forma justa.
