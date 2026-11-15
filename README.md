# 🚦 ExpoU — Control inteligente y coordinado de semáforos (Bogotá)

Sistema **multiagente de aprendizaje por refuerzo (Q-Learning)** que controla
semáforos de forma adaptativa y **coordinada** sobre una red real de Bogotá
simulada en **SUMO**. Cada semáforo es un agente que aprende cuándo cambiar la
luz verde para reducir las colas, y se coordina con sus vecinos para no propagar
atascos.

**Resultado principal:** los 5 agentes coordinados **superan al semáforo de
tiempo fijo** en viajes completados, espera y congestión, de forma consistente.
Ver [`RESULTADOS.md`](RESULTADOS.md) y [`MVP.md`](MVP.md).

| Métrica (demo, semilla 42) | Semáforo fijo | IA coordinada |
|---|---:|---:|
| Vehículos completados | 2418 | **2661** (+243) |
| Espera promedio (s) | 291.9 | **282.0** |
| Teleports (atascos) | 972 | **775** (−197) |

---

## Requisitos

Este proyecto NO corre solo con `pip install`. Necesita **SUMO**, un simulador de
tráfico de código abierto.

### 1. Instalar SUMO (obligatorio)
- Descarga SUMO 1.28.0 (o compatible) desde https://eclipse.dev/sumo/
- En Windows, el instalador lo deja normalmente en
  `C:\Program Files (x86)\Eclipse\Sumo` (o similar).
- Verifica la instalación abriendo una terminal y ejecutando: `sumo --version`
- Define la variable de entorno **`SUMO_HOME`** apuntando a la carpeta de SUMO
  (el instalador de Windows suele hacerlo automáticamente). Las librerías
  `traci` y `sumolib` vienen incluidas con SUMO.

### 2. Python
- Python 3.10+ recomendado.
- Crea y activa un entorno virtual:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1      # Windows PowerShell
  # source .venv/bin/activate       # Linux/Mac
  ```
- Instala dependencias:
  ```powershell
  pip install -r requirements.txt
  ```

> `traci` y `sumolib` NO se instalan con pip: vienen con SUMO. Si al correr un
> script ves `ModuleNotFoundError: No module named 'traci'`, revisa que SUMO esté
> instalado y que `SUMO_HOME` esté configurado.

---

## Cómo verlo funcionar (demo)

La solución ganadora son los **5 agentes coordinados** (modelos
`q_table_coord_*.pkl`, ya incluidos en el repo).

```powershell
# Demo con DOS ventanas simultaneas: semaforo fijo vs IA coordinada
python .\demo_coordinado.py --modo dual

# Solo IA coordinada (una ventana)
python .\demo_coordinado.py --modo ia

# Solo semaforo fijo (una ventana)
python .\demo_coordinado.py --modo fijo

# Sin ventanas: corre ambos e imprime la tabla de metricas (rapido)
python .\demo_coordinado.py --modo comparar
```

Opciones: `--semilla 42`, `--delay 80` (ritmo visual), `--sin-gui`.

---

## Reproducir el entrenamiento y la evaluación

```powershell
# Entrenar los 5 agentes coordinados (regenera q_table_coord_*.pkl)
python .\train_coordinado.py

# Evaluar coordinado vs baseline (5 semillas, sin ventana)
python .\evaluar_coordinado.py

# Tabla comparativa de las configuraciones probadas
python .\comparar_resultados.py
```

Sistema que cubre TODAS las intersecciones controlables (experimental):
```powershell
python .\autodetectar_semaforos.py      # genera la config de la red
python .\train_generico_coord.py        # entrena agentes coordinados genericos
python .\evaluar_generico_coord.py       # evalua
```

---

## Cómo funciona (resumen)

- **Estado:** nivel de cola de cada grupo de carriles + qué grupo tiene verde
  (discretizado). En la versión coordinada se añade la **presión del vecino**.
- **Acciones:** mantener el verde o cambiarlo.
- **Recompensa:** negativa, proporcional a los vehículos detenidos; la versión
  coordinada penaliza además alimentar a un vecino saturado.
- **Algoritmo:** Q-Learning tabular con política ε-greedy.

Detalles de diseño en [`ARQUITECTURA.md`](ARQUITECTURA.md).

---

## Documentación del proyecto

| Documento | Contenido |
|---|---|
| [`MVP.md`](MVP.md) | Qué hace, para qué, diferencial frente a Bogotá, funcionalidades |
| [`RESULTADOS.md`](RESULTADOS.md) | Resultado principal y narrativa por etapas |
| [`ARQUITECTURA.md`](ARQUITECTURA.md) | Arquitectura (3 niveles) y mapa de archivos |
| [`DIAGNOSTICO_ETAPA1.md`](DIAGNOSTICO_ETAPA1.md) | Diagnóstico de demanda y carriles |
| [`EVALUACION_ETAPA2.md`](EVALUACION_ETAPA2.md) | Evaluación IA local vs baseline |
| [`ETAPA3_CAUSA_RAIZ.md`](ETAPA3_CAUSA_RAIZ.md) | Causa de la inestabilidad |
| [`ESCALABILIDAD_ETAPA6.md`](ESCALABILIDAD_ETAPA6.md) | Escalar a más intersecciones |
| [`SISTEMA_19.md`](SISTEMA_19.md) | Sistema genérico para toda la red |

---

## Estructura (archivos clave)

```
ExpoU/
├── agents/
│   ├── sumo_q_learning.py            # agente local
│   ├── coordinated_agent.py          # agente coordinado (presion de vecino)
│   ├── generic_agent.py              # agente generico (N grupos)
│   └── generic_coordinated_agent.py  # generico + coordinacion
├── train_coordinado.py / evaluar_coordinado.py   # solucion ganadora (5)
├── demo_coordinado.py                # demo visual (fijo vs IA)
├── autodetectar_semaforos.py         # configura la red automaticamente
├── config_semaforos.py               # configuracion centralizada
├── comparar_resultados.py            # tabla comparativa de resultados
├── q_table_coord_*.pkl               # modelos entrenados ganadores
├── sumo_bogota/                      # red de Bogota (SUMO)
└── *.md                              # documentacion
```

---

## Limitaciones

- Prueba de concepto en **simulación** (SUMO), no un despliegue real.
- La mejora validada es sobre 5-6 intersecciones coordinadas en corredores.
- Los *teleports* son una limitación del simulador (vehículos muy atascados que
  SUMO reubica), no del controlador; se reportan siempre para no inflar métricas.
