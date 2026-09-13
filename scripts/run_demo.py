#!/usr/bin/env python3
"""Executa uma demonstração reproduzível do MVP e salva evidência JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from fixtures import FIXTURES
from seguramente.llm import build_provider
from seguramente.pipeline import run_pipeline_from_observation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=sorted(FIXTURES), default="chuva_intensa")
    parser.add_argument(
        "--provider", choices=["openai", "template"], default="template"
    )
    parser.add_argument("--output", default="evidence/demo_run.json")
    parser.add_argument("--simulate", action="store_true")
    args = parser.parse_args()

    observation = FIXTURES[args.scenario]()
    result = run_pipeline_from_observation(
        requested_location=observation.location,
        observation=observation,
        provider=build_provider(args.provider),
        approve_simulation=args.simulate,
    )
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(output.relative_to(ROOT)),
                "event": result.event.event_type,
                "eligible": sum(d.status == "elegivel" for d in result.decisions),
                "blocked": sum(d.status == "bloqueado" for d in result.decisions),
                "messages": len(result.messages),
                "simulations": len(result.simulations),
                "provider": args.provider,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
