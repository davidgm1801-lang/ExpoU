# Etapa 6 — Escalabilidad: de 5 a 10 semáforos (ExpoU)

## Motivación

La Etapa 3 demostró que el cuello de botella del sistema es la **red NO
controlada**: con solo 5 semáforos inteligentes, la mayoría de los atascos
ocurren fuera de su alcance. La forma más directa de ampliar el impacto es
**controlar más intersecciones**.

La Etapa 4 demostró que la **coordinación** entre agentes vecinos estabiliza la
política y supera al baseline. Esta etapa combina ambas lecciones: **más agentes,
coordinados**.

## Qué se hizo

### Exploración de la red
La red de Bogotá tiene **19 semáforos**. De ellos, **9 tienen la estructura de 4
fases** (dos grupos verdes alternos) que nuestros agentes saben controlar. Ya
usábamos 5; se añadieron **5 más**:

| Nuevo semáforo | Por qué se eligió |
|---|---|
| `317470710` | 4 fases compatibles |
| `GS_cluster_12519565096_12519565097` | 4 fases; conecta con el corredor |
| `cluster_261757164_261757167` | incluye `175956267#1`, un borde con muchos teleports en la Etapa 3 |
| `cluster_265804323_265804324` | 4 fases compatibles |
| `cluster_7792538741_7792538742` | recibe de `265804326` (vía `66953367#0`): extiende el corredor coordinado |

Los carriles de entrada por grupo (A = verde en fase 0, B = verde en fase 2) se
extrajeron de las conexiones de la red (`<connection tl=... linkIndex=...>`).

### Configuración centralizada
Se creó **`config_semaforos.py`** como fuente única de la verdad: define
`SEMAFOROS` (los 10 cruces y sus carriles) y `VECINO_DESTINO` (la topología de
vecindad). Los entrenadores y evaluadores lo importan. **Para escalar a más (o
menos) intersecciones basta editar este archivo.**

### Topología de vecindad ampliada
```
262567760 (A) --> 262567775
262567777 (A) --> 262567775
264377450 (B) --> 265804326
265804326 (B) --> cluster_7792538741_7792538742   (NUEVO corredor)
```

## Protección de modelos previos

El entrenamiento escalado usa el prefijo `q_table_coord10_` (variable
`PREFIJO_COORD`), de modo que **NO sobrescribe** los modelos de 5 semáforos de la
Etapa 4 (`q_table_coord_*`). Así se pueden comparar ambos.

## Flujo de ejecución (tu Windows, .venv activo)

```powershell
# 0) VALIDAR que los 10 semaforos y sus carriles existen en la red
python .\validar_config.py

# 1) ENTRENAR los 10 agentes coordinados (prefijo propio)
$env:PREFIJO_COORD="q_table_coord10_"; python .\train_coordinado.py

# 2) EVALUAR los 10 vs baseline (mismas 5 semillas)
$env:PREFIJO_COORD="q_table_coord10_"; python .\evaluar_coordinado.py
```

Esto genera `evaluacion_q_table_coord10.csv`.

> IMPORTANTE: ejecuta **primero** `validar_config.py`. Los carriles de los 5
> nuevos semáforos se extrajeron del XML de la red pero NO se han probado en
> ejecución; la validación confirma que existen antes de invertir tiempo en
> entrenar.

## Qué esperar / cómo interpretar

- Si al escalar a 10 el sistema **sigue superando al baseline de forma
  consistente** (par-a-par por semilla), se confirma que la arquitectura
  coordinada escala. Es el resultado buscado.
- Si aparecen inestabilidades nuevas, indicarán dónde la topología de vecindad
  necesita más relaciones (algún corredor sin modelar).

## Límites honestos

- La topología de vecindad entre los 10 es parcial: solo incluye las relaciones
  claras. Cruces nuevos sin vecindad modelada actúan como agentes locales.
- Los 5 nuevos semáforos agrupan varios carriles por grupo; la cola del grupo es
  la suma, lo que es correcto pero cambia la escala de cola respecto a los 5
  originales (que tenían 2 carriles por grupo).
- Entrenar 10 agentes tarda más que 5. Usa `EPISODIOS_COORD` para ajustar.
