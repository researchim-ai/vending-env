"""
LLM tool-loop агент: контекст (sliding window), вызов инструментов, memory tools (план 8.2, 7).
Использует один и тот же ToolRuntime (та же бизнес-логика, что и для RL).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from vending_env.tools.tool_runtime import ToolRuntime
from vending_env.tools.tool_schemas import MAIN_AGENT_TOOLS
from vending_env.tools.memory import Scratchpad, KVStore


@dataclass
class ToolCall:
    name: str
    args: Dict[str, Any]
    result: str
    terminated: bool


@dataclass
class LLMAgentLoop:
    """
    Цикл: получить ответ от LLM (текст + опционально tool_calls), выполнить инструменты,
    добавить результаты в историю, передать в LLM последние N сообщений (sliding window).
    """
    def __init__(
        self,
        runtime: Optional[ToolRuntime] = None,
        max_history_messages: int = 100,
        max_tokens_context: Optional[int] = 30000,
    ):
        self.runtime = runtime or ToolRuntime()
        self.max_history_messages = max_history_messages
        self.max_tokens_context = max_tokens_context
        self.scratchpad = Scratchpad()
        self.kv_store = KVStore()
        self._history: List[Dict[str, Any]] = []
        self._tool_schemas = MAIN_AGENT_TOOLS

    def get_system_prompt(self) -> str:
        return (
            "You operate a vending machine. Your goal is to maximize net worth (cash + inventory value). "
            "You can: get_money_balance, get_storage_inventory, read_inbox, send_email (to suppliers like supplier_1, body: 'product_name quantity'), "
            "search_products, wait_for_next_day (to get morning report), sub_agent_specs, run_sub_agent(instruction), chat_with_sub_agent(question). "
            "Order from suppliers by email (to_addr=supplier_1, body with lines like 'cola 50'). "
            "Delivery takes 2-5 days; check storage after delivery. Use run_sub_agent to restock machine, set prices, collect cash. "
            "Daily fee $2 is charged each day. You go bankrupt after 10 consecutive days unable to pay."
        )

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Список инструментов для LLM (включая memory)."""
        memory_tools = [
            {"name": "scratchpad_write", "description": "Write to scratchpad.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
            {"name": "scratchpad_read", "description": "Read last K entries from scratchpad.", "parameters": {"type": "object", "properties": {"last_k": {"type": "integer"}}, "additionalProperties": False}},
            {"name": "kv_put", "description": "Store key-value.", "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}},
            {"name": "kv_get", "description": "Get value by key.", "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}},
        ]
        return list(self._tool_schemas) + memory_tools

    def execute_tool(self, name: str, args: Dict[str, Any]) -> tuple[str, bool]:
        """Выполнить один инструмент (включая memory). Возвращает (message, terminated)."""
        if name == "scratchpad_write":
            return self.scratchpad.write(args.get("text", "")), False
        if name == "scratchpad_read":
            return self.scratchpad.read(args.get("last_k", 10)), False
        if name == "kv_put":
            return self.kv_store.put(args.get("key", ""), args.get("value", "")), False
        if name == "kv_get":
            return self.kv_store.get(args.get("key", "")), False
        return self.runtime.run_main_tool(name, args)

    def add_assistant_message(self, content: str, tool_calls: Optional[List[Dict]] = None) -> None:
        self._history.append({"role": "assistant", "content": content, "tool_calls": tool_calls or []})

    def add_tool_result(self, tool_name: str, result: str, terminated: bool) -> None:
        self._history.append({"role": "tool", "name": tool_name, "content": result, "terminated": terminated})

    def get_context_messages(self) -> List[Dict[str, Any]]:
        """Последние N сообщений для контекста (sliding window)."""
        return list(self._history[-self.max_history_messages:])

    def run_step(self, llm_callback: Callable[[str, List[Dict], List[Dict]], Dict]) -> tuple[bool, Optional[str]]:
        """
        Один шаг: вызвать llm_callback(system_prompt, context_messages, tools),
        ожидать ответ с content и опционально tool_calls; выполнить инструменты; вернуть (terminated, error).
        llm_callback возвращает {"content": str, "tool_calls": [{"name": str, "args": dict}]}.
        """
        system = self.get_system_prompt()
        context = self.get_context_messages()
        tools = self.get_available_tools()
        response = llm_callback(system, context, tools)
        content = response.get("content", "")
        tool_calls = response.get("tool_calls", [])
        self.add_assistant_message(content, tool_calls)
        if not tool_calls:
            return False, None
        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {})
            msg, term = self.execute_tool(name, args)
            self.add_tool_result(name, msg, term)
            if term:
                return True, msg
        return False, None
