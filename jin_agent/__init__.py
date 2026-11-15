"""JIN Agent - local, stdlib-only research and intelligence agent.

Design rule (from the opencode final plan):
    "LLM ko internet mat do - usay tools do."

The agent is intentionally standalone: it does not import or modify MobileLab.
All data stays under ``J:\\Ai Agent\\jin_agent\\data``.
"""

VERSION = "2.1.0"
POLICY_ID = "SAHULAT-SAFE-SERVICE-v1"
DATE_CHECKED = "2026-11-15"
PLAN_ID = "JIN-AGENT-FINAL-PLAN-P13-P22"

__all__ = ["VERSION", "POLICY_ID", "DATE_CHECKED", "PLAN_ID"]
