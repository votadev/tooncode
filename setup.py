from setuptools import setup, find_packages

setup(
    name="tooncode",
    version="2.0.0",
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
