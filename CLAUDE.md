# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

This repository is a Python-based stock analysis and trading suggestion project built around LLM-driven analysis. The main user-facing modes described in the repository are:

- Single-stock analysis
- Batch market scan
- LangGraph multi-role analysis flow
- 2560 strategy analysis
- Tail-session scan for short-term candidates
- Realtime monitoring and fast analysis

There is also a secondary `arbitrage/polymarket` subdomain in the repo. It shares configuration and some model-factory infrastructure with the stock-analysis code, but it is not the main path described in `README.md`.

The main stack visible in `pyproject.toml` is Python, LangChain, LangGraph, Pandas, SQLAlchemy, OpenPyXL, and MySQL-related access.

## Common commands

### Environment and dependency setup

`README.md` currently uses `uv` as the primary workflow:

```bash
uv sync
uv sync --extra polymarket
```

Prefer `uv sync` for dependency setup, and use the `polymarket` extra only on supported non-Windows environments.

Python version notes:

- `.python-version` pins `3.12`
- `pyproject.toml` says `requires-python = ">=3.12,<3.14"`
- `README.md` says Python 3.12 or 3.13

Treat Python 3.12 as the safest baseline when discussing environment issues.

### Main entry points

Single-stock analysis:

```bash
uv run main.py --code 601096
```

Batch analysis:

```bash
uv run main.py --batch --workers 80
```

LangGraph multi-role flow:

```bash
uv run analysisflow.py --code 601096
```

2560 strategy analysis:

```bash
uv run analysis2560.py --code 601096
uv run batch2560.py --workers 80
```

Tail-session scan:

```bash
uv run tail_scan.py --start 14:30 --deadline 14:50 --workers 80 --top 10
```

Realtime analysis:

```bash
uv run realtime_analysis.py
uv run realtime_analysis.py 000001
```

### Helper scripts

The repository also provides `.bat` and `.sh` wrappers for interactive startup, including:

- `run_main.*`
- `run_flow.*`
- `run_realtime.*`
- `run_batch2560.*`
- `run_tail_scan.*`

These helper scripts invoke the Python entry points through `uv run`; prefer matching that convention when giving runnable commands. Prefer these scripts when the user wants the repository’s documented interactive flow.

### Build, lint, and test status

No dedicated build system was found.

No repository-level lint command or lint configuration was found.

No unified test runner configuration was found (`pytest.ini`, `tox.ini`, and CI workflow files were not found during initialization).

Current lightweight validation entry points discovered in the repo include:

```bash
uv run main.py --help
uv run tail_scan.py --help
uv run python arbitrage/polymarket/test/test_model_switching.py
```

Treat the current test situation as script-based and partial, not as a standardized project-wide test suite. Do not assume `pytest`, `tox`, or CI-based repo-wide verification exists.

Most functional runs depend on local database access, LLM credentials, and sometimes external realtime/network services. Prefer help commands and narrow script-level checks before attempting full runs.

## Architecture notes

### Main stock-analysis path

`main.py` is only a CLI dispatcher. The main stock-analysis logic is centered in `analysis.py`.

The high-level flow for the main path is:

1. `main.py` parses CLI arguments
2. `analysis.py` pulls data through `database.py`
3. `analysis.py` computes indicators and applies prefilter logic
4. `agent.py` provides the LLM interface
5. Results are written to Excel in `output/`

### Core shared modules

- `config.py`: central settings definition using `pydantic.v1.BaseSettings`
- `database.py`: unified data-access layer for stock info, history, factors, and realtime quotes; historical/static data come from MySQL, while realtime quotes are fetched from the Tencent quote HTTP endpoint
- `agent.py`: model factory and stock-analysis system prompt
- `analysis.py`: main analysis backbone for indicator calculation, prefiltering, LLM invocation, and Excel export

### Alternative analysis modes

`analysisflow.py` reuses the same data/model foundation but changes the orchestration model: it uses a LangGraph workflow with parallel analyst roles and a final trader node.

`realtime_analysis.py` acts as a realtime wrapper around `Analysis`: it preloads history, synthesizes the current day into a temporary latest K-line, recalculates indicators, and triggers `quick_analysis` when price-change or time thresholds are met.

`tail_analysis.py` is the most pipeline-oriented module in the repository. It performs:

1. Broad market context preload
2. Realtime snapshot collection
3. Rule-based candidate scoring and filtering
4. LLM refinement on the top candidates
5. Excel output of scan results and selected candidates

This is best understood as a “rule-based fast filter + LLM final judgment” workflow, not a naive full-market LLM pass.

`analysis2560.py` and `batch2560.py` form a specialized strategy path that reuses the same infrastructure pattern but applies a dedicated 2560 strategy lens.

### Secondary Polymarket subdomain

`arbitrage/polymarket` is a separate subdomain inside the repository. It shares settings and agent-factory integration, but it should be understood as adjacent to the main stock-analysis workflow rather than identical to it.

## Configuration notes

Configuration is centralized in `config.py` through `pydantic.v1.BaseSettings`, with `.env` support enabled.

Important practical detail: this repository does not behave like a pure “environment variables only” app. `config.py` also contains in-code defaults. When debugging configuration issues, check both:

- `.env`
- `config.py`

The configuration areas include at least:

- Stock database connection
- LLM backend selection and credentials
- Redis settings
- Polymarket-related settings
- Optional factor-analysis toggle

Do not copy sensitive values, API keys, passwords, or internal endpoints into documentation or commits.

## Output and runtime side effects

Generated analysis artifacts are typically written to `output/`.

Examples documented in `README.md` include:

- `output/tail_scan_*.xlsx`
- `output/tail_selected_*.xlsx`

When working in this repository, treat files in `output/` as generated results, not source files.

## Repository facts that are easy to misread

These repository-specific discrepancies are worth remembering:

- `.python-version` pins 3.12, while `README.md` says Python 3.12 or 3.13 and `pyproject.toml` allows `>=3.12,<3.14`
- `README.md` and helper scripts follow a `uv` workflow (`uv sync`, `uv run ...`), while older local guidance may still mention `uv pip install -r pyproject.toml`
- `README.md` lists a top-level `engine.py`, but the database engine actually used by `database.py` is defined in `arbitrage/polymarket/engine.py`

When these sources differ, prefer the current code paths for implementation work, but describe the mismatch explicitly instead of silently rewriting project conventions.

## Practical navigation hints

When starting work, these are usually the first files to inspect:

- `README.md` for documented modes and commands
- `main.py` for the basic CLI entry
- `analysis.py` for the main analysis path
- `analysisflow.py` for LangGraph orchestration
- `realtime_analysis.py` for threshold-triggered realtime behavior
- `tail_analysis.py` for the tail-session pipeline
- `database.py` for data retrieval behavior
- `agent.py` for LLM selection and prompting
- `config.py` for runtime configuration
- `arbitrage/polymarket/engine.py` for the actual engine definitions used by `database.py`
