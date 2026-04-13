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

function getVenvDir() {
  // Use ~/.tooncode/.venv so venv lives outside npm package dir
  // This prevents EPERM errors on Windows when npm updates the package
  const home = process.env.HOME || process.env.USERPROFILE || require("os").homedir();
  return path.join(home, ".tooncode", ".venv");
}

function getVenvPython() {
  const venvDir = getVenvDir();
  return process.platform === "win32"
    ? path.join(venvDir, "Scripts", "python.exe")
    : path.join(venvDir, "bin", "python");
}

function checkDeps(py) {
  try {
    execSync(`"${py}" -c "import httpx, rich, prompt_toolkit" 2>&1`, { encoding: "utf-8" });
    return true;
  } catch { return false; }
}

function ensureVenv(sysPython) {
  const venvDir = getVenvDir();
  const venvPy = getVenvPython();
  if (!fs.existsSync(venvPy)) {
    // Ensure ~/.tooncode dir exists
    const parentDir = path.dirname(venvDir);
    if (!fs.existsSync(parentDir)) { fs.mkdirSync(parentDir, { recursive: true }); }
    console.log(`${C}Creating virtual environment...${X}`);
    execSync(`${sysPython} -m venv "${venvDir}"`, { stdio: "pipe", timeout: 60000 });
  }
  return venvPy;
}

function installDeps(py) {
  const req = path.join(__dirname, "..", "requirements.txt");
  console.log(`${D}Installing dependencies...${X}`);
  execSync(`"${py}" -m pip install --quiet -r "${req}"`, {
    stdio: ["ignore", "pipe", "pipe"], timeout: 120000
  });
}

// Find system Python
const sysPython = findPython();
if (!sysPython) {
  console.error(`${R}Python 3.10+ required. Install: https://python.org${X}`);
  process.exit(1);
}

// Determine which Python to use (prefer venv)
let usePython;
const venvPy = getVenvPython();

if (fs.existsSync(venvPy) && checkDeps(venvPy)) {
  // venv exists and has deps
  usePython = venvPy;
} else if (checkDeps(sysPython)) {
  // system Python has deps
  usePython = sysPython;
} else {
  // Need to install — try venv first
  console.log(`${C}First run — setting up...${X}`);
  try {
    const vp = ensureVenv(sysPython);
    installDeps(vp);
    usePython = vp;
    console.log(`${G}Ready.${X}\n`);
  } catch {
    // venv failed, try system pip
    const fallbacks = [
      `${sysPython} -m pip install --user --quiet --break-system-packages -r "${path.join(__dirname, "..", "requirements.txt")}"`,
      `${sysPython} -m pip install --user --quiet -r "${path.join(__dirname, "..", "requirements.txt")}"`,
    ];
    let ok = false;
    for (const cmd of fallbacks) {
      try { execSync(cmd, { stdio: ["ignore", "pipe", "pipe"], timeout: 120000 }); ok = true; break; } catch {}
    }
    if (ok) {
      usePython = sysPython;
    } else {
      console.error(`${R}Could not install dependencies.${X}`);
      console.error(`${C}  ${sysPython} -m pip install httpx rich prompt_toolkit${X}`);
      process.exit(1);
    }
  }
}

// Run tooncode
const mainPy = path.join(__dirname, "..", "tooncode.py");
const child = spawn(usePython, [mainPy, ...process.argv.slice(2)], {
  stdio: "inherit",
  cwd: process.cwd(),
  env: { ...process.env, PYTHONIOENCODING: "utf-8" },
});
child.on("exit", (code) => process.exit(code || 0));
child.on("error", (err) => { console.error(err.message); process.exit(1); });
