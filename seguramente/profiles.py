"""Carga de perfis de segurados a partir do banco SQLite.

Modulo legado que lia CSV diretamente. Agora delega ao Database.
Mantido para compatibilidade com scripts/run_demo.py.
"""

from __future__ import annotations

from .database import get_database
from .models import InsuredProfile


def load_profiles() -> list[InsuredProfile]:
    """Carrega todos os perfis do banco SQLite."""
    db = get_database()
    return db.load_profiles()
