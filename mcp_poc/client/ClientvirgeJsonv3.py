# integration_example.py
"""
Run:
  pip install mcp python-dotenv openai
  echo "CHATGPT_KEY=sk-..." > .env
  python integration_example.py
"""

import asyncio, json, logging, os, sys
import re
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
from urllib.parse import urlsplit

from dotenv import load_dotenv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from openai import AsyncOpenAI
from pydantic.v1.json import pydantic_encoder

# ---------- setup ----------
load_dotenv()
CHATGPT_KEY = os.getenv("CHATGPT_KEY")
if not CHATGPT_KEY:
    raise RuntimeError("CHATGPT_KEY is missing. Put it in .env or your environment.")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

# Create server parameters once and reuse
server_params = StdioServerParameters(
    command=sys.executable,
    args=["-u", "../server/virgeJson.py"],
    env={**os.environ, "PYTHONUNBUFFERED": "1"},
    cwd=PROJECT_ROOT,
)

_PLACEHOLDER_RE = re.compile(r"{([^}/]+)}")

MAX_REQUEST_STEPS = 25


# ---------- OpenAI wrapper ----------
class ChatGPTLLM:
    def __init__(self, api_key: str, model_name: str = "gpt-4o"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model_name = model_name

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        try:
            resp = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip() if resp.choices else ""
        except Exception as e:
            logger.exception("OpenAI error")
            return f"<<LLM error: {e}>>"


# ---------- helpers ----------


def _typename(x):
    if x is None:
        return "null"
    t = type(x).__name__
    return {
        "str": "string",
        "int": "number",
        "float": "number",
        "bool": "boolean",
        "list": "array",
        "dict": "object",
    }.get(t, t)


def _sample(v):
    try:
        s = json.dumps(v, ensure_ascii=False, default=str)
    except Exception:
        s = str(v)
    return s


def summarize_payload(data, *, max_keys=30, max_rows=5) -> str:
    if isinstance(data, dict):
        keys = list(data.keys())[:max_keys]
        lines = [f"type: object  | keys: {len(data)}"]
        for k in keys:
            v = data[k]
            lines.append(f"• {k}: {_typename(v)} = {_sample(v)}")
        if len(data) > max_keys:
            lines.append(f"… +{len(data)-max_keys} more keys")
        return "\n".join(lines)

    # array
    if isinstance(data, list):
        n = len(data)
        lines = [f"type: array  | length: {n}"]
        if n == 0:
            return "\n".join(lines + ["(empty)"])

        first = data[0]
        if isinstance(first, dict):
            cols = sorted(set().union(*[set(d.keys()) for d in data[:200]]))
            show_cols = cols[:max_keys]
            lines.append(f"element: object  | columns: {len(cols)}")
            if cols:
                lines.append(
                    "columns: "
                    + ", ".join(show_cols)
                    + (f", … +{len(cols)-len(show_cols)}" if len(cols) > len(show_cols) else "")
                )
            take = data[:max_rows]
            lines.append(f"samples ({len(take)}):")
            for i, row in enumerate(take, 1):
                preview = {k: row.get(k) for k in show_cols[:8]}
                lines.append(f"  {i}. " + _sample(preview))
            return "\n".join(lines)

        else:
            take = [_sample(x) for x in data[:max_rows]]
            lines.append(f"element: {_typename(first)}")
            lines.append("samples: " + ", ".join(take))
            return "\n".join(lines)

    return f"type: {_typename(data)}  | value: {_sample(data)}"


def _safe_json(obj) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    return s


def uri_to_path(uri: str) -> str:
    # accepts "api://path?..." or plain "/path"
    if uri.startswith("api://"):
        parts = urlsplit(uri.replace("api://", "scheme://", 1))
        return "/" + parts.path.lstrip("/")
    return "/" + uri.lstrip("/")


def path_segments(path: str) -> list[str]:
    return [seg for seg in path.strip("/").split("/") if seg]


def strip_param_segments(path: str) -> str:
    segs = [s for s in path_segments(path) if not _PLACEHOLDER_RE.fullmatch(s)]
    return "/" + "/".join(segs)


def suggest_discovery_paths(uri_template: str, index_paths: list[str]) -> list[str]:
    path = uri_to_path(uri_template)
    parent = strip_param_segments(path)
    non_param_paths = [p for p in index_paths if "{" not in p and "}" not in p]

    cands = []
    # exact parent
    if parent in non_param_paths:
        cands.append(f"api://{parent.lstrip('/')}?limit=50")

    # top-level entity (first segment)
    segs = path_segments(path)
    if segs:
        root = f"/{segs[0]}"
        if root in non_param_paths and f"api://{root.lstrip('/')}" not in cands:
            cands.append(f"api://{root.lstrip('/')}?limit=50")

    # de-dup while keeping order
    seen = set()
    out = []
    for u in cands:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _tool_payload_from_result(tr) -> Optional[dict]:
    first = tr.content[0]
    text = getattr(first, "text", None) or getattr(first, "content", None)
    if isinstance(text, (str, bytes)):
        try:
            return json.loads(text)
        except Exception:
            return {"raw": text.decode() if isinstance(text, bytes) else text}


def _extract_templates(resp) -> list:
    for attr in ("resource_templates", "templates", "items", "resourceTemplates"):
        val = getattr(resp, attr, None)
        if isinstance(val, list) and val:
            return val
    try:
        lst = list(resp)
        if lst:
            return lst
    except Exception:
        pass
    return []


def _templ_repr(t) -> dict:
    """
    Create a uniform dict for a template regardless of field naming.
    """
    # Possible names across versions
    uri_t = getattr(t, "uri_template", None) or getattr(t, "uriTemplate", None) or getattr(t, "uri", None) or ""
    name = getattr(t, "name", None) or getattr(t, "title", None) or getattr(t, "description", None) or uri_t
    desc = getattr(t, "description", None) or ""
    return {"name": name, "uri_template": uri_t, "description": desc}


# ---------- MCP calls ----------
async def discover_catalog(session) -> dict:
    resources = []
    index_paths = []
    templates = []

    try:
        response = await session.list_resources()
        for r in response.resources:
            name = getattr(r, "name", None) or getattr(r, "title", None) or getattr(r, "uri", "")
            uri = getattr(r, "uri", "")
            resources.append({"name": name, "uri": uri})

    except Exception as e:
        logger.info(f"list_resources unavailable: {e}")

    try:
        response = await session.list_resource_templates()
        tmpl_list = _extract_templates(response)
        templates = [_templ_repr(t) for t in tmpl_list]

    except Exception as e:
        logger.info("list_resource_templates unavailable: %s", e)

    try:
        rr = await session.read_resource(uri="api://index")
        content = getattr(rr, "content", None) or getattr(rr, "contents", None)
        txt = content[0].text if isinstance(content, list) and content and hasattr(content[0], "text") else str(content)
        idx = json.loads(txt)
        if isinstance(idx.get("get_paths"), list):
            index_paths = idx["get_paths"]

    except Exception:
        pass

    candidates = []
    for p in index_paths:
        if "{" not in p and "}" not in p:
            uri = f"api://{p.lstrip('/')}"
            candidates.append(uri)
            if p.rstrip("/").endswith("shops"):
                candidates.append(uri + "?limit=50")

    if any(t.get("uri_template") == "api://{path*}" for t in templates):
        seen = set()
        candidates = [x for x in candidates if not (x in seen or seen.add(x))]

    logger.info("*------------Discovery-start-------*")
    logger.info(
        "During discovery the following was found %d for templates (preview: %s)",
        len(templates),
        [t["uri_template"] for t in templates[:10]],
    )
    logger.info(
        "During discovery the following was found %d for resources (preview: %s)",
        len(resources),
        [t for t in resources[:10]],
    )
    logger.info(
        "During discovery the following was found %d for index_paths (preview: %s)",
        len(index_paths),
        [t for t in index_paths[:10]],
    )
    logger.info(
        "During discovery the following was found %d for candidates (preview: %s)",
        len(candidates),
        [t for t in candidates[:10]],
    )
    logger.info("*------------Discovery-end---------*\n\n")


    return {
        "resources": resources,
        "templates": templates,
        "index_paths": index_paths,
        "candidates": candidates,
    }


async def execute_mcp_action(session, action: dict, *, index_paths: list[str] | None = None) -> dict:
    logger.info("*----------MCP-call-start----------*")
    atype = action.get("type")

    if atype == "read_resource":
        uri = action.get("uri")
        if not uri:
            logger.info("MCP call skipped: read_resource missing 'uri'")
            return {"ok": False, "error": "Missing 'uri' for read_resource"}

        if bool(_PLACEHOLDER_RE.search(uri)):
            params = _PLACEHOLDER_RE.findall(uri or "")
            discover = suggest_discovery_paths(uri, index_paths or [])
            logger.info(
                "MCP READ_RESOURCE blocked uri=%s reason=templated params=%s discover=%s", uri, params, discover[:3]
            )
            return {
                "ok": False,
                "error": f"URI is a template that requires parameters: {params}",
                "needs": {"path_params": params, "uri_template": uri},
                "suggest": discover,  # model/user can pick one
            }

        logger.info("MCP READ_RESOURCE start uri=%s", uri)
        try:
            rr = await session.read_resource(uri=uri)
            content = getattr(rr, "content", None) or getattr(rr, "contents", None)
            txt = (
                content[0].text
                if isinstance(content, list) and content and hasattr(content[0], "text")
                else str(content)
            )
            try:
                data = json.loads(txt)
            except Exception:
                data = txt
            logger.info("MCP READ_RESOURCE done  uri=%s ok=True size=%s", uri, len(_safe_json(data)))
            return {"ok": True, "data": data}
        except Exception as e:
            logger.info("MCP READ_RESOURCE done  uri=%s ok=False err=%s", uri, e)
            return {"ok": False, "error": str(e)}

    logger.info("MCP call skipped: unsupported action type=%s", atype)
    return {"ok": False, "error": f"Unsupported action type: {atype}"}


# ---------- orchestration ----------
PLANNER_SYSTEM = (
    "You are an AI helper agent in a developer environment for the Virge shop. You are connected to a MCP server which is connected to a the Virge shop API \n"
    "You receive a catalog (resources, templates, index_paths, candidates)."
    "Once a user asks you a question you can help answer their question by using the catalog."
    "You can use multiple steps to get to their answer, once that answer has been reached you can stop"
    'by returning {"type":"none"}.'
    f"Keep in minda that you have a limited amount of steps you can perform this amount is {MAX_REQUEST_STEPS}"
    "To call the MCP tools you can use the following STRICT SINGLE-LINE JSON format:\n"
    '  {"type":"read_resource","uri":"api://...","why":"<<=20 words high-level purpose>>"}\n'
    '  {"type":"ask_user","question":"...","why":"<<=20 words>>"}\n'
    '  {"type":"none","why":"<<=20 words why you are done>>"}\n'
    "Chaining guidance:\n"
    " - If the user asks for something like a shop or user by NAME (e.g., 'Kingswood reptiles'), make sure that you have explored any logically connected list endpoints. "
    "   (e.g., api://shops or api://shops), fuzzy-match the shop (or user name etc...) by name, then use its ID or NAME to read the shop’s"
    "   products (e.g., api://shops/<id>/products or another discovered products endpoint from index_paths/templates). "
    " - If multiple matches exist, use ask_user to show them what they can choose from and/or is the most applicable.\n"
    "Rules:\n"
    " - NEVER return a templated URI containing braces (e.g., api://users/{user_id}).\n"
    " - NEVER use call_tool for URIs beginning with 'api://'. Those are resources; use read_resource with 'uri'."
    " - ONLY use known endpoints that you know from the catalog"
    "Output ONLY JSON; no extra text."
)

FINALIZER_SYSTEM = (
    "You are a concise assistant. You may receive multiple 'Previous tool results' entries. "
    "Summarize the final, user-relevant outcome. If the last tool failures indicate missing "
    "parameters, name them and either present suggested discovery URIs or ask for the ID."
)

def _json_fallback(o):
    try:
        return pydantic_encoder(o)
    except Exception:
        return str(o)


@asynccontextmanager
async def mcp_session():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def process_user_query(query: str, llm) -> str:
    async with mcp_session() as session:
        catalog = await discover_catalog(session)
        catalog_blob = json.dumps(catalog, ensure_ascii=False, default=str)

        history_snippets: list[str] = []
        followup_notes: list[str] = []

        max_steps = MAX_REQUEST_STEPS
        status = "no-op"


        logger.info("*---------Starting-planning--------*")
        for step in range(max_steps):
            planner_messages = [
                {"role": "system", "content": PLANNER_SYSTEM},
                {"role": "system", "content": "Catalog:\n" + catalog_blob},
            ]
            if history_snippets:
                planner_messages.append(
                    {
                        "role": "system",
                        "content": "Previous tool results (most recent last):\n" + "\n".join(history_snippets[-max_steps:]),
                    }
                )
            if followup_notes:
                planner_messages.append(
                    {
                        "role": "system",
                        "content": "User follow-ups provided in this session:\n" + "\n".join(followup_notes[-max_steps:]),
                    }
                )
            planner_messages.append({"role": "user", "content": query})

            plan_raw = await llm.generate(planner_messages)
            logger.info("Planner output: %s", plan_raw)
            try:
                plan = json.loads(plan_raw) if isinstance(plan_raw, str) else {"type": "none"}
            except Exception:
                plan = {"type": "none"}
            logger.info(f"Planner step: {step + 1}: %s", _safe_json(plan))

            if plan.get("type") == "none":
                status = "done"
                break

            if plan.get("type") == "ask_user":
                question = plan.get("question") or "I need more information. Please provide details."
                print("\n[Assistant needs info]")
                print(question)
                user_answer = input("\nYour answer: ").strip()
                followup_notes.append(f"Q: {question}\nA: {user_answer}")
                query = f"{query}\n\nFollow-up answer: {user_answer}"
                continue

            if plan.get("type") in ("read_resource", "call_tool"):
                exec_result = await execute_mcp_action(session, plan, index_paths=catalog.get("index_paths") or [])
                status = "success" if exec_result.get("ok") else "failed"

                # build a compact preview for humans
                if exec_result.get("ok"):
                    preview = summarize_payload(exec_result.get("data"))
                    print("\n[resource return preview]")
                    print(preview)
                    history_snippets.append(
                        f"Action: {json.dumps(plan)}\nPreview:\n{preview}\nResult: {_safe_json(exec_result)}"
                    )
                else:
                    history_snippets.append(f"Action: {json.dumps(plan)}\nResult: {_safe_json(exec_result)}")

                if not exec_result.get("ok"):
                    continue

                working_ctx = exec_result
                continue

        # Finalize with everything we’ve gathered
        final_messages = [{"role": "system", "content": FINALIZER_SYSTEM}]
        if history_snippets:
            final_messages.append(
                {"role": "system", "content": "Previous tool results:\n" + "\n\n".join(history_snippets)}
            )
        if followup_notes:
            final_messages.append({"role": "system", "content": "User follow-ups:\n" + "\n\n".join(followup_notes)})
        final_messages.append({"role": "system", "content": f"Action status: {status}"})
        final_messages.append({"role": "user", "content": query})
        return await llm.generate(final_messages)


# ---------- demo ----------
async def main():
    llm = ChatGPTLLM(api_key=CHATGPT_KEY, model_name="gpt-4o-mini")

    print("MCP + OpenAI MVP\n")

    # Add predefined questions list
    predefined_questions = [
        "Show all endpoints that are available please.",
        "Can you list all shops?",
        "How can i find out what products are available in the shop of Kingswood reptiles?",
        "Out of all the shops, which one has the most products?",
        "How many products does the reptile shop have",
        "Get the total amount of products for the first 5 shops you can find and also for the kingswood reptiles shop and then tell me what shop has the most products",
    ]

    while True:
        # Display menu
        print("\nAvailable options:")
        print("1. Enter a custom question")
        print("2. Choose from predefined questions")
        print("3. Exit")

        choice = input("\nEnter your choice (1-3): ")

        if choice == "1":
            question = input("\nEnter your question: ")
            if question.lower().strip() == "exit":
                break
            ans = await process_user_query(question,llm)
            print(f"\nQ: {question}\nA: {ans}\n")

        elif choice == "2":
            print("\nPredefined questions:")
            for i, q in enumerate(predefined_questions, 1):
                print(f"{i}. {q}")
            try:
                q_num = int(input("\nSelect question number (or 0 to go back): "))
                if q_num == 0:
                    continue
                if 1 <= q_num <= len(predefined_questions):
                    question = predefined_questions[q_num - 1]
                    ans = await process_user_query(question,llm)
                    print(f"\nQ: {question}\nA: {ans}\n")
                else:
                    print("Invalid question number!")
            except ValueError:
                print("Please enter a valid number!")

        elif choice == "3":
            print("Exiting...")
            break

        else:
            print("Invalid choice! Please select 1, 2, or 3.")


if __name__ == "__main__":
    asyncio.run(main())
