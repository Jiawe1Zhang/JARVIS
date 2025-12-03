import asyncio
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from src.mcp.agent import Agent
from src.mcp.mcp_client import MCPClient
from src.prompts.presets import SYSTEM_PROMPT
from src.config.loader import load_user_config
from src.utils import log_title
from src.rag.context import retrieve_context


def main() -> None:
    load_dotenv()
    cfg = load_user_config()

    # --- 用户可配置区 ---
    llm_cfg = cfg.get("llm", {})
    embed_cfg = cfg.get("embedding", {})
    knowledge_globs = cfg.get("knowledge_globs", ["knowledge/*.md"])
    output_dir = Path(cfg.get("output_dir", "output")).resolve()

    # 任务模板完全由用户配置决定（未提供则为空）
    task_template = cfg.get("task_template", "")

    # LLM/Embedding 端点/env 由用户配置决定（未填则回落到已有 env）
    if llm_cfg.get("base_url"):
        os.environ["OPENAI_BASE_URL"] = llm_cfg["base_url"]
    if llm_cfg.get("api_key"):
        os.environ["OPENAI_API_KEY"] = llm_cfg["api_key"]
    # 如果用户未提供 key，又使用本地端点，给占位符
    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("OPENAI_BASE_URL"):
        os.environ["OPENAI_API_KEY"] = "ollama"

    if embed_cfg.get("base_url"):
        os.environ["EMBEDDING_BASE_URL"] = embed_cfg["base_url"]
    if embed_cfg.get("api_key"):
        os.environ["EMBEDDING_KEY"] = embed_cfg["api_key"]

    output_dir = Path.cwd() / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    task_text = task_template.format(output_path=str(output_dir))

    context = retrieve_context(task_text, knowledge_globs, embed_cfg.get("model", "BAAI/bge-m3"))

    # 根据配置初始化 MCP servers
    mcp_clients = []
    for server in cfg.get("mcp_servers", []):
        args = [arg.replace("{output_dir}", str(output_dir)) for arg in server.get("args", [])]
        mcp_clients.append(MCPClient(command=server["command"], args=args))

    model_name = llm_cfg.get("model") or os.getenv("LLM_MODEL", "gpt-5")
    agent = Agent(model_name, mcp_clients, context=context, system_prompt=SYSTEM_PROMPT)

    async def run_agent():
        await agent.init()
        try:
            await agent.invoke(task_text)
        finally:
            await agent.close()

    asyncio.run(run_agent())


if __name__ == "__main__":
    main()
