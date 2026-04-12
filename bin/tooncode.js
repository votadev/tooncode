#!/usr/bin/env node
const { spawn, execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const R = "\x1b[31m", G = "\x1b[32m", C = "\x1b[36m", D = "\x1b[2m", X = "\x1b[0m";

function findPython() {
  const cmds = process.platform === "win32" ? ["python", "python3", "py"] : ["python3", "python"];
  for (const cmd of cmds) {
    try {
      const r = execSync(`${cmd} --version 2>&1`, { encoding: "utf-8" });
      if (r.includes("Python 3")) return cmd;
    } catch {}
  }
  return null;
}

function checkDeps(python) {
  try {
    execSync(`${python} -c "import httpx, rich, prompt_toolkit" 2>&1`, { encoding: "utf-8" });
    return true;
  } catch { return false; }
}

function installDeps(python) {
  const req = path.join(__dirname, "..", "requirements.txt");
  const cmds = [
    `${python} -m pip install --user --quiet --break-system-packages -r "${req}"`,
    `${python} -m pip install --user --quiet -r "${req}"`,
    `${python} -m pip install --quiet -r "${req}"`,
    `pip3 install --user --quiet --break-system-packages -r "${req}"`,
    `pip3 install --user --quiet -r "${req}"`,
    `pip3 install --quiet -r "${req}"`,
  ];
  console.log(`${D}Installing dependencies...${X}`);
  for (const cmd of cmds) {
    try {
      execSync(cmd, { stdio: ["ignore", "pipe", "pipe"], timeout: 120000 });
      return true;
    } catch {}
  }
  return false;
}

// Find Python
const python = findPython();
if (!python) {
  console.error(`${R}Python 3.10+ required. Install: https://python.org${X}`);
  process.exit(1);
}

// Check & install deps
if (!checkDeps(python)) {
  console.log(`${C}First run — installing Python dependencies...${X}`);
  if (!installDeps(python)) {
    console.error(`${R}Could not install dependencies. Run manually:${X}`);
    console.error(`${C}  ${python} -m pip install httpx rich prompt_toolkit${X}`);
    process.exit(1);
  }
  console.log(`${G}Dependencies ready.${X}\n`);
}

// Run tooncode
const mainPy = path.join(__dirname, "..", "tooncode.py");
const child = spawn(python, [mainPy, ...process.argv.slice(2)], {
  stdio: "inherit",
  cwd: process.cwd(),
  env: { ...process.env, PYTHONIOENCODING: "utf-8" },
});
child.on("exit", (code) => process.exit(code || 0));
child.on("error", (err) => { console.error(err.message); process.exit(1); });
