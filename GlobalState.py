# GlobalState.py
from MapOrchestrator import MapOrchestrator
from pathlib import Path

# This path should point to the base file
BASE_BOUNDARY_PATH = "C:\\Users\\ianmi\\Computer Programs\\Local_Election_forecaster\\data\\County Electoral Division (May 2025) Boundaries EN BFE\\CED_MAY_2025_EN_BFC.shp"

# Initialize the orchestrator globally once
map_orchestrator = MapOrchestrator(str(BASE_BOUNDARY_PATH))


