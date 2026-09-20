"""
ASTRA Capability Input Schema Validator.
Validates input parameter dictionaries against capability JSON Schemas before execution.
"""

from typing import Any
from src.core.capabilities.errors import CapabilityValidationError


class SchemaValidator:
    """Lightweight, deterministic JSON Schema validator for capability input parameters."""

    TYPE_MAP = {
        "string": (str,),
        "number": (int, float),
        "integer": (int,),
        "boolean": (bool,),
        "array": (list, tuple),
        "object": (dict,),
    }

    @classmethod
    def validate(
        cls,
        parameters: dict[str, Any],
        schema: dict[str, Any],
        capability_id: str = "unknown",
        raise_on_error: bool = False,
    ) -> tuple[bool, list[str]]:
        """
        Validate parameters against schema.
        Returns (is_valid, list_of_error_strings).
        If raise_on_error is True, raises CapabilityValidationError on failure.
        """
        errors: list[str] = []

        if not isinstance(parameters, dict):
            errors.append(f"Input parameters must be a dictionary, got {type(parameters).__name__}")
            if raise_on_error:
                raise CapabilityValidationError(capability_id, errors)
            return False, errors

        # 1. Check required fields
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in parameters:
                errors.append(f"Missing required parameter: '{field}'")

        # 2. Check property types & constraints
        properties = schema.get("properties", {})
        for param_name, param_val in parameters.items():
            if param_name not in properties:
                # Disallow unexpected parameters if additionalProperties is False
                if schema.get("additionalProperties") is False:
                    errors.append(f"Unrecognized parameter '{param_name}' is not allowed")
                continue

            prop_def = properties[param_name]
            expected_type_str = prop_def.get("type")

            # Check type if defined
            if expected_type_str and expected_type_str in cls.TYPE_MAP:
                allowed_types = cls.TYPE_MAP[expected_type_str]
                # Special case: bool is subclass of int in Python
                if expected_type_str == "integer" and isinstance(param_val, bool):
                    errors.append(f"Parameter '{param_name}' expected integer, got boolean")
                elif expected_type_str == "number" and isinstance(param_val, bool):
                    errors.append(f"Parameter '{param_name}' expected number, got boolean")
                elif not isinstance(param_val, allowed_types):
                    errors.append(
                        f"Parameter '{param_name}' expected type '{expected_type_str}', "
                        f"got '{type(param_val).__name__}'"
                    )

            # Check enum constraint
            enum_values = prop_def.get("enum")
            if enum_values and param_val not in enum_values:
                errors.append(
                    f"Parameter '{param_name}' value '{param_val}' is not one of allowed values: {enum_values}"
                )

            # Check minLength / maxLength for strings
            if isinstance(param_val, str):
                min_len = prop_def.get("minLength")
                if min_len is not None and len(param_val) < min_len:
                    errors.append(f"Parameter '{param_name}' length must be >= {min_len}")
                max_len = prop_def.get("maxLength")
                if max_len is not None and len(param_val) > max_len:
                    errors.append(f"Parameter '{param_name}' length must be <= {max_len}")

            # Check minimum / maximum for numbers
            if isinstance(param_val, (int, float)) and not isinstance(param_val, bool):
                minimum = prop_def.get("minimum")
                if minimum is not None and param_val < minimum:
                    errors.append(f"Parameter '{param_name}' must be >= {minimum}")
                maximum = prop_def.get("maximum")
                if maximum is not None and param_val > maximum:
                    errors.append(f"Parameter '{param_name}' must be <= {maximum}")

        is_valid = len(errors) == 0
        if not is_valid and raise_on_error:
            raise CapabilityValidationError(capability_id, errors)

        return is_valid, errors
