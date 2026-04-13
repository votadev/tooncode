"""
Shared context for all tool handlers.
Populated by init_tools() at startup — avoids circular imports.
"""

import os
import threading


class ToolContext:
    """Shared state accessible by all tool handlers."""

    def __init__(self):
        # Working directory
        self.cwd = os.getcwd()

        # Rich console (set by init_tools)
        self.console = None

        # Edit history for /undo
        self.edit_history = []
        self.edit_history_lock = threading.Lock()
        self.MAX_EDIT_HISTORY = 50

        # Task system
        self.tasks = []
        self.tasks_lock = threading.Lock()
        self.task_counter = 0

        # Memory
        self.memory_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "memory")

        # Auto-approve mode
        self.auto_approve = True

        # Permission callback (set by main)
        self.ask_permission = None  # func(action, detail) -> bool

        # Large file limit
        self.max_file_size = 512 * 1024  # 512KB


# Singleton context — shared across all tools
ctx = ToolContext()
