import re
from setuptools import setup, find_packages

with open("tooncode.py", encoding="utf-8") as f:
    version = re.search(r'VERSION\s*=\s*"(.+?)"', f.read()).group(1)

setup(
    name="tooncode",
    version=version,
    description="Thai AI Coding Agent CLI - Free, 21 tools, multi-agent team, semantic search",
    author="VotaLab",
    py_modules=["tooncode", "tui"],
    python_requires=">=3.10",
    install_requires=[
        "httpx>=0.27.0",
        "rich>=13.0.0",
        "prompt_toolkit>=3.0.0",
        "textual>=1.0.0",
        "lancedb>=0.20.0",
    ],
    entry_points={
        "console_scripts": [
            "tooncode=tooncode:main",
            "tooncode-tui=tui:ToonCodeApp.run",
        ],
    },
)
