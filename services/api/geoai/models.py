from typing import Protocol


class ModelAdapter(Protocol):
    def prepare_prompt(self, prompt: dict) -> dict: ...
    def prepare_query(self, query: dict) -> dict: ...
    def predict(self, query: dict, prompt: dict) -> dict: ...
    def postprocess(self, prediction: dict) -> dict: ...
    def healthcheck(self) -> dict: ...
    def model_info(self) -> dict: ...


class MockAdapter:
    def prepare_prompt(self, prompt):
        if not prompt.get("support_mask"):
            raise ValueError("Visual support mask is required")
        return prompt

    def prepare_query(self, query):
        width, height = query.get("width", 0), query.get("height", 0)
        if (
            not isinstance(width, int)
            or not isinstance(height, int)
            or not (1 <= width <= 512 and 1 <= height <= 512)
        ):
            raise ValueError("Mock query dimensions must be 1..512")
        return query

    def predict(self, query, prompt):
        query = self.prepare_query(query)
        self.prepare_prompt(prompt)
        return {"probabilities": [0.75] * (query["width"] * query["height"]), "mock": True}

    def postprocess(self, prediction):
        return prediction

    def healthcheck(self):
        return {"status": "ok", "provider": "mock"}

    def model_info(self):
        return {"id": "mock-v1", "usage_policy": "internal_only", "mock": True}


class ResearchSkySensePPAdapter:
    def model_info(self):
        return {"id": "skysensepp-research", "usage_policy": "research_only", "enabled": False}

    def healthcheck(self):
        return {"status": "disabled", "reason": "Research worker is outside P0 scope"}

    def prepare_prompt(self, prompt):
        raise NotImplementedError("Research worker is not enabled")

    def prepare_query(self, query):
        raise NotImplementedError("Research worker is not enabled")

    def predict(self, query, prompt):
        raise NotImplementedError("Research worker is not enabled")

    def postprocess(self, prediction):
        raise NotImplementedError("Research worker is not enabled")


class GeoExtractProductionAdapter(ResearchSkySensePPAdapter):
    def model_info(self):
        return {
            "id": "production-unconfigured",
            "usage_policy": "commercial_license_required",
            "enabled": False,
        }
