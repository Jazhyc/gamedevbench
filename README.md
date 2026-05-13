# GameDevBench: Evaluating Agentic Capabilities Through Game Development

Wayne Chi, Yixiong Fang, Arnav Yayavaram, Siddharth Yayavaram, Seth Karten,
Qiuhong Anna Wei, Runkun Chen, Alexander Wang, Valerie Chen, Ameet Talwalkar, Chris Donahue

*Carnegie Mellon University, Princeton University*

[![Project Page](https://img.shields.io/badge/Project-Page-blue.svg)](https://waynechi.com/gamedevbench)
[![arXiv](https://img.shields.io/badge/arXiv-2602.11103-b31b1b.svg)](https://arxiv.org/abs/2602.11103)
[![Hugging Face Paper](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Paper-yellow)](https://huggingface.co/papers/2602.11103)
[![Godot](https://img.shields.io/badge/Godot-4.x-brightgreen.svg)](https://godotengine.org/)

**The first benchmark for evaluating LLM agents on game development tasks in a modern game engine.**

## Abstract

Despite rapid progress on coding agents, progress on their multimodal counterparts has lagged behind. A key challenge is the scarcity of evaluation testbeds that combine the complexity of software development with the need for deep multimodal understanding. Game development provides such a testbed as agents must navigate large, dense codebases while manipulating intrinsically multimodal assets such as shaders, sprites, and animations within a visual game scene. We present **GameDevBench**, the first benchmark for evaluating agents on game development tasks. GameDevBench consists of 132 tasks derived from web and video tutorials. Tasks require significant multimodal understanding and are complex — the average solution requires over three times the amount of lines of code and file changes compared to prior software development benchmarks. Agents still struggle with game development, with the best agent solving only 54.5% of tasks. We find a strong correlation between perceived task difficulty and multimodal complexity, with success rates dropping from 46.9% on gameplay-oriented tasks to 31.6% on 2D graphics tasks. To improve multimodal capability, we introduce two simple image and video-based feedback mechanisms for agents. Despite their simplicity, these methods consistently improve performance, with the largest change being an increase in Claude Sonnet 4.5's performance from 33.3% to 47.7%. We release GameDevBench publicly to support further research into agentic game development.

<p align="center">
  <img src="https://arxiv.org/html/2602.11103v1/imgs/taxonomy-examples.png" alt="GameDevBench task taxonomy" width="90%">
</p>

## Overview

GameDevBench contains **132 game development tasks** to evaluate LLM agents' ability to complete game development problems in the **Godot game engine**. Tasks span four categories — 3D Graphics, 2D Graphics, Gameplay, and UI — and require agents to reason about multimodal assets including shaders, sprites, animations, and visual game scenes.

<p align="center">
  <img src="https://arxiv.org/html/2602.11103v1/imgs/example_workflow.png" alt="GameDevBench example workflow" width="90%">
</p>

## Installation

#### Prerequisites

1. **Godot 4.x** — Download and install from [godotengine.org](https://godotengine.org/download)
   - Ensure `godot` is available in your PATH, or set `GODOT_EXEC_PATH` environment variable

2. **Python 3.10+** — Required for all agents
   - **Python 3.12+** — Required for OpenHands agent

#### Install Agents

Install the agent(s) you want to use:

- **Claude Code** — [Claude Code](https://code.claude.com/docs/en/overview)
- **Codex** — [Codex](https://openai.com/codex/)
- **Gemini CLI** — [Gemini CLI](https://geminicli.com/)
- **OpenHands** — [OpenHands](https://www.openhands.dev/)

#### Setup Tasks

Before running the benchmark, unzip the tasks:

```bash
bash unzip_tasks.sh
```

This will unzip all individual task archives from `tasks/` and `tasks_gt/` in place.

> Tasks are distributed as individual zip files to prevent accidental data leakage.

## Configuration

You can use the built-in plans for `claude-code`, `codex`, and `gemini-cli`, or provide API keys directly. For OpenHands you must provide your own API keys. See [`.env.example`](.env.example) for a complete list of optional environment variables.

## Usage

```bash
uv run python gamedevbench/src/benchmark_runner.py \
  --agent AGENT \
  --model MODEL \
  run --task-list tasks.yaml
```

#### Available Agents

| Agent | Description |
|-------|-------------|
| `claude-code` | Anthropic's Claude Code CLI |
| `codex` | OpenAI Codex |
| `gemini-cli` | Google Gemini CLI |
| `openhands` | OpenHands (requires Python 3.12+) |

#### Command-Line Options

| Option | Description |
|--------|-------------|
| `--agent AGENT` | Agent to use (required) |
| `--model MODEL` | Model name (e.g., `claude-sonnet-4.5-20250929`) |
| `--enable-mcp` | Enable MCP server for screenshot capabilities |
| `--use-runtime-video` | Enable runtime video mode with Godot runtime instructions |
| `--skip-display` | Skip tasks that require display |
| `run --task-list FILE` | Run tasks from YAML file (e.g., `tasks.yaml`) |

## Platform Limitations

- MCP server screenshot functionality (`--enable-mcp`) currently only works on **macOS**
  - Uses AppleScript for display capture
  - Requires setting `GODOT_SCREENSHOT_DISPLAY` environment variable to correct display number

## Results

Benchmark results are saved to `results/` directory with the following information:
- Task success/failure status
- Token usage and costs
- Execution time
- Validation results

## Citation

If you find GameDevBench useful, please cite our paper:

```bibtex
@misc{chi2026gamedevbenchevaluatingagenticcapabilities,
      title={GameDevBench: Evaluating Agentic Capabilities Through Game Development},
      author={Wayne Chi and Yixiong Fang and Arnav Yayavaram and Siddharth Yayavaram and Seth Karten and Qiuhong Anna Wei and Runkun Chen and Alexander Wang and Valerie Chen and Ameet Talwalkar and Chris Donahue},
      year={2026},
      eprint={2602.11103},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2602.11103},
}
```

## License
