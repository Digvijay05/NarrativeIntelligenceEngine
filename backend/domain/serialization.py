import json
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any

class StrictForensicEncoder(json.JSONEncoder):
    """
    JSON Encoder that prioritizes Fidelity over Flexibility.
    
    RULES:
    1. Dates MUST be ISO 8601 strings (UTC).
    2. Enums MUST use their .value.
    3. Decimals MUST be preserved as strings (to avoid float precision loss) or floats if safe.
       (For D3 visualization, floats are usually required, but for storage, strings are better.
        We will use float for UI compatibility but ensure high precision).
    4. Sets -> Lists (sorted for determinism).
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, Decimal):
            return float(obj) # for frontend D3 compatibility
        if isinstance(obj, (set, frozenset)):
            return sorted(list(obj))
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "__dataclass_fields__"):
            from dataclasses import asdict
            return asdict(obj)
            
        return super().default(obj)
