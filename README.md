# 🚦 Semáforo Inteligente con Aprendizaje por Refuerzo

Sistema de control adaptativo de semáforos que usa **Q-Learning** para decidir
cuándo cambiar las luces según la cantidad de vehículos esperando en cada
dirección. El objetivo: que nadie espere en una intersección vacía.

Incluye una **simulación** de una intersección de 4 vías, un **agente de RL**
que aprende la política de control, un **baseline de tiempo fijo** para comparar,
y una **visualización en vivo** con Pygame.

## Resultados

Tras entrenar ~1500 episodios, el agente RL frente al semáforo tradicional:

| Métrica                      | Tiempo Fijo | RL      |
|------------------------------|-------------|---------|
| Carros esperando / paso      | 4.07        | **2.12** |
| Carros atendidos / episodio  | 275.4       | **281.4** |
| Cola máxima observada        | 10          | **6**   |

➡️ **~48% menos de espera promedio.** La IA aprende sola a dar más verde al
eje con más demanda, sin reglas programadas a mano.

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
# 1. Entrenar el agente (genera q_table.pkl)
python train.py --episodes 2000

# 2. Comparar RL vs semáforo fijo (métricas numéricas)
python evaluate.py --episodes 200

# 3. Ver la simulación en vivo
python visualize.py
```

**Controles de la visualización:**
`ESPACIO` cambia entre RL y Tiempo Fijo · `R` reinicia · `+/-` velocidad · `ESC` salir.

## Cómo funciona el RL

El problema se modela como un proceso de decisión de Markov:

- **Estado:** nivel de cola en el eje Norte-Sur y Este-Oeste (discretizado),
  fase actual, si hay amarillo, y tiempo en la fase actual.
- **Acciones:** `mantener` la fase verde o `cambiar` a la otra.
- **Recompensa:** negativa proporcional al total de carros esperando
  (minimizarla = minimizar la espera).
- **Algoritmo:** Q-Learning tabular con política epsilon-greedy.

Se usa Q-Learning tabular (no deep RL) porque el espacio de estados es pequeño,
entrena en segundos y la tabla aprendida es **inspeccionable**.

## Estructura

```
traffic_rl/
├── simulation/
│   ├── intersection.py   # Entorno estilo Gym (reset/step)
│   └── config.py         # Parámetros ajustables
├── agents/
│   ├── q_learning.py     # Agente de RL
│   └── fixed_timer.py    # Baseline de tiempo fijo
├── train.py              # Entrenamiento
├── evaluate.py           # Comparación RL vs fijo
└── visualize.py          # Simulación visual (Pygame)
```

## Próximos pasos (Opción B)

- **Visión por computadora:** reemplazar los contadores simulados por conteos
  reales de vehículos/peatones detectados con YOLO sobre video de cámara.
- **Deep RL (DQN):** manejar estados continuos / más complejos sin discretizar.
- **Peatones:** añadir cola de peatones con su propia fase y prioridad.
- **Múltiples intersecciones:** coordinar una red de semáforos (RL multiagente).
```
