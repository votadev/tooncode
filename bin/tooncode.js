#!/usr/bin/env node
const { spawn, execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

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

const python = findPython();
if (!python) {
  console.error("\x1b[31mPython 3.10+ required. Install: https://python.org\x1b[0m");
  process.exit(1);
}

const mainPy = path.join(__dirname, "..", "tooncode.py");
if (!fs.existsSync(mainPy)) {
  console.error("\x1b[31mtooncode.py not found\x1b[0m");
  process.exit(1);
}

const child = spawn(python, [mainPy, ...process.argv.slice(2)], {
  stdio: "inherit",
  cwd: process.cwd(),
  env: { ...process.env, PYTHONIOENCODING: "utf-8" },
});
child.on("exit", (code) => process.exit(code || 0));
child.on("error", (err) => { console.error(err.message); process.exit(1); });
