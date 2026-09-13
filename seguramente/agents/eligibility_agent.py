"""Agente de Elegibilidade.

Wrapper que importa a tool de elegibilidade do módulo tools.
"""

from __future__ import annotations

from ..tools.eligibility_tool import check_insured_eligibility

__all__ = ["check_insured_eligibility"]
