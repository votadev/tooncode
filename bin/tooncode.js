#!/usr/bin/env node
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

// Find Python
function findPython() {
  const candidates = process.platform === "win32"
    ? ["python", "python3", "py"]
    : ["python3", "python"];

  for (const cmd of candidates) {
    try {
      const r = require("child_process").execSync(`${cmd} --version 2>&1`, { encoding: "utf-8" });
      if (r.includes("Python 3")) return cmd;
    } catch {}
  }
  return null;
}

const python = findPython();
if (!python) {
  console.error("\x1b[31mError: Python 3.10+ is required but not found.\x1b[0m");
  console.error("Install from: https://www.python.org/downloads/");
  process.exit(1);
}

// Find tooncode.py
const libDir = path.join(__dirname, "..", "lib");
const mainPy = path.join(libDir, "tooncode.py");

if (!fs.existsSync(mainPy)) {
  console.error("\x1b[31mError: tooncode.py not found at", mainPy, "\x1b[0m");
  process.exit(1);
}

// Pass through all args
const args = [mainPy, ...process.argv.slice(2)];

// Spawn Python with inherit stdio for full interactive support
const child = spawn(python, args, {
  stdio: "inherit",
  cwd: process.cwd(),
  env: { ...process.env, PYTHONIOENCODING: "utf-8" },
});

child.on("exit", (code) => process.exit(code || 0));
child.on("error", (err) => {
  console.error("\x1b[31mFailed to start Python:", err.message, "\x1b[0m");
  process.exit(1);
});
