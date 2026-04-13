# ToonCode — 🇹🇭 Thai Coding Agent CLI

> **by VotaLab** | v2.5.0 | Thai AI Coding Agent powered by free AI models

```
  ████████╗ ██████╗  ██████╗ ███╗   ██╗ ██████╗ ██████╗ ██████╗ ███████╗
     ██║   ██║   ██║██║   ██║██╔██╗ ██║██║     ██║   ██║██║  ██║█████╗
     ╚═╝    ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
```

ToonCode is a **free, open-source** Thai AI coding agent that runs in your terminal. It uses free AI models (no API key needed) and provides a professional coding experience with 21 tools, multi-agent teams, semantic search, browser automation, and more.

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
curl -fsSL https://raw.githubusercontent.com/votalab/tooncode/main/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/votalab/tooncode/main/install.bat -OutFile install.bat; .\install.bat
```

### Method 2: Git clone (manual)

```bash
# Clone
git clone https://github.com/votalab/tooncode.git ~/.tooncode

# Install dependencies
pip install -r ~/.tooncode/requirements.txt

# Optional: Playwright for browser tool
pip install playwright && playwright install chromium

# Run
python ~/.tooncode/tooncode.py
```

**Add to PATH (run from anywhere):**

Mac/Linux — add to `~/.bashrc` or `~/.zshrc`:
```bash
alias tooncode="python ~/.tooncode/tooncode.py"
```

Windows — create `tooncode.cmd` in a PATH directory:
```cmd
@echo off
python %USERPROFILE%\.tooncode\tooncode.py %*
```

### Method 3: npm

```bash
npm install -g tooncode
```

### Method 4: Copy the folder

Just copy the entire `tooncode` folder anywhere and run:
```bash
cd /path/to/tooncode
pip install -r requirements.txt
python tooncode.py
```

---

## Quick Start

```bash
tooncode                          # Start in current directory
tooncode big-pickle              # Start with specific model
tooncode minimax-m2.5-free ~/my-project  # Model + directory
```

---

## Features

### 20 Tools

| Tool | Description |
|------|-------------|
| `bash` | Run shell commands (auto-detects PowerShell/bash) |
| `read` | Read files with line numbers |
| `write` | Create/overwrite files (shows diff) |
| `edit` | String replacement in files (shows diff) |
| `multi_edit` | Batch edits in one call |
| `glob` | Find files by pattern |
| `grep` | Search file contents with regex |
| `list_dir` | Browse directory structure |
| `web_search` | Search the web (DuckDuckGo) |
| `web_fetch` | Fetch web page content |
| `http` | Full HTTP client (GET/POST/PUT/DELETE + auth) |
| `browser` | Playwright browser: open, click, fill, screenshot, console, network |
| `screenshot` | Capture desktop/window screenshot |
| `spawn_agent` | Spawn sub-agent (coder/reviewer/tester/researcher) |
| `memory_save` | Save notes for future sessions |
| `memory_search` | Search past memories |
| `task_create/update/list` | Task management |
| `bosshelp` | Escalate to Boss AI or fallback model |

### Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/model [name]` | Switch AI model |
| `/boss <task>` | Create task plan (uses Boss AI or own model) |
| `/team <task>` | Multi-agent team: planner + frontend + backend + reviewer + tester |
| `/plan` | Toggle Plan Mode (read-only) |
| `/do` | Execute pending tasks |
| `/tasks` | Show task progress |
| `/continue`, `/c` | Continue where AI left off |
| `/save`, `/s` | Save session |
| `/resume`, `/r` | Load saved session |
| `/compact` | Compress context |
| `/memory` | Browse saved memories |
| `/paste`, `/v` | Send clipboard content |
| `/send <msg>` | Chat between ToonCode windows |
| `/bg`, `/ps` | Manage background processes |
| `/commit` | Git add & commit |
| `/diff` | Git diff |
| `/status` | Git status |
| `/undo` | Undo last file edit |
| `/init` | Create TOONCODE.md (auto-imports CLAUDE.md etc.) |
| `/config` | Show/edit config |
| `/skills` | List 32 built-in skills |
| `/cost` | Token usage stats |

### Multi-Agent Team

```bash
/team สร้างเว็บ portfolio           # Default: planner + frontend + backend
/team สร้าง API --roles planner,backend,tester   # Custom roles
```

Agents coordinate automatically via shared channel:
- 📋 **planner** — Creates plan, assigns work
- 🎨 **frontend** — Builds UI (HTML/CSS/JS)
- ⚙️ **backend** — Builds API/server logic
- 🔍 **reviewer** — Reviews code, fixes bugs
- 🧪 **tester** — Writes & runs tests

### 32 Built-in Skills

```bash
/refactor src/utils.py    # Refactor code
/review                    # Code review
/test api/users.js         # Generate tests
/fix                       # Fix bugs
/explain server.py         # Explain code
/optimize                  # Performance optimization
/docker                    # Create Dockerfile
/commit                    # Smart git commit
/audit                     # Security audit
```

### Available Models

| Model | Context | Notes |
|-------|---------|-------|
| `minimax-m2.5-free` | 200K | Default, good all-round |
| `big-pickle` | 200K | Strong coding |
| `nemotron-3-super-free` | 131K | Fast |
| `gpt-5-nano` | 1M | Largest context |

Auto-fallback: if a model fails, ToonCode automatically tries the next one.

---

## Project Context

ToonCode auto-reads these files from your project:
- `TOONCODE.md` — ToonCode project context
- `CLAUDE.md` — Boss AI context (auto-imported)
- `GEMINI.md` — Gemini context
- `.cursorrules` — Cursor rules
- `COPILOT.md` — Copilot instructions

Run `/init` to auto-create `TOONCODE.md` with imported content.

---

## Browser Tool

Requires Playwright:
```bash
pip install playwright && playwright install chromium
```

AI can control a real browser:
```
❯ เปิด google ค้นหา "ToonCode" แล้วสรุปผลลัพธ์

AI → browser open https://google.com/search?q=ToonCode
AI → browser text  (reads search results)
AI → browser console  (checks JS errors)
AI → browser screenshot  (captures page)
```

---

## Update

```bash
cd ~/.tooncode && git pull
```

---

## Cross-Platform

| Feature | Windows | Mac | Linux |
|---------|:-------:|:---:|:-----:|
| All tools | ✅ | ✅ | ✅ |
| Shell | PowerShell | bash | bash |
| Screenshot | ImageGrab | screencapture | scrot |
| Clipboard | Get-Clipboard | pbpaste | xclip |
| Browser | ✅ | ✅ | ✅ |

---

## License

MIT — Free to use, modify, and distribute.

**Made with ❤️ by VotaLab**
