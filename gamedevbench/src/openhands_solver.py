#!/usr/bin/env python3
"""
OpenHands solver for gamedev benchmark tasks.
Uses OpenHands SDK with MCP server for Godot screenshots.
"""

import json
import time
import os
import threading
from typing import Optional

from pydantic import SecretStr
from openhands.sdk import (
    LLM,
    Conversation,
    Event,
    get_logger,
    Agent,
)
from openhands.sdk.security.confirmation_policy import NeverConfirm
from openhands.tools.preset.default import get_default_tools, get_default_condenser
from gamedevbench.src.base_solver import BaseSolver
from gamedevbench.src.mcp_registry import DEFAULT_MCP_SERVER
from gamedevbench.src.utils.constants import HARD_CAP_GRACE
from gamedevbench.src.utils.data_types import SolverResult, TokenUsage
from gamedevbench.src.utils.prompts import create_system_prompt
from gamedevbench.src.utils.llm_keys import resolve_api_base, resolve_provider_api_key


logger = get_logger(__name__)


def _terminate_process_tree(pid: int, term_grace: float = 3.0) -> int:
    """Kill every descendant process of ``pid`` (not ``pid`` itself).

    The hard cap calls this when the cooperative soft timeout can't interrupt a
    solver step blocked inside a child subprocess — e.g. a hung MCP/godot
    process holding a stdio read. Killing the descendants closes those pipes so
    the blocked call unwinds and ``conversation.run()`` can return, and it reaps
    the orphaned ``godot``/``node`` processes that would otherwise leak. Only
    descendants of this worker are touched, so sibling workers are unaffected.
    Best-effort: returns the number of processes signalled (0 if psutil is
    unavailable or there are no children).
    """
    try:
        import psutil
    except Exception:
        return 0
    try:
        children = psutil.Process(pid).children(recursive=True)
    except Exception:
        return 0
    for child in children:
        try:
            child.terminate()
        except Exception:
            pass
    _gone, alive = psutil.wait_procs(children, timeout=term_grace)
    for child in alive:
        try:
            child.kill()
        except Exception:
            pass
    return len(children)


class OpenHandsSolver(BaseSolver):
    """Solver that uses OpenHands to complete game development tasks."""

    # Solver capabilities (required by BaseSolver)
    SUPPORTS_MCP = True
    SUPPORTS_SYSTEM_PROMPT = True  # Via custom_instructions

    # Model name mapping for litellm format
    MODEL_MAPPING = {
        "claude": "anthropic/claude-sonnet-4-20250514",
        "gpt": "openai/gpt-4o",
        "gpt-4o": "openai/gpt-4o",
        "gpt-4": "openai/gpt-4",
        "o1": "openai/o1",
        "o3": "openai/o3",
        # DeepSeek via its native API (litellm `deepseek/` provider, DEEPSEEK_API_KEY)
        "deepseek": "deepseek/deepseek-chat",
        "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
    }

    def __init__(
        self,
        timeout_seconds: int = 600,
        debug: bool = False,
        use_mcp: bool = False,
        model: str = "openai/gpt-4o",  # litellm format: provider/model
        use_runtime_video: bool = False,
        api_base: Optional[str] = None,
        openrouter_site_url: Optional[str] = None,
        openrouter_app_name: Optional[str] = None,
        mcp_server: str = DEFAULT_MCP_SERVER,
    ):
        """
        Initialize the OpenHands solver.

        Args:
            timeout_seconds: Maximum time to wait for solver
            debug: Whether to show debug output
            use_mcp: Whether to use MCP tools
            model: Model to use (default: openai/gpt-4o, supports vision)
            use_runtime_video: Whether to append Godot runtime video instructions to prompts
            mcp_server: Name of the MCP server to wire in when use_mcp is set
        """
        # Call parent constructor (handles MCP validation)
        super().__init__(
            timeout_seconds, debug, use_mcp, use_runtime_video, mcp_server=mcp_server
        )

        # OpenHands-specific parameters
        # Convert short model names to litellm format
        self.model = self.MODEL_MAPPING.get(model, model)

        # Optional overrides. The OpenRouter base URL must only apply to
        # OpenRouter-routed models; native providers (deepseek/, anthropic/, ...)
        # carry their own endpoints in litellm.
        self.api_base = resolve_api_base(
            self.model, api_base, os.environ.get("OPENROUTER_API_BASE")
        )
        self.openrouter_site_url = openrouter_site_url or os.environ.get("OR_SITE_URL")
        self.openrouter_app_name = openrouter_app_name or os.environ.get("OR_APP_NAME")

    @staticmethod
    def is_rate_limit_error(error_message: str) -> bool:
        """Check if the error message indicates API rate limit."""
        error_lower = error_message.lower()
        rate_limit_keywords = [
            "rate limit", "rate_limit", "ratelimit",
            "quota exceeded", "429", "too many requests",
        ]
        return any(keyword in error_lower for keyword in rate_limit_keywords)

    def solve_task(self) -> SolverResult:
        """Solve the task in the current directory using OpenHands."""
        config = self.load_config()
        if not config:
            return SolverResult(
                success=False,
                message="Could not load task configuration",
                duration_seconds=0.0,
            )

        start_time = time.time()
        prompt = self.get_task_prompt(config)

        if self.debug:
            print("=" * 60)
            print("SENDING PROMPT TO OPENHANDS:")
            print("=" * 60)
            print(prompt)
            print("=" * 60)

        # A live Godot editor (godot-ai) is brought up inside the try and must be
        # torn down whatever happens; bind it here so the finally can see it.
        editor_session = None
        try:
            # Get API key from environment based on model provider prefix
            api_key, key_name = resolve_provider_api_key(self.model)

            if not api_key:
                return SolverResult(
                    success=False,
                    message=f"{key_name} environment variable not set",
                    duration_seconds=0.0,
                )

            if self.debug:
                print(f"\nUsing model: {self.model}")
                print("\nOPENHANDS TRAJECTORY:")
                print("=" * 60)

            # Configure LLM with vision-capable model
            llm = LLM(
                model=self.model,
                api_key=SecretStr(api_key),
                temperature=0.0,
                base_url=self.api_base,
                openrouter_site_url=self.openrouter_site_url or "https://docs.all-hands.dev/",
                openrouter_app_name=self.openrouter_app_name or "OpenHands",
            )

            # Servers backed by a Godot editor plugin (godot-ai) need a live
            # editor running this server's plugin before the agent connects. Bring
            # it up in the sandbox (cwd) now; it picks its own free port, so the
            # MCP URL is read back from the session below. It is torn down in the
            # finally. Startup happens before the watchdog starts, so it isn't
            # charged to the task timeout (mirrors the runner's asset-import step).
            if self.use_mcp and self.mcp_spec.needs_godot_editor:
                from pathlib import Path
                from gamedevbench.src.godot_ai_editor import (
                    GodotAiEditorSession,
                    ensure_addon,
                )
                from gamedevbench.src.utils.constants import GODOT_EXEC_PATH

                editor_session = GodotAiEditorSession(
                    project_dir=Path(os.getcwd()),
                    godot_path=GODOT_EXEC_PATH,
                    addon_src=ensure_addon(),
                    extra_env=self.mcp_spec.env(),
                    debug=self.debug,
                )
                editor_session.__enter__()

            # Build the MCP server config from the selected registry spec so the
            # server is swappable per run (e.g. the bundled screenshot baseline
            # vs. the Godot-targeted @coding-solo/godot-mcp). stdio servers are
            # launched by the agent from command/args; http servers (godot-ai)
            # are reached at a URL — for an editor-backed server that URL is the
            # session's per-task port, otherwise the spec's static URL.
            if self.mcp_spec.transport == "http":
                http_url = (
                    editor_session.http_url
                    if editor_session is not None
                    else self.mcp_spec.http_url
                )
                server_config = {"url": http_url, "transport": "http"}
            else:
                server_config = {
                    "command": self.mcp_spec.command,
                    "args": list(self.mcp_spec.args),
                }
                server_env = self.mcp_spec.env()
                if server_env:
                    server_config["env"] = server_env
            mcp_config = {
                "mcpServers": {self.mcp_spec.server_id: server_config}
            }

            # Create agent with default tool selection (CLI mode disables browser)
            # We construct the Agent manually because it's a frozen Pydantic model
            # and we need to inject mcp_config during initialization.
            tools = get_default_tools(
                enable_browser=False,  # CLI mode disables browser
            )
            
            if self.use_mcp:
                agent = Agent(
                    llm=llm,
                    tools=tools,
                    system_prompt_kwargs={"cli_mode": True},
                    condenser=get_default_condenser(
                        llm=llm.model_copy(update={"usage_id": "condenser"})
                    ),
                    mcp_config=mcp_config
                )
            else:
                agent = Agent(
                    llm=llm,
                    tools=tools,
                    system_prompt_kwargs={"cli_mode": True},
                    condenser=get_default_condenser(
                        llm=llm.model_copy(update={"usage_id": "condenser"})
                    ),
                )

            # Collect output for logging and token tracking
            output_lines = []
            token_usage = TokenUsage()

            def event_callback(event: Event):
                """Callback to handle and log events."""
                nonlocal token_usage
                event_str = str(event)
                output_lines.append(event_str)

                # Try to extract token usage from events
                if hasattr(event, 'usage'):
                    usage = event.usage
                    if isinstance(usage, dict):
                        token_usage.input_tokens += usage.get('input_tokens', 0) or usage.get('prompt_tokens', 0)
                        token_usage.output_tokens += usage.get('output_tokens', 0) or usage.get('completion_tokens', 0)
                        token_usage.total_tokens = token_usage.input_tokens + token_usage.output_tokens
                        token_usage.cache_read_tokens += usage.get('cache_read_input_tokens', 0) or usage.get('cached_tokens', 0)

                # Also check for metrics attribute
                if hasattr(event, 'metrics') and event.metrics:
                    metrics = event.metrics
                    if isinstance(metrics, dict):
                        token_usage.input_tokens += metrics.get('input_tokens', 0)
                        token_usage.output_tokens += metrics.get('output_tokens', 0)
                        token_usage.total_tokens = token_usage.input_tokens + token_usage.output_tokens

                if self.debug:
                    # Print a summary of the event
                    event_type = type(event).__name__
                    preview = event_str[:150].replace('\n', ' ')
                    print(f"\n[{event_type}] {preview}...")

            # Create conversation with workspace set to current directory
            conversation = Conversation(
                agent=agent,
                callbacks=[event_callback],
                workspace=os.getcwd(),
            )
            # Run without confirmation prompts
            conversation.set_confirmation_policy(NeverConfirm())

            # Send message and run
            conversation.send_message(prompt)

            # Enforce a wall-clock cap. The agent loop is otherwise unbounded in
            # time (max_iteration_per_run is an iteration count, not seconds), so
            # a single hard task can run for tens of minutes. A watchdog pauses
            # the conversation at the deadline; pause() takes effect at the next
            # loop boundary, making run() return gracefully. It's a soft cap — a
            # call already blocked inside a single LLM/tool step finishes first —
            # but it bounds runaway trajectories. Partial work left in the
            # sandbox is still validated downstream.
            #
            # A step wedged inside a child subprocess (e.g. a hung MCP/godot tool
            # call holding a stdio read) never reaches the next loop boundary, so
            # pause() can't land and run() never returns. A second, hard cap
            # HARD_CAP_GRACE seconds later kills this worker's descendant
            # processes; that closes the stdio pipes so the blocked call unwinds
            # and run() returns, instead of stranding the worker (and, with it,
            # the whole process pool) indefinitely.
            timed_out = threading.Event()
            hard_capped = threading.Event()

            def _stop_on_timeout():
                timed_out.set()
                try:
                    conversation.pause()
                except Exception:
                    pass

            def _hard_stop():
                hard_capped.set()
                _terminate_process_tree(os.getpid())

            watchdog = threading.Timer(self.timeout_seconds, _stop_on_timeout)
            watchdog.daemon = True
            watchdog.start()
            hard_watchdog = threading.Timer(
                self.timeout_seconds + HARD_CAP_GRACE, _hard_stop
            )
            hard_watchdog.daemon = True
            hard_watchdog.start()
            try:
                conversation.run()
            finally:
                watchdog.cancel()
                hard_watchdog.cancel()

            duration = time.time() - start_time
            response_text = "\n".join(output_lines)

            # Get token usage from conversation_stats (the correct way)
            model_used = self.model
            cost_usd = 0.0

            # Access conversation stats for token/cost information
            if hasattr(conversation, 'conversation_stats') and conversation.conversation_stats:
                stats = conversation.conversation_stats
                combined_metrics = stats.get_combined_metrics()
                if combined_metrics:
                    # Get accumulated token usage
                    if combined_metrics.accumulated_token_usage:
                        usage = combined_metrics.accumulated_token_usage
                        token_usage.input_tokens = usage.prompt_tokens or 0
                        token_usage.output_tokens = usage.completion_tokens or 0
                        token_usage.cache_read_tokens = usage.cache_read_tokens or 0
                        token_usage.cache_write_tokens = usage.cache_write_tokens or 0
                        token_usage.total_tokens = token_usage.input_tokens + token_usage.output_tokens
                    # Get accumulated cost directly from metrics
                    cost_usd = combined_metrics.accumulated_cost or 0.0

            # Fallback: calculate cost if we have tokens but no cost
            if token_usage.total_tokens > 0 and cost_usd == 0.0:
                cost_usd = token_usage.calculate_cost(model_used)

            if self.debug:
                print(f"\n\nDuration: {duration:.2f} seconds")
                if token_usage.total_tokens > 0:
                    print(f"Tokens: input={token_usage.input_tokens}, output={token_usage.output_tokens}, total={token_usage.total_tokens}")
                    print(f"Cost: ${cost_usd:.4f}")
                print("=" * 60)

            if timed_out.is_set():
                success = False
                if hard_capped.is_set():
                    message = (
                        f"Solver timed out after {self.timeout_seconds}s; hard "
                        f"cap killed runaway subprocesses {HARD_CAP_GRACE}s "
                        "later (partial work validated)"
                    )
                else:
                    message = (
                        f"Solver timed out after {self.timeout_seconds}s "
                        "(agent paused; partial work validated)"
                    )
            else:
                success = True
                message = "Task completed"

            return SolverResult(
                success=success,
                message=message,
                duration_seconds=duration,
                stdout=response_text,
                stderr="",
                token_usage=token_usage if token_usage.total_tokens > 0 else None,
                model=model_used,
                cost_usd=cost_usd,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            is_rate_limited = self.is_rate_limit_error(error_msg)

            if self.debug:
                print(f"\nERROR INVOKING OPENHANDS: {error_msg}")
                if is_rate_limited:
                    print("⚠️  DETECTED RATE LIMIT/QUOTA ERROR")
                print("=" * 60)
                import traceback
                traceback.print_exc()

            return SolverResult(
                success=False,
                message=f"Error invoking OpenHands: {error_msg}",
                duration_seconds=duration,
                is_rate_limited=is_rate_limited,
            )
        finally:
            # Always tear the godot-ai editor (and its server/Xvfb) down, on
            # success, failure, or timeout — so nothing leaks into the next task.
            if editor_session is not None:
                try:
                    editor_session.__exit__(None, None, None)
                except Exception:
                    pass


def main():
    """Main function for testing the solver."""
    solver = OpenHandsSolver(debug=True)
    result = solver.solve_task()
    print("\n" + "=" * 60)
    print("RESULT:")
    print("=" * 60)
    print(f"Success: {result.success}")
    print(f"Message: {result.message[:500] if result.message else 'None'}")
    print(f"Duration: {result.duration_seconds:.2f}s")


if __name__ == "__main__":
    main()
