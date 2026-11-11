# Diagnóstico de tráfico — Etapa 1 (ExpoU)

**Objetivo de la etapa:** determinar si las diferencias de recompensa observadas
entre los cinco agentes Q-Learning se deben a la **demanda de tráfico** de cada
intersección o a **problemas en los agentes / en la medición**.

**Regla metodológica:** en esta etapa NO se cargan ni modifican las tablas Q.
Todas las mediciones se hacen con el **controlador original de SUMO**.

---

## 1. Insumos utilizados

| Insumo | Origen | Uso |
|---|---|---|
| `diagnostico_trafico_5.csv` | `diagnostico_trafico_5.py` (control original de SUMO, semilla 42, escala 2, 4556 s) | Demanda por grupo A/B de cada semáforo |
| Salida de `inspeccionar_cinco.py` | `getControlledLinks` + fases de cada semáforo | Verificar que los carriles configurados son los movimientos controlados |
| `resultados_entrenamiento_5.csv` | Entrenamiento de 100 episodios | Recompensas por agente (contexto) |

---

## 2. Verificación de carriles (¿miden lo correcto?)

Cada semáforo tiene 6 índices de señal y fases `GGGrrr` / `rrrGGG`:
- **Fase 0 (`GGGrrr`)** → verde para los índices **0, 1, 2** → corresponde al **grupo A**.
- **Fase 2 (`rrrGGG`)** → verde para los índices **3, 4, 5** → corresponde al **grupo B**.

Cruzando las entradas reales de cada fase (de `getControlledLinks`) con los
carriles configurados en `train_sumo_5.py`:

| Semáforo | Grupo A (config) | Grupo B (config) | Coincide con conexiones reales |
|---|---|---|---|
| 262567760 | `1083001223#0_0/_1` | `862794316#0_0/_1` | ✅ |
| 262567775 | `88757025#0_0/_1` | `1083001225#0_1/_2` | ✅ |
| 262567777 | `1060493360#3_1/_2` | `908369205#0_0/_1` | ✅ |
| 264377450 | `1083001233_0/_1` | `1056806207#0_0/_1` | ✅ |
| 265804326 | `88877450#2_0/_1` | `1083001234#0_0/_1` | ✅ |

**Conclusión:** los carriles de los cinco agentes están correctamente
configurados. No sobra ni falta ningún carril de entrada controlado. Queda
descartada la hipótesis de "carriles mal configurados".

---

## 3. Demanda por intersección (diagnóstico con control original)

Datos de `diagnostico_trafico_5.csv` (grupos A+B agregados salvo donde se indica):

| Semáforo | Cola prom. (A+B) | Cola máx. | Veh. únicos (A+B) | Detenido-seg. (A+B) |
|---|---:|---:|---:|---:|
| 262567760 | 0.044 | 3 | 118 | 201 |
| 265804326 | 0.063 | 3 | 174 | 287 |
| 262567775 | 0.106 | 4 | 375 | 483 |
| 262567777 | 0.193 | 4 | 445 | 876 |
| **264377450** | **11.572** | **28** | **524** | **52 722** |

Detalle de **264377450**, que concentra la congestión en su **grupo A**:

| Grupo | Cola prom. | Cola máx. | Velocidad media | Detenido-seg. |
|---|---:|---:|---:|---:|
| A | 10.876 | 28 | 0.685 m/s | 49 553 |
| B | 0.696 | 4 | 2.390 m/s | 3 169 |

**Orden de demanda (de menor a mayor):**
`262567760 < 265804326 < 262567775 < 262567777 ≪ 264377450`.

---

## 4. Respuesta a la pregunta de la Etapa 1

Las diferencias de recompensa entre agentes se explican **principalmente por la
demanda de tráfico**, no por fallos de aprendizaje.

Evidencia principal: el grupo A de **264377450** está crónicamente congestionado
(cola promedio ~11, velocidad 0.685 m/s) **incluso con el controlador original
de SUMO**, es decir, sin ningún agente inteligente. La recompensa de
entrenamiento de ese semáforo (≈ −17.4) es coherente con su demanda física:

> `R = -(cola_A + cola_B) - 0.25·|cola_A − cola_B|`
> Con cola_A ≈ 11 y cola_B ≈ 0.7 → R ≈ −14, del mismo orden que el −17 observado.

Por tanto, **NO** debe concluirse que 264377450 sea un "agente deficiente".
Comparar su −17 con el −0.26 de 262567760 es comparar intersecciones con
demandas radicalmente distintas.

---

## 5. Hipótesis fundada (pendiente de confirmar)

**Posible *spillback* 264377450 ← 265804326.** Son intersecciones vecinas
conectadas por el tramo `1083001234`:
- En 264377450, el grupo A (`1083001233`) **sale hacia** `1083001234#0`.
- En 265804326, el **grupo B** es precisamente `1083001234#0`.

Si 265804326 no desaloja con fluidez su grupo B, el tráfico puede represarse
hacia atrás y saturar el grupo A de 264377450. Esto es coherente con la
congestión crónica observada, pero **no está medido directamente**: se infiere
de la topología. Confirmarlo requeriría medir la ocupación del tramo
`1083001234` y los teleports en esa zona.

Este par (264377450 ↔ 265804326) es el candidato natural para la futura
**Etapa 4 (comunicación entre agentes)**.

---

## 6. Advertencia metodológica para la Etapa 2

Experimentos previos reportaron ~980 teleports. Un vehículo atascado que SUMO
teletransporta cuenta como "detenido" mientras permanece en el carril, lo que
puede **inflar** la cola crónica medida en 264377450. Al evaluar los agentes
(Etapa 2) deben registrarse y vigilarse los teleports, y no interpretarlos como
viajes completados.

---

## 7. Estado de la Etapa 1

- [x] Carriles de los 5 agentes verificados contra las conexiones reales.
- [x] Demanda por intersección medida con el control original.
- [x] Diferencias de recompensa explicadas por demanda (no por fallo de agente).
- [x] Caso 264377450 caracterizado como congestión estructural en el grupo A.
- [ ] (Hipótesis) Confirmar *spillback* 265804326 → 264377450 con mediciones de ocupación/teleports.

**Limitaciones honestas de este diagnóstico:**
- `salidas_observadas` nunca se incrementa en `diagnostico_trafico_5.py` (columna no usada).
- `detenido_segundos` es una estimación por conteo de vehículos con velocidad < 0.1 m/s por paso, no un tiempo de espera oficial de SUMO.
- La medición cubre solo los carriles de entrada observados de cada semáforo.
