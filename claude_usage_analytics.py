"""Analytics engine for Claude Code token usage.

Pure functions: records in, stats out. No CLI logic.
"""

# API pricing per 1M tokens (USD)
API_PRICING = {
    "opus": {
        "input": 15.00,
        "output": 75.00,
        "cache_write": 18.75,
        "cache_read": 1.50,
    },
    "sonnet": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "haiku": {
        "input": 0.80,
        "output": 4.00,
        "cache_write": 1.00,
        "cache_read": 0.08,
    },
}

_MODEL_KEYWORDS = ["opus", "sonnet", "haiku"]


def resolve_model_name(model_str: str) -> str:
    """Map a full model string to a pricing key.

    Returns 'opus', 'sonnet', 'haiku', or 'unknown'.
    """
    lower = model_str.lower()
    for kw in _MODEL_KEYWORDS:
        if kw in lower:
            return kw
    return "unknown"


def get_record_cost(rec: dict) -> float:
    """Calculate equivalent API cost for a single record in USD."""
    model_key = resolve_model_name(rec.get("model", ""))
    if model_key == "unknown":
        return 0.0

    pricing = API_PRICING[model_key]
    cost = (
        rec["input_tokens"] * pricing["input"]
        + rec["output_tokens"] * pricing["output"]
        + rec["cache_creation_input_tokens"] * pricing["cache_write"]
        + rec["cache_read_input_tokens"] * pricing["cache_read"]
    ) / 1_000_000
    return cost
