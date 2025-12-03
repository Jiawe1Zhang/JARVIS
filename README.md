# Jarvis Agent — MCP + Multi-LLM + RAG

Inspired by Iron Man’s J.A.R.V.I.S. (name also echoes mine). Goal: build a from-scratch MCP client and agent stack without heavy frameworks, then evolve into a multi-LLM, multi-vector, industrial-grade RAG system.

## What’s inside
- **Agent orchestrator**: drives prompts, calls tools, stitches LLM + retrieval + MCP tools.
- **MCP client**: lightweight Python client over stdio; one client connects to one MCP server; each server can expose many tools.
- **LLM layer**: pluggable providers (OpenAI-compatible for now), targeting on-prem runs via vLLM/Ollama/HF.
- **Retrieval layer**: simple in-memory vector store today; will grow to Faiss/Milvus with richer chunking/parsing.
- **Tools**: sourced from MCP servers (e.g., fetch/filesystem) plus custom domain tools later.

## Architecture sketch
1) Ingest docs → chunk/embed → store in vector DB  
2) User query → retrieve context → craft system/user messages  
3) LLM responds; if tool calls are suggested → route via MCP client → execute tool → feed results back  
4) Return grounded answer (and optionally diagrams/code)

## Quickstart
```bash
python -m src.main
```
Env vars (`.env`):
```
OPENAI_API_KEY=...
OPENAI_BASE_URL=...   # if using a custom endpoint / proxy
EMBEDDING_BASE_URL=...
EMBEDDING_KEY=...
```

## Roadmap / TODO
- [ ] Stdio MCP client hardening (reconnect, timeouts, multi-session support)
- [ ] Tool registry/dispatcher per server with richer schema surfacing
- [ ] Local LLM runners: vLLM / Ollama / HF backends
- [ ] Quantized models (GGUF/AWQ) for constrained boxes
- [ ] Multi-LLM routing/failover abstraction
- [ ] Retrieval backends: Faiss + Milvus; hybrid sparse+dense search
- [ ] Ingestion: PDF/CSV/Markdown/HTML with smarter chunking/windowing
- [ ] Extraction: tables/diagrams/metadata for indexing
- [ ] Diagram path: emit Mermaid/Graphviz DOT and render
- [ ] Domain DSL generation with few-shot/RAG guidance + schema checks
- [ ] RAG eval harness (context precision/recall, faithfulness)
- [ ] Correctness checks for diagrams/code via parsers/sim
- [ ] Tuning hooks: LoRA/QLoRA when retrieval isn’t enough
- [ ] On-prem friendly deploy recipes; config-driven pipelines
- [ ] Observability: logging/traces; latency/retrieval/model/tool metrics

## References
- MCP: https://modelcontextprotocol.io/
- RAG basics: https://scriv.ai/guides/retrieval-augmented-generation-overview/
- Vector DBs: https://milvus.io/, https://faiss.ai/
