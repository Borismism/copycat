"""
Pytest configuration for integration tests.
"""

import sys
from pathlib import Path

# Add service directories to Python path
project_root = Path(__file__).parent.parent.parent

# Add both services to path
discovery_service_path = project_root / "services" / "discovery-service"
risk_analyzer_service_path = project_root / "services" / "risk-analyzer-service"

if str(discovery_service_path) not in sys.path:
    sys.path.insert(0, str(discovery_service_path))

if str(risk_analyzer_service_path) not in sys.path:
    sys.path.insert(0, str(risk_analyzer_service_path))
