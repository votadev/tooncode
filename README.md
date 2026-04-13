# ToonCode — 🇹🇭 Thai Coding Agent CLI

> **by VotaLab** | v2.6.1 | Thai AI Coding Agent powered by free AI models

```
  ████████╗ ██████╗  ██████╗ ███╗   ██╗ ██████╗ ██████╗ ██████╗ ███████╗
     ██║   ██║   ██║██║   ██║██╔██╗ ██║██║     ██║   ██║██║  ██║█████╗
     ╚═╝    ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
```

ToonCode is a **free, open-source** Thai AI coding agent that runs in your terminal. It uses free AI models (no API key needed) and provides a professional coding experience with 21 tools, 32 skills, multi-agent teams, semantic search, browser automation, MCP server support, and more.

---

## Features

### 21 Built-in Tools

ToonCode comes with a comprehensive set of tools that the AI can use autonomously:

| Category | Tool | Description |
|----------|------|-------------|
| **File** | `read` | Read files with line numbers |
| | `write` | Create/overwrite files (shows diff) |
| | `edit` | String replacement in files (shows diff) |
| | `multi_edit` | Batch edits across multiple files in one call |
| | `glob` | Find files by pattern (e.g. `**/*.py`) |
| | `grep` | Search file contents with regex |
| | `list_dir` | Browse directory structure |
| **Shell** | `bash` | Run shell commands (auto-detects PowerShell on Windows, bash on Mac/Linux) |
| **Web** | `web_search` | Search the web via DuckDuckGo |
| | `web_fetch` | Fetch and extract web page content |
| | `http` | Full HTTP client — GET/POST/PUT/DELETE with headers, auth, JSON body |
| **Browser** | `browser` | Playwright browser automation — open pages, click, fill forms, take screenshots, read console, monitor network |
| **System** | `screenshot` | Capture desktop or window screenshot with OCR |
| **Agent** | `spawn_agent` | Spawn sub-agents (coder, reviewer, tester, researcher) |
| | `bosshelp` | Escalate difficult tasks to Boss AI (more powerful model) |
| **Memory** | `memory_save` | Save notes for future sessions |
| | `memory_search` | Search past memories by keyword |
| **Tasks** | `task_create` | Create a tracked task |
| | `task_update` | Update task status (pending/in_progress/done) |
| | `task_list` | View all tasks and progress |

### 32 Built-in Skills

Skills are pre-built prompt templates organized by category. Use them with slash commands:

| Category | Skills | Example |
|----------|--------|---------|
| **Code** (10) | refactor, review, test, lint, explain, optimize, scaffold, types, convert, deps | `/refactor src/utils.py` |
| **Debug** (4) | fix, error, perf, trace | `/fix` — auto-detect and fix bugs |
| **Git** (3) | commit, changelog, pr | `/commit` — smart commit message |
| **DevOps** (2) | docker, ci | `/docker` — generate Dockerfile |
| **Docs** (2) | readme, api | `/readme` — generate README |
| **Data** (3) | migrate, seed, sql | `/sql` — query helper |
| **API** (2) | endpoint, mock | `/endpoint` — create new API endpoint |
| **Architecture** (3) | diagram, pattern, split | `/diagram` — generate architecture diagram |
| **Security** (2) | audit, secrets | `/audit` — OWASP Top 10 security audit |

### Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/model [name]` | Switch AI model |
| `/boss <task>` | Create detailed implementation plan using Boss AI |
| `/team <task>` | Start multi-agent team (see below) |
| `/plan` | Toggle Plan Mode (AI plans only, no edits) |
| `/do` | Execute pending tasks |
| `/tasks` | Show task progress |
| `/continue`, `/c` | Continue where AI left off |
| `/save`, `/s` | Save session |
| `/resume`, `/r` | Load saved session |
| `/compact` | Compress conversation context |
| `/memory` | Browse saved memories |
| `/semantic <query>` | Semantic search across codebase (requires LanceDB) |
| `/index` | Rebuild codebase structure index |
| `/paste`, `/v` | Send clipboard content to AI |
| `/send <msg>` | Chat between ToonCode windows |
| `/bg`, `/ps` | Manage background processes |
| `/commit` | Git add & commit with smart message |
| `/diff` | Git diff |
| `/status` | Git status |
| `/undo` | Undo last file edit |
| `/init` | Create TOONCODE.md (auto-imports CLAUDE.md etc.) |
| `/config` | Show/edit configuration |
| `/skills` | List all 32 built-in skills |
| `/cost` | Token usage statistics |

### Multi-Agent Team System

ToonCode's most powerful feature. Spawn a team of specialized AI agents that coordinate and collaborate on complex tasks:

```bash
/team สร้างเว็บ portfolio             # Default: planner + frontend + backend + reviewer
/team build REST API --roles planner,backend,tester   # Custom roles
```

#### 13 Agent Roles

| Role | Emoji | Thai Name | Specialty |
|------|-------|-----------|-----------|
| **Planner** | 📋 | สมชาย | Breaks tasks into steps, assigns work to agents |
| **Supervisor** | 🧠 | สุภาพร | Monitors progress, resolves conflicts |
| **Frontend** | 🎨 | ณัฐพล | Builds UI — HTML/CSS/JS/React |
| **Backend** | ⚙️ | วิชัย | APIs, databases, server logic |
| **Reviewer** | 🔍 | มาลี | Code review, finds bugs, suggests improvements |
| **Tester** | 🧪 | ธนา | Writes and runs tests |
| **Researcher** | 🔬 | ปิยะ | Finds info, gathers data, provides sources |
| **Analyst** | 📊 | นภา | Data analysis, comparisons, insights |
| **Writer** | ✍️ | กานดา | Articles, docs, reports, plans |
| **Editor** | 📝 | อรุณ | Reviews and improves written content |
| **Designer** | 🎯 | พิมพ์ | Architecture, schemas, UI layouts |

#### How Teams Work

1. **Planner** receives the task and breaks it into sub-tasks
2. Tasks are assigned to specialized agents via JSON messages on a shared channel
3. Each agent works independently with access to all 21 tools
4. A shared **task board** tracks progress (pending / in_progress / done)
5. Agents communicate results back through the shared channel
6. **Supervisor** monitors progress and resolves conflicts when needed
7. Agents can dynamically spawn new agents if the task requires it

### Available AI Models

| Model | Context Window | Notes |
|-------|---------------|-------|
| `big-pickle` | 200K | **Default** — strong at coding tasks |
| `minimax-m2.5-free` | 204K | Good all-round performance |
| `nemotron-3-super-free` | 131K | Fast execution |
| `gpt-5-nano` | 1M | Largest context for big projects |

- **Auto-fallback**: if a model fails, ToonCode automatically tries the next available model
- **Per-model config**: each model can have its own API URL and key
- Switch models anytime with `/model <name>`

### Project Context Awareness

ToonCode automatically reads and understands your project:

- **Context Files** — auto-imports `TOONCODE.md`, `CLAUDE.md`, `GEMINI.md`, `.cursorrules`, `COPILOT.md`
- **Codebase Indexing** — scans project structure, extracts function/class symbols from code
- **Tech Stack Detection** — auto-detects frameworks (FastAPI, React, Next.js, Django, Express, Go, Rust, etc.)
- **Semantic Search** — optional vector-based code search using LanceDB for finding similar patterns

### Browser Automation

Control a real browser powered by Playwright:

```
❯ เปิด google ค้นหา "ToonCode" แล้วสรุปผลลัพธ์

AI → browser open https://google.com/search?q=ToonCode
AI → browser text        # reads page content
AI → browser screenshot  # captures the page
AI → browser console     # checks JS errors
AI → browser network     # monitors API calls
```

Requires: `pip install playwright && playwright install chromium`

### MCP Server Support

Extend ToonCode with custom tools via Model Context Protocol servers:

```json
// ~/.tooncode/mcp.json
{
  "servers": {
    "my-tool": {
      "command": "python",
      "args": ["path/to/server.py"],
      "env": { "API_KEY": "..." }
    }
  }
}
```

MCP servers are discovered automatically — their tools become available to the AI alongside built-in tools.

### Session & Memory

- **Save/Resume** — save conversations with `/save`, resume later with `/resume`
- **Persistent Memory** — AI saves important notes across sessions via `memory_save`
- **Edit History** — tracks recent file edits, supports `/undo`

### Cross-Platform

| Feature | Windows | Mac | Linux |
|---------|:-------:|:---:|:-----:|
| All 21 tools | ✅ | ✅ | ✅ |
| Shell | PowerShell | bash | bash |
| Screenshot | ImageGrab | screencapture | scrot |
| Clipboard | Get-Clipboard | pbpaste | xclip |
| Browser | ✅ | ✅ | ✅ |

---

## Requirements

- **Python 3.10+**
- **Git**
- **Node.js 16+** (optional, for npm install method)

---

## Installation

### Method 1: One-line install (recommended)

**Mac / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/votadev/tooncode/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/votadev/tooncode/main/install.bat -OutFile install.bat; .\install.bat
```

### Method 2: npm

```bash
npm install -g @votadev/tooncode
```

### Method 3: Git clone

```bash
git clone https://github.com/votadev/tooncode.git ~/.tooncode
pip install -r ~/.tooncode/requirements.txt
python ~/.tooncode/tooncode.py
```

**Add to PATH:**

Mac/Linux — add to `~/.bashrc` or `~/.zshrc`:
```bash
alias tooncode="python ~/.tooncode/tooncode.py"
```

Windows — create `tooncode.cmd` in a PATH directory:
```cmd
@echo off
python %USERPROFILE%\.tooncode\tooncode.py %*
```

### Method 4: Just copy the folder

```bash
cd /path/to/tooncode
pip install -r requirements.txt
python tooncode.py
```

---

## Quick Start

```bash
tooncode                                    # Start in current directory
tooncode big-pickle                         # Start with specific model
tooncode minimax-m2.5-free ~/my-project     # Model + directory
```

---

## Configuration

### Settings (`~/.tooncode/settings.json`)

```json
{
  "api_url": "https://opencode.ai/zen/v1/messages",
  "api_key": "public",
  "default_model": "big-pickle",
  "models": [
    { "name": "big-pickle", "context": 200000 },
    { "name": "custom-model", "api_url": "...", "api_key": "..." }
  ],
  "auto_approve": true
}
```

### Custom Skills

Add `.md` files to `~/.tooncode/skills/<category>/`:

```markdown
---
name: my-skill
description: What this skill does
---

Your prompt template here. Use {{input}} for user input.
```

---

## Update

```bash
cd ~/.tooncode && git pull
```

---

## License

MIT — Free to use, modify, and distribute.

**Made with ❤️ by VotaLab**
