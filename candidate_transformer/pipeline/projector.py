import re
import logging
from typing import Any
from jsonschema import validate
from candidate_transformer.pipeline.normalizer import Normalizer

logger = logging.getLogger(__name__)

def resolve_path(data: dict, path_str: str) -> Any:
    """
    Resolve a value from a dictionary using JSONPath-like syntax.
    Supports keys, array indices (e.g. emails[0]), list-property mapping (e.g. skills[].name),
    and nested path resolution (e.g. skills[0].name).
    Returns None on invalid paths, never crashes.
    """
    if not path_str or not isinstance(data, dict):
        return None

    try:
        # Check for list property mapping [].key (e.g. skills[].name)
        if "[]." in path_str:
            parts = path_str.split("[].")
            array_key = parts[0]
            prop_key = parts[1]

            arr = data.get(array_key)
            if isinstance(arr, list):
                res = []
                for item in arr:
                    if isinstance(item, dict):
                        res.append(item.get(prop_key))
                    else:
                        res.append(item)
                return res
            return None

        # Split by dot notation
        parts = path_str.split(".")
        curr = data
        for part in parts:
            # Check for list indexing array[idx] inside the part
            match_idx = re.match(r'^([^\[]+)\[(\d+)\]$', part)
            if match_idx:
                key = match_idx.group(1)
                idx = int(match_idx.group(2))
                if isinstance(curr, dict):
                    arr = curr.get(key)
                    if isinstance(arr, list) and 0 <= idx < len(arr):
                        curr = arr[idx]
                    else:
                        return None
                else:
                    return None
            else:
                if isinstance(curr, dict):
                    curr = curr.get(part)
                else:
                    return None
        return curr
    except Exception as e:
        logger.debug(f"Error resolving path '{path_str}': {e}")
        return None

class Projector:
    """
    Projects candidate data into custom formats according to dynamic configurations and validates output schemas.
    """
    def __init__(self):
        self.normalizer = Normalizer()

    def run(self, candidate_data: dict) -> dict:
        """
        Baseline runner calling apply with default configuration mapping.
        """
        default_config = {
            "fields": [
                {"path": "full_name", "type": "string"},
                {"path": "emails", "type": "array"},
                {"path": "phones", "type": "array"},
                {"path": "skills", "type": "array"}
            ],
            "include_confidence": True,
            "on_missing": "null"
        }
        return self.apply(candidate_data, default_config)

    def apply(self, canonical: dict, config: dict) -> dict:
        """
        Project the canonical candidate dictionary based on custom config rules.
        """
        output = {}
        on_missing = config.get("on_missing", "null")
        fields_conf = config.get("fields", [])
        
        for field in fields_conf:
            target_path = field.get("path")
            from_path = field.get("from") or target_path
            normalize_type = field.get("normalize")
            f_type = field.get("type", "string")

            # 1. Resolve path value
            val = resolve_path(canonical, from_path)
            
            # Auto-extract string property from dict if target type is string
            if isinstance(val, dict) and f_type == "string":
                val = val.get("name") or val.get("title") or val.get("institution") or str(val)

            # 2. Apply normalization if specified
            if val is not None and val != "" and val != []:
                if normalize_type == "E164":
                    if isinstance(val, list):
                        val = self.normalizer.normalize_phones(val)
                    elif isinstance(val, str):
                        res = self.normalizer.normalize_phones([val])
                        val = res[0] if res else None
                elif normalize_type == "canonical":
                    if isinstance(val, list):
                        val = self.normalizer.normalize_skills(val)
                    elif isinstance(val, str):
                        res = self.normalizer.normalize_skills([val])
                        val = res[0] if res else None

            # 3. Handle missing values based on on_missing policy
            is_missing = (val is None or val == "" or val == [])
            if is_missing:
                if field.get("required") and on_missing == "error":
                    val = f"ERROR: {target_path} is required but missing"
                elif on_missing == "omit":
                    continue
                else:  # "null" or default
                    val = None

            output[target_path] = val

        # 4. Handle confidence toggle
        include_confidence = config.get("include_confidence", False)
        if include_confidence:
            projected_conf = {}
            canonical_conf = canonical.get("per_field_confidence", {})
            for field in fields_conf:
                target_path = field.get("path")
                from_path = field.get("from") or target_path
                # Identify the root canonical key (e.g., 'emails' from 'emails[0]')
                root_key = from_path.split("[")[0].split(".")[0]
                if root_key in canonical_conf:
                    projected_conf[target_path] = canonical_conf[root_key]

            output["overall_confidence"] = canonical.get("overall_confidence")
            output["per_field_confidence"] = projected_conf

        # 5. Build dynamic JSON schema and validate
        properties = {}
        required_fields = []
        for field in fields_conf:
            target_path = field.get("path")
            from_path = field.get("from") or target_path
            f_type = field.get("type")
            
            if not f_type:
                root_key = from_path.split("[")[0].split(".")[0]
                if root_key in ["skills", "experience", "education", "provenance", "emails", "phones"]:
                    f_type = "array"
                elif root_key in ["location", "links"]:
                    f_type = "object"
                elif root_key in ["years_experience", "overall_confidence"]:
                    f_type = "number"
                else:
                    f_type = "string"
            
            # Map JS types from config to JSON schema keywords, allowing null/string (for errors) values
            if f_type == "array" or "[]" in f_type:
                properties[target_path] = {
                    "type": ["array", "null", "string"]
                }
            elif f_type == "object":
                properties[target_path] = {
                    "type": ["object", "null", "string"]
                }
            elif f_type == "integer" or f_type == "number":
                properties[target_path] = {"type": ["number", "null", "string"]}
            elif f_type == "boolean":
                properties[target_path] = {"type": ["boolean", "null", "string"]}
            else:
                properties[target_path] = {"type": ["string", "null"]}

            if field.get("required") and on_missing != "omit":
                required_fields.append(target_path)

        if include_confidence:
            properties["overall_confidence"] = {"type": ["number", "null"]}
            properties["per_field_confidence"] = {
                "type": ["object", "null"],
                "additionalProperties": {"type": "number"}
            }

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": properties,
        }
        if required_fields:
            schema["required"] = required_fields

        # Validate the projected output against dynamic schema
        validate(instance=output, schema=schema)

        return output
