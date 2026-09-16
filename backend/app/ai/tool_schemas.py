"""
Gemini function-declaration schemas for the Phase 1 tools. Kept separate
from tools.py so the "what Gemini is told about the tool" and "what the
tool actually does" stay easy to compare side by side.
"""

TOOL_DECLARATIONS = [
    {
        "name": "search_party",
        "description": "Search for a customer/party by name or phone number. Use this when the user refers to a party by a partial or approximate name.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Name or phone number (or part of one) to search for"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_party_balance",
        "description": "Get the outstanding balance and overdue amount for a specific party by name.",
        "parameters": {
            "type": "object",
            "properties": {
                "party_name": {"type": "string", "description": "The party's name, as close to exact as possible"},
            },
            "required": ["party_name"],
        },
    },
    {
        "name": "get_business_summary",
        "description": "Get overall business totals: total receivable, total overdue, total payable to suppliers, and the biggest overdue parties. Use this for general questions like 'how much is outstanding' or 'what's overdue'.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_stock",
        "description": "Get current stock quantity for a specific item, broken down by location.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string", "description": "The item's name, as close to exact as possible"},
            },
            "required": ["item_name"],
        },
    },
    {
        "name": "get_low_stock_items",
        "description": "List every item currently below its configured reorder threshold, across all locations combined.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "calculate",
        "description": "Evaluate a plain arithmetic expression (numbers and + - * / % parentheses only) exactly, rather than computing it yourself. Always use this for any calculation rather than doing the arithmetic mentally, even simple-looking ones.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "A plain arithmetic expression, e.g. '250000 * 0.05' or '(1250*50)+2000'"},
            },
            "required": ["expression"],
        },
    },
]

# Maps a tool name to the actual Python function that implements it -
# built lazily inside agent.py to avoid a circular import with tools.py.
