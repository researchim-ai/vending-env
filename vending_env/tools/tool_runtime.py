"""
Исполнение инструментов: вызов sim + sub-agent (план 2, 6).
Один и тот же core.sim используется для RL и LLM — разные контроллеры.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from vending_env.config import EnvConfig
from vending_env.core.sim import Sim, SimStepResult
from vending_env.agents.subagent.executor import SubAgentExecutor
from .tool_schemas import MAIN_AGENT_TOOL_NAMES, SUB_AGENT_TOOL_NAMES


class ToolRuntime:
    """
    Выполняет вызовы инструментов main-agent против Sim.
    wait_for_next_day вызывает sim.end_day_and_report(); остальные — sim.apply_tool_step + логику.
    """
    def __init__(self, config: Optional[EnvConfig] = None, seed: Optional[int] = None):
        from vending_env.config import EnvConfig as DefaultConfig
        self.config = config or DefaultConfig()
        self._seed = seed
        self.sim = Sim(self.config, seed)
        self.sub_agent = SubAgentExecutor(self.sim)
        self._terminated = False
        self._termination_reason: Optional[str] = None

    def setup_default_suppliers(self) -> None:
        """Зарегистрировать поставщиков по умолчанию (для тестов и демо)."""
        from vending_env.data import get_default_suppliers
        for s in get_default_suppliers():
            self.sim.register_supplier(s)

    @property
    def suppliers(self):
        return self.sim.suppliers

    def execute(
        self,
        tool_name: str,
        args: Optional[Dict[str, Any]] = None,
        *,
        is_sub_agent: bool = False,
    ) -> tuple[str, Optional[SimStepResult], bool]:
        """
        Выполнить инструмент.
        Returns: (result_message, sim_step_result_if_any, terminated).
        """
        args = args or {}
        if is_sub_agent:
            ok, msg = self.sub_agent.run_tool(tool_name, args)
            return msg, None, False

        if tool_name not in MAIN_AGENT_TOOL_NAMES:
            return f"Unknown tool: {tool_name}", None, False

        if self._terminated:
            return "Simulation already terminated.", None, True

        # Время двигаем для всех инструментов кроме wait_for_next_day
        if tool_name != "wait_for_next_day":
            step = self.sim.apply_tool_step(tool_name, args)
        else:
            step = None

        if tool_name == "get_money_balance":
            s = self.sim.state
            return (
                f"Cash at hand: ${s.cash_balance:.2f}. Cash in machine (not collected): ${s.cash_in_machine:.2f}.",
                step,
                False,
            )

        if tool_name == "get_storage_inventory":
            s = self.sim.state
            if not s.storage_inventory:
                return "Storage is empty.", step, False
            lines = ["Storage inventory:"]
            for item_id, qty in sorted(s.storage_inventory.items()):
                lines.append(f"  {item_id}: {qty}")
            return "\n".join(lines), step, False

        if tool_name == "read_inbox":
            s = self.sim.state
            if not s.inbox:
                return "Inbox is empty.", step, False
            lines = []
            for e in s.inbox[-20:]:
                status = "read" if e.is_read else "unread"
                lines.append(f"[{status}] From: {e.from_addr} | Subject: {e.subject}\n{e.body[:300]}")
                e.is_read = True
            return "\n---\n".join(lines), step, False

        if tool_name == "send_email":
            from vending_env.core.state import Email
            to_addr = str(args.get("to_addr", "")).strip()
            subject = str(args.get("subject", ""))
            body = str(args.get("body", ""))
            if not to_addr:
                return "Error: to_addr required.", step, False
            s = self.sim.state
            s.outbox.append(Email(
                email_id=s.next_email_id(),
                from_addr="agent",
                to_addr=to_addr,
                subject=subject,
                body=body,
                day_sent=s.current_day,
            ))
            result = self.sim.process_order_email("agent", to_addr, subject, body)
            # Ответ поставщика в inbox
            self.sim.state.inbox.append(Email(
                email_id=self.sim.state.next_email_id(),
                from_addr=to_addr,
                to_addr="agent",
                subject=result.reply_subject,
                body=result.reply_body,
                day_sent=self.sim.state.current_day,
            ))
            if result.success:
                return f"Email sent. Order confirmed: {result.order.order_id}. ETA day {result.order.eta_day}.", step, False
            if result.error_message:
                return f"Email sent. Supplier replied: {result.reply_body[:400]}", step, False
            return f"Email sent. Reply: {result.reply_body[:400]}", step, False

        if tool_name == "search_products":
            query = str(args.get("query", "")).strip() or "all"
            prods = self.sim.suppliers.product_catalog()
            if not prods:
                return "No product catalog loaded. Register suppliers first.", step, False
            lines = ["Products (register suppliers to see prices):"]
            for item_id, info in list(prods.items())[:30]:
                lines.append(f"  {item_id}: ${info.wholesale_price:.2f} ({info.size_class})")
            return "\n".join(lines), step, False

        if tool_name == "wait_for_next_day":
            res = self.sim.end_day_and_report()
            self._terminated = res.terminated
            self._termination_reason = res.termination_reason
            report = res.daily_report
            if not report:
                return "Next day.", res, res.terminated
            lines = [
                f"--- Morning report, Day {report.day} ---",
                f"Sales yesterday: {report.sales}",
                f"Cash collected yesterday: ${report.cash_collected_yesterday:.2f}",
                f"Deliveries: {report.deliveries}",
                f"New emails: {len(report.new_emails)}",
            ]
            return "\n".join(lines), res, res.terminated

        if tool_name == "sub_agent_specs":
            return (
                "Sub-agent can: machine_inventory, stock_from_storage(item_id, quantity, slot_id), set_price(item_id, price), collect_cash. "
                "Use run_sub_agent(instruction) or chat_with_sub_agent(question).",
                step,
                False,
            )

        if tool_name == "run_sub_agent":
            instruction = str(args.get("instruction", ""))
            r = self.sub_agent.run_instruction(instruction)
            # Время за run_sub_agent уже учтено в apply_tool_step выше — но мы не вызывали apply_tool_step для run_sub_agent до этого блока. Мы вызываем apply_tool_step в начале для всех != wait_for_next_day. So run_sub_agent already advanced time. Good.
            return r.message, step, False

        if tool_name == "chat_with_sub_agent":
            question = str(args.get("question", ""))
            return self.sub_agent.chat(question), step, False

        return "Tool not implemented.", step, False

    def run_main_tool(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> tuple[str, bool]:
        """Удобная обёртка: (message, terminated)."""
        msg, _, term = self.execute(tool_name, args or {}, is_sub_agent=False)
        return msg, term

    @property
    def state(self):
        return self.sim.state
