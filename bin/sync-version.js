#!/usr/bin/env node
/**
 * Sync version from tooncode.py (single source of truth) → package.json
 * Runs automatically before npm publish via prepublishOnly script.
 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const pyFile = path.join(root, "tooncode.py");
const pkgFile = path.join(root, "package.json");

// Read VERSION from tooncode.py
const pyContent = fs.readFileSync(pyFile, "utf-8");
const match = pyContent.match(/VERSION\s*=\s*"(.+?)"/);
if (!match) {
  console.error("ERROR: Could not find VERSION in tooncode.py");
  process.exit(1);
}
const version = match[1];

// Update package.json
const pkg = JSON.parse(fs.readFileSync(pkgFile, "utf-8"));
if (pkg.version === version) {
  console.log(`Version already in sync: ${version}`);
} else {
  console.log(`Syncing version: ${pkg.version} → ${version}`);
  pkg.version = version;
  fs.writeFileSync(pkgFile, JSON.stringify(pkg, null, 2) + "\n");
}
