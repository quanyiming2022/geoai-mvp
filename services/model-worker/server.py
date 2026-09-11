"""Remote entry point; uses the common HTTP contract, never database credentials."""
from research_adapter import ResearchSkySensePPAdapter
from geoai import model_worker

model_worker.adapter=ResearchSkySensePPAdapter()
app=model_worker.app
app.title='GeoAI Research Model Worker'
