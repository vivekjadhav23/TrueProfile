import json
from pathlib import Path
from jsonschema import validate

class Validator:
    """
    Validates canonical Candidate profiles against schemas/output_schema.json.
    """
    def __init__(self):
        base_path = Path(__file__).resolve().parent.parent
        self.schema_path = base_path / "schemas" / "output_schema.json"
        with self.schema_path.open(mode='r', encoding='utf-8') as sf:
            self.schema = json.load(sf)

    def validate(self, candidate_data: dict) -> None:
        """
        Validate the candidate data against the schema.
        """
        validate(instance=candidate_data, schema=self.schema)
