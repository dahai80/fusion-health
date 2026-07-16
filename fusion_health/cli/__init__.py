"""Fusion-Health CLI."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Fusion-Health — Local AI healthcare assistant")
    parser.add_argument("--mlx-url", default="http://localhost:11434/v1", help="fusion-mlx URL")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("ehr", help="EHR processing")
    p.add_argument("action", choices=["summary", "discharge", "vitals"])
    p.add_argument("--input", required=True, help="Input file path")
    p.add_argument("--output", default="", help="Output file path")

    p = sub.add_parser("code", help="Medical coding")
    p.add_argument("action", choices=["icd10", "cpt", "audit"])
    p.add_argument("--input", required=True, help="Input text or file")
    p.add_argument("--output", default="")

    p = sub.add_parser("literature", help="Clinical literature search")
    p.add_argument("query", help="Search query")
    p.add_argument("--max-results", type=int, default=5)
    p.add_argument("--output", default="")

    p = sub.add_parser("compliance", help="Compliance checking")
    p.add_argument("action", choices=["audit", "regulatory"])
    p.add_argument("--input", required=True)
    p.add_argument("--type", default="clinical_note")
    p.add_argument("--output", default="")

    sub.add_parser("version", help="Show version")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help(); sys.exit(1)
    if args.command == "version":
        print("Fusion-Health v0.1.0")
    elif args.command == "ehr":
        asyncio.run(_cmd_ehr(args))
    elif args.command == "code":
        asyncio.run(_cmd_code(args))
    elif args.command == "literature":
        asyncio.run(_cmd_literature(args))
    elif args.command == "compliance":
        asyncio.run(_cmd_compliance(args))


async def _cmd_ehr(args):
    from fusion_health.ehr.processor import EHRProcessor
    text = Path(args.input).read_text(encoding="utf-8", errors="replace")
    ehr = EHRProcessor(mlx_url=args.mlx_url)
    if args.action == "summary":
        result = await ehr.generate_summary(text)
    elif args.action == "discharge":
        result = await ehr.generate_discharge_summary(text, "", "")
    else:
        result = await ehr.extract_vitals(text)
    output = str(result)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


async def _cmd_code(args):
    from fusion_health.insurance.coder import InsuranceCoder
    text = Path(args.input).read_text(encoding="utf-8", errors="replace") if Path(args.input).exists() else args.input
    coder = InsuranceCoder(mlx_url=args.mlx_url)
    if args.action == "icd10":
        result = await coder.suggest_icd_codes(text)
    elif args.action == "cpt":
        result = await coder.suggest_cpt_codes(text)
    else:
        result = await coder.audit_claim({"text": text})
    output = str(result)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


async def _cmd_literature(args):
    from fusion_health.literature.retriever import LiteratureRetriever
    lit = LiteratureRetriever(mlx_url=args.mlx_url)
    results = await lit.search(args.query, args.max_results)
    import json
    output = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


async def _cmd_compliance(args):
    from fusion_health.literature.retriever import ComplianceChecker
    text = Path(args.input).read_text(encoding="utf-8", errors="replace")
    cc = ComplianceChecker(mlx_url=args.mlx_url)
    if args.action == "audit":
        result = await cc.audit_documentation(text)
    else:
        result = await cc.check_regulatory_compliance(args.type, text)
    import json
    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)