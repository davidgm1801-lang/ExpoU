import traci

SUMO_BINARY = "sumo-gui"

traci.start([
    SUMO_BINARY,
    "-c", "simulation.sumocfg"
])

try:
    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()

finally:
    traci.close()