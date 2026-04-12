#!/usr/bin/env node
const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const C = "\x1b[36m", G = "\x1b[32m", Y = "\x1b[33m", R = "\x1b[31m", D = "\x1b[2m", X = "\x1b[0m";
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

const python = findPython();
if (!python) {
  console.log(`${Y}Python 3.10+ not found. Install: https://python.org${X}`);
  console.log(`${D}Then: npm rebuild tooncode${X}\n`);
  process.exit(0);
}
console.log(`${D}Python: ${python}${X}`);

const req = path.join(__dirname, "..", "requirements.txt");
if (fs.existsSync(req)) {
  const pipCmds = [
    `${python} -m pip install --user --quiet --break-system-packages -r "${req}"`,
    `${python} -m pip install --user --quiet -r "${req}"`,
    `${python} -m pip install --quiet -r "${req}"`,
    `pip3 install --user --quiet --break-system-packages -r "${req}"`,
    `pip3 install --user --quiet -r "${req}"`,
  ];
  console.log(`${D}Installing Python packages...${X}`);
  let installed = false;
  for (const cmd of pipCmds) {
    try {
      execSync(cmd, { stdio: ["ignore", "pipe", "pipe"], timeout: 120000 });
      console.log(`${G}Dependencies installed.${X}`);
      installed = true;
      break;
    } catch {}
  }
  if (!installed) {
    console.log(`${Y}Auto-install failed. Run manually:${X}`);
    console.log(`${C}  pip install --user httpx rich prompt_toolkit${X}`);
  }
}

console.log(`\n${G}ToonCode ready!${X} Run: ${C}tooncode${X}\n`);
