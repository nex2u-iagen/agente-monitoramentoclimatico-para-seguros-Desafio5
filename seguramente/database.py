"""Camada de persistencia SQLite do SeguraMente.

Banco relacional com tabelas para perfis de segurados,
registros de simulacao e logs de execucao dos agentes.

Para popular o banco execute:
    python scripts/seed_db.py --reset
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .models import InsuredProfile, SimulationRecord, utc_now_iso

Base = declarative_base()

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "seguramente.db"


class InsuredProfileRow(Base):
    __tablename__ = "insured_profiles"

    profile_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    product = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    consent = Column(Boolean, nullable=False)
    contact = Column(String, nullable=False)


class SimulationRecordRow(Base):
    __tablename__ = "simulation_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_id = Column(String, nullable=False)
    profile_id = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    recipient = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(String, nullable=False)


class AgentLogRow(Base):
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, nullable=False, index=True)
    agent_name = Column(String, nullable=False)
    action = Column(String, nullable=False)
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    status = Column(String, nullable=False)
    started_at = Column(String, nullable=False)
    completed_at = Column(String, nullable=True)
    duration_ms = Column(Float, nullable=True)
    raw_input = Column(Text, nullable=True)
    raw_output = Column(Text, nullable=True)
    llm_provider = Column(String, nullable=True)
    llm_model = Column(String, nullable=True)
    location = Column(String, nullable=True)


class Database:
    """Encapsula acesso ao SQLite e operacoes CRUD."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connect_args = {"check_same_thread": False}
        self._engine = create_engine(
            f"sqlite:///{self._path}",
            echo=False,
            connect_args=connect_args,
        )
        with self._engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("PRAGMA journal_mode=WAL"))
            conn.commit()
        Base.metadata.create_all(self._engine)
        self._SessionLocal = sessionmaker(bind=self._engine)

    def _session(self) -> Session:
        return self._SessionLocal()

    def load_profiles(self) -> list[InsuredProfile]:
        """Retorna todos os perfis como dataclasses do dominio."""
        with self._session() as session:
            rows = session.query(InsuredProfileRow).all()
        return [
            InsuredProfile(
                profile_id=r.profile_id,
                name=r.name,
                city=r.city,
                state=r.state,
                product=r.product,
                channel=r.channel,
                consent=r.consent,
                contact=r.contact,
            )
            for r in rows
        ]

    def get_distinct_cities(self) -> list[str]:
        """Retorna cidades distintas dos segurados ativos (consent=True)."""
        with self._session() as session:
            rows = (
                session.query(InsuredProfileRow.city)
                .filter(InsuredProfileRow.consent == True)
                .distinct()
                .all()
            )
        return sorted([r[0] for r in rows])

    def save_simulation(self, record: SimulationRecord) -> None:
        """Persiste um registro de simulacao."""
        with self._session() as session:
            session.add(
                SimulationRecordRow(
                    simulation_id=record.simulation_id,
                    profile_id=record.profile_id,
                    channel=record.channel,
                    recipient=record.recipient,
                    text=record.text,
                    status=record.status,
                    created_at=record.created_at,
                )
            )
            session.commit()

    def get_simulations(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna os ultimos registros de simulacao."""
        with self._session() as session:
            rows = (
                session.query(SimulationRecordRow)
                .order_by(SimulationRecordRow.id.desc())
                .limit(limit)
                .all()
            )
        return [
            {
                "simulation_id": r.simulation_id,
                "profile_id": r.profile_id,
                "channel": r.channel,
                "recipient": r.recipient,
                "text": r.text,
                "status": r.status,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    def save_agent_log(
        self,
        run_id: str,
        agent_name: str,
        action: str,
        status: str,
        input_summary: str | None = None,
        output_summary: str | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
        duration_ms: float | None = None,
        raw_input: str | None = None,
        raw_output: str | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        location: str | None = None,
    ) -> None:
        """Persiste log detalhado de ativacao de agente."""
        with self._session() as session:
            session.add(
                AgentLogRow(
                    run_id=run_id,
                    agent_name=agent_name,
                    action=action,
                    input_summary=input_summary,
                    output_summary=output_summary,
                    status=status,
                    started_at=started_at or utc_now_iso(),
                    completed_at=completed_at,
                    duration_ms=duration_ms,
                    raw_input=raw_input,
                    raw_output=raw_output,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    location=location,
                )
            )
            session.commit()

    def get_agent_logs(self, run_id: str) -> list[dict[str, Any]]:
        """Retorna logs de uma execucao especifica."""
        with self._session() as session:
            rows = (
                session.query(AgentLogRow)
                .filter_by(run_id=run_id)
                .order_by(AgentLogRow.id.asc())
                .all()
            )
        return [
            {
                "id": r.id,
                "run_id": r.run_id,
                "agent_name": r.agent_name,
                "action": r.action,
                "input_summary": r.input_summary,
                "output_summary": r.output_summary,
                "status": r.status,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "duration_ms": r.duration_ms,
                "raw_input": r.raw_input,
                "raw_output": r.raw_output,
                "llm_provider": r.llm_provider,
                "llm_model": r.llm_model,
                "location": r.location,
            }
            for r in rows
        ]

    def get_all_agent_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Retorna logs de todas as execucoes."""
        with self._session() as session:
            rows = (
                session.query(AgentLogRow)
                .order_by(AgentLogRow.id.desc())
                .limit(limit)
                .all()
            )
        return [
            {
                "id": r.id,
                "run_id": r.run_id,
                "agent_name": r.agent_name,
                "action": r.action,
                "status": r.status,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "duration_ms": r.duration_ms,
                "location": r.location,
            }
            for r in rows
        ]


_instance: Database | None = None


def get_database(db_path: str | Path | None = None) -> Database:
    """Retorna instancia singleton do Database.

    O banco deve ja estar populado via scripts/seed_db.py.
    """
    global _instance
    if _instance is None:
        _instance = Database(db_path)
    return _instance
