# AI Architecture: Principal AI Architect cum Engineer

Hands-on portfolio following the *AI Agent Architect: Learning Path and Toolkit* (Stages 0–8 + capstone + Principal layer).
Every stage runs **Theory → Why and what → Hands-on → Checkpoint**, and every build ships with code, tests, a C4 diagram and at least one ADR.

## Progress

| Stage | Topic | Zone | Branch | Status |
|---|---|---|---|---|
| 0 | [Python for AI](stage-0-python-for-ai/) | Base | `feature/stage0` | 🟡 Hands-on done, drills pending |
| 1 | AI foundations: ML, tokens, transformers, embeddings | Base | `feature/stage1` | ⚪ |
| 2 | First LLM application: OpenAI, Claude, Gemini, cloud, Ollama | Base | `feature/stage2` | ⚪ |
| 3 | RAG and knowledge engineering | **Master** | `feature/stage3` | ⚪ |
| 4 | Agents, tools, MCP, A2A, LangGraph | **Master** | `feature/stage4` | ⚪ |
| 5 | Evals, observability, red teaming | **Master** | `feature/stage5` | ⚪ |
| 6 | Enterprise platforms and integration | Apply | `feature/stage6` | ⚪ |
| 7 | Production: security, cost, deployment | Apply | `feature/stage7` | ⚪ |
| 8 | Architect level: patterns, governance, ROI | End | `feature/stage8` | ⚪ |
| ★ | Capstone: Enterprise autonomous procurement AI platform | — | `feature/capstone` | ⚪ |

Portfolio projects: **P1** Multi-model document analysis assistant (Stage 2+) · **P2** Multi-agent procurement workflow (Stage 4–5) · **P3** Enterprise AI governance platform (Stage 7–8).

## Branch workflow

```
main ──────────────●──────────────●──────────── …
                  ↑ merge         ↑ merge
feature/stage0 ──●●●┘            │
feature/stage1 ──────────●●●●●───┘
```

1. `git switch main && git pull && git switch -c feature/stageN`
2. Build the stage's hands-on, commit in small steps.
3. When the stage **checkpoint** is passed, open a PR `feature/stageN → main` and merge.
4. Nothing is committed directly to `main`.

## Repo layout

```
stage-N-<topic>/          one self-contained uv project per stage
  src/  tests/  data/
  docs/c4-*.md            C4 diagram(s), Mermaid
  docs/adr/NNNN-*.md      Architecture Decision Records
  README.md               theory map, how to run, drills, checkpoint
notes/                    one page per concept, in my own words
docs/templates/           ADR and note templates
.github/workflows/ci.yml  lint + tests for every stage on each push/PR
```

## Prerequisites

Python 3.13 · [uv](https://docs.astral.sh/uv/) · Git · VS Code. Later stages add Docker, Node/TypeScript, cloud CLIs and model API keys (kept in `.env`, never committed).
