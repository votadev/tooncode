"""
ToonCode Tools Package — modular tool handlers + schemas.

Usage:
    from tools import TOOLS, TOOL_HANDLERS, init_tools

    # Initialize with shared context
    init_tools(cwd="/path", console=console_obj, ...)
"""

from tools.context import ctx
from tools.schemas import TOOLS
from tools.file_ops import exec_read, exec_write, exec_edit, exec_multi_edit, exec_glob, exec_grep, exec_list_dir
from tools.bash import exec_bash
from tools.web import exec_web_search, exec_web_fetch, exec_http
from tools.memory import exec_memory_search, exec_memory_save
from tools.tasks import exec_task_create, exec_task_update, exec_task_list
from tools.screenshot import exec_screenshot


def init_tools(**kwargs):
    """Initialize shared tool context. Call once at startup."""
    for k, v in kwargs.items():
        if hasattr(ctx, k):
            setattr(ctx, k, v)


def get_tool_handlers() -> dict:
    """Build TOOL_HANDLERS dict. Call after init_tools."""
    return {
        "bash": exec_bash,
        "read": exec_read,
        "write": exec_write,
        "edit": exec_edit,
        "multi_edit": exec_multi_edit,
        "glob": exec_glob,
        "grep": exec_grep,
        "list_dir": exec_list_dir,
        "web_search": exec_web_search,
        "web_fetch": exec_web_fetch,
        "http": exec_http,
        "memory_search": exec_memory_search,
        "memory_save": exec_memory_save,
        "task_create": exec_task_create,
        "task_update": exec_task_update,
        "task_list": exec_task_list,
        "screenshot": exec_screenshot,
    }
