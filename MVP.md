# ExpoU — MVP: Control inteligente de semáforos para Bogotá

## 1. Qué es (en una frase)

ExpoU es un **sistema de inteligencia artificial que controla semáforos de forma
adaptativa y coordinada**, usando aprendizaje por refuerzo (Q-Learning) sobre una
red real de Bogotá simulada en SUMO, y que **supera al semáforo de tiempo fijo**
en viajes completados y congestión.

## 2. Qué hace el software

- **Observa** el tráfico de cada intersección (cuántos vehículos esperan en cada
  grupo de carriles).
- **Decide** en tiempo real cuándo mantener o cambiar la luz verde, para reducir
  las colas.
- **Aprende** solo, por prueba y error, la mejor política de control — sin reglas
  escritas a mano.
- **Coordina** los semáforos entre sí: cada agente tiene en cuenta la congestión
  de su vecino aguas abajo para no propagar atascos.
- **Mide y compara** su desempeño contra el semáforo tradicional con una
  metodología rigurosa (varias semillas, mismas condiciones).
- **Demuestra** el resultado visualmente (dos simulaciones lado a lado: fijo vs IA).

## 3. Para qué sirve

Atacar la **congestión urbana**, uno de los mayores problemas de Bogotá (pérdida
de tiempo, combustible y calidad del aire). Un control de semáforos que se adapta
a la demanda real y coordina corredores puede mover más vehículos con menos
espera, sin obras físicas: solo software sobre la infraestructura existente.

## 4. Qué lo hace diferente de lo que ya existe en Bogotá

**Lo que Bogotá ya tiene (estado del arte local):**
Bogotá opera ~1.717 intersecciones semaforizadas con un **Sistema Centralizado de
Semaforización** que ajusta tiempos según el tráfico, y recientemente incorpora
**IA de detección** (del orden de 1.300 videodetectores que cuentan vehículos en
tiempo real) y un laboratorio público de semaforización. Es un control
**adaptativo basado en detección y optimización centralizada**.
*(Información de fuentes públicas; ver sección 8. Contenido reformulado.)*

**Lo que ExpoU propone (el diferencial):**

| Dimensión | Bogotá (actual) | ExpoU |
|---|---|---|
| Cómo decide | Reglas/optimización centralizada con conteo en tiempo real | Cada semáforo **aprende** su política por refuerzo (Q-Learning) |
| Arquitectura | Centralizada | **Multiagente**: agentes locales que deciden distribuidamente |
| Coordinación | Sincronización centralizada | **Emergente**: cada agente considera a su vecino, sin jefe central |
| Adaptación | Ajuste de planes | Política aprendida que generaliza a situaciones de cola |

**En resumen:** Bogotá ya es "inteligente" en el sentido de detectar y ajustar;
ExpoU explora un paradigma **más avanzado y complementario** — aprendizaje por
refuerzo **multiagente coordinado** — y demuestra su viabilidad sobre una red
real de la ciudad. No es lo que opera hoy la ciudad; es una prueba de concepto de
hacia dónde podría evolucionar.

> Nota honesta: ExpoU es una **prueba de concepto en simulación** (5-6
> intersecciones coordinadas), no un sistema desplegado en calle.

## 5. Funcionalidades

- **Agente de control por Q-Learning** (local y coordinado).
- **Autodetección de la red**: configura automáticamente los semáforos y sus
  carriles desde el archivo de red (sin configurar nada a mano).
- **Entrenamiento reproducible** con semillas fijas y reanudación.
- **Evaluación rigurosa**: compara IA vs semáforo fijo en 5 escenarios de tráfico
  idénticos, con métricas estándar (viajes completados, espera, duración, time
  loss, velocidad, colas, teleports, colisiones).
- **Coordinación entre vecinos**: señal de presión del semáforo aguas abajo.
- **Herramientas de diagnóstico**: demanda por intersección, localización de
  atascos (teleports) por zona.
- **Demo visual** con SUMO-GUI, incluyendo modo de **dos ventanas simultáneas**
  (fijo vs IA sobre el mismo tráfico) y modo comparar (tabla de métricas).

## 6. Resultado principal (validado)

Los **5 agentes coordinados** superan al semáforo fijo de SUMO, de forma
consistente en 5 escenarios de tráfico (ver `RESULTADOS.md`):

| Métrica | Semáforo fijo | IA coordinada | Mejora |
|---|---:|---:|:--:|
| Vehículos completados | 2418 | **2661** | +243 |
| Espera promedio (s) | 291.9 | **282.0** | −9.9 |
| Teleports (atascos) | 972 | **775** | −197 |

*(Cifras de una corrida de demo con semilla 42; la evaluación de 5 semillas da
una mejora consistente — ver `RESULTADOS.md` y `evaluacion_coordinado.csv`.)*

**Hallazgo central:** lo que mejora el tráfico no es poner IA en más semáforos,
sino que los agentes se **coordinen**. Agentes aislados o cobertura amplia sin
coordinar fueron inestables o peores; la coordinación en corredores conectados
fue lo que ganó.

## 7. Cómo verlo funcionar

Requiere SUMO instalado (ver `README.md` para instalación). Luego:

```powershell
# Demo: IA coordinada vs semáforo fijo, dos ventanas a la vez
python .\demo_coordinado.py --modo dual

# Solo la tabla de métricas (sin ventanas, más rápido)
python .\demo_coordinado.py --modo comparar
```

## 8. Fuentes (estado de la semaforización en Bogotá)

- Secretaría de Movilidad / Alcaldía de Bogotá — Sistema Centralizado de
  Semaforización y red semafórica:
  https://bogota.gov.co/mi-ciudad/movilidad/alerta-sobre-robo-y-vandalismo-semaforos-en-bosa-y-kennedy-bogota
- Laboratorio público de semaforización e IA con videodetección:
  https://www.elespectador.com/bogota/como-predecir-los-trancones-de-bogota-asi-funciona-el-primer-laboratorio-de-semaforos-del-pais/
- Semaforización inteligente de Bogotá (contexto):
  https://bogota.gov.co/mi-ciudad/movilidad/asi-funcionaran-los-semaforos-inteligentes-en-bogota

*(Contenido de las fuentes reformulado para cumplir restricciones de licencia.)*

## 9. Limitaciones honestas

- Es una simulación (SUMO), no un despliegue real.
- La mejora validada es sobre 5-6 intersecciones coordinadas en corredores.
- Los "teleports" son una limitación propia del simulador, no del controlador.
- Escalar a más intersecciones requiere coordinarlas, no solo añadirlas.
