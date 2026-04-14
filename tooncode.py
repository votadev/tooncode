#!/usr/bin/env python3
"""
ToonCode - A beautiful TUI coding agent powered by free AI models.
by VotaLab

Usage:
    pip install rich prompt_toolkit httpx
    python tooncode.py
"""

VERSION = "2.6.6"

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
import hashlib
import string
import random
import threading
import atexit
import signal
from collections import deque
from datetime import datetime
from typing import Optional, Dict

try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.text import Text
    from rich.markdown import Markdown
    from rich.live import Live
    from rich.rule import Rule
    from rich.style import Style
    from rich.theme import Theme
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.columns import Columns
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style as PTStyle
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.completion import Completer, Completion, PathCompleter, merge_completers
except ImportError as e:
    print(f"\033[31mMissing dependency: {e}\033[0m")
    print(f"\033[36mRun: pip install httpx rich prompt_toolkit\033[0m")
    sys.exit(1)


# ============================================================================
# Configuration
# ============================================================================

CWD = os.getcwd()
_worktree_original_cwd = None

# Default settings — overridden by ~/.tooncode/settings.json
_DEFAULT_SETTINGS = {
    "api_url": "https://opencode.ai/zen/v1/messages",
    "api_key": "public",
    "default_model": "big-pickle",
    "models": [
        {"name": "big-pickle", "context": 200000, "no_sampling": True},
        {"name": "minimax-m2.5-free", "context": 204800},
        {"name": "nemotron-3-super-free", "context": 131072},
        {"name": "gpt-5-nano", "context": 1047576, "no_sampling": True},
    ],
    "auto_approve": True,
    "theme": "default",
}
# Per-model settings example in settings.json:
# {"name": "claude-sonnet", "context": 200000, "api_url": "https://api.anthropic.com/v1/messages", "api_key": "sk-ant-..."}

def _load_settings() -> dict:
    """Load settings from ~/.tooncode/settings.json, merge with defaults."""
    settings = dict(_DEFAULT_SETTINGS)
    settings_path = os.path.join(os.path.expanduser("~"), ".tooncode", "settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                user = json.load(f)
            # Merge: user overrides defaults
            for k, v in user.items():
                if k == "models" and isinstance(v, list):
                    # Append user models to defaults (no duplicates)
                    existing = {m["name"] for m in settings["models"]}
                    for m in v:
                        if isinstance(m, dict) and m.get("name") and m["name"] not in existing:
                            settings["models"].append(m)
                            existing.add(m["name"])
                else:
                    settings[k] = v
        except Exception:
            pass
    else:
        # First run — create default settings.json
        try:
            _save_settings(settings)
        except Exception:
            pass
    return settings

def _save_settings(settings: dict):
    """Save settings to ~/.tooncode/settings.json."""
    settings_dir = os.path.join(os.path.expanduser("~"), ".tooncode")
    os.makedirs(settings_dir, exist_ok=True)
    settings_path = os.path.join(settings_dir, "settings.json")
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

# Load settings
_settings = _load_settings()
API_URL = _settings["api_url"]
API_KEY = _settings.get("api_key", "public")


MODEL = _settings["default_model"]
AVAILABLE_MODELS = [m["name"] for m in _settings["models"]]

def _get_model_config(model_name: str) -> dict:
    """Get per-model config (api_url, api_key, context, etc.)"""
    for m in _settings["models"]:
        if m["name"] == model_name:
            return m
    return {}

def _get_api_url() -> str:
    """Get API URL for current model (per-model or global)."""
    cfg = _get_model_config(MODEL)
    return cfg.get("api_url", API_URL)

def _get_api_key() -> str:
    """Get API key for current model (per-model or global)."""
    cfg = _get_model_config(MODEL)
    return cfg.get("api_key", API_KEY)


def _gen_id(prefix: str, length: int = 24) -> str:
    """Generate IDs matching OpenCode format: prefix + hex + mixed alphanumeric."""
    chars = string.ascii_letters + string.digits
    hex_part = uuid.uuid4().hex[:12]
    rand_part = "".join(random.choices(chars, k=length - 12))
    return f"{prefix}_{hex_part}{rand_part}"

SESSION_ID = _gen_id("ses", 24)

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "ai-sdk/anthropic/3.0.67 ai-sdk/provider-utils/4.0.23 runtime/bun/1.3.11",
    "anthropic-beta": "fine-grained-tool-streaming-2025-05-14",
    "anthropic-version": "2023-06-01",
    "x-api-key": API_KEY,
    "x-opencode-client": "desktop",
    "x-opencode-project": "global",
    "Connection": "keep-alive",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
}

# ============================================================================
# PROFESSIONAL NEON DARK THEME + REALTIME UI
# ============================================================================

PROFESSIONAL_THEME = Theme({
    "primary": "#00f5ff",      # Cyan Neon
    "accent": "#ff00aa",       # Pink Neon
    "success": "#00ff9d",
    "warning": "#ffd700",
    "error": "#ff2a6d",
    "status": "#00f5ff bold",
    "panel.border": "#00f5ff",
    "panel.title": "#ffffff bold",
    "chat.user": "#00ff9d bold",
    "chat.assistant": "#00f5ff bold",
    "tool.name": "#ff00aa bold",
    "thinking": "dim italic",
    "tool.result": "dim",
    "info": "dim cyan",
    "model.name": "bold magenta",
    "user": "#00ff9d bold",
    "assistant": "#00f5ff bold",
    "dim": "#8888aa",
})

console = Console(theme=PROFESSIONAL_THEME)


def make_thai_flag_small():
    """Small Thai flag decoration for banner."""
    flag = Text()
    flag.append("██", style="bold red")
    flag.append("██", style="white")
    flag.append("██", style="bold #0033A0")
    flag.append("██", style="white")
    flag.append("██", style="bold red")
    return flag


# Stats
total_input_tokens = 0
total_output_tokens = 0
last_input_tokens = 0  # input tokens of the most recent request (= context used)
message_count = 0

# Edit history for /undo
_edit_history = deque(maxlen=50)  # auto-trims oldest on append
_edit_history_lock = threading.Lock()
_MAX_EDIT_HISTORY = 50

# Plan mode
plan_mode = False  # When True, AI plans only (no writes/edits)

# Task system
_tasks = []  # [{"id": 1, "text": "...", "status": "pending"|"in_progress"|"done"}, ...]
_tasks_lock = threading.Lock()
_task_counter = 0

# Skills system
_skills = {}  # {"name": {"prompt": "...", "description": "..."}, ...}


def _load_skills():
    """Load skills from skills/ folders (project, install dir, ~/.tooncode/)."""
    global _skills
    _skills = {}
    skill_dirs = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills"),  # install dir
        os.path.join(CWD, "skills"),                                         # project dir
        os.path.join(os.path.expanduser("~"), ".tooncode", "skills"),        # user dir
    ]
    for sdir in skill_dirs:
        if not os.path.isdir(sdir):
            continue
        for md_file in glob_mod.glob(os.path.join(sdir, "**", "*.md"), recursive=True):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()
                # Parse frontmatter ---\nname: xxx\ndescription: xxx\n---
                name = None
                desc = ""
                prompt = content
                fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
                if fm_match:
                    frontmatter = fm_match.group(1)
                    prompt = fm_match.group(2).strip()
                    for line in frontmatter.split("\n"):
                        if line.startswith("name:"):
                            name = line.split(":", 1)[1].strip().lower()
                        elif line.startswith("description:"):
                            desc = line.split(":", 1)[1].strip()
                if not name:
                    name = os.path.splitext(os.path.basename(md_file))[0].lower()
                if not desc:
                    desc = name
                # Category = parent folder name
                category = os.path.basename(os.path.dirname(md_file))
                if category == "skills":
                    category = ""
                if prompt:
                    _skills[name] = {
                        "prompt": prompt,
                        "description": desc,
                        "category": category,
                        "source": md_file,
                    }
            except Exception:
                pass


# ============================================================================
# MCP (Model Context Protocol) Server Support
# ============================================================================

_mcp_servers: Dict[str, "MCPServer"] = {}  # name -> MCPServer instance


class MCPServer:
    """Manages a single MCP server subprocess communicating via JSON-RPC over stdin/stdout."""

    def __init__(self, name: str, command: str, args: list = None, env: dict = None):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env
        self.process: Optional[subprocess.Popen] = None
        self.tools: list = []  # discovered tools [{name, description, inputSchema}, ...]
        self._request_id = 0
        self._lock = threading.Lock()

    def start(self) -> bool:
        """Start the MCP server subprocess. Returns True on success."""
        try:
            full_env = os.environ.copy()
            if self.env:
                full_env.update(self.env)
            self.process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=full_env,
                bufsize=0,
            )
            # Initialize the server
            resp = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "tooncode", "version": VERSION},
            })
            if resp is None:
                self.stop()
                return False
            # Send initialized notification (no id, no response expected)
            self._send_notification("notifications/initialized", {})
            return True
        except Exception as e:
            console.print(f"[error]MCP server '{self.name}' failed to start: {e}[/error]")
            self.process = None
            return False

    def stop(self):
        """Stop the MCP server subprocess."""
        if self.process:
            try:
                self.process.stdin.close()
            except Exception:
                pass
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

    @property
    def is_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send_request(self, method: str, params: dict) -> Optional[dict]:
        """Send a JSON-RPC request and wait for the response."""
        if not self.process or not self.is_alive:
            return None
        with self._lock:
            try:
                req = {
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": method,
                    "params": params,
                }
                raw = json.dumps(req) + "\n"
                self.process.stdin.write(raw.encode("utf-8"))
                self.process.stdin.flush()

                # Read response line
                line = self.process.stdout.readline()
                if not line:
                    return None
                return json.loads(line.decode("utf-8"))
            except Exception as e:
                console.print(f"[error]MCP '{self.name}' request error ({method}): {e}[/error]")
                return None

    def _send_notification(self, method: str, params: dict):
        """Send a JSON-RPC notification (no id, no response expected)."""
        if not self.process or not self.is_alive:
            return
        try:
            notif = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            }
            raw = json.dumps(notif) + "\n"
            self.process.stdin.write(raw.encode("utf-8"))
            self.process.stdin.flush()
        except Exception:
            pass

    def discover_tools(self) -> list:
        """Send tools/list request and return discovered tools."""
        resp = self._send_request("tools/list", {})
        if resp and "result" in resp:
            self.tools = resp["result"].get("tools", [])
        else:
            self.tools = []
        return self.tools

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call a tool on this MCP server. Returns the result as a string."""
        if not self.is_alive:
            # Try to restart
            console.print(f"[dim]MCP server '{self.name}' is down, attempting restart...[/dim]")
            if not self.start():
                return f"[MCP error] Server '{self.name}' is not running and failed to restart."
            self.discover_tools()

        resp = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        if resp is None:
            return f"[MCP error] No response from server '{self.name}'."
        if "error" in resp:
            err = resp["error"]
            return f"[MCP error] {err.get('message', str(err))}"
        result = resp.get("result", {})
        # MCP tool results have a "content" array with text/image blocks
        content_parts = result.get("content", [])
        texts = []
        for part in content_parts:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
            elif isinstance(part, str):
                texts.append(part)
        return "\n".join(texts) if texts else json.dumps(result)


def _load_mcp_servers():
    """Load and start MCP servers from ~/.tooncode/mcp.json.

    Config format:
        {
          "servers": {
            "name": {"command": "...", "args": [...], "env": {...}},
            ...
          }
        }
    """
    global _mcp_servers
    config_path = os.path.join(os.path.expanduser("~"), ".tooncode", "mcp.json")
    if not os.path.exists(config_path):
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        console.print(f"[error]Failed to read MCP config ({config_path}): {e}[/error]")
        return

    servers_cfg = config.get("servers", {})
    if not servers_cfg:
        return

    for name, cfg in servers_cfg.items():
        command = cfg.get("command")
        if not command:
            console.print(f"[error]MCP server '{name}': missing 'command' in config[/error]")
            continue

        args = cfg.get("args", [])
        env = cfg.get("env")
        server = MCPServer(name, command, args, env)

        if not server.start():
            continue

        tools = server.discover_tools()
        _mcp_servers[name] = server

        # Register each discovered tool in TOOLS and TOOL_HANDLERS
        for tool in tools:
            tool_name = f"mcp_{name}_{tool['name']}"
            tool_def = {
                "name": tool_name,
                "description": f"[MCP:{name}] {tool.get('description', tool['name'])}",
                "input_schema": tool.get("inputSchema", {"type": "object", "properties": {}}),
            }
            TOOLS.append(tool_def)

            # Capture variables for closure
            _srv_name = name
            _tool_original_name = tool["name"]
            TOOL_HANDLERS[tool_name] = lambda args, sn=_srv_name, tn=_tool_original_name: _call_mcp_tool(sn, tn, args)

    total_tools = sum(len(s.tools) for s in _mcp_servers.values())
    if _mcp_servers:
        console.print(f"[dim]  MCP: {len(_mcp_servers)} server(s) started, {total_tools} tool(s) discovered[/dim]")


def _call_mcp_tool(server_name: str, tool_name: str, arguments: dict) -> str:
    """Forward a tool call to the appropriate MCP server."""
    server = _mcp_servers.get(server_name)
    if not server:
        return f"[MCP error] Server '{server_name}' not found."
    return server.call_tool(tool_name, arguments)


def _shutdown_mcp_servers():
    """Stop all MCP server subprocesses."""
    for name, server in _mcp_servers.items():
        try:
            server.stop()
        except Exception:
            pass
    _mcp_servers.clear()


# Codebase index
_codebase_index = ""  # formatted string of project structure + symbols

_INDEX_SKIP_DIRS = {"node_modules", "__pycache__", ".git", "venv", ".venv", "env",
                    "dist", "build", ".next", ".tox", ".mypy_cache", ".pytest_cache",
                    "coverage", ".svn", "vendor", "target"}
_INDEX_SKIP_EXTS = {".pyc", ".pyo", ".min.js", ".min.css", ".map", ".lock",
                    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".bmp", ".webp",
                    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
                    ".woff", ".woff2", ".ttf", ".eot", ".otf",
                    ".exe", ".dll", ".so", ".dylib", ".o", ".a",
                    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
                    ".db", ".sqlite", ".sqlite3", ".jar", ".class",
                    ".pdf", ".doc", ".docx", ".xls", ".xlsx"}
_SYMBOL_RE = re.compile(
    r'^\s*(?:'
    r'(?:export\s+)?(?:async\s+)?(?:def|function|class)\s+(\w+)'
    r'|(?:export\s+)?(?:const|let|var)\s+(\w+)\s*='
    r'|(?:export\s+default\s+(?:class|function)\s+(\w+))'
    r'|(?:interface|type|enum)\s+(\w+)'
    r')',
    re.MULTILINE
)


def _get_index_cache_path() -> str:
    """Return cache file path for current CWD's index."""
    cache_dir = os.path.join(os.path.expanduser("~"), ".tooncode", "index_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cwd_hash = hashlib.md5(CWD.encode()).hexdigest()[:12]
    return os.path.join(cache_dir, f"{cwd_hash}.txt")


def _build_codebase_index(directory: str = None) -> str:
    """Scan project directory and build a concise index of files and symbols."""
    global _codebase_index
    if directory is None:
        directory = CWD

    files_by_ext = {}
    symbols_by_file = {}
    total_files = 0
    max_files = 500

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in _INDEX_SKIP_DIRS and not d.startswith(".")]
        rel_root = os.path.relpath(root, directory)

        for fname in files:
            if total_files >= max_files:
                break
            ext = os.path.splitext(fname)[1].lower()
            if ext in _INDEX_SKIP_EXTS:
                continue

            rel_path = os.path.join(rel_root, fname) if rel_root != "." else fname
            rel_path = rel_path.replace("\\", "/")
            total_files += 1
            files_by_ext.setdefault(ext or "(no ext)", []).append(rel_path)

            if ext in (".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".go", ".rs", ".java", ".rb", ".php"):
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(50000)
                    seen = set()
                    syms = []
                    for m in _SYMBOL_RE.finditer(content):
                        sym = m.group(1) or m.group(2) or m.group(3) or m.group(4)
                        if sym and sym not in seen:
                            seen.add(sym)
                            syms.append(sym)
                    if syms:
                        symbols_by_file[rel_path] = syms
                except Exception:
                    pass
        if total_files >= max_files:
            break

    lines = [f"Project: {os.path.basename(directory)} ({total_files} files)"]
    type_summary = sorted(files_by_ext.items(), key=lambda x: -len(x[1]))
    lines.append("Types: " + ", ".join(f"{ext}:{len(p)}" for ext, p in type_summary[:15]))

    top_files = [p for paths in files_by_ext.values() for p in paths if "/" not in p]
    if top_files:
        lines.append("Root: " + ", ".join(sorted(top_files)[:20]))

    top_dirs = set()
    for paths in files_by_ext.values():
        for p in paths:
            parts = p.split("/")
            if len(parts) > 1:
                top_dirs.add(parts[0])
                if len(parts) > 2:
                    top_dirs.add(parts[0] + "/" + parts[1])
    if top_dirs:
        lines.append("Dirs: " + ", ".join(sorted(top_dirs)[:30]))

    lines.append("")
    lines.append("Symbols:")
    remaining = 2000 - sum(len(l) + 1 for l in lines)
    for fpath, syms in sorted(symbols_by_file.items()):
        entry = f"  {fpath}: {', '.join(syms[:15])}"
        if len(entry) > remaining:
            lines.append("  ... (truncated)")
            break
        lines.append(entry)
        remaining -= len(entry) + 1

    result = "\n".join(lines)
    _codebase_index = result

    try:
        cache_path = _get_index_cache_path()
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(result)
    except Exception:
        pass

    return result


def _load_cached_index() -> bool:
    """Load index from cache if it exists. Returns True if loaded."""
    global _codebase_index
    try:
        cache_path = _get_index_cache_path()
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                _codebase_index = f.read()
            return True
    except Exception:
        pass
    return False


# ============================================================================
# Advanced Project Init — Deep project understanding
# ============================================================================


def _detect_tech_stack() -> str:
    """Detect tech stack in detail."""
    stack = []
    files = os.listdir(CWD)

    # Python
    req_path = os.path.join(CWD, "requirements.txt")
    if any(f in files for f in ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]):
        stack.append("Python")
        if os.path.exists(req_path):
            try:
                with open(req_path, encoding="utf-8") as f:
                    req_content = f.read().lower()
                if "fastapi" in req_content: stack.append("FastAPI")
                elif "flask" in req_content: stack.append("Flask")
                elif "django" in req_content: stack.append("Django")
                if "sqlalchemy" in req_content: stack.append("SQLAlchemy")
                if "celery" in req_content: stack.append("Celery")
                if "pytest" in req_content: stack.append("pytest")
            except Exception:
                pass

    # Node.js / TypeScript
    if "package.json" in files:
        try:
            with open(os.path.join(CWD, "package.json"), encoding="utf-8") as f:
                pkg = json.load(f)
            deps = list(pkg.get("dependencies", {}).keys()) + list(pkg.get("devDependencies", {}).keys())
            if "typescript" in deps or "tsconfig.json" in files:
                stack.append("TypeScript")
            else:
                stack.append("Node.js")
            if any("next" in d for d in deps): stack.append("Next.js")
            elif any("nuxt" in d for d in deps): stack.append("Nuxt.js")
            elif any("react" in d for d in deps): stack.append("React")
            elif any("vue" in d for d in deps): stack.append("Vue.js")
            elif any("angular" in d for d in deps): stack.append("Angular")
            elif any("svelte" in d for d in deps): stack.append("Svelte")
            if any("express" in d for d in deps): stack.append("Express")
            if any("prisma" in d for d in deps): stack.append("Prisma")
            if any("drizzle" in d for d in deps): stack.append("Drizzle ORM")
            if any("tailwind" in d for d in deps): stack.append("Tailwind CSS")
            if any("vitest" in d for d in deps): stack.append("Vitest")
            elif any("jest" in d for d in deps): stack.append("Jest")
            if any("trpc" in d for d in deps): stack.append("tRPC")
            if any("supabase" in d for d in deps): stack.append("Supabase")
        except Exception:
            stack.append("Node.js")

    # Other languages
    if "Cargo.toml" in files: stack.append("Rust")
    if "go.mod" in files: stack.append("Go")
    if any(f.endswith(".csproj") or f.endswith(".sln") for f in files): stack.append(".NET")
    if "pubspec.yaml" in files: stack.append("Flutter / Dart")
    if "composer.json" in files: stack.append("PHP")
    if "Gemfile" in files: stack.append("Ruby")
    if "build.gradle" in files or "pom.xml" in files: stack.append("Java")

    # Infrastructure
    if "Dockerfile" in files or "docker-compose.yml" in files: stack.append("Docker")
    if ".github" in files: stack.append("GitHub Actions")
    if "vercel.json" in files: stack.append("Vercel")
    if "netlify.toml" in files: stack.append("Netlify")

    return " + ".join(stack) if stack else "Unknown / Custom"


def _find_important_files() -> dict:
    """Find important project files automatically."""
    patterns = {
        "README.md": "Project documentation",
        "package.json": "Node.js project config",
        "tsconfig.json": "TypeScript config",
        "requirements.txt": "Python dependencies",
        "pyproject.toml": "Python project config",
        "setup.py": "Python package config",
        "Cargo.toml": "Rust project config",
        "go.mod": "Go module file",
        "docker-compose.yml": "Docker services",
        "Dockerfile": "Container build",
        ".env.example": "Environment variables template",
        "prisma/schema.prisma": "Database schema (Prisma)",
        "app/layout.tsx": "Next.js root layout",
        "app/page.tsx": "Next.js home page",
        "src/main.py": "Python entry point",
        "src/app.py": "Python app entry point",
        "main.py": "Python entry point",
        "index.js": "Node.js entry point",
        "index.ts": "TypeScript entry point",
        "src/index.ts": "TypeScript entry point",
        "src/App.tsx": "React main component",
        "src/main.ts": "Vue/Vite entry point",
        "manage.py": "Django management",
        "alembic.ini": "Database migrations config",
    }
    result = {}
    for pattern, desc in patterns.items():
        full = os.path.join(CWD, pattern)
        if os.path.exists(full):
            rel = pattern.replace("\\", "/")
            result[rel] = desc
        else:
            # Try glob for nested matches
            matches = glob_mod.glob(os.path.join(CWD, "**", os.path.basename(pattern)), recursive=True)
            for m in matches[:2]:
                rel = os.path.relpath(m, CWD).replace("\\", "/")
                if rel not in result and ".git" not in rel and "node_modules" not in rel:
                    result[rel] = desc
    return result


def _call_model_for_summary(prompt: str) -> str:
    """Call current model for project summary."""
    body = {
        "model": MODEL,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "stream": False,
    }
    if MODEL not in NO_SAMPLING_PARAMS:
        body["temperature"] = 0.7

    headers = dict(HEADERS)
    headers["x-api-key"] = API_KEY
    headers["anthropic-version"] = "2023-06-01"

    with httpx.Client(timeout=90.0) as client:
        resp = client.post(_get_current_api_url(), headers=headers, json=body)
        if resp.status_code == 200:
            data = resp.json()
            for block in data.get("content", []):
                if block.get("type") == "text":
                    return block.get("text", "")
    return "AI summary generation failed."


def _advanced_init() -> str:
    """Create TOONCODE.md with deep project understanding."""
    console.print("[bold cyan]Starting Advanced Project Analysis...[/bold cyan]")

    # 1. Build codebase index if not exists
    if not _codebase_index:
        console.print("[dim]Scanning project structure...[/dim]")
        _build_codebase_index()

    # 2. Detect tech stack
    console.print("[dim]Detecting tech stack...[/dim]")
    tech_stack = _detect_tech_stack()
    console.print(f"[dim]  Stack: {tech_stack}[/dim]")

    # 3. Find and read important files
    console.print("[dim]Finding important files...[/dim]")
    important_files = _find_important_files()
    file_summaries = {}
    for fpath, desc in important_files.items():
        try:
            full_path = os.path.join(CWD, fpath)
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(3000)
            file_summaries[fpath] = {"description": desc, "preview": content[:1200]}
            console.print(f"[dim]  + {fpath}[/dim]")
        except Exception:
            file_summaries[fpath] = {"description": desc, "preview": "(could not read)"}

    # 4. Read README
    readme_content = ""
    readme_path = os.path.join(CWD, "README.md")
    if os.path.exists(readme_path):
        try:
            with open(readme_path, "r", encoding="utf-8") as f:
                readme_content = f.read()[:3000]
        except Exception:
            pass

    # 5. Build AI analysis prompt
    file_info = "\n".join(f"- {k}: {v['description']}" for k, v in file_summaries.items())
    analysis_prompt = f"""You are an expert software architect. Analyze this project and create a deep, accurate understanding.

Project directory: {CWD}

Codebase structure:
{_codebase_index[:3000] if _codebase_index else '(not available)'}

Tech stack: {tech_stack}

Important files found:
{file_info}

README.md (first 3000 chars):
{readme_content if readme_content else '(no README)'}

Create a comprehensive project overview for an AI coding agent.
Focus on:
- What this project actually does (purpose, domain)
- Architecture & main patterns used
- Key business logic / domain concepts
- Important files and their roles
- Coding style & conventions observed
- Things the AI must remember when editing code

Answer in Thai, be clear, natural, and detailed."""

    # 6. Call AI for summary
    console.print("[dim]Asking AI to deeply understand the project...[/dim]")
    try:
        summary = _call_model_for_summary(analysis_prompt)
    except Exception as e:
        summary = f"AI summary generation failed: {e}"

    # 7. Build TOONCODE.md content
    project_name = os.path.basename(CWD)
    content = f"""# {project_name} - Project Context for ToonCode

**Generated by ToonCode Advanced Init** — {datetime.now().strftime('%d %b %Y %H:%M')}

## 1. Project Overview
{summary}

## 2. Tech Stack
{tech_stack}

## 3. Architecture & Folder Structure
```
{_codebase_index[:5000] if _codebase_index else '(run /index to generate)'}
```

## 4. Key Files & Their Purpose

"""
    for fpath, info in file_summaries.items():
        content += f"### `{fpath}`\n{info['description']}\n\n"

    # Import from other AI config files
    _import_files = [
        ("CLAUDE.md", "Boss AI"), (".claude/CLAUDE.md", "Boss AI"),
        ("GEMINI.md", "Gemini"), (".cursorrules", "Cursor"),
        (".cursor/rules", "Cursor"), ("COPILOT.md", "Copilot"),
    ]
    imported_content = ""
    for fname, source in _import_files:
        fpath = os.path.join(CWD, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    imported_text = f.read().strip()
                if imported_text:
                    imported_content += f"\n\n## Imported from {source} ({fname})\n{imported_text[:2000]}"
                    console.print(f"[dim]  Imported from {source}: {fname}[/dim]")
            except Exception:
                pass

    content += """
## 5. AI Coding Guidelines
- Read this file before working on the project
- Always use absolute paths
- Read files before editing with `read` tool
- Use `edit` or `multi_edit` for modifications
- Don't add features not in the spec
- Follow the project's existing coding style
- Write clean, maintainable code

## 6. Notes / Recent Decisions
(Add important notes here)
"""
    if imported_content:
        content += imported_content

    content += f"\n\n---\n**Use `/init force` to regenerate**\n"

    # 8. Write file
    md_path = os.path.join(CWD, "TOONCODE.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)

    console.print(f"[bold green]Created TOONCODE.md with deep project understanding[/bold green]")
    console.print(f"[dim]   -> {md_path}[/dim]")
    return "Advanced initialization completed. TOONCODE.md created."


# ============================================================================
# Semantic Code Search — LanceDB vector search
# ============================================================================

_lance_db = None
_lance_table = None
_semantic_available = False

try:
    import lancedb
    _semantic_available = True
except ImportError:
    pass

# Backward compat alias
_chroma_available = _semantic_available


def _init_lance():
    """Initialize LanceDB with persistent storage."""
    global _lance_db, _lance_table
    if not _semantic_available:
        return False
    if _lance_table is not None:
        return True
    try:
        db_path = os.path.join(os.path.expanduser("~"), ".tooncode", "lance_db")
        os.makedirs(db_path, exist_ok=True)
        _lance_db = lancedb.connect(db_path)
        # Check if table exists for this project
        proj_hash = hashlib.md5(CWD.encode()).hexdigest()[:12]
        table_name = f"tooncode_{proj_hash}"
        if table_name in _lance_db.table_names():
            _lance_table = _lance_db.open_table(table_name)
        return True
    except Exception as e:
        console.print(f"[dim]LanceDB init failed: {e}[/dim]")
        return False


def _simple_embed(text: str) -> list:
    """Embedding using word n-grams + code-aware tokens. Fast, no GPU needed."""
    text_lower = text.lower()

    # Extract meaningful tokens: identifiers, keywords, strings
    words = re.findall(r'[a-z_][a-z0-9_]{1,}', text_lower)

    # Split camelCase and snake_case into sub-tokens
    expanded = []
    for w in words:
        # snake_case split
        parts = w.split("_")
        for p in parts:
            if p:
                expanded.append(p)
                # camelCase split
                sub = re.findall(r'[a-z]+', p)
                if len(sub) > 1:
                    expanded.extend(sub)
    words = expanded

    # Create a 384-dim embedding based on hash buckets
    dim = 384
    vec = [0.0] * dim

    # Word-level features (strongest signal)
    seen_words = set()
    for w in words:
        if len(w) < 2:
            continue
        idx = hash(w) % dim
        # TF-like: first occurrence counts more
        if w not in seen_words:
            vec[idx] += 2.0
            seen_words.add(w)
        else:
            vec[idx] += 0.3

    # Bigram features (word pairs capture context)
    for i in range(len(words) - 1):
        if len(words[i]) < 2 or len(words[i+1]) < 2:
            continue
        bigram = f"{words[i]}_{words[i+1]}"
        idx = hash(bigram) % dim
        vec[idx] += 1.0

    # Code structure signals
    structure_signals = {
        "def ": 5, "class ": 5, "function ": 5, "import ": 3, "from ": 3,
        "return ": 3, "if ": 2, "for ": 2, "while ": 2, "try:": 2,
        "async ": 3, "await ": 3, "export ": 3, "const ": 2, "let ": 2,
        "interface ": 4, "type ": 3, "struct ": 4, "impl ": 4,
        "SELECT ": 4, "INSERT ": 4, "CREATE ": 4, "ALTER ": 4,
        "http": 3, "api": 3, "route": 3, "handler": 3, "middleware": 3,
        "database": 3, "query": 3, "model": 3, "schema": 3,
        "test": 3, "assert": 3, "mock": 3, "expect": 3,
        "error": 3, "exception": 3, "catch": 3, "throw": 3,
        "render": 3, "component": 3, "template": 3, "view": 3,
        "config": 3, "setting": 3, "env": 3, "secret": 3,
        "auth": 4, "login": 4, "token": 4, "session": 4, "permission": 4,
        "stream": 3, "socket": 3, "channel": 3, "message": 3,
        "file": 3, "read": 3, "write": 3, "path": 3,
    }
    for signal, weight in structure_signals.items():
        if signal in text_lower:
            idx = hash(f"__signal_{signal}") % dim
            vec[idx] += weight

    # Normalize to unit vector
    magnitude = sum(v * v for v in vec) ** 0.5
    if magnitude > 0:
        vec = [v / magnitude for v in vec]

    return vec


def _index_codebase_semantic():
    """Index all code files into LanceDB for semantic search."""
    global _lance_table
    if not _semantic_available:
        return "LanceDB not available. Install with: pip install lancedb"
    if not _init_lance():
        return "LanceDB initialization failed."

    console.print("[dim]Indexing codebase for semantic search...[/dim]")

    code_exts = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".rb",
                 ".php", ".c", ".cpp", ".h", ".cs", ".swift", ".kt", ".scala",
                 ".html", ".css", ".scss", ".vue", ".svelte", ".sql", ".sh", ".bat",
                 ".yaml", ".yml", ".toml", ".json", ".md", ".txt"}

    skip_dirs = {".git", "node_modules", "__pycache__", ".next", "dist", "build",
                 "venv", ".venv", "env", ".env", "vendor", "target", ".tooncode"}

    records = []
    doc_id = 0

    for root, dirs, files_list in os.walk(CWD):
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for fname in files_list:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in code_exts:
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, CWD).replace("\\", "/")

            try:
                size = os.path.getsize(fpath)
                if size > 500_000 or size == 0:
                    continue
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue

            chunks = _split_into_chunks(content, rel_path, ext)

            for i, chunk in enumerate(chunks):
                if len(chunk.strip()) < 20:
                    continue
                doc_id += 1
                vec = _simple_embed(chunk)
                records.append({
                    "id": f"doc_{doc_id}",
                    "text": chunk[:2000],
                    "file": rel_path,
                    "chunk_index": i,
                    "ext": ext,
                    "vector": vec,
                })

    if not records:
        return "No code files found to index."

    try:
        import pyarrow as pa
        proj_hash = hashlib.md5(CWD.encode()).hexdigest()[:12]
        table_name = f"tooncode_{proj_hash}"

        # Drop old table if exists
        if table_name in _lance_db.table_names():
            _lance_db.drop_table(table_name)

        _lance_table = _lance_db.create_table(table_name, records)
        console.print(f"[green]Indexed {len(records)} code chunks[/green]")
        return f"Indexed {len(records)} code chunks for semantic search."
    except Exception as e:
        return f"Indexing failed: {e}"


def _split_into_chunks(content: str, filepath: str, ext: str) -> list:
    """Split file content into meaningful chunks for embedding."""
    lines = content.split("\n")

    # For Python: split by functions/classes
    if ext == ".py":
        return _split_python_chunks(lines)
    # For JS/TS: split by functions/classes
    elif ext in (".js", ".ts", ".tsx", ".jsx"):
        return _split_js_chunks(lines)
    # For other code: split by ~30 line blocks
    elif ext in (".java", ".go", ".rs", ".c", ".cpp", ".cs", ".rb", ".php"):
        return _split_by_lines(lines, 30)
    # For docs/config: split by sections or paragraphs
    else:
        return _split_by_lines(lines, 40)


def _split_python_chunks(lines: list) -> list:
    """Split Python code by functions and classes."""
    chunks = []
    current = []
    for line in lines:
        stripped = line.lstrip()
        if (stripped.startswith("def ") or stripped.startswith("class ") or
                stripped.startswith("async def ")):
            if current:
                chunks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current))
    # Merge very small chunks
    return _merge_small_chunks(chunks, min_size=50)


def _split_js_chunks(lines: list) -> list:
    """Split JS/TS code by functions and components."""
    chunks = []
    current = []
    for line in lines:
        stripped = line.lstrip()
        if (stripped.startswith("function ") or stripped.startswith("export ") or
                stripped.startswith("const ") and ("=>" in line or "function" in line) or
                stripped.startswith("class ")):
            if current and len("\n".join(current)) > 50:
                chunks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current))
    return _merge_small_chunks(chunks, min_size=50)


def _split_by_lines(lines: list, chunk_size: int = 30) -> list:
    """Split by fixed line count with overlap."""
    chunks = []
    for i in range(0, len(lines), chunk_size - 5):  # 5 line overlap
        chunk = "\n".join(lines[i:i+chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def _merge_small_chunks(chunks: list, min_size: int = 50) -> list:
    """Merge chunks smaller than min_size with their neighbor."""
    if not chunks:
        return chunks
    merged = []
    buffer = ""
    for chunk in chunks:
        if len(chunk) < min_size:
            buffer += "\n" + chunk
        else:
            if buffer:
                merged.append(buffer.strip())
                buffer = ""
            merged.append(chunk)
    if buffer:
        if merged:
            merged[-1] += "\n" + buffer
        else:
            merged.append(buffer.strip())
    return merged


def exec_semantic_search(args: dict) -> str:
    """Semantic search across the codebase using LanceDB."""
    if not _semantic_available:
        return "LanceDB not installed. Run: pip install lancedb"

    query = args.get("query", "")
    n_results = int(args.get("n_results", 5))

    if not query:
        return "Please provide a search query."

    if not _init_lance():
        return "LanceDB initialization failed."

    # Auto-index if no table
    if _lance_table is None:
        console.print("[dim]No index found. Building semantic index...[/dim]")
        _index_codebase_semantic()

    if _lance_table is None:
        return "No code indexed. No files found to search."

    try:
        query_vec = _simple_embed(query)
        results = _lance_table.search(query_vec).limit(min(n_results, 10)).to_list()

        if not results:
            return f"No results found for: {query}"

        output = []
        for i, row in enumerate(results):
            score = 1.0 - row.get("_distance", 0)  # cosine similarity
            fpath = row.get("file", "?")
            text = row.get("text", "")
            output.append(f"--- [{i+1}] {fpath} (score: {score:.3f}) ---")
            output.append(text[:500])
            output.append("")

        return "\n".join(output)
    except Exception as e:
        return f"Search failed: {e}"


# Context window sizes per model
# Build from settings
CONTEXT_WINDOWS = {m["name"]: m.get("context", 200_000) for m in _settings["models"]}
NO_SAMPLING_PARAMS = {m["name"] for m in _settings["models"] if m.get("no_sampling")}


# ============================================================================
# System Prompt
# ============================================================================

_system_prompt_cache = {"prompt": None, "mtimes": {}, "model": None, "plan_mode": None}

def build_system_prompt() -> str:
    # Cache: only rebuild if context files changed, model changed, or plan_mode changed
    _context_files_for_cache = [
        "TOONCODE.md", "CLAUDE.md", ".claude/CLAUDE.md", "GEMINI.md",
        ".cursorrules", ".cursor/rules", "COPILOT.md",
        ".github/copilot-instructions.md", "AGENTS.md", "AI_CONTEXT.md",
    ]
    current_mtimes = {}
    for cf in _context_files_for_cache:
        cf_path = os.path.join(CWD, cf)
        try:
            current_mtimes[cf] = os.path.getmtime(cf_path)
        except OSError:
            pass
    cache = _system_prompt_cache
    if (cache["prompt"] is not None
        and cache["mtimes"] == current_mtimes
        and cache["model"] == MODEL
        and cache["plan_mode"] == plan_mode):
        return cache["prompt"]
    prompt = f"""You are ToonCode, an expert AI coding agent. You MUST use tools to complete tasks — never just talk about what you would do.

# CRITICAL RULES
1. ALWAYS use tools. If asked to fix code → use read then edit. If asked a question about files → use read/glob/grep. If asked to run something → use bash.
2. NEVER respond with only text when a tool call would be more helpful. ACT, don't just explain.
3. You can call MULTIPLE tools in one response. Do it whenever possible for speed.
4. If a tool fails, try a different approach. Do NOT give up after one failure.
5. NEVER use wmic, systeminfo, or deprecated Windows commands. Use PowerShell cmdlets (Get-CimInstance, Get-ComputerInfo, etc).

# Tone and style
- Be concise and direct. Under 4 lines unless asked for detail.
- Output is displayed in a CLI terminal. Use GitHub-flavored markdown.
- DO NOT add comments to code unless asked.

# Doing tasks
- Read files BEFORE editing them.
- Use glob/grep to explore the codebase BEFORE making changes.
- Implement solutions completely — don't leave TODOs or placeholders.
- Verify your changes work (run tests, check syntax).
- NEVER commit unless explicitly asked.
- Prefer editing existing files over creating new ones.
- Always use ABSOLUTE file paths.

# Tool usage
- Batch independent tool calls in one response for speed.
{"- For bash on Windows: use PowerShell cmdlets ONLY. NEVER use Unix commands (grep, sed, awk, head, tail, curl|grep, mkdir -p). Use web_fetch instead of curl. Use Get-ChildItem instead of ls. NEVER use wmic." if platform.system() == "Windows" else "- For bash: use standard Unix commands (ls, cat, grep, etc)."}
- For bash: NEVER run interactive commands that wait for input.
- ANTI-LOOP RULE: If ANY tool fails, you MUST try a DIFFERENT approach. NEVER retry the exact same tool call.
  - bash fails? → try different command or use a dedicated tool instead
  - edit oldString not found? → READ the file first, then use the exact text from the file
  - web_fetch fails? → try web_search or browser instead
- To read web pages: use `web_fetch` tool (NOT curl). To search: use `web_search` tool.
- Before editing a file, ALWAYS read it first to see the exact content.

# Browser & Web
You have a `browser` tool (Playwright) and `web_fetch` tool:
- On Windows/Mac: use `browser` for full control (open, click, fill, screenshot, console, network)
- On Linux/headless: prefer `web_fetch` for reading pages (browser may not be available)
- `browser` auto-falls back to `web_fetch` if Playwright fails
- For simple page reading, `web_fetch` is faster and lighter than `browser`
- Use `browser` only when you need: clicking, filling forms, JavaScript, console logs, screenshots

# Sub-agents
For complex tasks, use `spawn_agent` to delegate work:
- **coder**: writes/edits code files
- **reviewer**: reviews code for bugs and fixes them
- **tester**: writes and runs tests
- **researcher**: reads codebase and answers questions
Example: spawn a coder to build a feature while you plan the next step.
Each agent runs its own tool-use loop independently and returns the result.

You are powered by {MODEL}.
<env>
  Working directory: {CWD}
  Platform: {platform.system()} ({platform.platform()})
  Today's date: {datetime.now().strftime('%a %b %d %Y')}
  Shell: {'powershell — use PowerShell cmdlets, NOT cmd.exe/wmic' if platform.system() == 'Windows' else 'bash'}
</env>

# Web research
When the user asks about current events, news, or anything requiring up-to-date information:
1. Use `web_search` to find relevant results — search results include dates when available (extracted from URLs or snippets), shown as [YYYY-MM-DD]
2. **Prioritize the most recent results** — prefer articles with dates closest to today's date
3. Then use `web_fetch` on the most relevant and recent URLs (1-3 pages) to get the actual content
4. Summarize the information from the fetched pages, **always include the publication date** for each piece of information
Always follow up web_search with web_fetch. When presenting information, clearly state WHEN it was published (e.g. "ตามข่าววันที่ 10 เม.ย. 2026..."). If no date is available, say so.

# Task System
You have task_create, task_update, task_list tools. For complex work:
1. First create tasks to break the work into steps (task_create)
2. Mark each task in_progress when you start it (task_update)
3. Mark each task done when finished (task_update)
This helps the user track your progress.

# Getting help when stuck
If you encounter a bug or error you cannot solve after 2 attempts, use the `bosshelp` tool.
It sends your problem to Boss AI (a more powerful AI) which will give you the exact solution.
Always include: the problem, what you tried, the code, and the error message.
After getting the answer, APPLY THE FIX IMMEDIATELY and continue working. Never stop."""

    if plan_mode:
        prompt += """

# PLAN MODE ACTIVE
You are in PLAN MODE. You must ONLY:
- Read files (read, glob, grep) to understand the codebase
- Create a detailed plan with numbered steps
- Create tasks for each step (task_create)
- DO NOT write, edit, or execute any bash commands that modify files
- DO NOT use write, edit tools
- Output a clear plan the user can review before executing"""

    # Auto-load project context files (TOONCODE.md + others)
    # Priority: TOONCODE.md first, then import from other AI tool configs
    _context_files = [
        "TOONCODE.md",
        "CLAUDE.md",
        ".claude/CLAUDE.md",
        "GEMINI.md",
        ".cursorrules",
        ".cursor/rules",
        "COPILOT.md",
        ".github/copilot-instructions.md",
        "AGENTS.md",
        "AI_CONTEXT.md",
    ]
    loaded_contexts = []
    for cf in _context_files:
        cf_path = os.path.join(CWD, cf)
        if os.path.exists(cf_path):
            try:
                with open(cf_path, "r", encoding="utf-8") as f:
                    ctx = f.read().strip()
                if ctx:
                    loaded_contexts.append((cf, ctx))
            except Exception:
                pass

    if loaded_contexts:
        prompt += "\n\n# Project Context"
        for fname, ctx in loaded_contexts:
            # Limit each file to 3000 chars
            if len(ctx) > 3000:
                ctx = ctx[:3000] + "\n... (truncated)"
            prompt += f"\n\n## From {fname}\n{ctx}"

    # Codebase index — gives AI awareness of project structure without glob/grep
    if _codebase_index:
        prompt += f"\n\n# Codebase Index\nPre-scanned project structure and symbols (use /index to refresh):\n```\n{_codebase_index}\n```"

    # Auto-load recent memories (last 3)
    memory_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
    if os.path.exists(memory_dir):
        md_files = sorted(glob_mod.glob(os.path.join(memory_dir, "*.md")), reverse=True)[:3]
        if md_files:
            prompt += "\n\n# Past Conversation Memories\nYou have memories from past sessions. Use the `memory_search` tool if you need to find specific past context.\nRecent summaries:\n"
            for mf in md_files:
                try:
                    with open(mf, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                    # Only include first 300 chars as preview
                    preview = content[:300]
                    if len(content) > 300:
                        preview += "..."
                    prompt += f"\n---\n**{os.path.basename(mf)}**\n{preview}\n"
                except Exception:
                    pass

    # Update cache
    cache["prompt"] = prompt
    cache["mtimes"] = current_mtimes
    cache["model"] = MODEL
    cache["plan_mode"] = plan_mode
    return prompt


# ============================================================================
# Tools Definition
# ============================================================================

TOOLS = [
    {
        "name": "bash",
        "description": "Executes a command in the shell. Use for running scripts, git, npm, pip, docker, etc. The command runs in a subprocess with the given working directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"},
                "description": {"type": "string", "description": "Brief description of what this command does (5-10 words)"},
                "workdir": {"type": "string", "description": "Working directory for the command (optional, defaults to CWD)"},
                "timeout": {"type": "number", "description": "Timeout in milliseconds (default 120000)"},
                "background": {"type": "boolean", "description": "Run in background for long-running commands like dev servers (default false, auto-detected for npm run dev etc.)"},
            },
            "required": ["command", "description"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web for information. Returns a list of search results with titles, URLs, and snippets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "max_results": {"type": "number", "description": "Maximum number of results (default 5)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch the content of a web page. Returns the page text content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"},
                "max_length": {"type": "number", "description": "Maximum content length in characters (default 20000)"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "memory_search",
        "description": "Search past conversation memories for relevant context. Use when you need information from previous sessions - e.g. what was discussed before, what files were changed, what decisions were made.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or topic to find in past memories"},
                "limit": {"type": "number", "description": "Max results to return (default 5)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_save",
        "description": "Save an important note to memory for future sessions. Use when the user asks you to remember something, or when you learn important project context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title for the memory"},
                "content": {"type": "string", "description": "Content to remember"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "task_create",
        "description": "Create a new task in the task list. Use this to break work into steps and track progress. Create tasks BEFORE starting complex work.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Task description"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "task_update",
        "description": "Update a task's status. Mark as 'in_progress' when starting, 'done' when finished.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "number", "description": "Task ID number"},
                "status": {"type": "string", "description": "New status: pending, in_progress, done"},
            },
            "required": ["id", "status"],
        },
    },
    {
        "name": "task_list",
        "description": "List all current tasks with their status.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "bosshelp",
        "description": "CALL THIS when you are STUCK, hit an error you can't fix, or need expert help. Sends your problem to Boss AI (a more powerful AI) which will analyze and give you the exact solution. Always include the error message and relevant code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "problem": {"type": "string", "description": "What you're stuck on - describe the problem clearly"},
                "context": {"type": "string", "description": "What you were trying to do and what you already tried"},
                "code": {"type": "string", "description": "The relevant code that's causing issues"},
                "error": {"type": "string", "description": "The exact error message"},
            },
            "required": ["problem"],
        },
    },
    {
        "name": "read",
        "description": "Read a file from the filesystem. Returns the file contents with line numbers. Use absolute file paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filePath": {"type": "string", "description": "The absolute path to the file to read"},
                "offset": {"type": "number", "description": "Line number to start reading from (1-indexed, default 1)"},
                "limit": {"type": "number", "description": "Maximum number of lines to read (default 2000)"},
            },
            "required": ["filePath"],
        },
    },
    {
        "name": "write",
        "description": "Write content to a file, creating parent directories if needed. Overwrites the existing file completely.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filePath": {"type": "string", "description": "The absolute path to the file to write"},
                "content": {"type": "string", "description": "The full content to write to the file"},
            },
            "required": ["filePath", "content"],
        },
    },
    {
        "name": "edit",
        "description": "Perform an exact string replacement in a file. The oldString must match exactly (including whitespace and indentation). Only replaces the first occurrence unless replaceAll is true.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filePath": {"type": "string", "description": "The absolute path to the file to edit"},
                "oldString": {"type": "string", "description": "The exact text to find in the file"},
                "newString": {"type": "string", "description": "The text to replace it with"},
                "replaceAll": {"type": "boolean", "description": "If true, replace all occurrences (default false)"},
            },
            "required": ["filePath", "oldString", "newString"],
        },
    },
    {
        "name": "glob",
        "description": "Find files matching a glob pattern. Returns a list of matching file paths sorted by modification time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern to match (e.g., '**/*.py', 'src/**/*.ts')"},
                "path": {"type": "string", "description": "Base directory to search in (optional, defaults to CWD)"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "grep",
        "description": "Search file contents using a regular expression pattern. Returns matching lines with file paths and line numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regular expression pattern to search for"},
                "path": {"type": "string", "description": "Directory to search in (optional, defaults to CWD)"},
                "include": {"type": "string", "description": "File glob filter (e.g., '*.py', '*.js')"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "list_dir",
        "description": "List files and directories in a given path. Returns names with [dir] or [file] prefix. Use this to explore project structure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory to list (defaults to CWD)"},
                "recursive": {"type": "boolean", "description": "If true, list recursively (max 3 levels deep)"},
            },
            "required": [],
        },
    },
    {
        "name": "multi_edit",
        "description": "Apply multiple edits to a single file at once. More efficient than calling edit multiple times. Each edit is a {oldString, newString} pair applied in order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filePath": {"type": "string", "description": "Absolute path to the file"},
                "edits": {
                    "type": "array",
                    "description": "Array of edits, each with oldString and newString",
                    "items": {
                        "type": "object",
                        "properties": {
                            "oldString": {"type": "string"},
                            "newString": {"type": "string"},
                        },
                        "required": ["oldString", "newString"],
                    },
                },
            },
            "required": ["filePath", "edits"],
        },
    },
    {
        "name": "spawn_agent",
        "description": "Spawn a sub-agent to work on a task in parallel. The agent runs independently and returns its result. Use this to delegate work while you continue on other tasks. Types: 'coder' (writes code), 'reviewer' (reviews code), 'tester' (writes+runs tests), 'researcher' (reads code and answers questions).",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Clear description of what the agent should do"},
                "type": {"type": "string", "description": "Agent type: coder, reviewer, tester, or researcher", "enum": ["coder", "reviewer", "tester", "researcher"]},
                "context": {"type": "string", "description": "Optional context: file paths, code snippets, or plan to follow"},
            },
            "required": ["task", "type"],
        },
    },
    {
        "name": "screenshot",
        "description": "Capture a screenshot of the desktop screen or a specific window. Returns the file path and OCR-extracted text from the image.",
        "input_schema": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "description": "Optional: 'full' (entire screen, default), or 'x,y,w,h' to capture a region"},
                "window": {"type": "string", "description": "Optional: window title to capture (partial match)"},
            },
            "required": [],
        },
    },
    {
        "name": "http",
        "description": "Send HTTP requests (GET/POST/PUT/PATCH/DELETE). Full control over method, headers, body, and auth. Use for API testing, webhooks, REST endpoints.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Request URL"},
                "method": {"type": "string", "description": "HTTP method (default GET)", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]},
                "headers": {"type": "object", "description": "Custom headers as key-value pairs"},
                "body": {"type": "string", "description": "Request body (string or JSON string)"},
                "json_body": {"type": "object", "description": "JSON body (auto sets Content-Type)"},
                "auth": {"type": "string", "description": "Bearer token or 'user:pass' for basic auth"},
                "timeout": {"type": "number", "description": "Timeout in seconds (default 30)"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "browser",
        "description": "Control a real browser (Playwright). Actions: 'open' (navigate to URL), 'screenshot' (capture page + extract text), 'text' (extract page text), 'click' (click element), 'fill' (type into input), 'eval' (run JS), 'console' (get captured console.log), 'network' (get captured requests), 'errors' (get JS errors), 'close' (close browser). Browser stays open between calls. Console/network are captured automatically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action to perform", "enum": ["open", "screenshot", "text", "click", "fill", "eval", "console", "network", "errors", "close"]},
                "url": {"type": "string", "description": "URL to navigate to (for 'open' action)"},
                "selector": {"type": "string", "description": "CSS selector for 'click'/'fill' actions"},
                "value": {"type": "string", "description": "Text to type (for 'fill') or JS code (for 'eval')"},
                "wait": {"type": "number", "description": "Wait seconds after action (default 1)"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "semantic_search",
        "description": "Semantic code search — find code by meaning, not just keywords. Uses AI embeddings + ChromaDB vector database. Much smarter than grep for finding related code, similar patterns, or answering 'where is the code that handles X?'. Auto-indexes on first use.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language query describing what you're looking for (e.g., 'user authentication logic', 'database connection setup', 'error handling for API calls')"},
                "n_results": {"type": "number", "description": "Number of results to return (default 5, max 10)"},
            },
            "required": ["query"],
        },
    },
]


# ============================================================================
# Tool Execution
# ============================================================================

# Background processes tracking
_bg_processes: Dict[str, subprocess.Popen] = {}
_bg_processes_lock = threading.Lock()

def _cleanup_dead_bg_processes():
    """Remove finished background processes from tracking dict."""
    dead = [bg_id for bg_id, proc in _bg_processes.items() if proc.poll() is not None]
    for bg_id in dead:
        del _bg_processes[bg_id]

# Commands that should auto-run in background
_BG_PATTERNS = [
    # Node / JS
    "npm run dev", "npm start", "npm run serve", "npm run watch",
    "yarn dev", "yarn start", "yarn serve",
    "pnpm dev", "pnpm start", "pnpm serve",
    "bun dev", "bun run dev", "bun start",
    "deno task dev", "deno run --watch",
    "npx next dev", "npx vite", "npx nuxt dev",
    "npx expo start", "npx react-native start",
    "npx storybook", "npx prisma studio",
    "webpack serve", "webpack-dev-server",
    "ng serve",  # Angular
    "remix dev", "astro dev", "turbo dev",
    "nest start", "nodemon",
    "node server", "node app", "node index",
    "live-server", "serve", "vite preview",
    # Python
    "python -m http.server", "python manage.py runserver",
    "flask run", "uvicorn", "gunicorn",
    "streamlit run", "gradio",
    "jupyter notebook", "jupyter lab",
    "celery worker", "celery beat",
    # Ruby / Rails
    "rails server", "rails s", "ruby -run",
    "jekyll serve", "bundle exec jekyll",
    # Go / Rust
    "cargo run", "cargo watch",
    "go run", "air",  # Go live reload
    # PHP
    "php -S", "php artisan serve",
    # Static / Other
    "hugo server", "gatsby develop",
    "caddy run", "nginx",
    # Database
    "redis-server", "mongod",
    # Docker
    "docker compose up", "docker-compose up", "docker run",
    # Monitoring
    "tail -f", "tail -F",
]


# Dangerous command patterns that require user approval
_DANGEROUS_PATTERNS = [
    r'\brm\s+-rf\b', r'\brm\s+-r\b', r'\brmdir\b', r'\bdel\s+/s\b',
    r'\bgit\s+push\b', r'\bgit\s+push\s+--force\b', r'\bgit\s+reset\s+--hard\b',
    r'\bgit\s+clean\b', r'\bgit\s+checkout\s+--\b',
    r'\bdrop\s+table\b', r'\bdrop\s+database\b', r'\btruncate\b',
    r'\bkill\s+-9\b', r'\btaskkill\b',
    r'\bnpm\s+publish\b', r'\bpip\s+install\b(?!.*-r)',
    r'\bcurl\s+.*-X\s*(DELETE|PUT|POST)\b',
    r'\bRemove-Item\s+-Recurse\b',
]

# Commands auto-approved (safe, read-only)
_SAFE_PATTERNS = [
    r'^(ls|dir|cat|head|tail|echo|pwd|cd|type|more)\b',
    r'^git\s+(status|log|diff|branch|show|blame)\b',
    r'^(Get-ChildItem|Get-Content|Get-Date|Get-Process|Get-CimInstance)\b',
    r'^(python|node|npm|pip)\s+--version\b',
    r'^(wc|sort|find|grep|rg)\b',
]

_auto_approve_session = True  # bypass all permissions by default

def _needs_approval(cmd: str) -> bool:
    """Check if a command needs user approval."""
    if _auto_approve_session:
        return False
    cmd_stripped = cmd.strip()
    # Check ALL parts of compound commands (;, &&, ||, |)
    # Dangerous check first — if ANY part is dangerous, require approval
    for pat in _DANGEROUS_PATTERNS:
        if re.search(pat, cmd_stripped, re.IGNORECASE):
            return True
    # Safe commands never need approval (only if entire command matches)
    for pat in _SAFE_PATTERNS:
        if re.match(pat, cmd_stripped, re.IGNORECASE):
            # But check for compound commands hiding after safe start
            if re.search(r'[;&|]', cmd_stripped):
                return True  # compound command — be safe, ask
            return False
    return False


def _ask_permission(action: str, detail: str) -> bool:
    """Ask user for permission. Returns True if approved."""
    console.print(Panel(
        Text(detail, style="bold white"),
        title=f"[bold yellow]Permission needed: {action}[/bold yellow]",
        border_style="yellow",
        padding=(0, 1),
    ))
    try:
        answer = input("  Allow? [y/N/a(lways)] > ").strip().lower()
        if answer == "a":
            global _auto_approve_session
            _auto_approve_session = True
            console.print("[dim]Auto-approve enabled for this session[/dim]")
            return True
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def exec_bash(args: dict) -> str:
    cmd = args.get("command", "")
    workdir = args.get("workdir", CWD)
    try:
        timeout_ms = float(args.get("timeout", 300000))
    except (ValueError, TypeError):
        timeout_ms = 300000
    timeout_s = max(1, min(timeout_ms / 1000, 1800))  # clamp 1s-30min
    background = args.get("background", False)

    # Check if command needs permission
    if _needs_approval(cmd):
        if not _ask_permission("bash", f"$ {cmd}"):
            return "[denied by user]"

    # Auto-detect long-running server commands -> run in background
    cmd_lower = cmd.strip().lower()
    is_server = any(pat in cmd_lower for pat in _BG_PATTERNS)
    ends_with_amp = cmd.strip().endswith("&")
    if is_server or background or ends_with_amp:
        if ends_with_amp:
            cmd = cmd.strip()[:-1].strip()  # remove trailing &
        return _exec_bash_background(cmd, workdir)

    try:
        # On Windows: try PowerShell first if command looks like PS
        use_ps = False
        if platform.system() == "Windows":
            ps_indicators = ["Get-", "Set-", "Remove-", "New-", "Select-", "Where-", "Out-", "ForEach-", "Import-", "Export-", "Invoke-"]
            if any(re.search(p, cmd) for p in ps_indicators):
                use_ps = True
        
        if use_ps:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True, text=True,
                cwd=workdir, timeout=timeout_s,
                stdin=subprocess.DEVNULL,
                encoding="utf-8", errors="replace",
            )
        else:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=workdir, timeout=timeout_s,
                stdin=subprocess.DEVNULL,
                encoding="utf-8", errors="replace",
            )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        # Detect PowerShell commands run in cmd.exe
        if "is not recognized as an internal or external command" in output:
            output += "\n\n[HINT: Command not found. Use cmd.exe syntax (del, dir, type) or use tools directly (read, write, list_dir, web_fetch). Do NOT use PowerShell cmdlets.]"
        return output[:50000] or "(no output)"
    except subprocess.TimeoutExpired:
        console.print(f"[yellow]Command timed out after {timeout_s:.0f}s — restarting in background...[/yellow]")
        return _exec_bash_background(cmd, workdir)
    except Exception as e:
        return f"[error: {e}]"


def _exec_bash_background(cmd: str, workdir: str) -> str:
    """Run a command in background, capture first few seconds of output."""
    try:
        proc = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=workdir, stdin=subprocess.DEVNULL,
        )
        # Wait a bit for startup
        time.sleep(2)

        output = ""
        if proc.poll() is not None:
            # Already finished (error or fast command)
            # Use a thread with timeout to avoid blocking on pipe read
            raw = b""
            def _read():
                nonlocal raw
                raw = proc.stdout.read() if proc.stdout else b""
            t = threading.Thread(target=_read, daemon=True)
            t.start()
            t.join(timeout=5)
            output = raw.decode("utf-8", errors="replace").strip()
            if proc.returncode != 0:
                output += f"\n[exit code: {proc.returncode}]"
            return output[:5000] or "(no output)"

        # Still running = server started OK
        # Read whatever output is available without blocking
        output = ""
        try:
            if proc.stdout and platform.system() == "Windows":
                import msvcrt
                import ctypes
                handle = msvcrt.get_osfhandle(proc.stdout.fileno())
                avail = ctypes.c_ulong(0)
                ctypes.windll.kernel32.PeekNamedPipe(
                    handle, None, 0, None, ctypes.byref(avail), None
                )
                if avail.value > 0:
                    output = proc.stdout.read(min(avail.value, 4096)).decode("utf-8", errors="replace")
            elif proc.stdout:
                import select
                if select.select([proc.stdout], [], [], 0)[0]:
                    output = proc.stdout.read(4096).decode("utf-8", errors="replace")
        except Exception:
            output = "(server started, output not captured)"

        with _bg_processes_lock:
            _cleanup_dead_bg_processes()
            bg_id = f"bg_{len(_bg_processes)+1}"
            _bg_processes[bg_id] = proc

        return (
            f"[background] Server started (PID: {proc.pid}, ID: {bg_id})\n"
            f"Command: {cmd}\n"
            f"{output[:2000]}\n"
            f"Running in background. Use curl to test. To stop: kill {proc.pid}"
        )
    except Exception as e:
        return f"[error: {e}]"


def exec_read(args: dict) -> str:
    fpath = args.get("filePath", "")
    try:
        offset = int(args.get("offset", 1))
        limit = int(args.get("limit", 2000))
    except (ValueError, TypeError):
        offset, limit = 1, 2000
    try:
        if os.path.isdir(fpath):
            entries = os.listdir(fpath)
            return "\n".join(
                f"{'[dir] ' if os.path.isdir(os.path.join(fpath, e)) else ''}{e}"
                for e in sorted(entries)
            )
        # Skip huge files
        fsize = os.path.getsize(fpath)
        if fsize > 10_000_000:  # 10MB
            return f"[error: file too large ({fsize//1_000_000}MB). Use bash to read specific parts: head/tail]"
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        start = max(0, offset - 1)
        end = start + limit
        result_lines = []
        for i, line in enumerate(lines[start:end], start=start + 1):
            result_lines.append(f"{i}\t{line.rstrip()}")
        return "\n".join(result_lines) if result_lines else "(empty file)"
    except Exception as e:
        return f"[error: {e}]"


def _make_diff(old_text: str, new_text: str, filename: str = "") -> str:
    """Generate a unified diff between old and new text."""
    import difflib
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{filename}", tofile=f"b/{filename}", lineterm="")
    result = list(diff)
    if not result:
        return "(no changes)"
    # Limit diff output
    diff_text = "\n".join(result[:100])
    if len(result) > 100:
        diff_text += f"\n... ({len(result)} total diff lines)"
    return diff_text


def _show_diff(old_text: str, new_text: str, filename: str):
    """Display a colored diff panel in the console."""
    diff_text = _make_diff(old_text, new_text, os.path.basename(filename))
    if diff_text != "(no changes)":
        console.print(Panel(
            Syntax(diff_text, "diff", theme="monokai"),
            title=f"[bold green]changes: {os.path.basename(filename)}[/bold green]",
            title_align="left",
            border_style="green",
            padding=(0, 1),
        ))


def _auto_lint(filepath: str) -> str:
    """Run a quick syntax/error check on the given file after edit. Returns lint output or empty string."""
    import shutil
    ext = os.path.splitext(filepath)[1].lower()
    cmds: list[list[str]] = []

    if ext == ".py":
        cmds.append([sys.executable, "-m", "py_compile", filepath])
        if shutil.which("ruff"):
            # errors only, no style warnings
            cmds.append(["ruff", "check", "--select=E9,F63,F7,F82", "--no-fix", filepath])
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        if shutil.which("npx"):
            cmds.append(["npx", "--no-install", "eslint", "--quiet", filepath])
        elif ext == ".js" and shutil.which("node"):
            cmds.append(["node", "--check", filepath])
    elif ext == ".json":
        cmds.append([sys.executable, "-m", "json.tool", filepath])
    # .html/.htm/.css — skip (too noisy or no reliable quick linter)

    if not cmds:
        return ""

    results: list[str] = []
    for cmd in cmds:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            # For json.tool, success means valid JSON — don't echo the formatted output
            if ext == ".json" and proc.returncode == 0:
                continue
            output = (proc.stdout.strip() + "\n" + proc.stderr.strip()).strip()
            if proc.returncode != 0 and output:
                results.append(output)
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass  # linter not installed, timed out, or other error — don't block

    if results:
        lint_text = "\n".join(results)
        if len(lint_text) > 2000:
            lint_text = lint_text[:2000] + "\n... (truncated)"
        return f"\n[lint errors]\n{lint_text}"
    return ""


def exec_write(args: dict) -> str:
    fpath = args.get("filePath", "")
    content = args.get("content", "")
    try:
        parent = os.path.dirname(fpath)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # Read old content for diff (if file exists)
        old_content = ""
        is_new = not os.path.exists(fpath)
        if not is_new:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    old_content = f.read()
                with _edit_history_lock:
                    _edit_history.append({"filePath": fpath, "content": old_content})
            except Exception:
                pass
        with open(fpath, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        lines = content.count("\n") + 1
        if is_new:
            console.print(f"[bold green]+ Created {fpath} ({lines} lines)[/bold green]")
        else:
            _show_diff(old_content, content, fpath)
        lint_out = _auto_lint(fpath)
        return f"Successfully wrote {lines} lines to {fpath}" + lint_out
    except Exception as e:
        return f"[error: {e}]"


def exec_edit(args: dict) -> str:
    fpath = args.get("filePath", "")
    old = args.get("oldString", "")
    new = args.get("newString", "")
    replace_all = args.get("replaceAll", False)
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        # Save for /undo
        with _edit_history_lock:
            _edit_history.append({"filePath": fpath, "content": content})
        count = content.count(old)
        if count == 0:
            # Show actual file content so AI can see what's really there
            lines = content.split("\n")
            preview = "\n".join(f"{i+1}: {l}" for i, l in enumerate(lines[:30]))
            if len(lines) > 30:
                preview += f"\n... ({len(lines)} total lines)"
            return f"[error: oldString not found in file. Read the file first!]\n\nActual file content:\n{preview}"
        if count > 1 and not replace_all:
            return f"[error: found {count} matches, but replaceAll is false. Provide more context or set replaceAll=true]"
        if replace_all:
            new_content = content.replace(old, new)
        else:
            new_content = content.replace(old, new, 1)
        with open(fpath, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
        replaced = count if replace_all else 1
        _show_diff(content, new_content, fpath)
        lint_out = _auto_lint(fpath)
        return f"Replaced {replaced} occurrence(s) in {fpath}" + lint_out
    except Exception as e:
        return f"[error: {e}]"


def exec_multi_edit(args: dict) -> str:
    fpath = args.get("filePath", "")
    edits = args.get("edits", [])
    if not edits:
        return "[error: no edits provided]"
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        original = content
        with _edit_history_lock:
            _edit_history.append({"filePath": fpath, "content": content})
        applied = 0
        for i, edit in enumerate(edits):
            old = edit.get("oldString", "")
            new = edit.get("newString", "")
            if old not in content:
                return f"[error: edit #{i+1} oldString not found (applied {applied}/{len(edits)} before failure)]"
            content = content.replace(old, new, 1)
            applied += 1
        with open(fpath, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        _show_diff(original, content, fpath)
        lint_out = _auto_lint(fpath)
        return f"Applied {applied} edit(s) to {fpath}" + lint_out
    except Exception as e:
        return f"[error: {e}]"


def exec_glob(args: dict) -> str:
    pattern = args.get("pattern", "")
    path = args.get("path", CWD)
    try:
        full_pattern = os.path.join(path, pattern)
        matches = glob_mod.glob(full_pattern, recursive=True)
        matches = sorted(matches, key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)
        matches = [m.replace("\\", "/") for m in matches[:200]]
        return "\n".join(matches) if matches else "(no matches)"
    except Exception as e:
        return f"[error: {e}]"


_regex_cache = {}  # cache compiled regexes

def exec_grep(args: dict) -> str:
    pattern = args.get("pattern", "")
    path = args.get("path", CWD)
    include = args.get("include", "*")
    try:
        file_pattern = os.path.join(path, "**", include)
        files = glob_mod.glob(file_pattern, recursive=True)
        results = []
        cache_key = (pattern, re.IGNORECASE)
        if cache_key not in _regex_cache:
            _regex_cache[cache_key] = re.compile(pattern, re.IGNORECASE)
        regex = _regex_cache[cache_key]
        for fpath in files[:1000]:
            if os.path.isdir(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append(f"{fpath.replace(chr(92), '/')}:{i}: {line.rstrip()}")
                            if len(results) >= 250:
                                break
            except Exception:
                pass
            if len(results) >= 250:
                break
        return "\n".join(results) if results else "(no matches)"
    except Exception as e:
        return f"[error: {e}]"


def exec_task_create(args: dict) -> str:
    global _task_counter
    _task_counter += 1
    task = {"id": _task_counter, "text": args.get("text", ""), "status": "pending"}
    _tasks.append(task)
    return f"Created task #{_task_counter}: {task['text']}"


def exec_task_update(args: dict) -> str:
    try:
        tid = int(args.get("id", 0))
    except (ValueError, TypeError):
        return "[error: invalid task id]"
    status = args.get("status", "pending")
    if status not in ("pending", "in_progress", "done"):
        return f"[error: invalid status '{status}', use: pending, in_progress, done]"
    for t in _tasks:
        if t["id"] == tid:
            t["status"] = status
            return f"Task #{tid} -> {status}"
    return f"[error: task #{tid} not found]"


def exec_task_list(args: dict) -> str:
    if not _tasks:
        return "(no tasks)"
    icons = {"pending": "[ ]", "in_progress": "[~]", "done": "[x]"}
    lines = []
    for t in _tasks:
        icon = icons.get(t["status"], "?")
        lines.append(f"  {icon} #{t['id']} [{t['status']}] {t['text']}")
    done = sum(1 for t in _tasks if t["status"] == "done")
    lines.append(f"\n  Progress: {done}/{len(_tasks)}")
    return "\n".join(lines)


def exec_memory_search(args: dict) -> str:
    query = args.get("query", "").lower()
    limit = int(args.get("limit", 5))
    memory_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
    if not os.path.exists(memory_dir):
        return "(no memories saved yet)"
    md_files = sorted(glob_mod.glob(os.path.join(memory_dir, "*.md")), reverse=True)
    if not md_files:
        return "(no memories saved yet)"

    # Score-based search: split query into words, score by matches
    query_words = query.split()
    scored = []
    for mf in md_files:
        try:
            with open(mf, "r", encoding="utf-8") as f:
                content = f.read()
            content_lower = content.lower()
            if not query_words:
                scored.append((1, mf, content))
                continue
            score = 0
            for w in query_words:
                score += content_lower.count(w)
            # Bonus for filename match
            fname_lower = os.path.basename(mf).lower()
            for w in query_words:
                if w in fname_lower:
                    score += 5
            if score > 0:
                scored.append((score, mf, content))
        except Exception:
            pass

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, mf, content in scored[:limit]:
        preview = content[:500]
        if len(content) > 500:
            preview += "..."
        results.append(f"--- {os.path.basename(mf)} (score:{score}) ---\n{preview}")

    if not results and query:
        # Fallback: return recent memories
        for mf in md_files[:limit]:
            try:
                with open(mf, "r", encoding="utf-8") as f:
                    content = f.read()[:500]
                results.append(f"--- {os.path.basename(mf)} ---\n{content}")
            except Exception:
                pass

    return "\n\n".join(results) if results else f"(no memories matching '{query}')"


_MAX_MEMORY_FILES = 100  # auto-cleanup oldest when exceeded

def exec_memory_save(args: dict) -> str:
    title = args.get("title", "note")
    content = args.get("content", "")
    tags = args.get("tags", "")
    memory_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
    os.makedirs(memory_dir, exist_ok=True)

    # Auto-cleanup: remove oldest files if over limit
    existing = sorted(glob_mod.glob(os.path.join(memory_dir, "*.md")))
    while len(existing) >= _MAX_MEMORY_FILES:
        oldest = existing.pop(0)
        try:
            os.remove(oldest)
        except Exception:
            break

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r'[^\w\-]', '_', title)[:40]
    md_file = os.path.join(memory_dir, f"{ts}_{safe_title}.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"**Saved:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Model:** {MODEL}\n")
        f.write(f"**CWD:** {CWD}\n")
        if tags:
            f.write(f"**Tags:** {tags}\n")
        f.write(f"\n{content}\n")
    return f"Saved memory: {title}"


def exec_web_search(args: dict) -> str:
    query = args.get("query", "")
    max_results = int(args.get("max_results", 5))

    def _parse_ddg(body: str) -> list:
        from urllib.parse import unquote
        results = []
        blocks = body.split('class="result__a"')[1:]
        for block in blocks[:max_results]:
            # href comes before the title text, then </a>
            href_match = re.search(r'href="([^"]+)"', block)
            url = ""
            if href_match:
                raw_url = href_match.group(1).replace("&amp;", "&")
                uddg = re.search(r'uddg=([^&]+)', raw_url)
                if uddg:
                    url = unquote(uddg.group(1))
                else:
                    url = raw_url
            # Title is between the closing > of the <a> tag and </a>
            title_start = block.find(">")
            title_end = block.find("</a>")
            if title_start != -1 and title_end != -1:
                title_raw = block[title_start + 1:title_end]
            else:
                title_raw = ""
            title = re.sub(r"<[^>]+>", "", title_raw).strip()
            title = title.replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'")
            # Snippet
            snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)', block, re.DOTALL)
            snippet = ""
            if snippet_match:
                snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()
                snippet = snippet.replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'")
            # Try to extract date from URL (e.g. /2026/04/08/) or snippet
            date_str = ""
            url_date = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
            if url_date:
                date_str = f"{url_date.group(1)}-{url_date.group(2)}-{url_date.group(3)}"
            else:
                # Look for dates in snippet like "Apr 8, 2026" or "April 8, 2026" or "2026-04-08"
                snip_date = re.search(r'(\w{3,9}\.?\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})', snippet)
                if snip_date:
                    date_str = snip_date.group(1)
            date_line = f"  [{date_str}]" if date_str else ""
            if title or url:
                results.append(f"[{len(results)+1}]{date_line} {title}\n    {url}\n    {snippet}")
        return results

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    ]

    last_err = None
    for attempt in range(2):
        try:
            ua = user_agents[attempt % len(user_agents)]
            resp = httpx.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": ua},
                timeout=30,
                follow_redirects=True,
            )
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}"
                continue
            results = _parse_ddg(resp.text)
            return "\n\n".join(results) if results else "(no results found)"
        except Exception as e:
            last_err = str(e)
            continue
    return f"[error: {last_err}]"


def exec_web_fetch(args: dict) -> str:
    url = args.get("url", "")
    max_length = int(args.get("max_length", 20000))
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"},
            timeout=30,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return f"[error: HTTP {resp.status_code}]"
        content_type = resp.headers.get("content-type", "")
        if "html" in content_type:
            # Strip HTML tags, scripts, styles
            text = resp.text
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
        else:
            text = resp.text
        if len(text) > max_length:
            text = text[:max_length] + f"\n... (truncated, {len(resp.text)} total chars)"
        return text if text else "(empty page)"
    except Exception as e:
        return f"[error: {e}]"


def exec_list_dir(args: dict) -> str:
    target = args.get("path", CWD)
    recursive = args.get("recursive", False)
    if not os.path.isdir(target):
        return f"[error: not a directory: {target}]"
    try:
        lines = []
        if recursive:
            for root, dirs, files in os.walk(target):
                depth = root.replace(target, "").count(os.sep)
                if depth >= 3:
                    dirs.clear()
                    continue
                indent = "  " * depth
                rel = os.path.relpath(root, target)
                if rel != ".":
                    lines.append(f"{indent}[dir] {os.path.basename(root)}/")
                # Skip hidden dirs and common noise
                dirs[:] = [d for d in sorted(dirs) if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".git", "venv", ".venv")]
                for f in sorted(files):
                    if not f.startswith("."):
                        lines.append(f"{indent}  [file] {f}")
                if len(lines) > 500:
                    lines.append("... (truncated at 500 entries)")
                    break
        else:
            entries = sorted(os.listdir(target))
            for e in entries:
                full = os.path.join(target, e)
                prefix = "[dir]" if os.path.isdir(full) else "[file]"
                lines.append(f"{prefix} {e}")
        return "\n".join(lines) if lines else "(empty directory)"
    except Exception as e:
        return f"[error: {e}]"


# ============================================================================
# HTTP Client
# ============================================================================

def exec_http(args: dict) -> str:
    """Full HTTP client — replaces curl for API testing."""
    url = args.get("url", "")
    method = args.get("method", "GET").upper()
    headers = args.get("headers", {})
    body = args.get("body", None)
    json_body = args.get("json_body", None)
    auth = args.get("auth", "")
    timeout_s = float(args.get("timeout", 30))

    if not url:
        return "[error: url required]"

    try:
        # Auth
        if auth:
            if ":" in auth and not auth.startswith("Bearer"):
                import base64
                cred = base64.b64encode(auth.encode()).decode()
                headers["Authorization"] = f"Basic {cred}"
            else:
                token = auth.replace("Bearer ", "").strip()
                headers["Authorization"] = f"Bearer {token}"

        # Set default user agent
        if "User-Agent" not in headers:
            headers["User-Agent"] = "ToonCode/2.0"

        req_kwargs = {
            "method": method,
            "url": url,
            "headers": headers,
            "timeout": timeout_s,
            "follow_redirects": True,
        }

        if json_body is not None:
            req_kwargs["json"] = json_body
        elif body is not None:
            req_kwargs["content"] = body

        with httpx.Client() as client:
            resp = client.request(**req_kwargs)

        # Build response summary
        parts = []
        parts.append(f"HTTP {resp.status_code} {resp.reason_phrase}")
        parts.append(f"URL: {resp.url}")
        parts.append(f"Time: {resp.elapsed.total_seconds():.2f}s")
        parts.append("")

        # Response headers (important ones)
        important_headers = ["content-type", "content-length", "server", "set-cookie", "location",
                             "x-request-id", "x-ratelimit-remaining", "www-authenticate"]
        resp_headers = []
        for k, v in resp.headers.items():
            if k.lower() in important_headers:
                resp_headers.append(f"  {k}: {v}")
        if resp_headers:
            parts.append("Headers:")
            parts.extend(resp_headers)
            parts.append("")

        # Body
        content_type = resp.headers.get("content-type", "")
        body_text = resp.text
        if "json" in content_type:
            try:
                parsed = resp.json()
                body_text = json.dumps(parsed, indent=2, ensure_ascii=False)
            except Exception:
                pass

        if len(body_text) > 10000:
            body_text = body_text[:10000] + f"\n... ({len(resp.text)} total chars)"

        parts.append("Body:")
        parts.append(body_text)

        return "\n".join(parts)

    except httpx.ConnectError as e:
        return f"[error: connection failed: {e}]"
    except httpx.ReadTimeout:
        return f"[error: timeout after {timeout_s}s]"
    except Exception as e:
        return f"[error: {e}]"


# ============================================================================
# Screenshot (Desktop Capture)
# ============================================================================

def exec_screenshot(args: dict) -> str:
    """Capture desktop screenshot and extract text via OCR if available."""
    region = args.get("region", "full")
    window_title = args.get("window", "")

    install_dir = os.path.dirname(os.path.abspath(__file__))
    ss_dir = os.path.join(install_dir, "screenshots")
    os.makedirs(ss_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(ss_dir, f"desktop_{ts}.png")

    try:
        img = None
        _sys = platform.system()

        # Linux: use scrot or gnome-screenshot
        if _sys == "Linux":
            for tool in ["scrot", "gnome-screenshot", "maim"]:
                try:
                    if tool == "gnome-screenshot":
                        subprocess.run(["gnome-screenshot", "-f", filepath], timeout=10, check=True)
                    else:
                        subprocess.run([tool, filepath], timeout=10, check=True)
                    from PIL import Image
                    img = Image.open(filepath)
                    break
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
            if img is None:
                return "[error: install scrot or gnome-screenshot for Linux screenshots]"

        # macOS: use screencapture
        elif _sys == "Darwin":
            try:
                subprocess.run(["screencapture", "-x", filepath], timeout=10, check=True)
                from PIL import Image
                img = Image.open(filepath)
            except Exception as e:
                return f"[error: macOS screenshot failed: {e}]"

        # Windows: use PIL ImageGrab
        else:
            from PIL import ImageGrab

            if window_title:
                try:
                    import ctypes
                    from ctypes import wintypes
                    user32 = ctypes.windll.user32
                    found_hwnd = None
                    def _enum_cb(hwnd, _):
                        nonlocal found_hwnd
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buf, length + 1)
                            if window_title.lower() in buf.value.lower():
                                if user32.IsWindowVisible(hwnd):
                                    found_hwnd = hwnd
                                    return False
                        return True
                    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
                    user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
                    if found_hwnd:
                        rect = wintypes.RECT()
                        user32.GetWindowRect(found_hwnd, ctypes.byref(rect))
                        bbox = (rect.left, rect.top, rect.right, rect.bottom)
                        img = ImageGrab.grab(bbox=bbox)
                    else:
                        img = ImageGrab.grab()
                except Exception:
                    img = ImageGrab.grab()
            elif region != "full" and "," in region:
                try:
                    parts_r = [int(p.strip()) for p in region.split(",")]
                    if len(parts_r) == 4:
                        x, y, w, h = parts_r
                        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
                    else:
                        img = ImageGrab.grab()
                except ValueError:
                    img = ImageGrab.grab()
            else:
                img = ImageGrab.grab()

        img.save(filepath)
        width, height = img.size

        # Try OCR with pytesseract if available
        ocr_text = ""
        try:
            import pytesseract
            ocr_text = pytesseract.image_to_string(img, lang="eng+tha")
            ocr_text = ocr_text.strip()
        except ImportError:
            ocr_text = "(OCR not available - install pytesseract for text extraction)"
        except Exception as e:
            ocr_text = f"(OCR failed: {e})"

        result = f"Screenshot saved: {filepath}\nSize: {width}x{height}"
        if ocr_text:
            preview = ocr_text[:3000]
            if len(ocr_text) > 3000:
                preview += f"\n... ({len(ocr_text)} total chars)"
            result += f"\n\nExtracted text:\n{preview}"
        return result

    except Exception as e:
        return f"[error: {e}]"


# ============================================================================
# Browser (Playwright)
# ============================================================================

_browser_console_logs = deque(maxlen=200)
_browser_requests = deque(maxlen=200)
_browser_errors = deque(maxlen=200)
_MAX_BROWSER_LOGS = 200
_browser_lock = threading.Lock()

# Browser runs in a dedicated thread to avoid asyncio event loop conflicts
class _BrowserWorker:
    """Robust Playwright browser worker with auto-install, headless support, and proper cleanup."""

    def __init__(self):
        self._thread = None
        self._pw = None
        self._browser = None
        self._page = None
        self._ready = threading.Event()
        self._cmd_queue = []
        self._cmd_event = threading.Event()
        self._stop = False
        self._headless = None

    def _auto_install(self):
        """Auto-install Playwright chromium binaries if missing."""
        console.print("[dim]Checking/Installing Playwright browsers...[/dim]")
        # Try npx first (Node.js install)
        try:
            subprocess.run(
                ["npx", "playwright", "install", "chromium"],
                check=True, timeout=180,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            console.print("[green]Playwright chromium installed/ready[/green]")
            return True
        except Exception:
            pass
        # Fallback: try Python playwright module (works on Mac/pip installs)
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True, timeout=180,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            console.print("[green]Playwright chromium installed/ready[/green]")
            return True
        except Exception as e:
            console.print(f"[yellow]Playwright install warning: {e}[/yellow]")
            return False

    def start(self):
        """Start browser worker with headless auto-detection."""
        with _browser_lock:
            if self._thread and self._thread.is_alive():
                return True
            # Detect headless environment
            self._headless = os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() == "true"
            if platform.system() == "Linux" and not os.environ.get("DISPLAY"):
                self._headless = True
            elif platform.system() == "Darwin" and os.environ.get("SSH_CONNECTION"):
                self._headless = True
            self._stop = False
            self._ready.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            if not self._ready.wait(timeout=25):
                console.print("[yellow]Browser start timeout — fallback mode[/yellow]")
                self.close()
                return False
            return True

    def _run(self):
        try:
            self._auto_install()
            from playwright.sync_api import sync_playwright, Error as PWError
            self._pw = sync_playwright().start()
            launch_args = {"headless": self._headless}
            if self._headless:
                launch_args["args"] = [
                    "--no-sandbox", "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage", "--disable-gpu"
                ]
            self._browser = self._pw.chromium.launch(**launch_args)
            self._page = self._browser.new_page()
            self._page.set_viewport_size({"width": 1280, "height": 720})

            # Capture events (thread-safe with truncation)
            def _safe_append(lst, item):
                lst.append(item)

            self._page.on("console", lambda msg: _safe_append(_browser_console_logs, f"[{msg.type}] {msg.text}"))
            self._page.on("request", lambda req: _safe_append(_browser_requests, f"{req.method} {req.url}"))
            self._page.on("pageerror", lambda err: _safe_append(_browser_errors, str(err)))

            self._ready.set()

            # Command loop
            while not self._stop:
                self._cmd_event.wait(timeout=0.5)
                self._cmd_event.clear()
                while self._cmd_queue:
                    fn, holder = self._cmd_queue.pop(0)
                    try:
                        holder["result"] = fn(self._page)
                    except Exception as e:
                        holder["result"] = f"[browser error: {e}]"
                    holder["done"].set()
        except Exception as e:
            console.print(f"[red]Browser worker crashed: {e}[/red]")
            self._ready.set()  # unblock waiters
        finally:
            self._cleanup()

    def _cleanup(self):
        """Safely close browser and playwright."""
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._browser = self._pw = self._page = None

    def execute(self, fn, timeout=30):
        """Run a function on the browser thread, auto-restart if dead."""
        if not self._thread or not self._thread.is_alive():
            console.print("[yellow]Browser was closed — restarting...[/yellow]")
            self.close()
            if not self.start():
                return "[browser error: failed to restart]"
        holder = {"result": None, "done": threading.Event()}
        self._cmd_queue.append((fn, holder))
        self._cmd_event.set()
        if holder["done"].wait(timeout=timeout):
            return holder["result"]
        return "[browser error: timeout]"

    def close(self):
        self._stop = True
        self._cmd_event.set()
        if self._thread:
            self._thread.join(timeout=8)
        self._thread = None
        _browser_console_logs.clear()
        _browser_requests.clear()
        _browser_errors.clear()


_browser_worker = None


def exec_browser(args: dict) -> str:
    action = args.get("action", "")
    url = args.get("url", "")
    selector = args.get("selector", "")
    value = args.get("value", "")
    wait_s = float(args.get("wait", 1))

    global _browser_worker

    if action == "close":
        if _browser_worker:
            _browser_worker.close()
            _browser_worker = None
        return "Browser closed."

    # Console/network/errors don't need the browser thread
    if action == "console":
        if not _browser_console_logs:
            return "(no console logs captured)"
        logs = _browser_console_logs[-50:]
        return f"Console logs (last {len(logs)}):\n" + "\n".join(logs)
    elif action == "network":
        if not _browser_requests:
            return "(no network requests captured)"
        reqs = _browser_requests[-50:]
        return f"Network requests (last {len(reqs)}):\n" + "\n".join(reqs)
    elif action == "errors":
        if not _browser_errors:
            return "(no JS errors captured)"
        return f"Page errors ({len(_browser_errors)}):\n" + "\n".join(_browser_errors[-20:])

    # Start browser if needed / detect if closed externally
    if _browser_worker and not _browser_worker._thread.is_alive():
        console.print("[yellow]Browser was closed. Restarting...[/yellow]")
        _browser_worker = None

    if not _browser_worker:
        _browser_worker = _BrowserWorker()
        console.print("[dim]Starting browser...[/dim]")
        if not _browser_worker.start():
            _browser_worker = None
            # Fallback: use web_fetch instead of Playwright
            if action == "open" and url:
                console.print("[yellow]Playwright not available — falling back to web_fetch[/yellow]")
                return exec_web_fetch({"url": url, "max_length": 20000})
            elif action == "text" or action == "screenshot":
                return "[error: browser not available. Ubuntu: sudo npx playwright install-deps && npx playwright install chromium | Mac: python3 -m playwright install chromium]"
            return "[error: could not start browser]"

    if action == "open":
        if not url:
            return "[error: url required]"
        def _do(page):
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(wait_s)
            return f"Opened: {page.title()}\nURL: {page.url}"
        return _browser_worker.execute(_do)

    elif action == "screenshot":
        def _do(page):
            install_dir = os.path.dirname(os.path.abspath(__file__))
            ss_dir = os.path.join(install_dir, "screenshots")
            os.makedirs(ss_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fp = os.path.join(ss_dir, f"screenshot_{ts}.png")
            page.screenshot(path=fp, full_page=False)
            text = page.inner_text("body")
            text = re.sub(r'\s+', ' ', text).strip()[:5000]
            return f"Screenshot: {fp}\n\nPage text:\n{text}"
        return _browser_worker.execute(_do)

    elif action == "text":
        def _do(page):
            text = page.inner_text("body")
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > 10000:
                text = text[:10000] + f"\n... (truncated)"
            return f"Page: {page.title()}\nURL: {page.url}\n\n{text}"
        return _browser_worker.execute(_do)

    elif action == "click":
        if not selector:
            return "[error: selector required]"
        def _do(page):
            page.click(selector, timeout=10000)
            time.sleep(wait_s)
            return f"Clicked: {selector}\nURL: {page.url}"
        return _browser_worker.execute(_do)

    elif action == "fill":
        if not selector:
            return "[error: selector required]"
        def _do(page):
            page.fill(selector, value, timeout=10000)
            time.sleep(wait_s)
            return f"Filled '{selector}' with: {value[:100]}"
        return _browser_worker.execute(_do)

    elif action == "eval":
        if not value:
            return "[error: JS code required]"
        def _do(page):
            result = page.evaluate(value)
            return f"JS result: {json.dumps(result, ensure_ascii=False, default=str)[:5000]}"
        return _browser_worker.execute(_do)

    else:
        return f"[error: unknown action '{action}']"


# Sub-agent system prompts
_SUBAGENT_PROMPTS = {
    "coder": "You are a CODER agent. Write clean, working code. Use write/edit tools to create and modify files. Always read files before editing. Keep text responses minimal — let the code speak.",
    "reviewer": "You are a REVIEWER agent. Read the code, check for bugs, security issues, and logic errors. If you find issues, use edit tool to fix them directly. Output: PASS or list of fixes made.",
    "tester": "You are a TESTER agent. Read the code, write test files, run tests using bash. Use pytest for Python, jest for JS. Focus on critical paths and edge cases. Report results.",
    "researcher": "You are a RESEARCHER agent. Read code, search files, and answer questions about the codebase. Use read, glob, grep tools to find information. Be thorough and precise.",
}

# Sub-agent gets a limited set of tools (no spawn_agent to prevent recursion)
_SUBAGENT_TOOLS = [t for t in TOOLS if t["name"] not in ("spawn_agent", "bosshelp", "task_create", "task_update", "task_list", "memory_save")]

_active_agents = {}  # id -> thread
_agent_counter = 0


def exec_spawn_agent(args: dict) -> str:
    """Spawn a sub-agent that runs a complete tool-use loop and returns the result."""
    global _agent_counter
    task = args.get("task", "")
    agent_type = args.get("type", "coder")
    context = args.get("context", "")

    if agent_type not in _SUBAGENT_PROMPTS:
        return f"[error: unknown agent type '{agent_type}'. Use: coder, reviewer, tester, researcher]"

    _agent_counter += 1
    agent_id = f"agent_{_agent_counter}"
    agent_emoji = {"coder": "💻", "reviewer": "🔍", "tester": "🧪", "researcher": "🔎"}.get(agent_type, "🤖")

    console.print(f"\n[bold cyan]{agent_emoji} Spawning {agent_type} agent (#{agent_id})...[/bold cyan]")
    console.print(f"[dim]  Task: {task[:100]}{'...' if len(task) > 100 else ''}[/dim]")

    system = f"""{_SUBAGENT_PROMPTS[agent_type]}

Working directory: {CWD}
Platform: {platform.system()}
IMPORTANT: On Windows use PowerShell cmdlets. NEVER use wmic.
You are a sub-agent. Complete the task and report your result concisely."""

    user_msg = task
    if context:
        user_msg = f"{task}\n\nContext:\n{context}"

    messages = [{"role": "user", "content": [{"type": "text", "text": user_msg}]}]
    headers = make_request_headers()

    all_output = []
    max_iterations = 15
    iteration = 0
    agent_start = time.time()
    AGENT_TIMEOUT = 300  # 5 min max for entire sub-agent

    try:
        for iteration in range(max_iterations):
            if time.time() - agent_start > AGENT_TIMEOUT:
                all_output.append(f"\n[agent timed out after {AGENT_TIMEOUT}s]")
                break
            body = {
                "model": MODEL,
                "max_tokens": 16000,
                "system": [{"type": "text", "text": system}],
                "messages": messages,
                "tools": _SUBAGENT_TOOLS,
                "tool_choice": {"type": "auto"},
                "stream": False,
            }
            if MODEL not in NO_SAMPLING_PARAMS:
                body["temperature"] = 1
                body["top_k"] = 40
                body["top_p"] = 0.95

            with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
                resp = client.post(_get_current_api_url(), headers=headers, json=body)
                if resp.status_code != 200:
                    return f"[agent error: HTTP {resp.status_code}]"
                data = resp.json()

            content = data.get("content", [])
            if not content:
                break

            # Collect text output
            for block in content:
                if block.get("type") == "text":
                    all_output.append(block["text"])

            # Check for tool use
            tool_blocks = [b for b in content if b.get("type") == "tool_use"]
            if not tool_blocks:
                break  # No tools = agent is done

            # Add assistant message
            messages.append({"role": "assistant", "content": content})

            # Execute tools
            tool_results = []
            for tb in tool_blocks:
                name = tb["name"]
                inp = tb.get("input", {})
                tid = tb["id"]

                handler = TOOL_HANDLERS.get(name)
                if handler and name != "spawn_agent":  # prevent recursion
                    console.print(f"[dim]  {agent_emoji} [{agent_type}] → {name}({list(inp.keys())})[/dim]")
                    result = handler(inp)
                else:
                    result = f"[tool not available for sub-agents: {name}]"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tid,
                    "content": result[:10000],
                })

            messages.append({"role": "user", "content": tool_results})

        # Compile results
        result_text = "\n".join(all_output).strip()
        if not result_text:
            result_text = "(agent completed with no text output)"

        console.print(f"[bold green]{agent_emoji} Agent #{agent_id} ({agent_type}) finished ({iteration+1} steps)[/bold green]")
        return f"[Agent {agent_type} result]\n{result_text}"

    except Exception as e:
        console.print(f"[error]{agent_emoji} Agent #{agent_id} failed: {e}[/error]")
        return f"[agent error: {e}]"


# ============================================================================
# Team Mode — multiple agents working together autonomously (v2)
# ============================================================================

_TEAM_ROLES = {
    # === General-Purpose Roles (ใช้ได้กับทุกงาน) ===
    "planner": {
        "emoji": "📋",
        "name": "สมชาย",
        "color": "cyan",
        "system": """You are the PLANNER. Your job:
1. Read the task and break it into clear steps
2. Understand the context — if it's a coding task, read project files. If it's research/writing/analysis, plan the approach.
3. Assign work to other agents via the channel using JSON:
   {"type":"assignment","to":"<role>","task":"<description>","priority":1}
4. You can also send plain text messages with @role mentions
5. Use team_task_create to add tasks to the shared task board
6. If you need a specialist not on the team, use spawn_team_agent to create one
Always analyze the task type first. Output a numbered plan, then send JSON assignments.""",
    },
    "supervisor": {
        "emoji": "🧠",
        "name": "สุภาพร",
        "color": "bright_cyan",
        "system": """You are the SUPERVISOR. You do NOT do the work yourself. Your job:
1. Monitor the team's progress by reading channel messages and the task board
2. Use team_task_list to check task progress regularly
3. If an agent is stuck or slow, reassign their task or send guidance
4. If you detect a conflict (2 agents working on the same thing), intervene
5. If you need a specialist, use spawn_team_agent to create one dynamically
6. Summarize overall progress periodically
7. When all tasks are done, send a final summary to the channel
Be concise. Focus on coordination, not execution.""",
    },

    # === Coding Roles ===
    "frontend": {
        "emoji": "🎨",
        "name": "ณัฐพล",
        "color": "green",
        "system": """You are the FRONTEND agent. You build UI: HTML, CSS, JS, React, etc.
Read channel messages for your assignments. When done, send results back.
Use write/edit tools. Always read files before editing.
Use team_task_update to mark your tasks as done on the task board.
Send "@reviewer please check my frontend code" when done.""",
    },
    "backend": {
        "emoji": "⚙️",
        "name": "วิชัย",
        "color": "yellow",
        "system": """You are the BACKEND agent. You build APIs, databases, server logic.
Read channel messages for your assignments. When done, send results back.
Use write/edit/bash tools. Always read files before editing.
Use team_task_update to mark your tasks as done on the task board.
Send "@tester please test the API" when done.""",
    },
    "reviewer": {
        "emoji": "🔍",
        "name": "มาลี",
        "color": "magenta",
        "system": """You are the REVIEWER. Read code written by other agents, find bugs, fix them.
Read channel messages. When asked to review, read the files and check.
Use edit tool to fix issues directly. Report: PASS or list of fixes.
Use team_task_update to mark your tasks as done on the task board.
Send results back to channel.""",
    },
    "tester": {
        "emoji": "🧪",
        "name": "ธนา",
        "color": "red",
        "system": """You are the TESTER. Write and run tests for code written by other agents.
Read channel messages for test requests. Write test files, run with bash.
Use team_task_update to mark your tasks as done on the task board.
Report results back to channel. If tests fail, send "@coder fix: ..." """,
    },

    # === Research & Knowledge Roles ===
    "researcher": {
        "emoji": "🔬",
        "name": "ปิยะ",
        "color": "bright_blue",
        "system": """You are the RESEARCHER. Your job is to find information, gather data, and provide facts.
Use web_search and web_fetch to find information online.
Use read/glob to find information in local files.
Summarize your findings clearly with sources.
Use team_task_update to mark your tasks as done on the task board.
Send results back to the channel when done.""",
    },
    "analyst": {
        "emoji": "📊",
        "name": "นภา",
        "color": "bright_yellow",
        "system": """You are the ANALYST. Your job is to analyze data, compare options, and provide insights.
Read information from the channel and files.
Organize findings into clear comparisons, pros/cons, or recommendations.
Use bash to run scripts for data processing if needed.
Use team_task_update to mark your tasks as done on the task board.
Send your analysis back to the channel.""",
    },

    # === Content & Writing Roles ===
    "writer": {
        "emoji": "✍️",
        "name": "กานดา",
        "color": "bright_green",
        "system": """You are the WRITER. Your job is to create written content: articles, docs, reports, summaries, plans, etc.
Read channel messages for your assignments and context from other agents.
Use write tool to create files. Use edit to revise.
Write clearly, concisely, and in the appropriate tone for the audience.
Use team_task_update to mark your tasks as done on the task board.
Send "@reviewer please check my writing" when done.""",
    },
    "editor": {
        "emoji": "📝",
        "name": "อรุณ",
        "color": "bright_magenta",
        "system": """You are the EDITOR. Your job is to review and improve written content.
Read files created by the writer or other agents.
Check for: clarity, grammar, structure, tone, completeness.
Use edit tool to fix issues directly.
Report: APPROVED or list of changes made.
Use team_task_update to mark your tasks as done on the task board.""",
    },

    # === Design & Creative Roles ===
    "designer": {
        "emoji": "🎯",
        "name": "พิมพ์",
        "color": "bright_red",
        "system": """You are the DESIGNER. Your job is to design structures, layouts, architectures, and plans.
For code: design file structure, APIs, database schemas, component architecture.
For non-code: design outlines, frameworks, workflows, organization systems.
Use write tool to create design documents or diagrams.
Use team_task_update to mark your tasks as done on the task board.
Send your design to the channel for feedback.""",
    },
}


# ---------------------------------------------------------------------------
# TeamAgent — each agent has its own context / memory / status
# ---------------------------------------------------------------------------
class TeamAgent:
    """A single team agent with private context and memory."""

    def __init__(self, role: str, task: str, manager: "TeamManager", custom_system: str = None):
        config = _TEAM_ROLES.get(role, {
            "emoji": "🤖", "color": "white",
            "system": f"You are a custom agent with role: {role}. Do your assigned work.",
        })
        self.role = role
        self.task = task
        self.manager = manager
        self.emoji = config["emoji"]
        self.name = config.get("name", role)  # Thai name
        self.color = config["color"]
        self.agent_id = f"team-{role}-{os.getpid()}-{int(time.time())}"
        self.messages = []  # private conversation context
        self.memory = {"files_read": [], "files_written": [], "decisions": [], "context": {}}
        self.status = "idle"
        self.iteration = 0
        self.current_task = task[:80]
        self.last_seen = time.time()
        self.max_iterations = 25
        self.thread = None
        self._system_prompt = custom_system or config["system"]

    @property
    def display_name(self):
        """Thai name + role for display."""
        return f"{self.name}({self.role})"

    def get_status_dict(self):
        return {
            "status": self.status, "iteration": self.iteration, "name": self.name,
            "current_task": self.current_task, "last_seen": self.last_seen,
            "emoji": self.emoji, "color": self.color,
        }

    def _build_system(self):
        """Build full system prompt including team context."""
        team_roles = ", ".join(f"{a.emoji}{a.name}({a.role})" for a in self.manager.agents.values())
        mem_summary = ""
        if self.memory["files_read"] or self.memory["files_written"]:
            mem_summary = f"\n\nYour memory:\n- Files read: {', '.join(self.memory['files_read'][-5:])}\n- Files written: {', '.join(self.memory['files_written'][-5:])}"
        return f"""{self._system_prompt}

Working directory: {CWD}
Platform: {platform.system()}
Your agent ID: {self.agent_id}
Team task: {self.task}
Team members: {team_roles}

CHANNEL PROTOCOL:
- Send @role to address a specific agent (e.g. @frontend, @backend)
- Send @all to broadcast to everyone
- The planner may assign tasks via JSON: {{"type":"assignment","to":"your_role","task":"..."}}
  Watch for assignments addressed to you and act on them
- When you finish your part, send a summary to channel
- ALWAYS read files before editing (another agent may have changed them)
- Do NOT edit files that another agent is currently working on

AVAILABLE TEAM TOOLS:
- team_task_create: Create a task on the shared board
- team_task_update: Update task status (pending/in_progress/done)
- team_task_list: View all tasks on the board
- agent_memory_save: Save something to your private memory
- agent_memory_recall: Recall from your private memory{mem_summary}"""

    def _get_team_tools(self):
        """Get tools available to this agent including team-specific tools."""
        team_tools = [
            {
                "name": "team_task_create",
                "description": "Create a task on the shared team task board.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Task description"},
                        "assignee": {"type": "string", "description": "Role to assign (e.g. frontend, backend)"},
                        "priority": {"type": "integer", "description": "Priority 1-5 (1=highest)", "default": 3},
                    },
                    "required": ["text"],
                },
            },
            {
                "name": "team_task_update",
                "description": "Update a task's status on the shared board.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID (e.g. 'task-1')"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "done"], "description": "New status"},
                    },
                    "required": ["task_id", "status"],
                },
            },
            {
                "name": "team_task_list",
                "description": "List all tasks on the shared team task board.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "agent_memory_save",
                "description": "Save a key-value pair to your private agent memory.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Memory key"},
                        "value": {"type": "string", "description": "Value to remember"},
                    },
                    "required": ["key", "value"],
                },
            },
            {
                "name": "agent_memory_recall",
                "description": "Recall all entries from your private agent memory.",
                "input_schema": {"type": "object", "properties": {}},
            },
        ]
        # planner and supervisor can spawn new agents
        if self.role in ("planner", "supervisor"):
            team_tools.append({
                "name": "spawn_team_agent",
                "description": "Dynamically create and start a new team agent at runtime. Max 8 agents total.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string", "description": "Role name (e.g. 'database', 'devops', or a predefined role)"},
                        "custom_prompt": {"type": "string", "description": "Custom system prompt for the new agent (optional if using a predefined role)"},
                    },
                    "required": ["role"],
                },
            })
        return _SUBAGENT_TOOLS + team_tools

    def _handle_team_tool(self, name: str, inp: dict) -> str:
        """Handle team-specific tool calls."""
        if name == "team_task_create":
            return self.manager.task_board_create(
                inp.get("text", ""), assignee=inp.get("assignee"), priority=inp.get("priority", 3),
                created_by=self.role,
            )
        elif name == "team_task_update":
            return self.manager.task_board_update(inp.get("task_id", ""), inp.get("status", ""))
        elif name == "team_task_list":
            return self.manager.task_board_list()
        elif name == "agent_memory_save":
            self.memory["context"][inp.get("key", "")] = inp.get("value", "")
            return f"Saved to memory: {inp.get('key', '')}"
        elif name == "agent_memory_recall":
            if not self.memory["context"]:
                return "Memory is empty."
            return "\n".join(f"- {k}: {v}" for k, v in self.memory["context"].items())
        elif name == "spawn_team_agent":
            return self.manager.spawn_agent(inp.get("role", ""), inp.get("custom_prompt"))
        return f"[unknown team tool: {name}]"

    def run(self):
        """Main agent execution loop."""
        self.status = "idle"
        self.last_seen = time.time()

        # Build initial message with channel context
        recent_msgs = self.manager.get_messages(for_role=self.role, n=20)
        channel_text = "\n".join(f"[{m['from']}] {m['text']}" for m in recent_msgs) if recent_msgs else "(empty — you're first!)"
        self.messages = [{"role": "user", "content": [{"type": "text", "text":
            f"Team task: {self.task}\n\nCheck the channel for your assignments. If you're the planner, create the plan first. If you're the supervisor, monitor progress. Otherwise, wait for instructions or start on your part.\n\nChannel messages so far:\n{channel_text}"}]}]

        headers = make_request_headers()
        tools = self._get_team_tools()
        team_tool_names = {"team_task_create", "team_task_update", "team_task_list",
                           "agent_memory_save", "agent_memory_recall", "spawn_team_agent"}

        for iteration in range(self.max_iterations):
            if not self.manager.running:
                break

            self.status = "working"
            self.iteration = iteration + 1
            self.last_seen = time.time()

            # Inject channel updates + assignments (after first iteration)
            if iteration > 0:
                recent = self.manager.get_messages(for_role=self.role, n=10)
                if recent:
                    recent_text = "\n".join(f"[{m['from']}] {m['text']}" for m in recent)
                    # Parse JSON assignments
                    my_assignments = self._parse_assignments(recent)
                    assign_text = ""
                    if my_assignments:
                        assign_lines = [f"  - [{a.get('priority', '?')}] {a['task']}" for a in my_assignments]
                        assign_text = f"\n\n📌 YOUR ASSIGNMENTS:\n" + "\n".join(assign_lines)
                        self.current_task = my_assignments[0]["task"][:80]
                    # Add task board summary
                    board_summary = self.manager.task_board_list()
                    board_text = f"\n\n📋 TASK BOARD:\n{board_summary}" if "task-" in board_summary else ""
                    self.messages.append({"role": "user", "content": [{"type": "text", "text":
                        f"Channel update:\n{recent_text}{assign_text}{board_text}\n\nContinue your work or respond to messages."}]})

            try:
                body = {
                    "model": MODEL,
                    "max_tokens": 16000,
                    "system": [{"type": "text", "text": self._build_system()}],
                    "messages": self.messages[-12:],
                    "tools": tools,
                    "tool_choice": {"type": "auto"},
                    "stream": False,
                }
                if MODEL not in NO_SAMPLING_PARAMS:
                    body["temperature"] = 1
                    body["top_k"] = 40
                    body["top_p"] = 0.95

                with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
                    resp = client.post(_get_current_api_url(), headers=headers, json=body)
                    if resp.status_code != 200:
                        self.status = "error"
                        self.current_task = f"API {resp.status_code}"
                        break
                    data = resp.json()

                content = data.get("content", [])
                if not content:
                    break

                # Process text output → route through manager
                for block in content:
                    if block.get("type") == "text" and block.get("text"):
                        text = block["text"].strip()
                        if text:
                            self.manager.route_message(self.role, text)
                            console.print(f"  [{self.color}]{self.emoji} {self.name}({self.role})[/{self.color}]: {text[:200]}")

                # Process tool calls
                tool_blocks = [b for b in content if b.get("type") == "tool_use"]
                if not tool_blocks:
                    # Check if this agent still has pending/in_progress tasks
                    has_pending = False
                    with self.manager.task_board_lock:
                        for t in self.manager.task_board.values():
                            if t.get("assignee") == self.role and t["status"] != "done":
                                has_pending = True
                                break
                    if has_pending and iteration < self.max_iterations - 1:
                        # Still has work — nudge agent to continue
                        self.messages.append({"role": "assistant", "content": content})
                        self.messages.append({"role": "user", "content": [{"type": "text", "text":
                            "You still have unfinished tasks on the board. Please continue working on them. Use your tools to complete them."}]})
                        time.sleep(2)
                        continue
                    break

                self.messages.append({"role": "assistant", "content": content})

                tool_results = []
                for tb in tool_blocks:
                    name = tb["name"]
                    inp = tb.get("input", {})
                    tid = tb["id"]

                    if name in team_tool_names:
                        # Team-specific tools
                        console.print(f"  [dim]{self.emoji} {self.name} -> {name}[/dim]")
                        result = self._handle_team_tool(name, inp)
                    else:
                        handler = TOOL_HANDLERS.get(name)
                        if handler and name not in ("spawn_agent", "browser"):
                            console.print(f"  [dim]{self.emoji} {self.name} -> {name}[/dim]")
                            self.current_task = f"running {name}"
                            result = handler(inp)
                            # Track files in agent memory
                            if name == "read" and inp.get("file_path"):
                                fpath = inp["file_path"]
                                if fpath not in self.memory["files_read"]:
                                    self.memory["files_read"].append(fpath)
                            elif name in ("write", "edit") and inp.get("file_path"):
                                fpath = inp["file_path"]
                                if fpath not in self.memory["files_written"]:
                                    self.memory["files_written"].append(fpath)
                        else:
                            result = f"[not available for team agents: {name}]"
                    tool_results.append({"type": "tool_result", "tool_use_id": tid, "content": str(result)[:5000]})

                self.messages.append({"role": "user", "content": tool_results})
                self.last_seen = time.time()
                time.sleep(1)

            except Exception as e:
                self.status = "error"
                self.current_task = str(e)[:60]
                console.print(f"  [red]{self.emoji} {self.name}({self.role}) error: {e}[/red]")
                break

        self.status = "done"
        self.last_seen = time.time()
        console.print(f"  [{self.color}]{self.emoji} {self.name}({self.role}) finished[/{self.color}]")

    def _parse_assignments(self, messages_list):
        """Extract JSON assignments addressed to this role."""
        assignments = []
        for m in messages_list:
            text = m.get("text", "")
            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "assignment" and obj.get("to") == self.role:
                            assignments.append(obj)
                    except (json.JSONDecodeError, KeyError):
                        pass
        return assignments


# ---------------------------------------------------------------------------
# TeamManager — orchestrator for all agents
# ---------------------------------------------------------------------------
class TeamManager:
    """Manages team agents, message routing, task board, and monitoring."""

    MAX_AGENTS = 8

    def __init__(self):
        self.agents: Dict[str, TeamAgent] = {}
        self.channel_history = []
        self.channel_lock = threading.Lock()
        self.running = False
        self.task_board = {}
        self.task_board_lock = threading.Lock()
        self._task_counter = 0
        self._monitor_thread = None

    # ---- Message routing ----

    def post_message(self, from_label: str, text: str, to: str = None):
        """Post a message to the channel with optional routing."""
        msg = {"from": from_label, "text": text[:300], "time": time.time(), "to": to}
        with self.channel_lock:
            self.channel_history.append(msg)

    def route_message(self, from_role: str, text: str):
        """Route a message based on @mentions."""
        agent = self.agents.get(from_role)
        from_label = f"{agent.emoji} {agent.name}({from_role})" if agent else from_role

        # Detect @mentions
        if "@all" in text or "@team" in text:
            self.post_message(from_label, text, to="@all")
        else:
            # Check for specific @role mentions
            mentioned = []
            for role_name in self.agents:
                if f"@{role_name}" in text:
                    mentioned.append(role_name)
            if mentioned:
                for target in mentioned:
                    self.post_message(from_label, text, to=target)
            else:
                # No specific mention → shared channel (visible to all)
                self.post_message(from_label, text, to=None)

    def get_messages(self, for_role: str = None, n: int = 10):
        """Get recent messages relevant to a specific role."""
        with self.channel_lock:
            if for_role is None:
                return list(self.channel_history[-n:])
            # Filter: messages addressed to this role, @all, or shared (to=None)
            relevant = [m for m in self.channel_history
                        if m.get("to") is None or m.get("to") == "@all" or m.get("to") == for_role]
            return list(relevant[-n:])

    # ---- Task board ----

    def task_board_create(self, text: str, assignee: str = None, priority: int = 3, created_by: str = None) -> str:
        with self.task_board_lock:
            self._task_counter += 1
            tid = f"task-{self._task_counter}"
            self.task_board[tid] = {
                "text": text, "status": "pending", "assignee": assignee or "unassigned",
                "priority": priority, "created_by": created_by or "unknown",
                "created_at": time.time(),
            }
        return f"Created {tid}: {text[:60]} (assigned to {assignee or 'unassigned'})"

    def task_board_update(self, task_id: str, status: str) -> str:
        with self.task_board_lock:
            if task_id not in self.task_board:
                return f"Task {task_id} not found. Use team_task_list to see all tasks."
            if status not in ("pending", "in_progress", "done"):
                return f"Invalid status: {status}. Use: pending, in_progress, done"
            self.task_board[task_id]["status"] = status
        return f"Updated {task_id} -> {status}"

    def task_board_list(self) -> str:
        with self.task_board_lock:
            if not self.task_board:
                return "Task board is empty."
            lines = []
            status_icons = {"pending": "⬜", "in_progress": "🔄", "done": "✅"}
            for tid, t in sorted(self.task_board.items(), key=lambda x: x[1].get("priority", 3)):
                icon = status_icons.get(t["status"], "❓")
                lines.append(f"{icon} {tid} [{t['status']}] P{t['priority']} → {t['assignee']}: {t['text'][:60]}")
            done = sum(1 for t in self.task_board.values() if t["status"] == "done")
            total = len(self.task_board)
            lines.append(f"\nProgress: {done}/{total} done")
            return "\n".join(lines)

    # ---- Dynamic agent spawning (Level 3.1) ----

    def spawn_agent(self, role: str, custom_prompt: str = None) -> str:
        if len(self.agents) >= self.MAX_AGENTS:
            return f"Cannot spawn: max {self.MAX_AGENTS} agents reached."
        if role in self.agents:
            return f"Agent '{role}' already exists."

        agent = TeamAgent(role, self._current_task, self, custom_system=custom_prompt)
        self.agents[role] = agent
        t = threading.Thread(target=agent.run, daemon=True)
        agent.thread = t
        t.start()
        console.print(f"  [bold bright_cyan]🆕 Spawned: {agent.emoji} {agent.name}({role})[/bold bright_cyan]")
        self.post_message("🧠 system", f"New agent joined: {agent.emoji} {role}", to="@all")
        return f"Spawned new agent: {role} ({agent.emoji})"

    # ---- Heartbeat monitor (Level 2.5) ----

    def _heartbeat_monitor(self):
        """Background thread that monitors agent health."""
        while self.running:
            time.sleep(10)
            if not self.running:
                break
            for role, agent in list(self.agents.items()):
                if agent.status in ("done", "error"):
                    continue
                elapsed = time.time() - agent.last_seen
                if elapsed > 120:
                    console.print(f"  [bold red]⚠ {agent.emoji} {agent.name} unresponsive ({int(elapsed)}s)[/bold red]")
                    agent.status = "error"
                    agent.current_task = f"timeout ({int(elapsed)}s)"
                elif elapsed > 60:
                    console.print(f"  [yellow]⚠ {agent.emoji} {agent.name} slow ({int(elapsed)}s)[/yellow]")

    # ---- Start / Stop ----

    def start(self, task: str, roles: list, isolation: str = "thread", max_rounds: int = 25):
        """Start the team. isolation='thread' or 'process'."""
        import multiprocessing as mp

        self.running = True
        self._current_task = task
        self._isolation = isolation
        self._max_rounds = max_rounds
        with self.channel_lock:
            self.channel_history.clear()
        with self.task_board_lock:
            self.task_board.clear()
            self._task_counter = 0
        self.agents.clear()

        # Create agents
        for role in roles:
            agent = TeamAgent(role, task, self)
            agent.max_iterations = max_rounds
            self.agents[role] = agent

        console.print(f"\n[bold cyan]Starting team ({len(roles)} agents) [isolation={isolation}]:[/bold cyan]")
        for role, agent in self.agents.items():
            console.print(f"  {agent.emoji} {agent.name}({role})")
        console.print()

        # Start agents — planner/supervisor first
        first_roles = [r for r in roles if r in ("planner", "supervisor")]
        other_roles = [r for r in roles if r not in ("planner", "supervisor")]

        processes = []

        def _start_agent(role):
            agent = self.agents[role]
            if isolation == "process":
                # Process-based: each agent runs in its own process
                # Note: agent.run uses httpx + console, so we wrap in a subprocess
                p = mp.Process(target=self._run_agent_in_process, args=(role, task), daemon=True)
                p.start()
                processes.append((role, p))
                agent.thread = None  # track via process instead
            else:
                t = threading.Thread(target=agent.run, daemon=True)
                agent.thread = t
                t.start()

        for role in first_roles:
            _start_agent(role)
        if first_roles:
            time.sleep(3)  # let planner/supervisor create the plan
        for role in other_roles:
            _start_agent(role)
            time.sleep(1)

        # Start heartbeat monitor
        self._monitor_thread = threading.Thread(target=self._heartbeat_monitor, daemon=True)
        self._monitor_thread.start()

        # Wait for all to finish
        if isolation == "process":
            for role, p in processes:
                p.join(timeout=300)
                if p.is_alive():
                    console.print(f"  [red]⚠ {role} timed out — terminating[/red]")
                    p.terminate()
        else:
            for role, agent in self.agents.items():
                if agent.thread:
                    agent.thread.join(timeout=300)

        self.running = False
        with self.channel_lock:
            msg_count = len(self.channel_history)
            summary = "\n".join(f"[{m['from']}] {m['text']}" for m in self.channel_history)
        console.print(f"\n[bold green]Team finished! {msg_count} messages exchanged.[/bold green]")

        # Show final task board
        board = self.task_board_list()
        if "task-" in board:
            console.print(f"\n[bold]Final Task Board:[/bold]")
            console.print(board)

        # Show files created/modified by agents
        all_files_written = []
        for role, agent in self.agents.items():
            if agent.memory["files_written"]:
                for f in agent.memory["files_written"]:
                    if f not in all_files_written:
                        all_files_written.append(f)
        if all_files_written:
            console.print(f"\n[bold]Files created/modified:[/bold]")
            for f in all_files_written:
                console.print(f"  [green]+[/green] {f}")

        # Build rich summary for main conversation
        files_summary = ""
        if all_files_written:
            files_summary = "\n\nFiles created/modified:\n" + "\n".join(f"  - {f}" for f in all_files_written)
            # Include content of written files in summary
            for fpath in all_files_written[:5]:  # limit to 5 files
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read(3000)
                        files_summary += f"\n\n--- {fpath} ---\n{content}"
                except Exception:
                    pass

        return summary + files_summary

    def _run_agent_in_process(self, role: str, task: str):
        """Wrapper to run an agent in a separate process."""
        # In process mode, we create a fresh agent (can't share TeamManager across processes easily)
        # So process mode uses a simplified loop with channel communication via the shared manager
        try:
            agent = self.agents.get(role)
            if agent:
                agent.run()
        except Exception as e:
            console.print(f"  [red]{role} process error: {e}[/red]")

    def stop(self):
        self.running = False

    def get_agent_statuses(self) -> dict:
        return {role: agent.get_status_dict() for role, agent in self.agents.items()}

    # ---- Visualization (Level 3.5) ----

    def render_status_table(self):
        """Render a Rich table showing all agent statuses."""
        tbl = Table(title="Team Agent Status", show_lines=True)
        tbl.add_column("Agent", style="bold")
        tbl.add_column("Status")
        tbl.add_column("Iter", justify="center")
        tbl.add_column("Current Task")
        tbl.add_column("Files", justify="center")
        tbl.add_column("Last Seen")
        status_colors = {"idle": "dim", "working": "yellow", "done": "green", "error": "red"}
        for role, agent in self.agents.items():
            st_color = status_colors.get(agent.status, "white")
            elapsed = time.time() - agent.last_seen
            ago = f"{int(elapsed)}s ago" if elapsed > 1 else "just now"
            files = len(agent.memory["files_read"]) + len(agent.memory["files_written"])
            tbl.add_row(
                f"{agent.emoji} {agent.name}({role})",
                f"[{st_color}]{agent.status}[/{st_color}]",
                str(agent.iteration),
                agent.current_task[:50],
                str(files),
                ago,
            )
        return tbl

    def render_task_graph(self) -> str:
        """Generate a Mermaid diagram of the task board."""
        if not self.task_board:
            return "No tasks on the board."
        lines = ["```mermaid", "graph TD"]
        status_style = {"pending": ":::pending", "in_progress": ":::active", "done": ":::done"}
        for tid, t in self.task_board.items():
            safe_text = t['text'][:40].replace('"', "'")
            node_id = tid.replace("-", "_")
            style = status_style.get(t["status"], "")
            lines.append(f'    {node_id}["{tid}: {safe_text}"]{style}')
            if t.get("assignee") and t["assignee"] != "unassigned":
                assignee_id = f"agent_{t['assignee']}"
                lines.append(f'    {assignee_id}(("{t["assignee"]}")) --> {node_id}')
        lines.append("    classDef pending fill:#f9f,stroke:#333")
        lines.append("    classDef active fill:#ff9,stroke:#333")
        lines.append("    classDef done fill:#9f9,stroke:#333")
        lines.append("```")
        return "\n".join(lines)


# Global TeamManager instance
_team_manager = TeamManager()

# Backward-compatible globals (used by /team command and _cleanup_all)
_team_running = False
_team_agent_status = {}


def _detect_team_roles(task: str) -> list:
    """Auto-detect the best team composition based on the task description."""
    task_lower = task.lower()
    # Coding keywords (strong signals)
    code_kw = ["code", "build", "create app", "website", "web app", "api", "rest api",
               "frontend", "backend", "html", "css", "react", "vue", "angular",
               "python", "javascript", "typescript", "deploy", "fix bug", "debug",
               "refactor", "implement", "develop", "server", "database", "component",
               "function", "class", "module", "endpoint", "cli", "script"]
    # Research keywords
    research_kw = ["research", "find out", "compare", "investigate", "search for",
                   "analyze", "study", "explore", "survey", "benchmark", "evaluate",
                   "pros and cons", "what is", "how does"]
    # Writing keywords (content creation, not code-related "write")
    write_kw = ["write a", "write about", "write an", "article", "blog", "blog post",
                "document", "report", "summary", "summarize", "content", "essay",
                "proposal", "strategy", "readme", "translate", "draft", "copywrite",
                "narrative", "presentation", "slide"]

    # Count keyword matches to determine strength of signal
    code_hits = [kw for kw in code_kw if kw in task_lower]
    research_hits = [kw for kw in research_kw if kw in task_lower]
    write_hits = [kw for kw in write_kw if kw in task_lower]

    is_code = len(code_hits) > 0
    is_research = len(research_hits) > 0
    is_writing = len(write_hits) > 0

    # Writing/research take priority when explicitly stated (e.g. "write a blog post about Python")
    if is_writing and is_research:
        return ["planner", "researcher", "analyst", "writer"]
    elif is_writing and is_code:
        # "write about" + code topic → writing team; "build + docs" → code team
        if len(write_hits) >= len(code_hits):
            return ["planner", "writer", "editor"]
        return ["planner", "frontend", "backend"]
    elif is_writing:
        return ["planner", "writer", "editor"]
    elif is_research:
        if is_code:
            return ["planner", "researcher", "frontend", "backend"]
        return ["planner", "researcher", "analyst"]
    elif is_code:
        return ["planner", "frontend", "backend"]
    else:
        return ["planner", "researcher", "writer"]


def run_team(task: str, roles: list = None, isolation: str = "thread", max_rounds: int = 25):
    """Start a team of agents working together."""
    global _team_running, _team_agent_status

    if not roles:
        roles = _detect_team_roles(task)
        role_str = ", ".join(roles)
        console.print(f"[dim]Auto-detected team: {role_str}[/dim]")

    # Validate roles — allow custom roles too, just warn
    known_roles = set(_TEAM_ROLES.keys())
    for r in roles:
        if r not in known_roles:
            console.print(f"[warning]Note: '{r}' is a custom role (no predefined prompt)[/warning]")

    _team_running = True
    result = _team_manager.start(task, roles, isolation=isolation, max_rounds=max_rounds)
    _team_running = False
    _team_agent_status = _team_manager.get_agent_statuses()

    return result


TOOL_HANDLERS = {
    "bash": exec_bash,
    "read": exec_read,
    "write": exec_write,
    "edit": exec_edit,
    "glob": exec_glob,
    "grep": exec_grep,
    "list_dir": exec_list_dir,
    "multi_edit": exec_multi_edit,
    "web_search": exec_web_search,
    "web_fetch": exec_web_fetch,
    "memory_search": exec_memory_search,
    "memory_save": exec_memory_save,
    "task_create": exec_task_create,
    "task_update": exec_task_update,
    "task_list": exec_task_list,
    "spawn_agent": exec_spawn_agent,
    "browser": exec_browser,
    "http": exec_http,
    "screenshot": exec_screenshot,
    "semantic_search": exec_semantic_search,
    "bosshelp": lambda args: _boss_help(
        problem=args.get("problem", ""),
        context=args.get("context", ""),
        code=args.get("code", ""),
        error=args.get("error", ""),
    ),
}


# ============================================================================
# Streaming Response Renderer (Professional Neon Dark + Realtime)
# ============================================================================


def make_professional_header():
    """Header v2 (compact + clean)."""
    ctx_max = CONTEXT_WINDOWS.get(MODEL, 200000)
    ctx_pct = (last_input_tokens / ctx_max * 100) if last_input_tokens > 0 else 0
    task_count = len([t for t in _tasks if t["status"] != "done"])

    # Shorten path for clean display
    short_cwd = CWD
    if len(short_cwd) > 35:
        short_cwd = "..." + short_cwd[-32:]

    header = Columns([
        Text(" ToonCode ", style="bold primary on #0f0f23"),
        Text(f" {MODEL} ", style="bold accent"),
        Text(f" {short_cwd} ", style="dim white"),
        Text(f" msgs:{message_count} ", style="dim"),
        Text(f" ctx:{last_input_tokens//1000}k ",
             style="bold warning" if ctx_pct > 75 else "dim"),
        Text(f" tasks:{task_count} ", style="dim"),
        Text(f" {datetime.now().strftime('%H:%M')} ", style="dim"),
    ], expand=True)

    return Panel(
        header,
        style="on #16213e",
        padding=(0, 1),
        title="[bold primary]ToonCode[/bold primary]",
        title_align="left",
    )


class StreamRenderer:
    """Professional Neon Dark StreamRenderer with realtime smooth updates."""

    def __init__(self):
        self.text_buffer = ""
        self.thinking_buffer = ""
        self.current_block_type = None
        self.tool_blocks = []
        self.content_blocks = []
        self.current_tool_name = ""
        self.current_tool_json = ""
        self.current_tool_id = ""
        self.current_signature = ""
        self.in_thinking = False
        self.in_text = False
        self.in_tool = False
        self._live = None
        self._finalized = False
        self._start_time = time.time()
        self._token_count = 0

    def start(self):
        """Start the live display."""
        self._live = Live(
            self._build_display(),
            console=console,
            refresh_per_second=30,          # smoother realtime updates
            vertical_overflow="visible",
            transient=True,
        )
        self._live.start()

    def stop(self):
        """Stop the live display and print final formatted output."""
        if self._live:
            self._live.update(Text(""))
            self._live.stop()
            self._live = None
            self._print_final()

    def _build_display(self) -> Group:
        """Build display — no header, just content."""
        renderables = []

        # Thinking panel
        if self.thinking_buffer:
            renderables.append(Panel(
                Text(self.thinking_buffer, style="dim italic"),
                title="[dim]thinking...[/dim]",
                border_style="accent",
                padding=(0, 2),
            ))

        # Tool cards
        for tool in self.tool_blocks:
            renderables.append(self._make_tool_panel(tool))

        # Current tool being built
        if self.in_tool and self.current_tool_name:
            renderables.append(Panel(
                Text(f"calling {self.current_tool_name}...", style="dim italic"),
                border_style="accent",
                padding=(0, 1),
            ))

        # Main response
        if self.text_buffer:
            renderables.append(Panel(
                Text(self.text_buffer),
                border_style="primary",
                padding=(1, 2),
                title="[bold primary]Response[/bold primary]",
            ))

        return Group(*renderables)

    def _make_tool_panel(self, tool: dict) -> Panel:
        """Create a neon-styled panel for a tool call."""
        name = tool.get("name", "unknown")
        inp = tool.get("input", {})

        if name == "bash":
            cmd = inp.get("command", "")
            desc = inp.get("description", "")
            summary = f"$ {cmd}"
            if len(summary) > 120:
                summary = summary[:117] + "..."
            title_extra = f" - {desc}" if desc else ""
        elif name == "read":
            summary = inp.get("filePath", "")
        elif name == "write":
            fp = inp.get("filePath", "")
            content = inp.get("content", "")
            lines = content.count("\n") + 1
            summary = f"{fp} ({lines} lines)"
        elif name == "edit":
            summary = inp.get("filePath", "")
        elif name == "glob":
            summary = inp.get("pattern", "")
        elif name == "grep":
            summary = f"/{inp.get('pattern', '')}/"
            if inp.get("include"):
                summary += f" in {inp['include']}"
        elif name == "web_search":
            summary = inp.get("query", "")
        elif name == "web_fetch":
            summary = inp.get("url", "")
        else:
            summary = json.dumps(inp)[:100]
            title_extra = ""

        if name != "bash":
            title_extra = ""

        title = f"[bold #ff00aa]{name}[/bold #ff00aa]{title_extra if name == 'bash' else ''}"
        content_text = Text(summary, style="#8888aa")

        return Panel(
            content_text,
            title=title,
            title_align="left",
            border_style="#ff00aa",
            padding=(0, 1),
        )

    def _print_final(self):
        """Print the final formatted output after streaming stops (no duplicate header)."""
        # Print thinking if any
        if self.thinking_buffer:
            thinking_text = Text(self.thinking_buffer, style="dim italic")
            console.print(Panel(
                thinking_text,
                title="[dim]thinking[/dim]",
                title_align="left",
                border_style="accent",
                padding=(0, 1),
            ))

        # Print tool panels
        for tool in self.tool_blocks:
            self._print_tool_result(tool)

        # Print text response with enhanced markdown table rendering
        if self.text_buffer:
            try:
                self._print_rich_text(self.text_buffer)
            except Exception:
                console.print(self.text_buffer)

    def _print_rich_text(self, text: str):
        """Print text with markdown tables converted to Rich Tables for better display."""
        lines = text.split("\n")
        i = 0
        non_table_lines = []

        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("|") and line.count("|") >= 3:
                if non_table_lines:
                    try:
                        console.print(Markdown("\n".join(non_table_lines)))
                    except Exception:
                        console.print("\n".join(non_table_lines))
                    non_table_lines = []

                table_lines = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1

                self._render_rich_table(table_lines)
            else:
                non_table_lines.append(lines[i])
                i += 1

        if non_table_lines:
            content = "\n".join(non_table_lines).strip()
            if content:
                try:
                    console.print(Markdown(content))
                except Exception:
                    console.print(content)

    def _render_rich_table(self, table_lines: list):
        """Convert markdown table lines to a Rich Table with neon styling."""
        if len(table_lines) < 2:
            console.print("\n".join(table_lines))
            return

        def _parse_row(line: str) -> list:
            cells = line.strip().strip("|").split("|")
            return [c.strip().replace("**", "").replace("*", "") for c in cells]

        headers = _parse_row(table_lines[0])

        start = 1
        if start < len(table_lines) and re.match(r'^[\|\s\-:]+$', table_lines[start]):
            start = 2

        table = Table(border_style="#00f5ff", show_header=True, header_style="bold #00f5ff", padding=(0, 1))
        for h in headers:
            table.add_column(h)

        for row_line in table_lines[start:]:
            cells = _parse_row(row_line)
            while len(cells) < len(headers):
                cells.append("")
            table.add_row(*cells[:len(headers)])

        console.print(table)

    def _print_tool_result(self, tool: dict):
        """Print a tool result panel with neon styling."""
        name = tool.get("name", "unknown")
        inp = tool.get("input", {})
        result = tool.get("result", "")

        parts = []
        if name == "bash":
            cmd = inp.get("command", "")
            parts.append(Text(f"$ {cmd}", style="bold"))
        elif name == "read":
            parts.append(Text(inp.get("filePath", ""), style="bold"))
        elif name == "write":
            parts.append(Text(inp.get("filePath", ""), style="bold"))
        elif name == "edit":
            parts.append(Text(inp.get("filePath", ""), style="bold"))
        elif name == "glob":
            parts.append(Text(inp.get("pattern", ""), style="bold"))
        elif name == "grep":
            parts.append(Text(f"/{inp.get('pattern', '')}/", style="bold"))
        elif name == "web_search":
            parts.append(Text(inp.get("query", ""), style="bold"))
        elif name == "web_fetch":
            parts.append(Text(inp.get("url", ""), style="bold"))

        if result:
            preview = result[:500]
            if len(result) > 500:
                preview += f"\n... ({len(result)} chars total)"
            parts.append(Text(""))
            parts.append(Text(preview, style="#8888aa"))

        content = Group(*parts) if parts else Text("(done)")
        desc = inp.get("description", "") if name == "bash" else ""
        title = f"[bold #ff00aa]{name}[/bold #ff00aa]"
        if desc:
            title += f" [#8888aa]- {desc}[/#8888aa]"

        console.print(Panel(
            content,
            title=title,
            title_align="left",
            border_style="#ff00aa",
            padding=(0, 1),
        ))

    def update(self):
        """Update the live display."""
        if self._live:
            self._live.update(self._build_display())

    # -- Event handlers --

    def on_thinking_delta(self, text: str):
        self.thinking_buffer += text
        self._token_count += max(1, len(text) // 4)
        self.update()

    def on_text_delta(self, text: str):
        self.text_buffer += text
        self._token_count += max(1, len(text) // 4)
        self.update()

    def on_tool_start(self, tool_id: str, name: str):
        self.in_tool = True
        self.current_tool_name = name
        self.current_tool_id = tool_id
        self.current_tool_json = ""
        self.update()

    def on_tool_json_delta(self, json_str: str):
        self.current_tool_json += json_str

    def on_tool_stop(self):
        try:
            inp = json.loads(self.current_tool_json) if self.current_tool_json else {}
        except json.JSONDecodeError:
            inp = {}
        self.tool_blocks.append({
            "name": self.current_tool_name,
            "id": self.current_tool_id,
            "input": inp,
        })
        self.in_tool = False
        self.current_tool_name = ""
        self.current_tool_json = ""
        self.current_tool_id = ""
        self.update()

    def on_thinking_start(self):
        self.in_thinking = True

    def on_thinking_stop(self):
        self.in_thinking = False

    def on_text_start(self):
        self.in_text = True

    def on_text_stop(self):
        self.in_text = False


# ============================================================================
# API Communication
# ============================================================================

def make_request_headers() -> dict:
    msg_id = _gen_id("msg", 24)
    h = {
        **HEADERS,
        "x-api-key": _get_api_key(),
        "x-opencode-request": msg_id,
        "x-opencode-session": SESSION_ID,
    }
    # If using a real API key (not "public"), also set Authorization header
    key = _get_api_key()
    if key and key != "public":
        h["x-api-key"] = key
        h["Authorization"] = f"Bearer {key}" if not key.startswith("sk-ant-") else f"x-api-key {key}"
    return h

def _get_current_api_url() -> str:
    """Get API URL for current request."""
    return _get_api_url()


def _validate_messages(messages: list):
    """Fix message ordering issues before sending to API."""
    # Rules:
    # 1. Must alternate user/assistant
    # 2. tool_result (in user msg) must come right after assistant with tool_use
    # 3. First message must be user
    fixed = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", [])
        if not content:
            continue

        # Detect message types
        is_tool_result = isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
        has_tool_use = isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_use" for b in content)

        if not fixed:
            # First message must be user
            if role != "user":
                fixed.append({"role": "user", "content": [{"type": "text", "text": "(start)"}]})
            fixed.append(msg)
            continue

        prev = fixed[-1]
        prev_role = prev.get("role", "")
        prev_content = prev.get("content", [])
        prev_has_tool_use = isinstance(prev_content, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_use" for b in prev_content)

        # tool_result must follow assistant with tool_use
        if is_tool_result and role == "user":
            if prev_role != "assistant" or not prev_has_tool_use:
                # Remove this tool_result — it's orphaned
                continue
            fixed.append(msg)
            continue

        # Fix consecutive same role
        if role == prev_role:
            if role == "user":
                fixed.append({"role": "assistant", "content": [{"type": "text", "text": "(continuing)"}]})
            else:
                fixed.append({"role": "user", "content": [{"type": "text", "text": "(continue)"}]})

        fixed.append(msg)

    messages.clear()
    messages.extend(fixed)


def stream_response(messages: list, renderer: StreamRenderer) -> dict:
    """Send request and stream the response, returning parsed content blocks."""
    global total_input_tokens, total_output_tokens, last_input_tokens

    # Validate message ordering
    _validate_messages(messages)

    system_prompt = build_system_prompt()

    body = {
        "model": MODEL,
        "max_tokens": 32000,
        "system": [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": {"type": "auto"},
        "stream": True,
    }

    # Only add sampling params for models that support them
    if MODEL not in NO_SAMPLING_PARAMS:
        body["temperature"] = 1
        body["top_k"] = 40
        body["top_p"] = 0.95

    headers = make_request_headers()
    content_blocks = []
    current_block = None
    stop_reason = "end_turn"  # default; updated from message_delta

    # Sanitize body in-place: remove surrogate characters that break JSON encoding
    def _sanitize_inplace(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    obj[k] = v.encode("utf-8", errors="replace").decode("utf-8")
                elif isinstance(v, (dict, list)):
                    _sanitize_inplace(v)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if isinstance(v, str):
                    obj[i] = v.encode("utf-8", errors="replace").decode("utf-8")
                elif isinstance(v, (dict, list)):
                    _sanitize_inplace(v)
    _sanitize_inplace(body)

    try:
        with httpx.Client(timeout=httpx.Timeout(300.0, connect=15.0, read=300.0)) as client:
            with client.stream("POST", _get_current_api_url(), headers=headers, json=body) as resp:
                if resp.status_code != 200:
                    err = resp.read().decode(errors="replace")
                    console.print(f"[error]API Error ({resp.status_code}): {err[:500]}[/error]")
                    return {"content": [{"type": "text", "text": f"API Error {resp.status_code}: {err[:200]}"}]}

                line_buf = b""
                _MAX_LINE_BUF = 1024 * 1024  # 1MB max buffer
                for chunk in resp.iter_bytes():
                    line_buf += chunk
                    if len(line_buf) > _MAX_LINE_BUF:
                        console.print("[yellow](stream buffer overflow - flushing)[/yellow]")
                        line_buf = b""
                    while b"\n" in line_buf:
                        raw_line, line_buf = line_buf.split(b"\n", 1)
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        # Handle both "data: {...}" (Anthropic) and bare "{...}" (GPT) formats
                        if line.startswith("data: "):
                            data_str = line[6:]
                        elif line.startswith("{"):
                            data_str = line
                        else:
                            continue
                        if data_str.strip() in ("[DONE]", ""):
                            continue
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        if not event:
                            continue

                        etype = event.get("type", "")

                        # Track token usage
                        if etype == "message_start":
                            usage = event.get("message", {}).get("usage", {})
                            req_input = usage.get("input_tokens", 0)
                            cache_read = usage.get("cache_read_input_tokens", 0)
                            cache_create = usage.get("cache_creation_input_tokens", 0)
                            last_input_tokens = req_input + cache_read + cache_create
                            total_input_tokens += req_input

                        elif etype == "message_delta":
                            usage = event.get("usage", {})
                            total_output_tokens += usage.get("output_tokens", 0)
                            # Track stop reason
                            delta_obj = event.get("delta", {})
                            if delta_obj.get("stop_reason"):
                                stop_reason = delta_obj["stop_reason"]
                            # Real input token count often arrives here
                            delta_input = usage.get("input_tokens", 0)
                            delta_cache_read = usage.get("cache_read_input_tokens", 0)
                            delta_cache_create = usage.get("cache_creation_input_tokens", 0)
                            if delta_input + delta_cache_read + delta_cache_create > 0:
                                last_input_tokens = delta_input + delta_cache_read + delta_cache_create

                        elif etype == "content_block_start":
                            block = event.get("content_block", {})
                            btype = block.get("type", "text")
                            current_block = {"type": btype, "index": event.get("index", 0)}

                            if btype == "text":
                                current_block["text"] = block.get("text", "")
                                renderer.on_text_start()
                                if current_block["text"]:
                                    renderer.on_text_delta(current_block["text"])
                            elif btype == "thinking":
                                current_block["thinking"] = block.get("thinking", "")
                                current_block["signature"] = ""
                                renderer.on_thinking_start()
                                if current_block["thinking"]:
                                    renderer.on_thinking_delta(current_block["thinking"])
                            elif btype == "tool_use":
                                current_block["id"] = block.get("id", "")
                                current_block["name"] = block.get("name", "")
                                current_block["input_json"] = ""
                                renderer.on_tool_start(current_block["id"], current_block["name"])

                        elif etype == "content_block_delta":
                            delta = event.get("delta", {})
                            dtype = delta.get("type", "")

                            # GPT models skip content_block_start, auto-create block
                            if current_block is None:
                                if dtype == "text_delta":
                                    current_block = {"type": "text", "text": "", "index": event.get("index", 0)}
                                    renderer.on_text_start()
                                elif dtype == "thinking_delta":
                                    current_block = {"type": "thinking", "thinking": "", "signature": "", "index": event.get("index", 0)}
                                    renderer.on_thinking_start()

                            if dtype == "text_delta" and current_block:
                                txt = delta.get("text", "")
                                current_block["text"] = current_block.get("text", "") + txt
                                renderer.on_text_delta(txt)

                            elif dtype == "thinking_delta" and current_block:
                                t = delta.get("thinking", "")
                                current_block["thinking"] = current_block.get("thinking", "") + t
                                renderer.on_thinking_delta(t)

                            elif dtype == "signature_delta" and current_block:
                                sig = delta.get("signature", "")
                                current_block["signature"] = current_block.get("signature", "") + sig

                            elif dtype == "input_json_delta" and current_block:
                                pj = delta.get("partial_json", "")
                                current_block["input_json"] = current_block.get("input_json", "") + pj
                                renderer.on_tool_json_delta(pj)

                        elif etype == "content_block_stop":
                            if current_block:
                                if current_block.get("type") == "tool_use":
                                    try:
                                        current_block["input"] = json.loads(current_block.get("input_json", "{}"))
                                    except (json.JSONDecodeError, Exception):
                                        current_block["input"] = {}
                                    if "input_json" in current_block:
                                        del current_block["input_json"]
                                    renderer.on_tool_stop()
                                elif current_block.get("type") == "thinking":
                                    renderer.on_thinking_stop()
                                elif current_block.get("type") == "text":
                                    renderer.on_text_stop()
                                content_blocks.append(current_block)
                            current_block = None

                        elif etype == "message_stop":
                            break

                        # GPT models send bare {"usage": {...}} without type
                        if not etype and "usage" in event:
                            usage = event["usage"]
                            total_output_tokens += usage.get("output_tokens", 0)
                            u_input = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
                            if u_input > 0:
                                last_input_tokens = u_input

    except httpx.ConnectError as e:
        console.print(f"[error]Connection error: {e}[/error]")
        return {"content": [{"type": "text", "text": f"Connection error: {e}"}]}
    except httpx.ReadTimeout:
        console.print("[error]Request timed out[/error]")
        return {"content": [{"type": "text", "text": "Request timed out"}]}
    except Exception as e:
        console.print(f"[error]Error: {e}[/error]")
        return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    # Flush any remaining block (GPT models may not send content_block_stop)
    if current_block:
        if current_block.get("type") == "tool_use":
            try:
                current_block["input"] = json.loads(current_block.get("input_json", "{}"))
            except (json.JSONDecodeError, Exception):
                current_block["input"] = {}
            if "input_json" in current_block:
                del current_block["input_json"]
            renderer.on_tool_stop()
        content_blocks.append(current_block)

    # Build response content list
    result_content = []
    for block in content_blocks:
        btype = block.get("type", "text")
        if btype == "text":
            result_content.append({"type": "text", "text": block.get("text", "")})
        elif btype == "thinking":
            result_content.append({
                "type": "thinking",
                "thinking": block.get("thinking", ""),
                "signature": block.get("signature", ""),
            })
        elif btype == "tool_use":
            result_content.append({
                "type": "tool_use",
                "id": block.get("id", ""),
                "name": block.get("name", ""),
                "input": block.get("input", {}),
            })

    # If response is completely empty, return an error so the retry logic can handle it
    if not result_content:
        console.print("[yellow](model returned empty response)[/yellow]")
        return {"content": [{"type": "text", "text": "Error: empty response from model"}], "stop_reason": "error"}

    return {"content": result_content, "stop_reason": stop_reason}


# ============================================================================
# Tool Execution with Rich Output
# ============================================================================

_recent_tool_calls = deque(maxlen=20)  # track last N tool calls to detect loops
_recent_tool_calls_lock = threading.Lock()
_MAX_SAME_CALL = 2  # max times same tool+args can repeat
_loop_break = False  # signal to break agent loop

def execute_tools(content: list) -> list:
    """Execute all tool calls and return tool results."""
    global _loop_break
    tool_results = []
    for block in content:
        if block.get("type") != "tool_use":
            continue

        name = block.get("name", "unknown")
        args = block.get("input", {})
        tool_id = block.get("id", "")

        # Anti-loop: detect same tool call repeating
        # Use shorter signature to catch similar (not just exact) repeated calls
        if name == "bash":
            call_sig = f"bash:{args.get('command', '')[:80]}"
        else:
            call_sig = f"{name}:{json.dumps(args, sort_keys=True)[:100]}"
        with _recent_tool_calls_lock:
            same_count = sum(1 for c in list(_recent_tool_calls)[-6:] if c == call_sig)
            _recent_tool_calls.append(call_sig)

        if same_count >= _MAX_SAME_CALL:
            console.print(f"[yellow]Loop detected: {name} called {same_count+1}x with same args — skipping[/yellow]")
            if same_count >= 4:
                _loop_break = True
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": f"[LOOP DETECTED] You already called {name} with the same arguments {same_count+1} times and it failed. "
                           f"You MUST try a completely different approach. Read the file first, use a different tool, or ask the user for help.",
            })
            continue

        handler = TOOL_HANDLERS.get(name)
        if handler:
            # Show execution indicator
            desc = args.get("description", name) if name == "bash" else name
            with console.status(f"[dim]Executing {name}...[/dim]", spinner="dots"):
                result = handler(args)

            # Show result panel
            preview = result[:600]
            if len(result) > 600:
                preview += f"\n... ({len(result)} total chars)"

            result_parts = []
            if name == "bash":
                cmd = args.get("command", "")
                result_parts.append(Text(f"$ {cmd}", style="bold white"))
                result_parts.append(Text(""))
            elif name == "read":
                result_parts.append(Text(args.get("filePath", ""), style="bold white"))
                result_parts.append(Text(""))
            elif name == "write":
                result_parts.append(Text(args.get("filePath", ""), style="bold white"))
                result_parts.append(Text(""))
            elif name == "edit":
                result_parts.append(Text(args.get("filePath", ""), style="bold white"))
                result_parts.append(Text(""))
            elif name == "glob":
                result_parts.append(Text(args.get("pattern", ""), style="bold white"))
                result_parts.append(Text(""))
            elif name == "grep":
                pat = args.get("pattern", "")
                result_parts.append(Text(f"/{pat}/", style="bold white"))
                result_parts.append(Text(""))

            result_parts.append(Text(preview, style="dim"))

            title = f"[bold yellow]{name}[/bold yellow]"
            if name == "bash" and args.get("description"):
                title += f" [dim]- {args['description']}[/dim]"

            console.print(Panel(
                Group(*result_parts),
                title=title,
                title_align="left",
                border_style="yellow dim",
                padding=(0, 1),
            ))
        else:
            result = f"[unknown tool: {name}]"
            console.print(f"[error]Unknown tool: {name}[/error]")

        # Build content — if result is a dict with "images", include as vision content
        if isinstance(result, dict) and "images" in result:
            content_blocks = []
            for img in result["images"]:
                content_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.get("media_type", "image/png"),
                        "data": img["data"],
                    },
                })
            if result.get("text"):
                content_blocks.append({"type": "text", "text": result["text"]})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": content_blocks,
            })
        else:
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result if isinstance(result, str) else str(result),
            })

    return tool_results


def _find_claude_cmd() -> Optional[str]:
    """Find claude CLI path."""
    import shutil
    cmd = shutil.which("claude")
    if cmd:
        return cmd
    for p in [
        os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"),
        os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "npm", "claude.cmd"),
        "/usr/local/bin/claude",
    ]:
        if os.path.exists(p):
            return p
    return None


def _boss_help(problem: str, context: str = "", code: str = "", error: str = "") -> str:
    """Ask Boss AI (boss) for help when stuck. Falls back to own model if CLI not found."""

    # Build help prompt
    help_prompt = f"""I'm an AI coding agent and I'm STUCK. I need your help to solve this problem.

## Problem
{problem}

## Working directory: {CWD}
"""
    if context:
        help_prompt += f"\n## Context\n{context}\n"
    if code:
        help_prompt += f"\n## Relevant Code\n```\n{code[:3000]}\n```\n"
    if error:
        help_prompt += f"\n## Error Message\n```\n{error[:2000]}\n```\n"
    help_prompt += """
## What I need
1. Root cause explanation
2. EXACT fix — complete code or commands
3. Step by step if needed
Be specific. Give copy-paste ready solutions."""

    # Try Boss AI CLI first
    claude_cmd = _find_claude_cmd()
    if claude_cmd:
        console.print("[bold magenta][bosshelp] Asking Boss AI...[/bold magenta]")
        try:
            result = subprocess.run(
                [claude_cmd, "--print", "--dangerously-skip-permissions"],
                input=help_prompt,
                capture_output=True, text=True, cwd=CWD, timeout=180,
                encoding="utf-8", errors="replace",
            )
            answer = result.stdout.strip()
            if answer:
                console.print(Panel(
                    Text(answer[:500] + ("..." if len(answer) > 500 else ""), style="dim"),
                    title="[bold magenta]Boss Answer (Boss AI)[/bold magenta]",
                    border_style="magenta",
                ))
                return answer
        except subprocess.TimeoutExpired:
            console.print("[yellow]Boss AI timed out, falling back to own model...[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Boss AI error ({e}), falling back to own model...[/yellow]")

    # Fallback: use our own model via API
    console.print(f"[bold magenta][bosshelp] Asking {MODEL} for help...[/bold magenta]")
    try:
        body = {
            "model": MODEL,
            "max_tokens": 4000,
            "system": [{"type": "text", "text": "You are a senior debugging expert. The user is an AI coding agent that is stuck. Give precise, actionable fixes with exact code. No vague advice."}],
            "messages": [{"role": "user", "content": [{"type": "text", "text": help_prompt}]}],
            "stream": False,
        }
        if MODEL not in NO_SAMPLING_PARAMS:
            body["temperature"] = 1
            body["top_k"] = 40
            body["top_p"] = 0.95

        with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
            resp = client.post(_get_current_api_url(), headers=make_request_headers(), json=body)
            if resp.status_code != 200:
                err_text = resp.text[:300]
                console.print(f"[error]Boss API error ({resp.status_code}): {err_text}[/error]")
                # Try other models as fallback
                for fallback_model in AVAILABLE_MODELS:
                    if fallback_model == MODEL:
                        continue
                    console.print(f"[dim]Trying {fallback_model}...[/dim]")
                    body["model"] = fallback_model
                    if fallback_model in NO_SAMPLING_PARAMS:
                        body.pop("temperature", None)
                        body.pop("top_k", None)
                        body.pop("top_p", None)
                    try:
                        # Use that model's endpoint if it has one
                        mcfg = _get_model_config(fallback_model)
                        fb_url = mcfg.get("api_url", _get_current_api_url())
                        fb_headers = dict(make_request_headers())
                        if mcfg.get("api_key"):
                            fb_headers["x-api-key"] = mcfg["api_key"]
                        resp2 = client.post(fb_url, headers=fb_headers, json=body)
                        if resp2.status_code == 200:
                            data2 = resp2.json()
                            for block in data2.get("content", []):
                                if block.get("type") == "text" and block.get("text"):
                                    answer = block["text"]
                                    console.print(Panel(
                                        Text(answer[:500] + ("..." if len(answer) > 500 else ""), style="dim"),
                                        title=f"[bold magenta]Boss Answer ({fallback_model})[/bold magenta]",
                                        border_style="magenta",
                                    ))
                                    return answer
                    except Exception:
                        continue
                return "[bosshelp: all models failed]"

            data = resp.json()
            answer = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    answer += block.get("text", "")
            if answer:
                console.print(Panel(
                    Text(answer[:500] + ("..." if len(answer) > 500 else ""), style="dim"),
                    title=f"[bold magenta]Boss Answer ({MODEL})[/bold magenta]",
                    border_style="magenta",
                ))
                return answer
            else:
                console.print("[yellow]Boss returned empty response[/yellow]")
    except Exception as e:
        console.print(f"[error]Boss fallback error: {e}[/error]")

    return "[bosshelp: all methods failed]"


def _do_autocompact(messages: list):
    """Autocompact: summarize conversation, save to memory, reload context, auto-continue."""
    ctx_max = CONTEXT_WINDOWS.get(MODEL, 200_000)

    pending_tasks = [t for t in _tasks if t["status"] != "done"]
    task_info = ""
    if pending_tasks:
        task_info = "\n\nPENDING TASKS (must continue):\n"
        task_info += "\n".join(f"- #{t['id']} [{t['status']}] {t['text']}" for t in pending_tasks)

    done_tasks = [t for t in _tasks if t["status"] == "done"]
    done_info = ""
    if done_tasks:
        done_info = "\n\nCOMPLETED TASKS:\n"
        done_info += "\n".join(f"- #{t['id']} {t['text']}" for t in done_tasks)

    # Only send last N messages to summarizer to avoid context overflow
    # (if messages are huge, sending all would fail)
    max_msgs_for_summary = min(len(messages), 20)
    recent_messages = messages[-max_msgs_for_summary:]

    compact_body = {
        "model": MODEL,
        "max_tokens": 3000,
        "system": [{"type": "text", "text": "Summarize the conversation. Include: what was asked, what was done, what files were changed, and what's still pending. Be thorough but concise."}],
        "messages": recent_messages + [
            {"role": "user", "content": [{"type": "text", "text":
                f"Summarize everything. Include all important context needed to continue.\n{task_info}\n{done_info}\nEnd with:\nCONTINUE_TASK: <what to do next>"}]}
        ],
        "stream": False,
    }
    if MODEL not in NO_SAMPLING_PARAMS:
        compact_body["temperature"] = 1
        compact_body["top_k"] = 40
        compact_body["top_p"] = 0.95

    summary = ""
    continue_task = ""
    try:
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
            resp = client.post(_get_current_api_url(), headers=make_request_headers(), json=compact_body)
            if resp.status_code == 200:
                data = resp.json()
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        summary += block.get("text", "")
    except Exception as e:
        console.print(f"[error]Autocompact failed: {e}[/error]")
        return

    if not summary:
        console.print("[error]Empty summary - skipping compact[/error]")
        return

    # Extract CONTINUE_TASK
    ct_match = re.search(r'CONTINUE_TASK:\s*(.+?)$', summary, re.MULTILINE)
    if ct_match:
        continue_task = ct_match.group(1).strip()
        summary = summary[:ct_match.start()].strip()

    # Save to memory
    memory_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
    os.makedirs(memory_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_file = os.path.join(memory_dir, f"autocompact_{ts}.md")
    try:
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(f"# Autocompact - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(f"**Model:** {MODEL}\n**CWD:** {CWD}\n**Reason:** autocompact\n\n")
            f.write(f"## Summary\n\n{summary}\n")
            if pending_tasks:
                f.write(f"\n## Pending Tasks\n\n")
                for t in pending_tasks:
                    f.write(f"- #{t['id']} [{t['status']}] {t['text']}\n")
            if continue_task:
                f.write(f"\n## Next Action\n\n{continue_task}\n")
    except Exception as e:
        console.print(f"[error]Failed to save summary: {e}. Aborting compact.[/error]")
        return

    console.print(f"[info]Saved to {os.path.basename(md_file)}[/info]")

    # Clear and reload — only after summary is safely saved
    old_count = len(messages)
    messages.clear()

    reload_text = f"[Autocompact - previous conversation had {old_count} messages]\n\n{summary}"
    if pending_tasks:
        reload_text += "\n\nPending tasks:\n"
        reload_text += "\n".join(f"- #{t['id']} [{t['status']}] {t['text']}" for t in pending_tasks)

    messages.append({
        "role": "user",
        "content": [{"type": "text", "text": reload_text, "cache_control": {"type": "ephemeral"}}],
    })
    messages.append({
        "role": "assistant",
        "content": [{"type": "text", "text": "Context loaded. I know what we were working on. Continuing."}],
    })

    console.print(Panel(
        Text(f"Compacted {old_count} -> 2 messages. Context freed.", style="bold green"),
        border_style="green",
    ))

    # Auto-continue
    if continue_task or pending_tasks:
        next_action = continue_task or f"Continue task #{pending_tasks[0]['id']}: {pending_tasks[0]['text']}"
        console.print(f"[bold cyan]Auto-continuing: {next_action}[/bold cyan]\n")
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text":
                f"Continue where we left off. Next: {next_action}",
                "cache_control": {"type": "ephemeral"}}],
        })


_failed_models = set()  # models that failed in this session

def _get_fallback_model() -> Optional[str]:
    """Get next available model to try. Returns None if all exhausted."""
    global _failed_models
    _failed_models.add(MODEL)
    for m in AVAILABLE_MODELS:
        if m not in _failed_models:
            return m
    # All models tried — reset and give up
    _failed_models.clear()
    return None


def _smart_truncate(messages: list):
    """Truncate old tool results and long text to free context space without losing conversation flow."""
    truncated = 0
    # Only truncate older messages (keep last 6 intact)
    for msg in messages[:-6]:
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                # Truncate long tool results
                if block.get("type") == "tool_result" and isinstance(block.get("content"), str):
                    if len(block["content"]) > 500:
                        block["content"] = block["content"][:500] + "\n...(truncated)"
                        truncated += 1
                # Truncate long text blocks
                elif block.get("type") == "text" and len(block.get("text", "")) > 2000:
                    block["text"] = block["text"][:2000] + "\n...(truncated)"
                    truncated += 1
        elif isinstance(content, str) and len(content) > 500:
            msg["content"] = content[:500] + "\n...(truncated)"
            truncated += 1
    if truncated > 0:
        console.print(f"[dim](smart truncation: trimmed {truncated} old messages to free context)[/dim]")


def has_tool_use(content: list) -> bool:
    return any(b.get("type") == "tool_use" for b in content)


# ============================================================================
# Slash Commands
# ============================================================================

def _save_session(messages: list, name: str = None, auto: bool = False) -> Optional[str]:
    """Save current conversation to a session file."""
    session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
    os.makedirs(session_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if name:
        safe_name = re.sub(r'[^\w\-]', '_', name)[:40]
        filename = f"{safe_name}_{ts}.json"
    else:
        filename = f"session_{ts}.json"
    filepath = os.path.join(session_dir, filename)
    try:
        # Clean messages for JSON serialization
        clean = []
        for msg in messages:
            clean.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", []),
            })
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=1)
        if auto:
            console.print(f"[dim]Session auto-saved: {filename}[/dim]")
        return filepath
    except Exception as e:
        console.print(f"[error]Save failed: {e}[/error]")
        return None


def _load_session(filepath: str) -> Optional[list]:
    """Load a session from file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return None
    except Exception as e:
        console.print(f"[error]Load failed: {e}[/error]")
        return None


def handle_slash_command(cmd: str, messages: list) -> Optional[bool]:
    """Handle slash commands. Returns True if handled, None to quit, False if not a command."""
    global MODEL, CWD, plan_mode, _task_counter, _worktree_original_cwd, message_count

    parts = cmd.strip().split(None, 1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command in ("/quit", "/exit"):
        # Auto-save session on exit if there are messages
        if messages and len(messages) >= 2:
            _save_session(messages, auto=True)
        return None

    elif command in ("/save", "/s"):
        if not messages:
            console.print("[info]Nothing to save.[/info]")
            return True
        name = arg if arg else None
        path = _save_session(messages, name=name)
        if path:
            console.print(f"[info]Session saved: {os.path.basename(path)}[/info]")
        return True

    elif command in ("/resume", "/r"):
        session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")
        if not os.path.exists(session_dir):
            console.print("[info]No saved sessions.[/info]")
            return True
        files = sorted(glob_mod.glob(os.path.join(session_dir, "*.json")), key=os.path.getmtime, reverse=True)
        if not files:
            console.print("[info]No saved sessions.[/info]")
            return True
        if arg:
            # /resume <number> — load specific session
            try:
                idx = int(arg) - 1
                if 0 <= idx < len(files):
                    loaded = _load_session(files[idx])
                    if loaded:
                        messages.clear()
                        messages.extend(loaded)
                        console.print(f"[info]Resumed session ({len(loaded)} messages). Use /continue to keep going.[/info]")
                    else:
                        console.print("[error]Failed to load session.[/error]")
                else:
                    console.print("[error]Invalid number.[/error]")
            except ValueError:
                console.print("[error]Usage: /resume <number>[/error]")
        else:
            # List sessions
            console.print("[bold]Saved Sessions:[/bold]")
            for i, f in enumerate(files[:15], 1):
                name = os.path.basename(f).replace(".json", "")
                size = os.path.getsize(f)
                mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%m/%d %H:%M")
                # Try to read first user message for preview
                preview = ""
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                        for msg in data:
                            if msg.get("role") == "user":
                                content = msg.get("content", [])
                                if isinstance(content, list):
                                    for b in content:
                                        if b.get("type") == "text":
                                            preview = b["text"][:50]
                                            break
                                elif isinstance(content, str):
                                    preview = content[:50]
                                if preview:
                                    break
                except Exception:
                    pass
                console.print(f"  {i}. [bold]{name}[/bold] [dim]({mtime}, {size//1024}KB)[/dim]")
                if preview:
                    console.print(f"     [dim]{preview}{'...' if len(preview) >= 50 else ''}[/dim]")
            console.print("\n[info]/resume <number> to load | /continue to keep working[/info]")
        return True

    elif command in ("/continue", "/c"):
        # Build context from last messages
        context_parts = []
        # Find what AI was doing last
        for msg in reversed(messages[-6:]):
            if msg.get("role") == "assistant":
                for block in (msg.get("content") if isinstance(msg.get("content"), list) else []):
                    if block.get("type") == "text" and block.get("text"):
                        last_text = block["text"]
                        if len(last_text) > 200:
                            last_text = "..." + last_text[-200:]
                        context_parts.append(last_text)
                        break
                break

        # Check pending tasks
        pending = [t for t in _tasks if t["status"] in ("pending", "in_progress")]
        task_info = ""
        if pending:
            task_info = "\nPending tasks:\n" + "\n".join(f"- #{t['id']} [{t['status']}] {t['text']}" for t in pending)

        continue_msg = arg if arg else "Continue where you left off. Keep working."
        if context_parts:
            continue_msg += f"\n\nYour last response ended with:\n{context_parts[0]}"
        if task_info:
            continue_msg += task_info

        # Ensure alternating roles
        if messages and messages[-1].get("role") == "user":
            messages.append({"role": "assistant", "content": [{"type": "text", "text": "(continuing)"}]})

        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": continue_msg, "cache_control": {"type": "ephemeral"}}],
        })
        message_count += 1
        console.print("[dim]Continuing...[/dim]")
        return "do"  # Jump to agent loop

    elif command in ("/paste", "/v"):
        # Read clipboard and send as message
        clip_text = ""
        try:
            if platform.system() == "Windows":
                r = subprocess.run("powershell -command Get-Clipboard", shell=True,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
                clip_text = r.stdout.strip()
            else:
                try:
                    r = subprocess.run("xclip -selection clipboard -o", shell=True,
                                       capture_output=True, text=True, timeout=5)
                    clip_text = r.stdout.strip()
                except Exception:
                    r = subprocess.run("pbpaste", shell=True,
                                       capture_output=True, text=True, timeout=5)
                    clip_text = r.stdout.strip()
        except Exception as e:
            console.print(f"[error]Clipboard read failed: {e}[/error]")
            return True

        if not clip_text:
            console.print("[info]Clipboard is empty.[/info]")
            return True

        line_count = clip_text.count("\n") + 1
        char_count = len(clip_text)
        _paste_counter = getattr(handle_slash_command, '_paste_counter', 0) + 1
        handle_slash_command._paste_counter = _paste_counter

        console.print(f"[bold cyan]  [ Pasted text #{_paste_counter}  +{line_count} lines  {char_count} chars ][/bold cyan]")

        # Add optional prefix from arg
        if arg:
            full_msg = f"{arg}\n\n```\n{clip_text}\n```"
        else:
            full_msg = clip_text

        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": full_msg, "cache_control": {"type": "ephemeral"}}],
        })
        message_count += 1
        return "do"  # jump to agent loop

    elif command in ("/bg", "/ps"):
        if not arg:
            # List all background processes
            if not _bg_processes:
                console.print("[info]No background processes running.[/info]")
                return True
            bg_table = Table(title="Background Processes", border_style="yellow", show_header=True)
            bg_table.add_column("ID", style="bold yellow")
            bg_table.add_column("PID", style="bold")
            bg_table.add_column("Status", style="cyan")
            bg_table.add_column("Command", style="dim")
            for bg_id, proc in _bg_processes.items():
                alive = proc.poll() is None
                status = "[green]running[/green]" if alive else f"[red]exited ({proc.returncode})[/red]"
                # Try to get command from proc.args
                cmd_str = ""
                if hasattr(proc, 'args'):
                    cmd_str = str(proc.args)[:60]
                bg_table.add_row(bg_id, str(proc.pid), status, cmd_str)
            console.print(bg_table)
            console.print(f"\n[info]/bg kill <id|pid|all> to stop  |  /bg logs <id> to see output[/info]")
            # Cleanup dead processes
            _cleanup_dead_bg_processes()
            return True

        parts_bg = arg.split(None, 1)
        subcmd = parts_bg[0].lower()
        bg_arg = parts_bg[1] if len(parts_bg) > 1 else ""

        if subcmd == "kill":
            if bg_arg == "all":
                with _bg_processes_lock:
                    for bg_id, proc in list(_bg_processes.items()):
                        if proc.poll() is None:
                            proc.terminate()
                            console.print(f"[info]Terminated {bg_id} (PID {proc.pid})[/info]")
                    _bg_processes.clear()
                return True
            # Try by ID or PID
            found = False
            for bg_id, proc in list(_bg_processes.items()):
                if bg_arg == bg_id or bg_arg == str(proc.pid):
                    if proc.poll() is None:
                        proc.terminate()
                        console.print(f"[info]Terminated {bg_id} (PID {proc.pid})[/info]")
                    else:
                        console.print(f"[info]{bg_id} already exited[/info]")
                    del _bg_processes[bg_id]
                    found = True
                    break
            if not found:
                console.print(f"[error]Process not found: {bg_arg}[/error]")
            return True

        elif subcmd == "logs":
            for bg_id, proc in _bg_processes.items():
                if bg_arg == bg_id or bg_arg == str(proc.pid):
                    output = ""
                    try:
                        if proc.stdout and platform.system() == "Windows":
                            import msvcrt, ctypes
                            handle = msvcrt.get_osfhandle(proc.stdout.fileno())
                            avail = ctypes.c_ulong(0)
                            ctypes.windll.kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(avail), None)
                            if avail.value > 0:
                                output = proc.stdout.read(min(avail.value, 8192)).decode("utf-8", errors="replace")
                    except Exception:
                        output = "(could not read output)"
                    if output:
                        console.print(f"[bold]{bg_id} output:[/bold]")
                        console.print(Text(output[:3000], style="dim"))
                    else:
                        console.print(f"[dim]{bg_id}: no new output[/dim]")
                    return True
            console.print(f"[error]Process not found: {bg_arg}[/error]")
            return True

        else:
            console.print("[info]Usage: /bg [kill <id|all>] [logs <id>][/info]")
            return True

    elif command == "/team":
        if not arg:
            console.print("[info]Usage: /team <task> [--roles role1,role2,...] [--rounds 25] [--isolation thread|process][/info]")
            console.print(f"[info]Available roles: {', '.join(_TEAM_ROLES.keys())} (+ custom)[/info]")
            console.print("[info]Auto-detect: roles are picked based on task (code/research/writing)[/info]")
            console.print("[info]  Code task    -> planner, frontend, backend[/info]")
            console.print("[info]  Research     -> planner, researcher, analyst[/info]")
            console.print("[info]  Writing      -> planner, writer, editor[/info]")
            console.print("[info]  General      -> planner, researcher, writer[/info]")
            console.print("[info]/team status — show agent statuses + task board[/info]")
            console.print("[info]/team graph  — show task dependency graph (Mermaid)[/info]")
            console.print("[info]/team stop   — stop running team[/info]")
            return True

        if arg == "stop":
            global _team_running
            _team_manager.stop()
            _team_running = False
            console.print("[info]Stopping team...[/info]")
            return True

        if arg == "status":
            if not _team_manager.agents:
                console.print("[info]No team is running. Use /team <task> to start one.[/info]")
                return True
            console.print(_team_manager.render_status_table())
            with _team_manager.channel_lock:
                console.print(f"[dim]Channel: {len(_team_manager.channel_history)} messages[/dim]")
            board = _team_manager.task_board_list()
            if "task-" in board:
                console.print(f"\n[bold]Task Board:[/bold]")
                console.print(board)
            return True

        if arg == "graph":
            graph = _team_manager.render_task_graph()
            if "task-" in graph:
                console.print(Markdown(graph))
                # Also save to file
                graph_path = os.path.join(CWD, ".tooncode-team-graph.md")
                try:
                    with open(graph_path, "w", encoding="utf-8") as f:
                        f.write(f"# Team Task Graph\n\n{graph}\n")
                    console.print(f"[dim]Saved to {graph_path}[/dim]")
                except Exception:
                    pass
            else:
                console.print("[info]No tasks on the board yet.[/info]")
            return True

        # Parse flags: --roles, --isolation, --rounds
        roles = None
        isolation = "thread"
        max_rounds = 25
        task_text = arg
        if "--rounds" in task_text:
            parts_rnd = task_text.split("--rounds")
            task_text = parts_rnd[0].strip()
            rnd_parts = parts_rnd[1].strip().split() if len(parts_rnd) > 1 else []
            if rnd_parts and rnd_parts[0].isdigit():
                max_rounds = max(5, min(50, int(rnd_parts[0])))  # clamp 5-50
                task_text = task_text + " " + " ".join(rnd_parts[1:])
                task_text = task_text.strip()
        if "--isolation" in task_text:
            parts_iso = task_text.split("--isolation")
            task_text = parts_iso[0].strip()
            iso_parts = parts_iso[1].strip().split() if len(parts_iso) > 1 else []
            if iso_parts and iso_parts[0] in ("thread", "process"):
                isolation = iso_parts[0]
                task_text = task_text + " " + " ".join(iso_parts[1:])
                task_text = task_text.strip()
        if "--roles" in task_text:
            parts_r = task_text.split("--roles")
            task_text = parts_r[0].strip()
            role_parts = parts_r[1].strip().split() if len(parts_r) > 1 else []
            role_str = role_parts[0] if role_parts else ""
            if role_str:
                roles = [r.strip() for r in role_str.split(",") if r.strip()]

        if isolation == "process":
            console.print("[bold cyan]Isolation mode: process[/bold cyan]")
        if max_rounds != 25:
            console.print(f"[dim]Max rounds per agent: {max_rounds}[/dim]")
        summary = run_team(task_text, roles, isolation=isolation, max_rounds=max_rounds)
        if summary:
            messages.append({
                "role": "user",
                "content": [{"type": "text", "text":
                    f"[Team work completed]\nTask: {task_text}\n\nTeam conversation:\n{summary[:3000]}",
                    "cache_control": {"type": "ephemeral"}}],
            })
            messages.append({
                "role": "assistant",
                "content": [{"type": "text", "text": "Team work complete. The agents have finished their tasks."}],
            })
        return True

    elif command in ("/send", "/chat"):
        # Send message to other ToonCode instances via shared channel
        channel_dir = os.path.join(os.path.expanduser("~"), ".tooncode", "channels")
        os.makedirs(channel_dir, exist_ok=True)

        if not arg:
            # Read messages
            inbox = sorted(glob_mod.glob(os.path.join(channel_dir, "*.json")), key=os.path.getmtime, reverse=True)
            if not inbox:
                console.print("[info]No messages. Use /send <message> to send.[/info]")
                return True
            console.print("[bold cyan]Channel Messages:[/bold cyan]")
            for mf in inbox[:10]:
                try:
                    with open(mf, "r", encoding="utf-8") as f:
                        msg = json.load(f)
                    age = time.time() - msg.get("time", 0)
                    age_str = f"{int(age)}s ago" if age < 60 else f"{int(age/60)}m ago" if age < 3600 else f"{int(age/3600)}h ago"
                    sender = msg.get("from", "?")
                    text = msg.get("text", "")
                    console.print(f"  [bold cyan]{sender}[/bold cyan] [dim]({age_str})[/dim]: {text[:100]}")
                except Exception:
                    pass
            console.print(f"\n[info]/send <msg> to reply | /send clear to delete all[/info]")
            return True

        if arg == "clear":
            for f in glob_mod.glob(os.path.join(channel_dir, "*.json")):
                os.remove(f)
            console.print("[info]Channel cleared.[/info]")
            return True

        # Send message
        instance_id = f"tooncode-{os.getpid()}"
        msg_data = {
            "from": instance_id,
            "text": arg,
            "time": time.time(),
            "cwd": CWD,
            "model": MODEL,
        }
        msg_file = os.path.join(channel_dir, f"{int(time.time()*1000)}_{os.getpid()}.json")
        with open(msg_file, "w", encoding="utf-8") as f:
            json.dump(msg_data, f, ensure_ascii=False)
        console.print(f"[bold cyan]Sent to channel:[/bold cyan] {arg[:100]}")

        # Also inject into conversation so AI knows about it
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text":
                f"[Channel message sent to other ToonCode instances]: {arg}",
                "cache_control": {"type": "ephemeral"}}],
        })
        messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": "Message sent to channel."}],
        })
        return True

    elif command == "/index":
        console.print("[info]Indexing codebase...[/info]")
        t0 = time.time()
        result = _build_codebase_index()
        elapsed = time.time() - t0
        n_lines = result.count("\n") + 1
        console.print(f"[info]Structure index: {elapsed:.1f}s ({n_lines} lines)[/info]")
        console.print(Panel(result, title="Codebase Index", border_style="cyan", expand=False))
        # Also build semantic index if ChromaDB available
        if _chroma_available:
            console.print("[info]Building semantic search index...[/info]")
            t1 = time.time()
            sem_result = _index_codebase_semantic()
            console.print(f"[info]Semantic index: {time.time()-t1:.1f}s — {sem_result}[/info]")
        else:
            console.print("[dim]Semantic search not available (pip install chromadb)[/dim]")
        return True

    elif command == "/semantic":
        if not _chroma_available:
            console.print("[error]ChromaDB not installed. Run: pip install chromadb[/error]")
            return True
        if not arg:
            console.print("[info]Usage: /semantic <query>[/info]")
            console.print("[info]Examples:[/info]")
            console.print("[dim]  /semantic user authentication logic[/dim]")
            console.print("[dim]  /semantic database connection setup[/dim]")
            console.print("[dim]  /semantic error handling[/dim]")
            return True
        result = exec_semantic_search({"query": arg, "n_results": 5})
        console.print(Panel(result, title=f"Semantic Search: {arg}", border_style="cyan"))
        return True

    elif command == "/clear":
        messages.clear()
        console.print("[info]Conversation cleared.[/info]")
        return True

    elif command == "/help":
        help_table = Table(title="ToonCode Commands", border_style="cyan", show_header=True)
        help_table.add_column("Command", style="bold cyan")
        help_table.add_column("Description", style="white")
        help_table.add_row("/continue, /c", "Continue where AI left off (add msg: /c fix the bug)")
        help_table.add_row("/paste, /v [msg]", "Read clipboard and send (or just paste directly)")
        help_table.add_row("/save, /s [name]", "Save current session (auto-saves on /quit)")
        help_table.add_row("/resume, /r [num]", "List saved sessions or resume one")
        help_table.add_row("/model [name]", "Switch model or list available models")
        help_table.add_row("/cd <path>", "Change working directory")
        help_table.add_row("/boss <task>", "Send to Boss AI to create task plan")
        help_table.add_row("/plan", "Toggle Plan Mode (AI plans only, no file changes)")
        help_table.add_row("/tasks", "Show task list with progress")
        help_table.add_row("/do", "Execute pending tasks from plan")
        help_table.add_row("/task-rm <id|all>", "Remove task or clear all")
        help_table.add_row("/compact", "Summarize, save to memory/, compress context")
        help_table.add_row("/memory", "List saved memories (/memory 1 to read, /memory load 1)")
        help_table.add_row("/cost", "Show token usage stats")
        help_table.add_row("/commit [msg]", "Git add all & commit")
        help_table.add_row("/diff", "Git diff")
        help_table.add_row("/status", "Git status")
        help_table.add_row("/worktree <name>", "Create git worktree & switch to it")
        help_table.add_row("/worktree list", "List existing git worktrees")
        help_table.add_row("/worktree done", "Merge back & remove worktree")
        help_table.add_row("/undo", "Undo last file edit")
        help_table.add_row("/bg, /ps", "List background processes (kill/logs)")
        help_table.add_row("/team <task>", "Start multi-agent team (planner+frontend+backend+...)")
        help_table.add_row("/send <msg>", "Send message to other ToonCode windows")
        help_table.add_row("/send", "Read messages from other windows")

        help_table.add_row("/index", "Rebuild codebase index (structure + semantic)")
        help_table.add_row("/semantic <query>", "Semantic code search (AI-powered, find by meaning)")
        help_table.add_row("/init", "Create TOONCODE.md project memory")
        help_table.add_row("/config", "Show/edit config (~/.tooncode/config.json)")
        help_table.add_row("/clear", "Clear conversation history")
        help_table.add_row("/skills", "List loaded skills from SKILLS.md")
        help_table.add_row("!command", "Run shell command directly (e.g. !git log)")
        help_table.add_row("/help", "Show this help message")
        help_table.add_row("/update", "Check & install latest version")
        help_table.add_row("/quit, /exit", "Exit ToonCode")
        console.print(help_table)
        return True

    elif command == "/model":
        if arg:
            if arg in AVAILABLE_MODELS:
                MODEL = arg
                console.print(f"[info]Model switched to [model.name]{MODEL}[/model.name][/info]")
            else:
                console.print(f"[error]Unknown model: {arg}[/error]")
                console.print(f"[info]Available: {', '.join(AVAILABLE_MODELS)}[/info]")
        else:
            console.print("[bold]Available models:[/bold]")
            for i, m in enumerate(AVAILABLE_MODELS, 1):
                marker = " [bold green]<-- current[/bold green]" if m == MODEL else ""
                console.print(f"  {i}. [model.name]{m}[/model.name]{marker}")
            console.print(f"\n[info]Use /model <name> to switch[/info]")
        return True

    elif command == "/compact":
        if len(messages) < 2:
            console.print("[info]Nothing to compact.[/info]")
            return True
        summary_msgs = [
            {"role": "user", "content": [{"type": "text", "text":
                "Summarize the entire conversation so far in a concise bullet list. "
                "Include: what was discussed, what files were changed, what decisions were made, "
                "and any important context. Keep it under 500 words. Respond ONLY with the summary."
            }]}
        ]
        compact_body = {
            "model": MODEL,
            "max_tokens": 2000,
            "system": [{"type": "text", "text": "You are a conversation summarizer. Summarize concisely."}],
            "messages": messages + summary_msgs,
            "stream": False,
        }
        if MODEL not in NO_SAMPLING_PARAMS:
            compact_body["temperature"] = 1
            compact_body["top_k"] = 40
            compact_body["top_p"] = 0.95
        console.print("[info]Compacting conversation...[/info]")
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                resp = client.post(_get_current_api_url(), headers=make_request_headers(), json=compact_body)
                if resp.status_code == 200:
                    data = resp.json()
                    summary = ""
                    for block in data.get("content", []):
                        if block.get("type") == "text":
                            summary += block.get("text", "")
                    if summary:
                        # Save to memory/.md
                        memory_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
                        os.makedirs(memory_dir, exist_ok=True)
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        md_file = os.path.join(memory_dir, f"chat_{ts}.md")
                        with open(md_file, "w", encoding="utf-8") as f:
                            f.write(f"# Chat Summary - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                            f.write(f"**Model:** {MODEL}\n")
                            f.write(f"**CWD:** {CWD}\n")
                            f.write(f"**Messages:** {len(messages)}\n\n")
                            f.write("## Summary\n\n")
                            f.write(summary)
                            f.write("\n")

                        old_count = len(messages)
                        messages.clear()
                        messages.append({
                            "role": "user",
                            "content": [{"type": "text", "text": f"[Conversation Summary]\n{summary}"}],
                        })
                        messages.append({
                            "role": "assistant",
                            "content": [{"type": "text", "text": "Understood. I have the context from our previous conversation. How can I help?"}],
                        })
                        console.print(f"[info]Compacted {old_count} messages -> 2. Saved to {md_file}[/info]")
                        console.print()
                        console.print(Markdown(summary))
                    else:
                        console.print("[error]Failed to generate summary.[/error]")
                else:
                    console.print(f"[error]Compact failed: HTTP {resp.status_code}[/error]")
        except Exception as e:
            console.print(f"[error]Compact error: {e}[/error]")
        return True

    elif command == "/memory":
        memory_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
        if not os.path.exists(memory_dir):
            console.print("[info]No memories yet. Use /compact to save.[/info]")
            return True
        files = sorted(glob_mod.glob(os.path.join(memory_dir, "*.md")), reverse=True)
        if not files:
            console.print("[info]No memories yet.[/info]")
            return True
        if arg:
            # /memory <number> - read specific memory
            try:
                idx = int(arg) - 1
                if 0 <= idx < len(files):
                    with open(files[idx], "r", encoding="utf-8") as f:
                        content = f.read()
                    console.print(Markdown(content))
                else:
                    console.print("[error]Invalid number.[/error]")
            except ValueError:
                # /memory load <number> - load into conversation
                if arg.startswith("load "):
                    try:
                        idx = int(arg[5:]) - 1
                        if 0 <= idx < len(files):
                            with open(files[idx], "r", encoding="utf-8") as f:
                                content = f.read()
                            messages.append({
                                "role": "user",
                                "content": [{"type": "text", "text": f"[Loaded Memory]\n{content}"}],
                            })
                            messages.append({
                                "role": "assistant",
                                "content": [{"type": "text", "text": "Got it, I've loaded this context. How can I help?"}],
                            })
                            console.print(f"[info]Loaded memory into conversation.[/info]")
                    except (ValueError, IndexError):
                        console.print("[error]Usage: /memory load <number>[/error]")
        else:
            # List all memories
            console.print("[bold]Saved Memories:[/bold]")
            for i, f in enumerate(files[:20], 1):
                name = os.path.basename(f)
                size = os.path.getsize(f)
                console.print(f"  {i}. {name} ({size} bytes)")
            console.print("\n[info]Use /memory <number> to read, /memory load <number> to load into chat[/info]")
        return True

    elif command == "/cost":
        ctx_max = CONTEXT_WINDOWS.get(MODEL, 200_000)
        ctx_pct = (last_input_tokens / ctx_max * 100) if last_input_tokens > 0 else 0
        cost_table = Table(title="Token Usage", border_style="cyan", show_header=False)
        cost_table.add_column("Key", style="bold")
        cost_table.add_column("Value", style="white")
        cost_table.add_row("Model", MODEL)
        cost_table.add_row("Input tokens (total)", f"{total_input_tokens:,}")
        cost_table.add_row("Output tokens (total)", f"{total_output_tokens:,}")
        cost_table.add_row("Context used", f"{last_input_tokens:,} / {ctx_max:,} ({ctx_pct:.1f}%)")
        cost_table.add_row("Messages", str(message_count))
        console.print(cost_table)
        return True

    elif command == "/skills":
        _load_skills()
        if not _skills:
            console.print("[info]No skills loaded. Create SKILLS.md in your project or ~/.tooncode/[/info]")
            console.print("[info]Example SKILLS.md:[/info]")
            console.print(Markdown("""```markdown
## /review - Review code for bugs and security issues
Read all files in the project and review for:
- Security vulnerabilities
- Logic errors
- Performance issues
Give a summary with severity ratings.

## /test - Generate tests for a file
Write comprehensive tests for: {{input}}
Use pytest. Cover edge cases.

## /doc - Generate documentation
Read {{input}} and generate clear documentation with examples.
```"""))
            return True
        skill_table = Table(title="Loaded Skills", border_style="magenta", show_header=True)
        skill_table.add_column("Category", style="dim cyan")
        skill_table.add_column("Command", style="bold magenta")
        skill_table.add_column("Description")
        # Group by category
        by_cat = {}
        for name, skill in _skills.items():
            cat = skill.get("category", "")
            by_cat.setdefault(cat, []).append((name, skill))
        for cat in sorted(by_cat.keys()):
            for name, skill in sorted(by_cat[cat]):
                skill_table.add_row(cat, f"/{name}", skill["description"])
        console.print(skill_table)
        console.print("[info]Use /<skill> [args] to run. {{input}} = your args.[/info]")
        return True

    elif command == "/boss":
        if not arg:
            console.print("[error]Usage: /boss <task description>[/error]")
            return True
        console.print("[bold magenta]Step 1: Expanding task to English...[/bold magenta]")

        # Step 1: Use tooncode's model to translate + expand the task to clear English
        expand_body = {
            "model": MODEL,
            "max_tokens": 1000,
            "system": [{"type": "text", "text": "You are a translator and requirements analyst. Your job: take the user's task (any language) and output a clear, detailed English specification. Do NOT code. Do NOT plan steps. Just describe WHAT to build in detail."}],
            "messages": [{"role": "user", "content": [{"type": "text", "text":
                f"Translate and expand this task into a detailed English specification:\n\n{arg}\n\n"
                f"Output ONLY the English specification. Be specific about: pages, features, tech stack, design style, language/locale."}]}],
            "stream": False,
        }
        if MODEL not in NO_SAMPLING_PARAMS:
            expand_body["temperature"] = 1
            expand_body["top_k"] = 40
            expand_body["top_p"] = 0.95

        expanded_task = arg  # fallback to original
        try:
            with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                resp = client.post(_get_current_api_url(), headers=make_request_headers(), json=expand_body)
                if resp.status_code == 200:
                    data = resp.json()
                    for block in data.get("content", []):
                        if block.get("type") == "text":
                            expanded_task = block.get("text", "").strip()
                            break
        except Exception as e:
            console.print(f"[yellow]Expand failed ({e}), using original task[/yellow]")

        console.print(f"[dim]{expanded_task[:200]}{'...' if len(expanded_task) > 200 else ''}[/dim]")
        console.print("[bold magenta]Step 2: Sending to Boss AI (boss)...[/bold magenta]")

        boss_prompt = f"""You are a senior software architect. Create a detailed implementation plan.

TASK SPECIFICATION:
{expanded_task}

Project directory: {CWD}

RULES:
- FOLLOW THE SPECIFICATION EXACTLY. Do NOT invent features not mentioned.
- The folder name is irrelevant - only the specification matters.
- Do NOT ask questions. Make reasonable assumptions.
- Do NOT explain. Just output the plan.
- If the directory is empty, plan from scratch.
- Break into 5-15 concrete, actionable steps.
- Each step must be specific and actionable.

OUTPUT FORMAT: A JSON array of strings. Nothing else. No markdown fences. No explanation before or after.
EXAMPLE OUTPUT:
["สร้างโครงสร้างโปรเจค HTML/CSS/JS", "สร้าง index.html หน้าแรก", "เพิ่ม style.css ธีมสวยหรู"]

OUTPUT THE JSON ARRAY NOW:"""

        try:
            output = ""
            # Try Claude CLI first, fallback to own model
            claude_cmd = _find_claude_cmd()
            if claude_cmd:
                console.print("[dim]Using Boss AI CLI...[/dim]")
                try:
                    result = subprocess.run(
                        [claude_cmd, "--print", "--dangerously-skip-permissions"],
                        input=boss_prompt,
                        capture_output=True, text=True, cwd=CWD, timeout=180,
                        encoding="utf-8", errors="replace",
                    )
                    output = result.stdout.strip()
                except (subprocess.TimeoutExpired, Exception) as e:
                    console.print(f"[yellow]Claude CLI failed ({e}), using {MODEL}...[/yellow]")

            if not output:
                # Fallback: use own model
                console.print(f"[dim]Using {MODEL} to plan...[/dim]")
                body = {
                    "model": MODEL,
                    "max_tokens": 4000,
                    "system": [{"type": "text", "text": "You are a senior software architect. Output ONLY a JSON array of task strings. No markdown, no explanation."}],
                    "messages": [{"role": "user", "content": [{"type": "text", "text": boss_prompt}]}],
                    "stream": False,
                }
                if MODEL not in NO_SAMPLING_PARAMS:
                    body["temperature"] = 1
                    body["top_k"] = 40
                    body["top_p"] = 0.95
                with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
                    resp = client.post(_get_current_api_url(), headers=make_request_headers(), json=body)
                    if resp.status_code == 200:
                        data = resp.json()
                        for block in data.get("content", []):
                            if block.get("type") == "text":
                                output += block.get("text", "")

            # Parse tasks - try JSON first, then fallback to line-by-line
            tasks_parsed = []

            # Try 1: find JSON array
            match = re.search(r'\[[\s\S]*\]', output)
            if match:
                try:
                    tasks_parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

            # Try 2: JSON in markdown code block
            if not tasks_parsed:
                match2 = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', output)
                if match2:
                    try:
                        tasks_parsed = json.loads(match2.group(1))
                    except json.JSONDecodeError:
                        pass

            # Try 3: fallback - parse numbered/bulleted lines as tasks
            if not tasks_parsed:
                for line in output.split("\n"):
                    line = line.strip()
                    # Match: "1. ...", "- ...", "* ...", "1) ..."
                    m = re.match(r'^(?:\d+[\.\)]\s*|-\s*|\*\s*)(.+)', line)
                    if m:
                        task_text = m.group(1).strip().strip('"').strip("'")
                        if len(task_text) > 5:
                            tasks_parsed.append(task_text)

            if tasks_parsed and isinstance(tasks_parsed, list):
                global _task_counter
                added = 0
                for task_text in tasks_parsed:
                    if isinstance(task_text, str) and task_text.strip():
                        _task_counter += 1
                        _tasks.append({"id": _task_counter, "text": task_text.strip(), "status": "pending"})
                        added += 1

                if added > 0:
                    console.print(f"\n[bold magenta]Boss created {added} tasks:[/bold magenta]")
                    for t in _tasks[-added:]:
                        console.print(f"  [dim][ ][/dim] #{t['id']} {t['text']}")
                    console.print(f"\n[info]/tasks = review | /do = execute | /task-rm <id> = remove[/info]")

                    task_list_str = "\n".join(f"- Task #{t['id']}: {t['text']}" for t in _tasks)
                    messages.append({
                        "role": "user",
                        "content": [{"type": "text", "text":
                            f"[Boss Plan from Boss AI]\nTask: {arg}\n\nTasks:\n{task_list_str}\n\n"
                            f"These tasks are loaded. Wait for /do command to execute them.",
                            "cache_control": {"type": "ephemeral"}}],
                    })
                    messages.append({
                        "role": "assistant",
                        "content": [{"type": "text", "text":
                            f"Boss created {added} tasks. Use /do to start or /tasks to review."}],
                    })
                else:
                    console.print(f"[error]Could not parse tasks from response.[/error]")
                    console.print(f"[dim]{output[:500]}[/dim]")
            else:
                console.print(f"[error]Could not parse tasks from response.[/error]")
                console.print(f"[dim]{output[:500]}[/dim]")
        except subprocess.TimeoutExpired:
            console.print("[error]Boss timed out (180s)[/error]")
        except FileNotFoundError:
            console.print("[error]'claude' CLI not found.[/error]")
        except Exception as e:
            console.print(f"[error]Boss error: {e}[/error]")
        return True

    elif command == "/task-rm":
        if not arg:
            console.print("[info]Usage: /task-rm <id> or /task-rm all[/info]")
            return True
        if arg == "all":
            _tasks.clear()
            _task_counter = 0
            console.print("[info]All tasks cleared.[/info]")
        else:
            try:
                tid = int(arg)
                _tasks[:] = [t for t in _tasks if t["id"] != tid]
                console.print(f"[info]Removed task #{tid}[/info]")
            except ValueError:
                console.print("[error]Usage: /task-rm <id>[/error]")
        return True

    elif command == "/plan":
        plan_mode = not plan_mode
        if plan_mode:
            console.print("[bold cyan]Plan Mode ON[/bold cyan] - AI จะวางแผน + สร้าง tasks เท่านั้น ไม่แก้ไฟล์")
        else:
            console.print("[bold green]Plan Mode OFF[/bold green] - AI กลับมาทำงานปกติ")
        return True

    elif command == "/tasks":
        if not _tasks:
            console.print("[info]No tasks. AI will create tasks automatically in plan mode.[/info]")
            return True
        icons = {"pending": "[dim][ ][/dim]", "in_progress": "[cyan][~][/cyan]", "done": "[green][x][/green]"}
        task_table = Table(title="Tasks", border_style="cyan", show_header=True)
        task_table.add_column("#", style="bold", width=4)
        task_table.add_column("Status", width=12)
        task_table.add_column("Task")
        for t in _tasks:
            icon = icons.get(t["status"], "?")
            status_style = {"pending": "dim", "in_progress": "cyan", "done": "green"}.get(t["status"], "")
            task_table.add_row(str(t["id"]), f"{icon} {t['status']}", t["text"])
        done = sum(1 for t in _tasks if t["status"] == "done")
        console.print(task_table)
        console.print(f"[info]  Progress: {done}/{len(_tasks)} done[/info]")
        return True

    elif command == "/do":
        # /do - execute all pending tasks one by one
        pending = [t for t in _tasks if t["status"] == "pending"]
        if not pending:
            console.print("[info]No pending tasks. Use /plan or /boss first.[/info]")
            return True
        console.print(f"[bold cyan]Executing {len(pending)} tasks...[/bold cyan]")
        # Send first pending task - the never-stop loop will pick up the rest
        t = pending[0]
        t["status"] = "in_progress"
        console.print(f"\n[bold cyan]> Task #{t['id']}: {t['text']}[/bold cyan]")
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text":
                f"Execute this task NOW (task #{t['id']}): {t['text']}\n"
                f"When done, call task_update with id={t['id']} and status='done'. "
                f"There are {len(pending)} total tasks to complete.",
                "cache_control": {"type": "ephemeral"}}],
        })
        return "do"  # Special: tell main loop to run AI without waiting for input

    elif command == "/commit":
        msg = arg if arg else "auto commit by tooncode"
        result = subprocess.run(
            f'git add -A && git commit -m "{msg}"',
            shell=True, capture_output=True, text=True, cwd=CWD,
            encoding="utf-8", errors="replace",
        )
        output = (result.stdout + result.stderr).strip()
        console.print(f"[info]{output}[/info]" if result.returncode == 0 else f"[error]{output}[/error]")
        return True

    elif command == "/diff":
        result = subprocess.run("git diff", shell=True, capture_output=True, text=True, cwd=CWD, encoding="utf-8", errors="replace")
        output = result.stdout.strip() or "(no changes)"
        if len(output) > 3000:
            output = output[:3000] + "\n... (truncated)"
        console.print(Syntax(output, "diff", theme="monokai"))
        return True

    elif command == "/status":
        result = subprocess.run("git status -sb", shell=True, capture_output=True, text=True, cwd=CWD, encoding="utf-8", errors="replace")
        console.print(f"[info]{result.stdout.strip()}[/info]")
        return True

    elif command == "/worktree":
        if not arg:
            console.print("[error]Usage: /worktree <name> | /worktree list | /worktree done[/error]")
            return True

        if arg == "list":
            result = subprocess.run(
                "git worktree list", shell=True, capture_output=True, text=True,
                cwd=CWD, encoding="utf-8", errors="replace",
            )
            output = result.stdout.strip() or "(no worktrees)"
            console.print(f"[info]{output}[/info]")
            return True

        if arg == "done":
            if not _worktree_original_cwd:
                console.print("[error]Not currently in a worktree session.[/error]")
                return True

            # Check for uncommitted changes
            status_result = subprocess.run(
                "git status --porcelain", shell=True, capture_output=True, text=True,
                cwd=CWD, encoding="utf-8", errors="replace",
            )
            if status_result.stdout.strip():
                console.print("[warn]Uncommitted changes detected. Committing before merge...[/warn]")
                subprocess.run(
                    'git add -A && git commit -m "worktree: auto-commit before merge"',
                    shell=True, capture_output=True, text=True,
                    cwd=CWD, encoding="utf-8", errors="replace",
                )

            # Get current branch name to merge from
            branch_result = subprocess.run(
                "git rev-parse --abbrev-ref HEAD", shell=True, capture_output=True, text=True,
                cwd=CWD, encoding="utf-8", errors="replace",
            )
            worktree_branch = branch_result.stdout.strip()
            worktree_path = CWD

            # Switch back to original directory
            CWD = _worktree_original_cwd
            _worktree_original_cwd = None
            os.chdir(CWD)

            # Merge the worktree branch
            if worktree_branch:
                merge_result = subprocess.run(
                    f"git merge {worktree_branch}", shell=True, capture_output=True, text=True,
                    cwd=CWD, encoding="utf-8", errors="replace",
                )
                merge_output = (merge_result.stdout + merge_result.stderr).strip()
                if merge_result.returncode == 0:
                    console.print(f"[info]Merged branch '{worktree_branch}' successfully.[/info]")
                else:
                    console.print(f"[error]Merge failed: {merge_output}[/error]")
                    # Abort failed merge to keep clean state
                    subprocess.run("git merge --abort", shell=True, capture_output=True, cwd=CWD)
                    console.print(f"[info]Merge aborted. Branch '{worktree_branch}' still exists — merge manually with: git merge {worktree_branch}[/info]")

            # Remove the worktree
            remove_result = subprocess.run(
                f"git worktree remove {worktree_path}", shell=True, capture_output=True, text=True,
                cwd=CWD, encoding="utf-8", errors="replace",
            )
            if remove_result.returncode == 0:
                console.print(f"[info]Removed worktree at {worktree_path}[/info]")
            else:
                err = (remove_result.stdout + remove_result.stderr).strip()
                console.print(f"[error]Failed to remove worktree: {err}[/error]")

            console.print(f"[info]Back in original directory: {CWD}[/info]")
            return True

        # /worktree <name> — create a new worktree
        name = arg.strip()
        parent_dir = os.path.dirname(CWD)
        worktree_path = os.path.join(parent_dir, f"{name}-worktree")

        result = subprocess.run(
            f"git worktree add {worktree_path} -b {name}",
            shell=True, capture_output=True, text=True,
            cwd=CWD, encoding="utf-8", errors="replace",
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            console.print(f"[error]{output}[/error]")
            return True

        _worktree_original_cwd = CWD
        CWD = worktree_path
        os.chdir(CWD)
        console.print(f"[info]{output}[/info]")
        console.print(f"[info]Now working in isolated branch '{name}' at {worktree_path}[/info]")
        console.print("[info]Use /worktree done to merge back and clean up.[/info]")
        return True

    elif command == "/undo":
        with _edit_history_lock:
            if not _edit_history:
                console.print("[info]Nothing to undo.[/info]")
                return True
            last = _edit_history.pop()
        try:
            with open(last["filePath"], "w", encoding="utf-8", newline="\n") as f:
                f.write(last["content"])
            console.print(f"[info]Undid edit: {last['filePath']}[/info]")
        except Exception as e:
            console.print(f"[error]Undo failed: {e}[/error]")
        return True

    elif command == "/init":
        force = arg.strip() == "force"
        md_path = os.path.join(CWD, "TOONCODE.md")

        if os.path.exists(md_path) and not force:
            console.print(f"[info]TOONCODE.md already exists[/info]")
            console.print(f"[dim]Use /init force to regenerate with deep analysis[/dim]")
            return True

        console.print("[bold cyan]Starting deep project analysis...[/bold cyan]")
        result = _advanced_init()
        console.print(f"\n[bold green]{result}[/bold green]")
        return True

    elif command == "/update":
        console.print("[dim]Checking for updates from npm...[/dim]")
        try:
            r = subprocess.run(
                "npm view @votadev/tooncode version",
                shell=True, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=15
            )
            latest = r.stdout.strip()

            if not latest or r.returncode != 0:
                console.print("[yellow]Cannot connect to npm registry. Try again later.[/yellow]")
                return True

            current = VERSION
            if latest == current:
                console.print(f"[green]Already up to date (v{current})[/green]")
                return True

            console.print(f"[bold cyan]Update: v{current} -> v{latest}[/bold cyan]")
            console.print("[dim]Installing... (10-30 seconds)[/dim]")

            # Clean up old venv inside npm package to prevent EPERM on Windows
            try:
                npm_prefix = subprocess.run("npm prefix -g", shell=True, capture_output=True,
                                            text=True, encoding="utf-8", errors="replace", timeout=10)
                old_venv = os.path.join(npm_prefix.stdout.strip(), "node_modules", "@votadev", "tooncode", ".venv")
                if os.path.isdir(old_venv):
                    import shutil
                    shutil.rmtree(old_venv, ignore_errors=True)
            except Exception:
                pass

            # Real-time output instead of capture_output (no hang)
            process = subprocess.Popen(
                "npm install -g @votadev/tooncode@latest",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    console.print(f"[dim]{line}[/dim]")

            process.wait()

            if process.returncode == 0:
                console.print(f"\n[bold green]Updated to v{latest}![/bold green]")
                console.print("[bold yellow]Please restart ToonCode manually[/bold yellow]")
                console.print("[dim]Type /quit then run: tooncode[/dim]")
            else:
                console.print(f"[error]Install failed (code {process.returncode})[/error]")
                console.print("[dim]Try manually: npm install -g @votadev/tooncode@latest[/dim]")

        except subprocess.TimeoutExpired:
            console.print("[error]Timeout checking npm[/error]")
        except Exception as e:
            console.print(f"[error]Update failed: {e}[/error]")
        return True

    elif command == "/config":
        config_dir = os.path.join(os.path.expanduser("~"), ".tooncode")
        config_path = os.path.join(config_dir, "config.json")
        if arg == "edit":
            if platform.system() == "Windows":
                subprocess.Popen(["notepad", config_path])
            else:
                editor = os.environ.get("EDITOR", "nano")
                subprocess.run([editor, config_path])
            return True
        if not os.path.exists(config_path):
            os.makedirs(config_dir, exist_ok=True)
            default_config = {"default_model": MODEL, "theme": "default"}
            with open(config_path, "w") as f:
                json.dump(default_config, f, indent=2)
            console.print(f"[info]Created config: {config_path}[/info]")
        else:
            with open(config_path, "r") as f:
                cfg = json.load(f)
            console.print(f"[info]Config ({config_path}):[/info]")
            for k, v in cfg.items():
                console.print(f"  {k}: {v}")
        console.print("[info]Use /config edit to modify[/info]")
        return True

    elif command == "/cd":
        if not arg:
            console.print(f"[info]CWD: {CWD}[/info]")
            return True
        new_dir = os.path.abspath(os.path.join(CWD, arg))
        if os.path.isdir(new_dir):
            CWD = new_dir
            console.print(f"[info]CWD: {CWD}[/info]")
        else:
            console.print(f"[error]Not a directory: {new_dir}[/error]")
        return True

    return False


# ============================================================================
# Status Bar
# ============================================================================

# ============================================================================
# Main Chat Loop
# ============================================================================

def print_banner():
    """Print the welcome banner with gradient colors + Thai flag."""

    # ASCII art logo lines
    logo_lines = [
        r"  ████████╗ ██████╗  ██████╗ ███╗   ██╗ ██████╗ ██████╗ ██████╗ ███████╗",
        r"  ╚══██╔══╝██╔═══██╗██╔═══██╗████╗  ██║██╔════╝██╔═══██╗██╔══██╗██╔════╝",
        r"     ██║   ██║   ██║██║   ██║██╔██╗ ██║██║     ██║   ██║██║  ██║█████╗  ",
        r"     ██║   ██║   ██║██║   ██║██║╚██╗██║██║     ██║   ██║██║  ██║██╔══╝  ",
        r"     ██║   ╚██████╔╝╚██████╔╝██║ ╚████║╚██████╗╚██████╔╝██████╔╝███████╗",
        r"     ╚═╝    ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝",
    ]

    # Gradient colors (cyan -> blue -> magenta)
    gradient = [
        "#00ffff",  # cyan
        "#00ccff",  # light blue
        "#0099ff",  # blue
        "#6666ff",  # indigo
        "#9933ff",  # purple
        "#cc00ff",  # magenta
    ]

    # Build gradient logo
    logo = Text()
    for i, line in enumerate(logo_lines):
        logo.append(line + "\n", style=f"bold {gradient[i % len(gradient)]}")

    # Tagline with small Thai flag
    tagline = Text()
    tagline.append("                         ", style="dim")
    tagline.append("by ", style="dim")
    tagline.append("VotaLab", style="bold #ff6600")
    tagline.append("  |  ", style="dim")
    tagline.append(f"v{VERSION}", style="bold #00ccff")
    tagline.append("  |  ", style="dim")
    # Small Thai flag inline
    tagline.append("█", style="bold red")
    tagline.append("█", style="white")
    tagline.append("█", style="bold #0033A0")
    tagline.append("█", style="white")
    tagline.append("█", style="bold red")
    tagline.append(" Thai Coding Agent", style="dim white")

    # Count stats
    install_dir = os.path.dirname(os.path.abspath(__file__))
    session_dir = os.path.join(install_dir, "sessions")
    memory_dir = os.path.join(install_dir, "memory")
    session_count = len(glob_mod.glob(os.path.join(session_dir, "*.json"))) if os.path.exists(session_dir) else 0
    memory_count = len(glob_mod.glob(os.path.join(memory_dir, "*.md"))) if os.path.exists(memory_dir) else 0

    # Detect project info
    has_git = os.path.exists(os.path.join(CWD, ".git"))
    has_tooncode_md = os.path.exists(os.path.join(CWD, "TOONCODE.md"))
    git_branch = ""
    if has_git:
        try:
            r = subprocess.run("git branch --show-current", shell=True, capture_output=True, text=True,
                               cwd=CWD, timeout=5, encoding="utf-8", errors="replace")
            git_branch = r.stdout.strip()
        except Exception:
            pass

    # Short CWD
    short_cwd = CWD
    home = os.path.expanduser("~")
    if short_cwd.startswith(home):
        short_cwd = "~" + short_cwd[len(home):]

    # Build status badges
    badges = Text()
    badges.append("  ")
    badges.append(f" {MODEL} ", style="bold white on #6633cc")
    badges.append(" ", style="dim")
    badges.append(f" {len(TOOLS)} tools ", style="bold white on #006699")
    badges.append(" ", style="dim")
    skill_count = len(_skills) if _skills else 0
    if skill_count > 0:
        badges.append(f" {skill_count} skills ", style="bold white on #009966")
        badges.append(" ", style="dim")
    mcp_count = len(_mcp_servers) if _mcp_servers else 0
    if mcp_count > 0:
        mcp_tools = sum(len(s.tools) for s in _mcp_servers.values())
        badges.append(f" MCP:{mcp_count} ({mcp_tools} tools) ", style="bold white on #cc3399")
        badges.append(" ", style="dim")
    if has_git:
        badges.append(f" git:{git_branch or '?'} ", style="bold white on #cc6600")

    # Directory & date line
    dir_line = Text()
    dir_line.append("  > ", style="bold #00cc66")
    dir_line.append(short_cwd, style="bold white")
    if has_tooncode_md:
        dir_line.append("  TOONCODE.md", style="dim green")

    date_line = Text()
    date_line.append("  > ", style="bold #00cc66")
    date_line.append(datetime.now().strftime("%A, %B %d %Y  %H:%M"), style="dim white")

    # History stats
    history_line = Text()
    if session_count > 0 or memory_count > 0:
        history_line.append("  > ", style="bold #00cc66")
        if session_count > 0:
            history_line.append(f"{session_count} saved sessions", style="dim cyan")
        if session_count > 0 and memory_count > 0:
            history_line.append("  |  ", style="dim")
        if memory_count > 0:
            history_line.append(f"{memory_count} memories", style="dim cyan")
        history_line.append("  (/resume to load)", style="dim")

    # Quick commands
    cmds = Text()
    cmds.append("  ")
    for name, color in [("/help", "#00ccff"), ("/boss", "#ff6600"), ("/plan", "#cc00ff"),
                        ("/save", "#00cc66"), ("/resume", "#ffcc00"), ("/continue", "#00ffcc"),
                        ("/skills", "#ff3366"), ("!cmd", "#999999")]:
        cmds.append(f" {name} ", style=f"bold {color}")
        cmds.append(" ", style="dim")

    sep = Text("  " + "-" * 68, style="dim #333366")

    # Print it all
    console.print()
    console.print(logo)
    console.print(tagline)
    console.print()
    console.print(Panel(
        Group(
            badges,
            Text(),
            dir_line,
            date_line,
            history_line if (session_count > 0 or memory_count > 0) else Text(),
            sep,
            Text(),
            cmds,
            Text(),
        ),
        border_style="#00f5ff",
        padding=(0, 1),
    ))
    console.print()


def _detect_paste_language(text: str) -> str:
    """Detect programming language from pasted code. Returns language name or empty string."""
    text_stripped = text.strip()
    lines = text_stripped.split("\n")
    first_lines = "\n".join(lines[:10]).lower()

    # Already wrapped in code block — extract language
    if text_stripped.startswith("```"):
        first_line = lines[0].strip("`").strip()
        return first_line if first_line else ""

    # Shebang
    if text_stripped.startswith("#!"):
        if "python" in lines[0]: return "python"
        if "node" in lines[0]: return "javascript"
        if "bash" in lines[0] or "sh" in lines[0]: return "bash"
        if "ruby" in lines[0]: return "ruby"

    # Python signals
    py_signals = ["def ", "import ", "from ", "class ", "if __name__", "print(", "self.", "async def ", "elif ", "except:"]
    if sum(1 for s in py_signals if s in text_stripped) >= 2:
        return "python"

    # JavaScript/TypeScript
    js_signals = ["const ", "let ", "var ", "function ", "=> {", "require(", "import ", "export ", "console.log", "async "]
    if sum(1 for s in js_signals if s in text_stripped) >= 2:
        if "interface " in text_stripped or ": string" in text_stripped or ": number" in text_stripped:
            return "typescript"
        return "javascript"

    # HTML
    if "<html" in first_lines or "<!doctype" in first_lines or ("<div" in first_lines and ">" in first_lines):
        return "html"

    # CSS
    if ("{" in text_stripped and ":" in text_stripped and ";" in text_stripped and
            any(kw in first_lines for kw in ["color:", "margin:", "padding:", "display:", "font-", "background:"])):
        return "css"

    # Java
    if "public class " in text_stripped or "public static void main" in text_stripped:
        return "java"

    # Go
    if "func " in text_stripped and "package " in first_lines:
        return "go"

    # Rust
    if "fn " in text_stripped and ("let mut " in text_stripped or "impl " in text_stripped):
        return "rust"

    # SQL
    sql_kw = ["SELECT ", "INSERT ", "CREATE TABLE", "ALTER TABLE", "DROP ", "UPDATE ", "DELETE FROM"]
    if any(kw in text_stripped.upper() for kw in sql_kw):
        return "sql"

    # Shell/Bash
    bash_signals = ["#!/bin", "echo ", "if [", "fi\n", "done\n", "do\n", "export ", "alias "]
    if sum(1 for s in bash_signals if s in text_stripped) >= 2:
        return "bash"

    # JSON
    if (text_stripped.startswith("{") and text_stripped.endswith("}")) or \
       (text_stripped.startswith("[") and text_stripped.endswith("]")):
        try:
            json.loads(text_stripped)
            return "json"
        except Exception:
            pass

    # YAML
    if ":" in lines[0] and not lines[0].strip().startswith("{"):
        yaml_count = sum(1 for l in lines[:5] if ":" in l and not l.strip().startswith("#"))
        if yaml_count >= 3:
            return "yaml"

    # C/C++
    if "#include" in first_lines or ("int main(" in text_stripped):
        return "cpp"

    # PHP
    if "<?php" in first_lines:
        return "php"

    return ""


def main(_initial_prompt=None):
    global MODEL, CWD, message_count, _loop_break

    # Fix Windows encoding for Thai/Unicode
    if platform.system() == "Windows":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")

    console.clear()
    print_banner()
    _load_skills()
    if _skills:
        console.print(f"[dim]  {len(_skills)} skills loaded (/skills to list)[/dim]")

    # Check for updates in background (non-blocking)
    def _check_update():
        try:
            r = subprocess.run("npm view @votadev/tooncode version",
                               shell=True, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=10)
            latest = r.stdout.strip()
            if latest and latest != VERSION:
                console.print(f"[bold cyan]  Update available: v{VERSION} → v{latest} (/update to install)[/bold cyan]")
        except Exception:
            pass
    threading.Thread(target=_check_update, daemon=True).start()

    # Load MCP servers from ~/.tooncode/mcp.json
    _load_mcp_servers()

    # Auto-detect project context files
    _other_mds = ["CLAUDE.md", ".claude/CLAUDE.md", "GEMINI.md", ".cursorrules", ".cursor/rules",
                  "COPILOT.md", ".github/copilot-instructions.md"]
    tooncode_md = os.path.join(CWD, "TOONCODE.md")
    found_others = [f for f in _other_mds if os.path.exists(os.path.join(CWD, f))]

    if os.path.exists(tooncode_md):
        console.print(f"[dim]  Loaded TOONCODE.md[/dim]")
        if found_others:
            console.print(f"[dim]  Also reading: {', '.join(found_others)}[/dim]")
    elif found_others:
        console.print(f"[bold cyan]  Found: {', '.join(found_others)} — importing to TOONCODE.md...[/bold cyan]")
        # Auto-create TOONCODE.md with imported content
        handle_slash_command("/init", [])

    # Auto-index codebase on first start (load from cache or build fresh)
    if not _load_cached_index():
        console.print("[dim]  Indexing codebase...[/dim]", end="")
        _build_codebase_index()
        console.print(f"[dim] done ({_codebase_index.count(chr(10)) + 1} lines)[/dim]")
    else:
        console.print(f"[dim]  Loaded codebase index from cache (use /index to refresh)[/dim]")

    console.print()

    messages = []

    # prompt_toolkit session with history (fallback to input() if no real terminal)
    session = None
    try:
        if sys.stdin.isatty():
            pt_style = PTStyle.from_dict({
                "prompt": "#00ccff bold",
                "": "#ffffff",
                "bottom-toolbar": "bg:#16161e #7a88cf noinherit",
                "bottom-toolbar.text": "bg:#16161e #7a88cf noinherit",
                "rprompt": "#555577",
                "separator": "#333366",
            })
            kb = KeyBindings()

            _ctrl_c_count = {"n": 0, "t": 0.0}

            @kb.add("c-c")
            def _(event):
                now = time.time()
                if event.current_buffer.text:
                    # Has text → just clear the line
                    event.current_buffer.reset()
                    _ctrl_c_count["n"] = 0
                    return

                # Empty prompt → count rapid Ctrl+C
                _ctrl_c_count["n"] += 1
                _ctrl_c_count["t"] = now

                if _ctrl_c_count["n"] >= 2:
                    # Double Ctrl+C on empty prompt → exit
                    event.app.exit(exception=EOFError())
                else:
                    # Single Ctrl+C → return empty (shows "press again to exit")
                    event.app.exit(result="__CTRL_C__")

            @kb.add("c-d")
            def _(event):
                raise EOFError()

            @kb.add("escape", "escape")
            def _(event):
                event.current_buffer.reset()

            def _bottom_toolbar():
                """Boss AI-style bottom toolbar."""
                ctx_max = CONTEXT_WINDOWS.get(MODEL, 200_000)
                ctx_pct = (last_input_tokens / ctx_max * 100) if last_input_tokens > 0 else 0
                ctx_left = 100.0 - ctx_pct
                warn = "!" if ctx_pct >= 70 else ""

                short = CWD
                h = os.path.expanduser("~")
                if short.startswith(h):
                    short = "~" + short[len(h):]
                if len(short) > 35:
                    short = "..." + short[-32:]

                task_str = ""
                if _tasks:
                    done = sum(1 for t in _tasks if t["status"] == "done")
                    task_str = f" | tasks:{done}/{len(_tasks)}"

                mode_str = " [PLAN]" if plan_mode else ""

                info = f" {MODEL}  {short}  msgs:{message_count}  ctx:{ctx_left:.0f}%{warn}{task_str}{mode_str} "

                return [("class:bottom-toolbar", info)]

            session = PromptSession(
                history=InMemoryHistory(),
                auto_suggest=AutoSuggestFromHistory(),
                style=pt_style,
                key_bindings=kb,
                enable_history_search=True,
                multiline=True,
                prompt_continuation="  ",
                bottom_toolbar=_bottom_toolbar,
            )

            # Enter = submit (not newline). Paste automatically handles multiline.
            @kb.add("enter")
            def _(event):
                buf = event.current_buffer
                # If we're in paste mode, let it add newline
                if buf.document.is_cursor_at_the_end and not event.app.current_buffer.selection_state:
                    buf.validate_and_handle()
                else:
                    buf.validate_and_handle()
    except Exception:
        session = None

    _show_status = True  # only show status bar before real input
    _last_channel_check = 0
    _my_pid = os.getpid()
    _seen_msgs = set()
    _injected_prompt = _initial_prompt  # for -p flag

    while True:
        try:
            # Check channel for new messages from other instances
            now = time.time()
            if now - _last_channel_check > 3:  # check every 3 seconds
                _last_channel_check = now
                ch_dir = os.path.join(os.path.expanduser("~"), ".tooncode", "channels")
                if os.path.exists(ch_dir):
                    for mf in glob_mod.glob(os.path.join(ch_dir, "*.json")):
                        if mf in _seen_msgs:
                            continue
                        _seen_msgs.add(mf)
                        try:
                            with open(mf, "r", encoding="utf-8") as f:
                                msg = json.load(f)
                            # Skip own messages
                            if str(_my_pid) in msg.get("from", ""):
                                continue
                            # Only show recent (< 30s old)
                            if now - msg.get("time", 0) < 30:
                                sender = msg.get("from", "?")
                                text = msg.get("text", "")
                                console.print(f"\n[bold magenta]  >> {sender}:[/bold magenta] {text[:150]}")
                        except Exception:
                            pass

            # Injected prompt from -p flag
            if _injected_prompt:
                user_input = _injected_prompt
                _injected_prompt = None
                console.print(f"[dim]> {user_input[:100]}[/dim]")
            else:
                # Get input
                try:
                    if session:
                        if _show_status:
                            try:
                                tw = os.get_terminal_size().columns
                            except Exception:
                                tw = 80
                            console.print(Text("─" * tw, style="#333366"))
                            _show_status = False
                        try:
                            user_input = session.prompt(
                                HTML("<prompt>❯ </prompt>"),
                            ).strip()
                        except Exception:
                            session = None
                            user_input = input("❯ ").strip()
                    else:
                        if _show_status:
                            print("─" * 60)
                            _show_status = False
                        user_input = input("❯ ").strip()
                except KeyboardInterrupt:
                    console.print("\n[dim]Ctrl+C again to exit.[/dim]")
                    _show_status = True
                    continue
                except EOFError:
                    console.print("\n[dim]Goodbye![/dim]")
                    break

            # Handle Ctrl+C signal from prompt_toolkit
            if user_input == "__CTRL_C__":
                console.print("[dim]Ctrl+C again to exit.[/dim]")
                _show_status = True
                continue

            if not user_input:
                continue

            # Detect pasted long text — auto-detect code + syntax highlight preview
            _paste_counter = getattr(main, '_paste_counter', 0)
            lines_in = user_input.count("\n")
            if lines_in >= 3:
                _paste_counter += 1
                main._paste_counter = _paste_counter
                line_count = lines_in + 1

                # Auto-detect language from content
                detected_lang = _detect_paste_language(user_input)

                if detected_lang:
                    # Code paste — show syntax highlighted preview
                    console.print(f"[bold cyan]  [ Pasted code #{_paste_counter}  {detected_lang}  +{line_count} lines  {len(user_input)} chars ][/bold cyan]")
                    # Show preview with syntax highlighting (max 15 lines)
                    preview_lines = user_input.split("\n")[:15]
                    preview_text = "\n".join(preview_lines)
                    if line_count > 15:
                        preview_text += f"\n... (+{line_count - 15} more lines)"
                    try:
                        console.print(Syntax(preview_text, detected_lang, theme="monokai", line_numbers=True, padding=1))
                    except Exception:
                        console.print(f"[dim]{preview_text[:500]}[/dim]")

                    # Auto-wrap in code block if not already wrapped
                    if not user_input.strip().startswith("```"):
                        user_input = f"```{detected_lang}\n{user_input}\n```"
                else:
                    # Plain text paste
                    first_line = user_input.split("\n")[0][:60]
                    console.print(f"[bold cyan]  [ Pasted text #{_paste_counter}  +{line_count} lines  {len(user_input)} chars ][/bold cyan]")
                    console.print(f"[dim]  {first_line}{'...' if len(first_line) >= 60 else ''}[/dim]")
            console.print()

            _show_status = True  # show status after next real interaction

            # !command - run shell directly
            if user_input.startswith("!"):
                shell_cmd = user_input[1:].strip()
                if shell_cmd:
                    try:
                        shell_r = subprocess.run(
                            shell_cmd, shell=True, capture_output=True, text=True,
                            cwd=CWD, timeout=60, stdin=subprocess.DEVNULL,
                            encoding="utf-8", errors="replace",
                        )
                        output = (shell_r.stdout + shell_r.stderr).strip()
                        if output:
                            console.print(Text(output, style="dim"))
                        if shell_r.returncode != 0:
                            console.print(f"[dim][exit code: {shell_r.returncode}][/dim]")
                    except subprocess.TimeoutExpired:
                        console.print("[error]Command timed out after 60s[/error]")
                    except Exception as e:
                        console.print(f"[error]Shell error: {e}[/error]")
                continue

            # Check for slash commands
            cmd_result = None
            if user_input.startswith("/"):
                cmd_result = handle_slash_command(user_input, messages)
                if cmd_result is None:
                    console.print("[dim]Goodbye![/dim]")
                    break
                if cmd_result == "do":
                    # /do: message already appended, jump to agent loop
                    message_count += 1
                    console.print()
                    # Go directly to agent loop (below)
                elif cmd_result:
                    continue
                else:
                    # cmd_result == False: not a built-in command, check skills
                    parts = user_input.split(None, 1)
                    skill_name = parts[0][1:].lower()
                    skill_arg = parts[1] if len(parts) > 1 else ""

                    if skill_name in _skills:
                        skill = _skills[skill_name]
                        desc = skill.get("description", "")
                        console.print(f"[bold magenta]/{skill_name}[/bold magenta] [dim]— {desc}[/dim]")
                        prompt = skill["prompt"]
                        if skill_arg:
                            prompt = prompt.replace("{{input}}", skill_arg)
                        else:
                            prompt = prompt.replace("{{input}}", "(not specified - auto-detect from project context)")
                            prompt += "\n\nNo specific target was given. Auto-detect: look at recent git changes, project files, errors, and decide what to work on."
                        prompt = prompt.replace("{{cwd}}", CWD)
                        prompt = prompt.replace("{{model}}", MODEL)
                        user_input = prompt
                    else:
                        console.print(f"[error]Unknown command: {parts[0]}[/error]")
                        console.print("[info]Type /help for commands, /skills for skills[/info]")
                        continue

            # -- Normal message or skill prompt: add to messages --
            if cmd_result == "do":
                # /do already appended message and incremented count
                pass
            else:
                message_count += 1
                # Prevent consecutive user messages (API requires alternating roles)
                if messages and messages[-1].get("role") == "user":
                    messages.append({"role": "assistant", "content": [{"type": "text", "text": "(continuing)"}]})
                messages.append({
                    "role": "user",
                    "content": [{"type": "text", "text": user_input, "cache_control": {"type": "ephemeral"}}],
                })

            console.print()

            # Agent loop - NEVER STOP until work is done
            iteration = 0
            api_retries = 0
            _last_errors = []  # track recent tool errors to detect stuck
            _post_bosshelp = False  # flag: just got bosshelp, force continue even if text-only
            _empty_count = 0  # track consecutive empty responses
            while True:
                iteration += 1

                # -- Mid-loop: smart truncation at 60% to delay autocompact --
                ctx_max = CONTEXT_WINDOWS.get(MODEL, 200_000)
                if last_input_tokens > 0 and (last_input_tokens / ctx_max) >= 0.60 and len(messages) > 10:
                    _smart_truncate(messages)

                # -- Mid-loop autocompact: if context is getting full --
                if last_input_tokens > 0 and (last_input_tokens / ctx_max) >= 0.80:
                    console.print()
                    console.print(Panel(
                        Text(f"Context {last_input_tokens:,}/{ctx_max:,} ({last_input_tokens/ctx_max*100:.0f}%) - Auto-compacting...", style="bold yellow"),
                        border_style="yellow",
                    ))
                    _do_autocompact(messages)
                    iteration = 0  # Reset iteration counter after compact

                # -- Mid-loop: iteration limit only compacts if context is actually filling up --
                if iteration > 50:
                    ctx_used_pct = (last_input_tokens / ctx_max * 100) if last_input_tokens > 0 else 0
                    if ctx_used_pct >= 50:
                        console.print(Panel(
                            Text(f"50 iterations + {ctx_used_pct:.0f}% context - compacting...", style="bold yellow"),
                            border_style="yellow",
                        ))
                        _do_autocompact(messages)
                        iteration = 0
                    else:
                        # Context still fine, just reset counter and keep going
                        iteration = 0

                # Show AI response header
                if iteration == 1:
                    console.print("[assistant]AI >[/assistant]")
                else:
                    console.print(f"\n[assistant]AI > [/assistant][dim](step {iteration})[/dim]")

                # Stream the response
                renderer = StreamRenderer()
                renderer.start()

                try:
                    response = stream_response(messages, renderer)
                except KeyboardInterrupt:
                    renderer.stop()
                    console.print("\n[dim]Interrupted. Back to prompt.[/dim]")
                    if messages and messages[-1].get("role") == "user":
                        messages.pop()
                    break
                except Exception as e:
                    console.print(f"[error]Stream error: {e}[/error]")
                    response = {"content": [{"type": "text", "text": f"Error: {e}"}]}
                finally:
                    renderer.stop()

                content = response.get("content", [])

                # -- API error detection: retry up to 3 times --
                is_error = False
                for block in content:
                    if block.get("type") == "text" and block.get("text", "").startswith(("API Error", "Connection error", "Request timed out", "Error:")):
                        is_error = True
                        break

                if is_error:
                    api_retries += 1
                    if api_retries <= 2:
                        wait = min(api_retries * 3, 6)
                        console.print(f"[yellow]Retry {api_retries}/2 with {MODEL} in {wait}s...[/yellow]")
                        for _ in range(wait):
                            time.sleep(1)
                        continue
                    else:
                        # Try fallback to next model
                        fallback = _get_fallback_model()
                        if fallback:
                            console.print(f"[bold yellow]Model {MODEL} failed. Switching to fallback: {fallback}[/bold yellow]")
                            MODEL = fallback
                            api_retries = 0
                            continue
                        else:
                            console.print("[error]All models failed. Waiting for your input.[/error]")
                            api_retries = 0
                            break
                else:
                    api_retries = 0

                # Build assistant message for history
                assistant_content = []
                for block in content:
                    if block["type"] == "thinking":
                        assistant_content.append({
                            "type": "thinking",
                            "thinking": block["thinking"],
                            "signature": block.get("signature", ""),
                        })
                    elif block["type"] == "text":
                        assistant_content.append({"type": "text", "text": block["text"]})
                    elif block["type"] == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block["id"],
                            "name": block["name"],
                            "input": block["input"],
                        })

                # Add cache_control to last text block
                for b in reversed(assistant_content):
                    if b["type"] == "text":
                        b["cache_control"] = {"type": "ephemeral"}
                        break

                if assistant_content:
                    _empty_count = 0  # reset on successful response
                    messages.append({"role": "assistant", "content": assistant_content})
                else:
                    # Empty response from model — inject a placeholder so messages stay valid
                    # (API requires alternating user/assistant messages)
                    _empty_count += 1
                    console.print(f"[yellow](empty response from model, attempt {_empty_count})[/yellow]")
                    messages.append({"role": "assistant", "content": [{"type": "text", "text": "(no response)"}]})

                    if _empty_count >= 3:
                        console.print("[error]Model returned empty response 3 times. Try a different model with /model or rephrase your request.[/error]")
                        _empty_count = 0
                        break

                    # Retry: rephrase the last user message to nudge the model
                    if _post_bosshelp:
                        _post_bosshelp = False
                        messages.append({
                            "role": "user",
                            "content": [{"type": "text", "text":
                                "Your response was empty. Read the BOSSHELP fix above. "
                                "Step 1: use the read tool to read the file mentioned. "
                                "Step 2: use the edit tool to apply the fix. Do it now.",
                                "cache_control": {"type": "ephemeral"}}],
                        })
                    else:
                        messages.append({
                            "role": "user",
                            "content": [{"type": "text", "text":
                                "Your response was empty. Please try again. Use tools if needed.",
                                "cache_control": {"type": "ephemeral"}}],
                        })
                    continue

                # Check if we need to execute tools
                if has_tool_use(content):
                    console.print()
                    tool_results = execute_tools(content)

                    messages.append({"role": "user", "content": tool_results})

                    # Hard break if loop detected too many times
                    if _loop_break:
                        _loop_break = False
                        with _recent_tool_calls_lock:
                            _recent_tool_calls.clear()
                        console.print("[bold red]Stopped: AI stuck in loop. Back to prompt.[/bold red]")
                        break

                    continue  # Always continue after tool use

                # No tool use - AI gave a text response

                # After bosshelp: AI might respond with text only explaining the fix
                # Force it to continue and actually apply the fix
                if _post_bosshelp:
                    _post_bosshelp = False
                    console.print(f"\n[dim](bosshelp response received - pushing AI to apply fix...)[/dim]")
                    messages.append({
                        "role": "user",
                        "content": [{"type": "text", "text":
                            "You explained the fix but didn't apply it. NOW use the edit/write/bash tools to actually make the changes. Do it now.",
                            "cache_control": {"type": "ephemeral"}}],
                    })
                    continue  # Force another round

                # Check if there are still pending tasks -> auto-continue
                pending = [t for t in _tasks if t["status"] in ("pending", "in_progress")]
                if pending:
                    console.print(f"\n[dim]({len(pending)} tasks remaining - continuing...)[/dim]")
                    next_task = pending[0]
                    if next_task["status"] == "pending":
                        next_task["status"] = "in_progress"
                    messages.append({
                        "role": "user",
                        "content": [{"type": "text", "text":
                            f"Continue working. Next pending task: #{next_task['id']} - {next_task['text']}\n"
                            f"Mark it done with task_update when finished.",
                            "cache_control": {"type": "ephemeral"}}],
                    })
                    continue  # Keep going

                # Auto-continue if response was cut off (max_tokens)
                resp_stop = response.get("stop_reason", "end_turn")
                if resp_stop == "max_tokens":
                    console.print(f"\n[dim](response truncated - auto-continuing...)[/dim]")
                    messages.append({
                        "role": "user",
                        "content": [{"type": "text", "text":
                            "Your response was cut off. Continue exactly where you left off.",
                            "cache_control": {"type": "ephemeral"}}],
                    })
                    continue

                # No pending tasks, no tool use -> work is done
                break

            console.print()

        except KeyboardInterrupt:
            # Ctrl+C during AI processing → back to prompt
            console.print("\n[dim]Interrupted. Ctrl+C again to exit.[/dim]")
            continue
        except Exception as e:
            console.print(f"[error]Unexpected error: {e}[/error]")
            import traceback
            traceback.print_exc()
            continue


def _cli():
    """Parse CLI arguments."""
    global MODEL, CWD
    import argparse

    parser = argparse.ArgumentParser(
        prog="tooncode",
        description="ToonCode — 🇹🇭 Thai Coding Agent CLI by VotaLab",
        epilog="""Examples:
  tooncode                     Start interactive mode
  tooncode -m big-pickle       Use specific model
  tooncode -C ~/project        Start in specific directory
  tooncode -p "fix the bug"    Run a prompt and exit
  tooncode --models            List available models
  tooncode --update            Update to latest version

Settings: ~/.tooncode/settings.json
  Add/remove models, change defaults, set API URL.

  Default (OpenCode - free):
  {
    "default_model": "big-pickle",
    "models": [
      {"name": "my-custom-model", "context": 128000},
      {"name": "local-llama", "context": 32000, "no_sampling": true}
    ],
    "api_url": "https://opencode.ai/zen/v1/messages",
    "auto_approve": true
  }

More info: https://www.npmjs.com/package/@votadev/tooncode""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--version", action="version", version=f"tooncode {VERSION}")
    parser.add_argument("-m", "--model", choices=AVAILABLE_MODELS, help="AI model to use")
    parser.add_argument("-C", "--cwd", metavar="DIR", help="Working directory")
    parser.add_argument("-p", "--prompt", metavar="TEXT", help="Run a single prompt and exit")
    parser.add_argument("--models", action="store_true", help="List available models")
    parser.add_argument("--update", action="store_true", help="Update to latest version")
    # Legacy positional args (backward compat)
    parser.add_argument("legacy_model", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("legacy_cwd", nargs="?", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # --models
    if args.models:
        print("Available models:")
        for m in AVAILABLE_MODELS:
            marker = " (default)" if m == MODEL else ""
            print(f"  {m}{marker}")
        sys.exit(0)

    # --update
    if args.update:
        # Clean up old venv inside npm package to prevent EPERM on Windows
        try:
            import shutil
            npm_prefix = subprocess.run("npm prefix -g", shell=True, capture_output=True,
                                        text=True, encoding="utf-8", errors="replace", timeout=10)
            old_venv = os.path.join(npm_prefix.stdout.strip(), "node_modules", "@votadev", "tooncode", ".venv")
            if os.path.isdir(old_venv):
                shutil.rmtree(old_venv, ignore_errors=True)
        except Exception:
            pass
        os.system("npm install -g @votadev/tooncode@latest")
        sys.exit(0)

    # Model
    if args.model:
        MODEL = args.model
    elif args.legacy_model and args.legacy_model in AVAILABLE_MODELS:
        MODEL = args.legacy_model

    # CWD
    if args.cwd and os.path.isdir(args.cwd):
        CWD = os.path.abspath(args.cwd)
    elif args.legacy_cwd and os.path.isdir(args.legacy_cwd):
        CWD = os.path.abspath(args.legacy_cwd)

    return args


def _cleanup_all():
    """Cleanup all resources on exit."""
    global _team_running
    # 1. Browser
    if _browser_worker:
        try:
            _browser_worker.close()
        except Exception:
            pass

    # 2. Background processes — use list() to avoid dict mutation during iteration
    with _bg_processes_lock:
        for bg_id, proc in list(_bg_processes.items()):
            try:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        _bg_processes.clear()

    # 3. MCP servers
    try:
        _shutdown_mcp_servers()
    except Exception:
        pass

    # 4. Team agents
    try:
        _team_manager.stop()
        _team_running = False
    except Exception:
        pass


atexit.register(_cleanup_all)


if __name__ == "__main__":
    args = _cli()

    try:
        if args.prompt:
            # Single prompt mode: run one prompt and exit (for piping/scripting)
            main(_initial_prompt=args.prompt)
        else:
            main()
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/dim]")
    finally:
        _cleanup_all()
