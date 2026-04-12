#!/usr/bin/env node
const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const C = "\x1b[36m", G = "\x1b[32m", Y = "\x1b[33m", D = "\x1b[2m", X = "\x1b[0m";
console.log(`\n${C}ToonCode${X} — Installing...\n`);

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

function getVenvDir() {
  return path.join(__dirname, "..", ".venv");
}

function getVenvPython() {
  const venvDir = getVenvDir();
  return process.platform === "win32"
    ? path.join(venvDir, "Scripts", "python.exe")
    : path.join(venvDir, "bin", "python");
}

function ensureVenv(python) {
  const venvDir = getVenvDir();
  const venvPy = getVenvPython();
  if (!fs.existsSync(venvPy)) {
    console.log(`${D}Creating virtual environment...${X}`);
    execSync(`${python} -m venv "${venvDir}"`, { stdio: "pipe", timeout: 60000 });
  }
  return venvPy;
}

const python = findPython();
if (!python) {
  console.log(`${Y}Python 3.10+ not found. Install: https://python.org${X}\n`);
  process.exit(0);
}
console.log(`${D}Python: ${python}${X}`);

const req = path.join(__dirname, "..", "requirements.txt");
if (!fs.existsSync(req)) { process.exit(0); }

// Strategy 1: venv inside package (works on all OS)
try {
  const venvPy = ensureVenv(python);
  console.log(`${D}Installing into venv...${X}`);
  execSync(`"${venvPy}" -m pip install --quiet -r "${req}"`, {
    stdio: ["ignore", "pipe", "pipe"], timeout: 120000
  });
  console.log(`${G}Dependencies installed (venv).${X}`);
  console.log(`\n${G}ToonCode ready!${X} Run: ${C}tooncode${X}\n`);
  process.exit(0);
} catch (e) {
  console.log(`${D}venv failed, trying system pip...${X}`);
}

// Strategy 2: system pip fallbacks
const pipCmds = [
  `${python} -m pip install --user --quiet --break-system-packages -r "${req}"`,
  `${python} -m pip install --user --quiet -r "${req}"`,
  `${python} -m pip install --quiet -r "${req}"`,
];
for (const cmd of pipCmds) {
  try {
    execSync(cmd, { stdio: ["ignore", "pipe", "pipe"], timeout: 120000 });
    console.log(`${G}Dependencies installed (system).${X}`);
    console.log(`\n${G}ToonCode ready!${X} Run: ${C}tooncode${X}\n`);
    process.exit(0);
  } catch {}
}

console.log(`${Y}Auto-install failed. Run manually:${X}`);
console.log(`${C}  pip install --user httpx rich prompt_toolkit${X}\n`);
