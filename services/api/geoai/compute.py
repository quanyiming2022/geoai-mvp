from typing import Protocol
from .models import ModelAdapter


class ComputeProvider(Protocol):
    def execute(self, query: dict, prompt: dict) -> dict: ...
    def healthcheck(self) -> dict: ...


class MockComputeProvider:
    def __init__(self, adapter: ModelAdapter):
        if adapter.model_info()["id"] != "mock-v1":
            raise ValueError("P0 compute accepts only the mock model")
        self.adapter = adapter

    def execute(self, query, prompt):
        return self.adapter.postprocess(
            self.adapter.predict(
                self.adapter.prepare_query(query), self.adapter.prepare_prompt(prompt)
            )
        )

    def healthcheck(self):
        return self.adapter.healthcheck()
