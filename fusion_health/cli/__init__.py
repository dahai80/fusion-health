from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Fusion-Health — Local AI healthcare assistant")
    parser.add_argument("--mlx-url", default=None, help="fusion-mlx URL (default: from config/env)")
    parser.add_argument("--model", default=None, help="Model name (default: from config/env)")
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

    sub.add_parser("tui", help="Interactive TUI mode")

    p = sub.add_parser("chat", help="Multi-turn conversation")
    p.add_argument("--session", default=None, help="Resume session ID or path")
    p.add_argument("--system-prompt", default=None, help="Custom system prompt")

    p = sub.add_parser("batch", help="Batch process files")
    p.add_argument("--dir", required=True, help="Input directory")
    p.add_argument("--action", required=True, choices=["ehr_summary", "ehr_vitals", "code_icd10", "compliance_audit", "tcm_analyze"])
    p.add_argument("--pattern", default="*.txt", help="File glob pattern")
    p.add_argument("--output-dir", default=None, help="Output directory for results")
    p.add_argument("--concurrency", type=int, default=3, help="Max concurrent tasks")

    p = sub.add_parser("template", help="Template rendering")
    p.add_argument("action", choices=["render", "list", "init"])
    p.add_argument("--name", default=None, help="Template name")
    p.add_argument("--data", default=None, help="JSON data file for rendering")
    p.add_argument("--output", default="", help="Output file path")

    sub.add_parser("version", help="Show version")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    from fusion_health.config import HealthConfig
    config = HealthConfig.from_env()
    if args.mlx_url:
        config.mlx_url = args.mlx_url
    if args.model:
        config.model = args.model

    if args.command == "version":
        print("Fusion-Health v1.0.0")
    elif args.command == "tui":
        from fusion_health.cli.tui import run_tui
        run_tui(config)
    elif args.command == "chat":
        asyncio.run(_cmd_chat(args, config))
    elif args.command == "batch":
        asyncio.run(_cmd_batch(args, config))
    elif args.command == "template":
        _cmd_template(args, config)
    elif args.command == "ehr":
        asyncio.run(_cmd_ehr(args, config))
    elif args.command == "code":
        asyncio.run(_cmd_code(args, config))
    elif args.command == "literature":
        asyncio.run(_cmd_literature(args, config))
    elif args.command == "compliance":
        asyncio.run(_cmd_compliance(args, config))


async def _cmd_ehr(args, config):
    from fusion_health.ehr.processor import EHRProcessor
    text = Path(args.input).read_text(encoding="utf-8", errors="replace")
    ehr = EHRProcessor(config=config)
    if args.action == "summary":
        result = await ehr.generate_summary(text)
    elif args.action == "discharge":
        result = await ehr.generate_discharge_summary(text, "", "")
    else:
        result = await ehr.extract_vitals(text)
    output = json.dumps(result, indent=2, ensure_ascii=False) if isinstance(result, dict) else str(result)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


async def _cmd_code(args, config):
    from fusion_health.insurance.coder import InsuranceCoder
    text = Path(args.input).read_text(encoding="utf-8", errors="replace") if Path(args.input).exists() else args.input
    coder = InsuranceCoder(config=config)
    if args.action == "icd10":
        result = await coder.suggest_icd_codes(text)
    elif args.action == "cpt":
        result = await coder.suggest_cpt_codes(text)
    else:
        result = await coder.audit_claim({"text": text})
    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


async def _cmd_literature(args, config):
    from fusion_health.literature.retriever import LiteratureRetriever
    lit = LiteratureRetriever(config=config)
    results = await lit.search(args.query, args.max_results)
    output = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


async def _cmd_compliance(args, config):
    from fusion_health.compliance.checker import ComplianceChecker
    text = Path(args.input).read_text(encoding="utf-8", errors="replace")
    cc = ComplianceChecker(config=config)
    if args.action == "audit":
        result = await cc.audit_documentation(text)
    else:
        result = await cc.check_regulatory_compliance(args.type, text)
    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


async def _cmd_chat(args, config):
    from fusion_health.conversation import ConversationSession
    session = ConversationSession(config)
    if args.session:
        p = Path(args.session)
        if p.exists():
            session.load(p)
            print(f"Resumed session: {session.memory.session_id}")
        else:
            session.start(session_id=args.session, system_prompt=args.system_prompt)
            print(f"Started session: {session.memory.session_id}")
    else:
        sid = session.start(system_prompt=args.system_prompt)
        print(f"Started session: {sid}")
    print("Type 'quit' to exit, 'save' to save conversation.\n")
    while True:
        try:
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "save":
            session.save()
            print("Conversation saved.\n")
            continue
        result = await session.chat(user_input)
        if result.content:
            print(f"AI> {result.content}\n")
        else:
            print(f"AI> [Error: {result.error}]\n")
    await session.close()
    print("Bye.")


async def _cmd_batch(args, config):
    from fusion_health.batch import BatchProcessor
    bp = BatchProcessor(config, max_concurrent=args.concurrency)
    output_dir = Path(args.output_dir) if args.output_dir else None
    result = await bp.process_directory(
        directory=Path(args.dir),
        action=args.action,
        pattern=args.pattern,
        output_dir=output_dir,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


def _cmd_template(args, config):
    from fusion_health.templates import TemplateEngine
    engine = TemplateEngine(config)
    if args.action == "list":
        templates = engine.list_templates()
        for t in templates:
            print(f"  {t}")
    elif args.action == "init":
        TemplateEngine.init_default_templates()
        print("Default templates initialized.")
    elif args.action == "render":
        if not args.name:
            print("Error: --name required for render")
            return
        context = {}
        if args.data:
            context = json.loads(Path(args.data).read_text(encoding="utf-8"))
        result = engine.render(args.name, context)
        if args.output:
            Path(args.output).write_text(result, encoding="utf-8")
        else:
            print(result)
