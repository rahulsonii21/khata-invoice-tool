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
    {
        "name": "propose_create_party",
        "description": "Check for duplicates and validate details for a new party (customer), WITHOUT creating anything yet. Always call this before confirm_create_party - never create a party without first proposing it and getting the user's explicit yes.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "phone": {"type": "string", "description": "10-digit Indian mobile number, if given"},
                "gstin": {"type": "string"},
                "address": {"type": "string"},
                "city": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "confirm_create_party",
        "description": "Actually creates the party. Only call this after propose_create_party succeeded (requires_confirmation: true) AND the user has explicitly said yes/confirmed - use the exact same arguments from the proposal.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "phone": {"type": "string"},
                "gstin": {"type": "string"},
                "address": {"type": "string"},
                "city": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "propose_create_invoice",
        "description": "Resolve the party and validate an invoice amount, WITHOUT creating anything yet. Always call this before confirm_create_invoice.",
        "parameters": {
            "type": "object",
            "properties": {
                "party_name": {"type": "string"},
                "amount": {"type": "number"},
                "invoice_date": {"type": "string", "description": "YYYY-MM-DD, if given"},
                "due_date": {"type": "string", "description": "YYYY-MM-DD, if given"},
            },
            "required": ["party_name", "amount"],
        },
    },
    {
        "name": "confirm_create_invoice",
        "description": "Actually creates the invoice. Only call this after propose_create_invoice succeeded (requires_confirmation: true) AND the user has explicitly said yes/confirmed - use the exact party_id it returned, not the party name.",
        "parameters": {
            "type": "object",
            "properties": {
                "party_id": {"type": "string"},
                "amount": {"type": "number"},
                "invoice_date": {"type": "string"},
                "due_date": {"type": "string"},
            },
            "required": ["party_id", "amount"],
        },
    },
    {
        "name": "draft_payment_reminder",
        "description": "Draft a WhatsApp payment reminder message for a party with an outstanding balance. This does NOT send anything - there is no server-side WhatsApp sending in this app. It returns the drafted message and the party's phone number, which the app shows as a button the user taps to actually open WhatsApp and send it themselves.",
        "parameters": {
            "type": "object",
            "properties": {
                "party_name": {"type": "string"},
            },
            "required": ["party_name"],
        },
    },
    {
        "name": "propose_stock_transfer",
        "description": "Check that enough stock is available and resolve the item/locations by name for a transfer between two locations, WITHOUT moving anything yet. Always call this before confirm_stock_transfer.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string"},
                "from_location_name": {"type": "string"},
                "to_location_name": {"type": "string"},
                "quantity": {"type": "number"},
            },
            "required": ["item_name", "from_location_name", "to_location_name", "quantity"],
        },
    },
    {
        "name": "confirm_stock_transfer",
        "description": "Actually moves the stock. Only call this after propose_stock_transfer succeeded (requires_confirmation: true) AND the user has explicitly said yes/confirmed - use the exact item_id/from_location_id/to_location_id it returned, not the names.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string"},
                "from_location_id": {"type": "string"},
                "to_location_id": {"type": "string"},
                "quantity": {"type": "number"},
            },
            "required": ["item_id", "from_location_id", "to_location_id", "quantity"],
        },
    },
]

# Maps a tool name to the actual Python function that implements it -
# built lazily inside agent.py to avoid a circular import with tools.py.
