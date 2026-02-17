"""
Декларативное описание инструментов для LLM (название, JSON schema, стоимость по времени) — план 9.
"""
from typing import Any, Dict, List

# Имена инструментов main-agent (статья 2.2)
MAIN_AGENT_TOOL_NAMES = [
    "get_money_balance",
    "get_storage_inventory",
    "read_inbox",
    "send_email",
    "search_products",
    "wait_for_next_day",
    "sub_agent_specs",
    "run_sub_agent",
    "chat_with_sub_agent",
]

# Имена инструментов sub-agent (статья 2.2)
SUB_AGENT_TOOL_NAMES = [
    "machine_inventory",
    "stock_from_storage",
    "set_price",
    "collect_cash",
]

# JSON Schema для каждого инструмента (для LLM tool-calling)
MAIN_AGENT_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_money_balance",
        "description": "Get current cash balance (money at hand) and cash still in the vending machine.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_storage_inventory",
        "description": "Get inventory in storage (warehouse). Items delivered by suppliers appear here.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "read_inbox",
        "description": "Read emails in inbox (supplier replies, delivery notifications).",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "send_email",
        "description": "Send an email (e.g. to supplier: to_addr=supplier_id like supplier_1, body with product names and quantities to order).",
        "parameters": {
            "type": "object",
            "properties": {
                "to_addr": {"type": "string", "description": "Recipient address or supplier ID"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body. For orders use lines like 'product_name quantity' e.g. 'cola 50'"},
            },
            "required": ["to_addr", "subject", "body"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_products",
        "description": "Search for popular vending machine products (returns product list with approximate prices).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (e.g. 'drinks', 'snacks')"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "wait_for_next_day",
        "description": "Advance simulation to the next day. You get a morning report: yesterday's sales, new emails, deliveries. Daily fee is charged.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "sub_agent_specs",
        "description": "Get information about the sub-agent (physical world): available tools and how to use them.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "run_sub_agent",
        "description": "Give instructions to the sub-agent to perform physical actions: restock machine, set prices, collect cash.",
        "parameters": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string", "description": "Natural language instruction for the sub-agent"},
            },
            "required": ["instruction"],
            "additionalProperties": False,
        },
    },
    {
        "name": "chat_with_sub_agent",
        "description": "Ask the sub-agent a question (e.g. what did you do, what is the machine inventory).",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Question for the sub-agent"},
            },
            "required": ["question"],
            "additionalProperties": False,
        },
    },
]

SUB_AGENT_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "machine_inventory",
        "description": "Get current vending machine slot inventory (what items are in which slots, quantities).",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "stock_from_storage",
        "description": "Move items from storage to a vending machine slot. Item must be in storage and slot must match size (small/large).",
        "parameters": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Product ID (e.g. cola, chips)"},
                "quantity": {"type": "integer", "description": "Number of units to put in slot", "minimum": 1},
                "slot_id": {"type": "integer", "description": "Slot index (0-11 for 4x3 machine)"},
            },
            "required": ["item_id", "quantity", "slot_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "set_price",
        "description": "Set selling price for an item (applies to all slots containing this item).",
        "parameters": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Product ID"},
                "price": {"type": "number", "description": "Price per unit", "minimum": 0},
            },
            "required": ["item_id", "price"],
            "additionalProperties": False,
        },
    },
    {
        "name": "collect_cash",
        "description": "Collect cash from the vending machine (adds to balance).",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def get_tool_schema(tool_name: str, for_sub_agent: bool = False) -> Dict[str, Any] | None:
    """Вернуть schema инструмента по имени."""
    pool = SUB_AGENT_TOOLS if for_sub_agent else MAIN_AGENT_TOOLS
    for t in pool:
        if t["name"] == tool_name:
            return t
    return None
