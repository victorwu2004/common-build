"""DB2 text-to-SQL agent powered by the GitHub Copilot SDK.

The Copilot agent is given two tools — get_schema and run_query — and a system
instruction telling it to inspect the schema, write a read-only DB2 query, run
it, and self-correct on error. The permission handler is the hard security gate:
it denies any run_query whose SQL is not read-only, regardless of what the model
generates.

Install:  pip install github-copilot-sdk ibm_db
Auth:     run `copilot` CLI login once, OR set COPILOT_GITHUB_TOKEN / GH_TOKEN,
          OR configure BYOK (see docs/auth/byok.md in the copilot-sdk repo).
"""

import asyncio
import json
import os
import sys

from copilot import CopilotClient
from copilot.tools import Tool, ToolInvocation, ToolResult
from copilot.session import PermissionHandler

from .db2 import Db2

MODEL = os.getenv("COPILOT_MODEL", "gpt-5")

SYSTEM_INSTRUCTION = """\
You are a DB2 database analyst. To answer a question:
1. Call get_schema first to learn the tables, columns, and foreign keys.
2. Write ONE read-only DB2 SQL query (SELECT or WITH only).
   - Use DB2 syntax: FETCH FIRST n ROWS ONLY (never LIMIT).
   - Never write INSERT/UPDATE/DELETE/DROP/ALTER/MERGE/CALL.
3. Call run_query with that SQL.
4. If run_query returns an error, read it, fix the SQL, and try again.
5. When you have results, summarize the answer for the user in plain language
   and show the SQL you ran.
"""


def build_tools(db: Db2) -> list[Tool]:
    """Wrap DB2 methods as Copilot SDK tools."""

    async def _get_schema(_: ToolInvocation) -> ToolResult:
        try:
            schema = db.get_schema()
            return ToolResult(
                text_result_for_llm=schema,
                result_type="success",
                session_log="Returned DB2 schema",
            )
        except Exception as e:  # surface to the agent so it can react
            return ToolResult(
                text_result_for_llm=f"ERROR getting schema: {e}",
                result_type="error",
                session_log=f"Schema error: {e}",
            )

    async def _run_query(inv: ToolInvocation) -> ToolResult:
        sql = inv.arguments.get("sql", "")
        try:
            result = db.run_query(sql)
            return ToolResult(
                text_result_for_llm=json.dumps(result, default=str),
                result_type="success",
                session_log=f"Ran query, {result['row_count']} rows",
            )
        except Exception as e:
            return ToolResult(
                text_result_for_llm=f"QUERY ERROR: {e}. Revise the SQL and retry.",
                result_type="error",
                session_log=f"Query error: {e}",
            )

    return [
        Tool(
            name="get_schema",
            description="Return DB2 tables, columns, and foreign-key relationships.",
            parameters={"type": "object", "properties": {}},
            handler=_get_schema,
        ),
        Tool(
            name="run_query",
            description="Execute a read-only DB2 SELECT/WITH query and return rows.",
            parameters={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A read-only DB2 SELECT or WITH query.",
                    }
                },
                "required": ["sql"],
            },
            handler=_run_query,
        ),
    ]


def make_permission_handler():
    """Hard security gate. Approves read-only tools; denies anything that would
    execute non-read-only SQL — even if the model tries to. This is independent
    of, and in addition to, the read-only DB2 account you should connect with."""

    async def handler(request):
        # File system / shell / web tools: deny outright for a DB agent.
        kind = getattr(request, "kind", None)
        if kind in ("shell", "write", "url"):
            return "denied"

        # Custom-tool calls: only allow our two tools; gate run_query SQL.
        name = getattr(request, "tool_name", None) or getattr(request, "name", None)
        if name == "get_schema":
            return "approved"
        if name == "run_query":
            args = getattr(request, "arguments", {}) or {}
            try:
                Db2.validate(args.get("sql", ""))  # raises if not read-only
                return "approved"
            except Exception:
                return "denied"
        return "denied"

    return handler


async def ask(question: str) -> None:
    db = Db2()
    tools = build_tools(db)
    try:
        async with CopilotClient() as client:
            async with await client.create_session(
                on_permission_request=make_permission_handler(),
                model=MODEL,
                tools=tools,
                # system_prompt customization is supported via the SDK; the
                # simplest portable approach is to prepend the instruction to
                # the first prompt:
            ) as session:
                done = asyncio.Event()

                def on_event(event):
                    etype = getattr(event.type, "value", event.type)
                    if etype == "assistant.message":
                        print(event.data.content, end="", flush=True)
                    elif etype == "session.idle":
                        done.set()
                    elif etype == "session.error":
                        print(f"\n[session error] {event.data}", file=sys.stderr)
                        done.set()

                session.on(on_event)
                await session.send(
                    {"prompt": f"{SYSTEM_INSTRUCTION}\n\nUSER QUESTION: {question}"}
                )
                await done.wait()
                print()
    finally:
        db.close()


def main():
    if len(sys.argv) < 2:
        print('Usage: python -m db2_agent.agent "your question"')
        sys.exit(1)
    asyncio.run(ask(" ".join(sys.argv[1:])))


if __name__ == "__main__":
    main()
