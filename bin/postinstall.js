#!/usr/bin/env node
const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const RESET = "\x1b[0m";
const CYAN = "\x1b[36m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const RED = "\x1b[31m";
const DIM = "\x1b[2m";

console.log(`\n${CYAN}ToonCode${RESET} — Installing Python dependencies...\n`);

// Find Python
function findPython() {
  const candidates = process.platform === "win32"
    ? ["python", "python3", "py"]
    : ["python3", "python"];
  for (const cmd of candidates) {
    try {
      const r = execSync(`${cmd} --version 2>&1`, { encoding: "utf-8" });
      if (r.includes("Python 3")) {
        const ver = r.match(/Python (\d+)\.(\d+)/);
        if (ver && parseInt(ver[1]) >= 3 && parseInt(ver[2]) >= 10) return cmd;
        console.log(`${YELLOW}Found ${r.trim()} but need 3.10+${RESET}`);
      }
    } catch {}
  }
  return null;
}

const python = findPython();
if (!python) {
  console.log(`${RED}Python 3.10+ not found.${RESET}`);
  console.log(`${DIM}Install from: https://www.python.org/downloads/${RESET}`);
  console.log(`${DIM}Then run: npm rebuild tooncode${RESET}\n`);
  process.exit(0); // Don't fail npm install
}

console.log(`${DIM}Using: ${python}${RESET}`);

// Install pip dependencies
const reqFile = path.join(__dirname, "..", "requirements.txt");
if (fs.existsSync(reqFile)) {
  try {
    console.log(`${DIM}Installing: httpx, rich, prompt_toolkit...${RESET}`);
    execSync(`${python} -m pip install --quiet --disable-pip-version-check -r "${reqFile}"`, {
      stdio: ["ignore", "pipe", "pipe"],
      encoding: "utf-8",
    });
    console.log(`${GREEN}Dependencies installed.${RESET}`);
  } catch (e) {
    console.log(`${YELLOW}pip install failed — you may need to run manually:${RESET}`);
    console.log(`${DIM}  ${python} -m pip install -r ${reqFile}${RESET}`);
  }
}

// Install Playwright browsers (optional)
try {
  execSync(`${python} -c "from playwright.sync_api import sync_playwright"`, {
    stdio: "ignore",
  });
  console.log(`${DIM}Playwright found. Installing browser...${RESET}`);
  try {
    execSync(`${python} -m playwright install chromium`, {
      stdio: ["ignore", "pipe", "pipe"],
    });
    console.log(`${GREEN}Chromium browser installed.${RESET}`);
  } catch {
    console.log(`${YELLOW}Playwright browser install failed (optional).${RESET}`);
  }
} catch {
  console.log(`${DIM}Playwright not installed (optional — for browser tool).${RESET}`);
}

console.log(`\n${GREEN}ToonCode ready!${RESET} Run: ${CYAN}tooncode${RESET}\n`);
