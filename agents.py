#!/usr/bin/env python3
"""
ToonCode Multi-Agent - หลาย Agent ทำงานพร้อมกัน มี panel ข��าบอกสถานะ
แต่ละ agent lock ไฟล์ที่ตัวเองแก้ ไม่ให้ซ้ำกัน

Usage:
    python agents.py "สร้าง REST API พร้อม tests"
    python agents.py --agents planner,coder,reviewer "refactor auth module"
"""

import httpx
import json
import uuid
import sys
import os
import subprocess
import glob as glob_mod
import re
import platform
import time
import string
import random
import threading
from datetime import datetime
from typing import Optional, Dict, List, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.live import Live
from rich.layout import Layout
from rich.table import Table
from rich.syntax import Syntax
from rich.rule import Rule
from rich.spinner import Spinner
from rich.align import Align

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style as PTStyle


# ============================================================================
# Config
# ============================================================================

API_URL = "https://opencode.ai/zen/v1/messages"
CWD = os.getcwd()
MODEL = "big-pickle"
AVAILABLE_MODELS = ["minimax-m2.5-free", "big-pickle", "nemotron-3-super-free", "gpt-5-nano"]
NO_SAMPLING_PARAMS = {"big-pickle", "gpt-5-nano"}

CONTEXT_WINDOWS = {
    "minimax-m2.5-free": 204_800,
    "big-pickle": 200_000,
    "nemotron-3-super-free": 131_072,
    "gpt-5-nano": 1_047_576,
}

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "ai-sdk/anthropic/3.0.67 ai-sdk/provider-utils/4.0.23 runtime/bun/1.3.11",
    "anthropic-beta": "fine-grained-tool-streaming-2025-05-14",
    "anthropic-version": "2023-06-01",
    "x-api-key": "public",
    "x-opencode-client": "desktop",
    "x-opencode-project": "global",
    "Connection": "keep-alive",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
}

console = Console()


def _gen_id(prefix: str, length: int = 24) -> str:
    chars = string.ascii_letters + string.digits
    return f"{prefix}_{uuid.uuid4().hex[:12]}{''.join(random.choices(chars, k=length - 12))}"


# ============================================================================
# File Lock Registry - หัวใจของระบบกัน agent แก้ไฟล���ซ้ำ
# ============================================================================

class FileLockRegistry:
    """Track which agent owns which files. Prevent conflicts."""

    def __init__(self):
        self._locks: Dict[str, str] = {}  # filepath -> agent_name
        self._lock = threading.Lock()

    def try_lock(self, filepath: str, agent_name: str) -> bool:
        """Try to lock a file for an agent. Returns False if already locked by another."""
        filepath = os.path.normpath(filepath)
        with self._lock:
            owner = self._locks.get(filepath)
            if owner is None or owner == agent_name:
                self._locks[filepath] = agent_name
                return True
            return False

    def release(self, filepath: str, agent_name: str):
        with self._lock:
            if self._locks.get(filepath) == agent_name:
                del self._locks[filepath]

    def release_all(self, agent_name: str):
        with self._lock:
            to_del = [f for f, a in self._locks.items() if a == agent_name]
            for f in to_del:
                del self._locks[f]

    def get_owner(self, filepath: str) -> Optional[str]:
        filepath = os.path.normpath(filepath)
        return self._locks.get(filepath)

    def get_agent_files(self, agent_name: str) -> List[str]:
        with self._lock:
            return [f for f, a in self._locks.items() if a == agent_name]

    def get_all(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._locks)


FILE_LOCKS = FileLockRegistry()


# ============================================================================
# Agent Definition
# ============================================================================

AGENT_PRESETS = {
    "planner": {
        "emoji": "📋",
        "color": "cyan",
        "system": """You are the PLANNER agent. Your job:
1. Analyze the user's request and break it into clear, actionable steps
2. Identify which files need to be created or modified
3. Define the order of work
4. Output a structured plan as a numbered list

You should ONLY plan - do NOT write code. Use 'read' and 'glob' tools to understand the codebase.
Output your plan clearly so other agents can execute it.
End your response with a JSON block:
```json
{"files_to_create": ["path1.py"], "files_to_modify": ["path2.py"], "steps": ["step1", "step2"]}
```""",
    },
    "coder": {
        "emoji": "💻",
        "color": "green",
        "system": """You are the CODER agent. Your job:
1. Follow the plan provided and write/edit code
2. Use 'write' and 'edit' tools to create and modify files
3. Write clean, working code with no unnecessary comments
4. Focus on implementation - no reviews, no tests

IMPORTANT: Before editing a file, always 'read' it first.
Keep your text responses minimal - let the code speak.""",
    },
    "reviewer": {
        "emoji": "🔍",
        "color": "yellow",
        "system": """You are the REVIEWER agent. Your job:
1. Read the code that was written/modified
2. Check for bugs, security issues, and logic errors
3. Verify the code follows best practices
4. If you find issues, use 'edit' to fix them directly

Be concise. Only flag real problems, not style preferences.
Output a summary: PASS (no issues), or list of fixes you made.""",
    },
    "tester": {
        "emoji": "🧪",
        "color": "magenta",
        "system": """You are the TESTER agent. Your job:
1. Read the implementation code
2. Write test files for the code
3. Run tests using 'bash' tool
4. Report results

Use pytest for Python, jest/vitest for JS/TS.
Focus on critical paths and edge cases.""",
    },
}


class Agent:
    """Single agent with its own conversation, tools, and file tracking."""

    def __init__(self, name: str, preset: str, file_locks: FileLockRegistry):
        config = AGENT_PRESETS[preset]
        self.name = name
        self.preset = preset
        self.emoji = config["emoji"]
        self.color = config["color"]
        self.system_prompt = config["system"]
        self.file_locks = file_locks
        self.messages: List[dict] = []
        self.status = "idle"        # idle, thinking, tool:xxx, done, error
        self.current_tool = ""
        self.files_touched: List[str] = []
        self.output_text = ""       # final response text
        self.session_id = _gen_id("ses", 24)
        self._log: List[str] = []   # activity log

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(f"[{ts}] {msg}")

    # -- Tool Handlers (with file lock checks) --

    def _exec_bash(self, args: dict) -> str:
        cmd = args.get("command", "")
        workdir = args.get("workdir", CWD)
        self.log(f"bash: {cmd[:60]}")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=workdir, timeout=120, stdin=subprocess.DEVNULL,
            )
            output = (result.stdout + result.stderr)[:50000]
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return "[timed out]"
        except Exception as e:
            return f"[error: {e}]"

    def _exec_read(self, args: dict) -> str:
        fpath = args.get("filePath", "")
        offset = int(args.get("offset", 1))
        limit = int(args.get("limit", 2000))
        self.log(f"read: {os.path.basename(fpath)}")
        try:
            if os.path.isdir(fpath):
                return "\n".join(sorted(os.listdir(fpath))[:50])
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            start = max(0, offset - 1)
            return "\n".join(
                f"{i}\t{line.rstrip()}"
                for i, line in enumerate(lines[start:start + limit], start=start + 1)
            ) or "(empty)"
        except Exception as e:
            return f"[error: {e}]"

    def _exec_write(self, args: dict) -> str:
        fpath = args.get("filePath", "")
        content = args.get("content", "")
        # File lock check
        if not self.file_locks.try_lock(fpath, self.name):
            owner = self.file_locks.get_owner(fpath)
            self.log(f"BLOCKED write {os.path.basename(fpath)} (locked by {owner})")
            return f"[BLOCKED: file '{fpath}' is locked by agent '{owner}'. Choose a different file or wait.]"
        self.log(f"write: {os.path.basename(fpath)}")
        if fpath not in self.files_touched:
            self.files_touched.append(fpath)
        try:
            os.makedirs(os.path.dirname(fpath) or ".", exist_ok=True)
            with open(fpath, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            return f"Wrote {content.count(chr(10)) + 1} lines to {fpath}"
        except Exception as e:
            return f"[error: {e}]"

    def _exec_edit(self, args: dict) -> str:
        fpath = args.get("filePath", "")
        old = args.get("oldString", "")
        new = args.get("newString", "")
        replace_all = args.get("replaceAll", False)
        if not self.file_locks.try_lock(fpath, self.name):
            owner = self.file_locks.get_owner(fpath)
            self.log(f"BLOCKED edit {os.path.basename(fpath)} (locked by {owner})")
            return f"[BLOCKED: file '{fpath}' is locked by agent '{owner}'. Choose a different file or wait.]"
        self.log(f"edit: {os.path.basename(fpath)}")
        if fpath not in self.files_touched:
            self.files_touched.append(fpath)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            count = content.count(old)
            if count == 0:
                return "[error: oldString not found]"
            if count > 1 and not replace_all:
                return f"[error: {count} matches, set replaceAll=true]"
            new_content = content.replace(old, new) if replace_all else content.replace(old, new, 1)
            with open(fpath, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_content)
            return f"Replaced {count if replace_all else 1} in {fpath}"
        except Exception as e:
            return f"[error: {e}]"

    def _exec_glob(self, args: dict) -> str:
        pattern = args.get("pattern", "")
        path = args.get("path", CWD)
        try:
            matches = glob_mod.glob(os.path.join(path, pattern), recursive=True)
            matches = sorted(matches, key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
            return "\n".join(m.replace("\\", "/") for m in matches[:100]) or "(no matches)"
        except Exception as e:
            return f"[error: {e}]"

    def _exec_grep(self, args: dict) -> str:
        pattern = args.get("pattern", "")
        path = args.get("path", CWD)
        include = args.get("include", "*")
        try:
            files = glob_mod.glob(os.path.join(path, "**", include), recursive=True)
            results = []
            regex = re.compile(pattern, re.IGNORECASE)
            for fp in files[:500]:
                if os.path.isdir(fp):
                    continue
                try:
                    with open(fp, "r", encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append(f"{fp.replace(chr(92), '/')}:{i}: {line.rstrip()}")
                                if len(results) >= 100:
                                    break
                except Exception:
                    pass
                if len(results) >= 100:
                    break
            return "\n".join(results) or "(no matches)"
        except Exception as e:
            return f"[error: {e}]"

    TOOL_MAP = {
        "bash": "_exec_bash",
        "read": "_exec_read",
        "write": "_exec_write",
        "edit": "_exec_edit",
        "glob": "_exec_glob",
        "grep": "_exec_grep",
    }

    TOOLS_SCHEMA = [
        {"name": "bash", "description": "Execute shell command.",
         "input_schema": {"type": "object", "properties": {"command": {"type": "string"}, "description": {"type": "string"}, "workdir": {"type": "string"}}, "required": ["command", "description"]}},
        {"name": "read", "description": "Read a file with line numbers.",
         "input_schema": {"type": "object", "properties": {"filePath": {"type": "string"}, "offset": {"type": "number"}, "limit": {"type": "number"}}, "required": ["filePath"]}},
        {"name": "write", "description": "Write content to file. Will be BLOCKED if another agent owns this file.",
         "input_schema": {"type": "object", "properties": {"filePath": {"type": "string"}, "content": {"type": "string"}}, "required": ["filePath", "content"]}},
        {"name": "edit", "description": "Edit file with string replacement. Will be BLOCKED if another agent owns this file.",
         "input_schema": {"type": "object", "properties": {"filePath": {"type": "string"}, "oldString": {"type": "string"}, "newString": {"type": "string"}, "replaceAll": {"type": "boolean"}}, "required": ["filePath", "oldString", "newString"]}},
        {"name": "glob", "description": "Find files matching pattern.",
         "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}}, "required": ["pattern"]}},
        {"name": "grep", "description": "Search file contents with regex.",
         "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}, "include": {"type": "string"}}, "required": ["pattern"]}},
    ]

    # -- API Call --

    def run(self, task: str, context: str = ""):
        """Run agent on a task. Blocks until done."""
        self.status = "thinking"
        self.output_text = ""
        self.log(f"Starting: {task[:60]}")

        full_system = f"""{self.system_prompt}

Working directory: {CWD}
Platform: {platform.system()}
Date: {datetime.now().strftime('%a %b %d %Y')}"""

        if context:
            full_system += f"\n\n# Context from previous agents:\n{context}"

        user_msg = {"role": "user", "content": [
            {"type": "text", "text": task, "cache_control": {"type": "ephemeral"}}
        ]}
        self.messages = [user_msg]

        iteration = 0
        while iteration < 15:
            iteration += 1
            self.status = f"thinking" if iteration == 1 else f"step {iteration}"

            body = {
                "model": MODEL,
                "max_tokens": 16000,
                "system": [{"type": "text", "text": full_system, "cache_control": {"type": "ephemeral"}}],
                "messages": self.messages,
                "tools": self.TOOLS_SCHEMA,
                "tool_choice": {"type": "auto"},
                "stream": False,
            }
            if MODEL not in NO_SAMPLING_PARAMS:
                body["temperature"] = 1
                body["top_k"] = 40
                body["top_p"] = 0.95

            headers = {
                **HEADERS,
                "x-opencode-request": _gen_id("msg"),
                "x-opencode-session": self.session_id,
            }

            try:
                resp = httpx.post(API_URL, headers=headers, json=body, timeout=300)
                if resp.status_code != 200:
                    self.status = "error"
                    self.log(f"API error: {resp.status_code}")
                    self.output_text = f"API Error {resp.status_code}"
                    return
                data = resp.json()
            except Exception as e:
                self.status = "error"
                self.log(f"Error: {e}")
                self.output_text = f"Error: {e}"
                return

            content = data.get("content", [])

            # Build assistant message
            assistant_content = []
            has_tools = False
            for block in content:
                btype = block.get("type", "")
                if btype == "text":
                    self.output_text += block.get("text", "")
                    assistant_content.append({"type": "text", "text": block["text"]})
                elif btype == "thinking":
                    assistant_content.append({
                        "type": "thinking",
                        "thinking": block.get("thinking", ""),
                        "signature": block.get("signature", ""),
                    })
                elif btype == "tool_use":
                    has_tools = True
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block["id"],
                        "name": block["name"],
                        "input": block.get("input", {}),
                    })

            self.messages.append({"role": "assistant", "content": assistant_content})

            if not has_tools:
                break

            # Execute tools
            tool_results = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                name = block["name"]
                args = block.get("input", {})
                self.status = f"tool:{name}"
                self.current_tool = name

                handler_name = self.TOOL_MAP.get(name)
                if handler_name:
                    result = getattr(self, handler_name)(args)
                else:
                    result = f"[unknown tool: {name}]"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": result,
                })

            self.messages.append({"role": "user", "content": tool_results})
            self.current_tool = ""

        self.status = "done"
        self.log("Done")
        self.file_locks.release_all(self.name)


# ============================================================================
# Live Dashboard - จอขวามือ
# ============================================================================

class Dashboard:
    """Live-updating right panel showing all agents' status and file ownership."""

    def __init__(self, agents: List[Agent]):
        self.agents = agents
        self._live: Optional[Live] = None

    def build(self) -> Layout:
        layout = Layout()
        layout.split_row(
            Layout(name="main", ratio=3),
            Layout(name="panel", ratio=1, minimum_size=30),
        )

        # -- Right Panel --
        panel_parts = []

        # Agent status table
        tbl = Table(
            title="Agents",
            border_style="cyan",
            show_header=True,
            expand=True,
            padding=(0, 1),
        )
        tbl.add_column("Agent", style="bold", no_wrap=True)
        tbl.add_column("Status", no_wrap=True)
        tbl.add_column("Files", style="dim")

        for agent in self.agents:
            # Status with color
            if agent.status == "idle":
                status = Text("● idle", style="dim")
            elif agent.status == "done":
                status = Text("✓ done", style="bold green")
            elif agent.status == "error":
                status = Text("✗ error", style="bold red")
            elif agent.status.startswith("tool:"):
                tool = agent.status[5:]
                status = Text(f"⚙ {tool}", style="bold yellow")
            else:
                status = Text(f"◌ {agent.status}", style="bold cyan")

            # Files this agent owns
            owned_files = agent.file_locks.get_agent_files(agent.name)
            file_names = [os.path.basename(f) for f in owned_files]
            files_str = ", ".join(file_names[-3:]) if file_names else "-"
            if len(file_names) > 3:
                files_str += f" +{len(file_names)-3}"

            name_text = Text(f"{agent.emoji} {agent.name}", style=f"bold {agent.color}")
            tbl.add_row(name_text, status, files_str)

        panel_parts.append(tbl)

        # File ownership map
        all_locks = FILE_LOCKS.get_all()
        if all_locks:
            file_tbl = Table(
                title="File Locks",
                border_style="yellow",
                show_header=True,
                expand=True,
                padding=(0, 1),
            )
            file_tbl.add_column("File", style="white", no_wrap=True)
            file_tbl.add_column("Owner", style="bold", no_wrap=True)

            for fpath, owner in list(all_locks.items())[-10:]:
                fname = os.path.basename(fpath)
                agent_obj = next((a for a in self.agents if a.name == owner), None)
                color = agent_obj.color if agent_obj else "white"
                file_tbl.add_row(fname, Text(owner, style=f"bold {color}"))

            panel_parts.append(file_tbl)

        # Recent activity
        all_logs = []
        for agent in self.agents:
            for log_line in agent._log[-3:]:
                all_logs.append((agent, log_line))
        all_logs = all_logs[-8:]

        if all_logs:
            log_text = Text()
            for agent, line in all_logs:
                log_text.append(f"{agent.emoji} ", style=f"bold {agent.color}")
                log_text.append(line + "\n", style="dim")
            panel_parts.append(Panel(log_text, title="Activity", border_style="dim", padding=(0, 1)))

        right_panel = Panel(
            Group(*panel_parts) if panel_parts else Text("No agents running", style="dim"),
            title="[bold cyan]Agent Dashboard[/bold cyan]",
            border_style="cyan",
            padding=(0, 0),
        )
        layout["panel"].update(right_panel)

        return layout

    def update_main(self, layout: Layout, content):
        layout["main"].update(content)
        return layout

    def start(self):
        self._live = Live(
            self.build(),
            console=console,
            refresh_per_second=4,
            vertical_overflow="visible",
        )
        self._live.start()

    def refresh(self, main_content=None):
        if self._live:
            layout = self.build()
            if main_content:
                layout["main"].update(main_content)
            self._live.update(layout)

    def stop(self):
        if self._live:
            self._live.stop()
            self._live = None


# ============================================================================
# Orchestrator - สั่ง Agent ทำงาน
# ============================================================================

class Orchestrator:
    """Run multiple agents in sequence or parallel with live dashboard."""

    def __init__(self):
        self.agents: List[Agent] = []
        self.dashboard: Optional[Dashboard] = None

    def run_pipeline(self, task: str, agent_names: List[str] = None):
        """Run agents in pipeline: planner -> coder -> reviewer."""
        if agent_names is None:
            agent_names = ["planner", "coder", "reviewer"]

        # Create agents
        self.agents = []
        for preset in agent_names:
            if preset not in AGENT_PRESETS:
                console.print(f"[red]Unknown agent: {preset}[/red]")
                return
            agent = Agent(name=preset, preset=preset, file_locks=FILE_LOCKS)
            self.agents.append(agent)

        self.dashboard = Dashboard(self.agents)

        console.print(Panel(
            Text(f"Task: {task}", style="bold white"),
            title="[bold cyan]ToonCode Multi-Agent Pipeline[/bold cyan]",
            subtitle=f"[dim]{' → '.join(a.emoji + ' ' + a.name for a in self.agents)}[/dim]",
            border_style="cyan",
        ))
        console.print()

        # Run pipeline: each agent passes context to next
        context = ""
        for i, agent in enumerate(self.agents):
            step_label = f"[{i+1}/{len(self.agents)}]"

            # Build task with context
            if i == 0:
                agent_task = task
            else:
                agent_task = f"""Original task: {task}

Previous agent ({self.agents[i-1].name}) output:
{context}

Now do your part."""

            # Show header
            console.print(Rule(
                f"{agent.emoji} {agent.name} {step_label}",
                style=agent.color,
            ))

            # Run with live dashboard
            self.dashboard = Dashboard(self.agents)
            self.dashboard.start()

            # Run agent in thread so dashboard can update
            def run_agent(a, t, c):
                a.run(t, c)

            thread = threading.Thread(target=run_agent, args=(agent, agent_task, context))
            thread.start()

            # Update dashboard while agent runs
            while thread.is_alive():
                main_content = self._build_main_view(agent)
                self.dashboard.refresh(main_content)
                time.sleep(0.3)

            # Final update
            self.dashboard.refresh(self._build_main_view(agent))
            self.dashboard.stop()

            # Show agent output
            if agent.output_text:
                console.print()
                console.print(Panel(
                    Markdown(agent.output_text),
                    title=f"[bold {agent.color}]{agent.emoji} {agent.name} output[/bold {agent.color}]",
                    border_style=agent.color,
                    padding=(1, 2),
                ))

            # Pass output as context
            files_info = ""
            if agent.files_touched:
                files_info = "\nFiles touched: " + ", ".join(agent.files_touched)
            context = agent.output_text + files_info

            if agent.status == "error":
                console.print(f"[red]Agent {agent.name} failed. Stopping pipeline.[/red]")
                break

            console.print()

        # Summary
        console.print(Rule("Pipeline Complete", style="bold green"))
        self._print_summary()

    def run_parallel(self, task: str, agent_configs: List[dict]):
        """Run agents in parallel with file lock protection.
        agent_configs: [{"name": "coder-1", "preset": "coder", "task": "write api.py"}, ...]
        """
        self.agents = []
        for cfg in agent_configs:
            preset = cfg.get("preset", "coder")
            name = cfg.get("name", preset)
            agent = Agent(name=name, preset=preset, file_locks=FILE_LOCKS)
            self.agents.append(agent)

        console.print(Panel(
            Text(f"Task: {task}", style="bold white"),
            title="[bold cyan]ToonCode Parallel Agents[/bold cyan]",
            subtitle=f"[dim]{' + '.join(a.emoji + ' ' + a.name for a in self.agents)}[/dim]",
            border_style="cyan",
        ))
        console.print()

        self.dashboard = Dashboard(self.agents)
        self.dashboard.start()

        # Run all agents in parallel
        threads = []
        for agent, cfg in zip(self.agents, agent_configs):
            agent_task = cfg.get("task", task)
            t = threading.Thread(target=agent.run, args=(agent_task, ""))
            threads.append(t)
            t.start()

        # Update dashboard
        while any(t.is_alive() for t in threads):
            main_text = Text()
            for agent in self.agents:
                style = f"bold {agent.color}"
                main_text.append(f"\n{agent.emoji} {agent.name}: ", style=style)
                main_text.append(agent.status, style="dim")
                if agent.files_touched:
                    main_text.append(f" [{', '.join(os.path.basename(f) for f in agent.files_touched)}]", style="dim yellow")
            self.dashboard.refresh(Panel(main_text, title="Progress", border_style="dim"))
            time.sleep(0.3)

        self.dashboard.stop()

        # Show results
        for agent in self.agents:
            if agent.output_text:
                console.print(Panel(
                    Markdown(agent.output_text),
                    title=f"[bold {agent.color}]{agent.emoji} {agent.name}[/bold {agent.color}]",
                    border_style=agent.color,
                    padding=(1, 2),
                ))
        console.print()
        self._print_summary()

    def _build_main_view(self, current_agent: Agent) -> Panel:
        parts = []
        # Show current agent's log
        if current_agent._log:
            log_text = Text()
            for line in current_agent._log[-12:]:
                log_text.append(line + "\n", style="dim")
            parts.append(log_text)

        # Streaming output preview
        if current_agent.output_text:
            preview = current_agent.output_text[-500:]
            if len(current_agent.output_text) > 500:
                preview = "..." + preview
            parts.append(Text(preview, style=current_agent.color))

        content = Group(*parts) if parts else Text(f"{current_agent.emoji} {current_agent.name} working...", style="dim")
        return Panel(
            content,
            title=f"[bold {current_agent.color}]{current_agent.emoji} {current_agent.name}[/bold {current_agent.color}]",
            border_style=current_agent.color,
        )

    def _print_summary(self):
        tbl = Table(title="Summary", border_style="green", show_header=True)
        tbl.add_column("Agent", style="bold")
        tbl.add_column("Status")
        tbl.add_column("Files Touched", style="yellow")
        tbl.add_column("Steps")

        for agent in self.agents:
            status_style = "green" if agent.status == "done" else "red"
            files = ", ".join(os.path.basename(f) for f in agent.files_touched) or "-"
            steps = str(len([m for m in agent.messages if m["role"] == "assistant"]))
            tbl.add_row(
                Text(f"{agent.emoji} {agent.name}", style=f"bold {agent.color}"),
                Text(agent.status, style=status_style),
                files,
                steps,
            )

        console.print(tbl)


# ============================================================================
# Interactive Mode
# ============================================================================

def interactive():
    """Interactive mode - chat-like interface to launch agents."""
    global MODEL
    orch = Orchestrator()

    console.print(Panel(
        Group(
            Text("\n  ToonCode Multi-Agent", style="bold cyan"),
            Text(f"  Model: {MODEL}", style="magenta"),
            Text(f"  CWD:   {CWD}", style="dim"),
            Text(),
            Text("  Commands:", style="bold"),
            Text("    /run <task>              Pipeline: planner → coder → reviewer", style="dim"),
            Text("    /parallel <task>         Run coder agents in parallel", style="dim"),
            Text("    /agents p,c,r <task>     Custom agent sequence", style="dim"),
            Text("    /model <name>            Switch model", style="dim"),
            Text("    /quit                    Exit", style="dim"),
            Text(),
        ),
        border_style="cyan",
    ))

    try:
        session = PromptSession(
            history=InMemoryHistory(),
            style=PTStyle.from_dict({"prompt": "#00cc66 bold"}),
        )
    except Exception:
        session = None

    while True:
        try:
            if session:
                user_input = session.prompt(HTML("<prompt>agent &gt; </prompt>")).strip()
            else:
                user_input = input("agent > ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/dim]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit"):
            break

        elif user_input.startswith("/model"):
            parts = user_input.split(None, 1)
            if len(parts) > 1 and parts[1] in AVAILABLE_MODELS:
                MODEL = parts[1]
                console.print(f"[cyan]Model: {MODEL}[/cyan]")
            else:
                console.print(f"[cyan]Available: {', '.join(AVAILABLE_MODELS)}[/cyan]")

        elif user_input.startswith("/run "):
            task = user_input[5:].strip()
            if task:
                orch.run_pipeline(task)

        elif user_input.startswith("/parallel "):
            task = user_input[10:].strip()
            if task:
                # Auto-split into 2 coder agents
                orch.run_parallel(task, [
                    {"name": "coder-A", "preset": "coder", "task": f"{task}\n\nFocus on the MAIN implementation files."},
                    {"name": "coder-B", "preset": "coder", "task": f"{task}\n\nFocus on TESTS and DOCUMENTATION."},
                ])

        elif user_input.startswith("/agents "):
            rest = user_input[8:].strip()
            parts = rest.split(None, 1)
            if len(parts) == 2:
                agent_str, task = parts
                agent_map = {"p": "planner", "c": "coder", "r": "reviewer", "t": "tester"}
                agents = []
                for char in agent_str.replace(",", ""):
                    if char in agent_map:
                        agents.append(agent_map[char])
                    elif char in AGENT_PRESETS:
                        agents.append(char)
                if agents:
                    orch.run_pipeline(task, agents)
                else:
                    console.print("[red]Invalid agents. Use: p=planner, c=coder, r=reviewer, t=tester[/red]")
            else:
                console.print("[dim]Usage: /agents p,c,r <task>[/dim]")

        else:
            # Default: run pipeline
            orch.run_pipeline(user_input)


# ============================================================================
# Entry
# ============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ToonCode Multi-Agent")
    parser.add_argument("task", nargs="?", help="Task to run (or enter interactive mode)")
    parser.add_argument("--agents", "-a", default="planner,coder,reviewer", help="Agent pipeline (e.g. planner,coder,reviewer)")
    parser.add_argument("--model", "-m", default=MODEL, help="Model to use")
    parser.add_argument("--parallel", "-p", action="store_true", help="Run coder agents in parallel")
    args = parser.parse_args()

    if args.model in AVAILABLE_MODELS:
        MODEL = args.model

    if args.task:
        orch = Orchestrator()
        agent_names = [a.strip() for a in args.agents.split(",")]
        if args.parallel:
            configs = [{"name": f"coder-{i+1}", "preset": "coder", "task": args.task} for i in range(2)]
            orch.run_parallel(args.task, configs)
        else:
            orch.run_pipeline(args.task, agent_names)
    else:
        interactive()
