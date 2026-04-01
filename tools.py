import os
import sys
import subprocess
import tempfile
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from typing import List, Dict

# ─────────────────────────────────────────────
# 1. WEB SEARCH
# ─────────────────────────────────────────────
def google_search(query: str) -> List[Dict[str, str]]:
    """Search the web using DuckDuckGo and return top results."""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
        return results
    except Exception as e:
        return [{"error": str(e)}]

# ─────────────────────────────────────────────
# 2. FETCH URL CONTENT
# ─────────────────────────────────────────────
def fetch_url(url: str) -> str:
    """Fetch a URL and return a cleaned text summary of the page content."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # Truncate to first 3000 chars for context window safety
        return text[:3000]
    except Exception as e:
        return f"Error fetching URL: {str(e)}"

# ─────────────────────────────────────────────
# 3. FILE OPERATIONS
# ─────────────────────────────────────────────
def write_file(filename: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed."""
    try:
        parent = os.path.dirname(filename)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(filename, 'w') as f:
            f.write(content)
        return f"✅ File '{filename}' written successfully ({len(content)} chars)."
    except Exception as e:
        return f"❌ Error writing file: {str(e)}"

def read_file(filename: str) -> str:
    """Read content from a file."""
    try:
        with open(filename, 'r') as f:
            content = f.read()
        return content[:5000] if len(content) > 5000 else content
    except Exception as e:
        return f"❌ Error reading file: {str(e)}"

def list_files(directory: str = ".") -> List[str]:
    """List files in a directory with details."""
    try:
        entries = []
        for item in os.listdir(directory):
            path = os.path.join(directory, item)
            kind = "📁" if os.path.isdir(path) else "📄"
            entries.append(f"{kind} {item}")
        return entries if entries else ["(empty directory)"]
    except Exception as e:
        return [f"❌ Error: {str(e)}"]

def create_directory(path: str) -> str:
    """Create a directory (and parents if needed)."""
    try:
        os.makedirs(path, exist_ok=True)
        return f"✅ Directory '{path}' created."
    except Exception as e:
        return f"❌ Error creating directory: {str(e)}"

# ─────────────────────────────────────────────
# 4. CODE EXECUTION
# ─────────────────────────────────────────────
def run_python_code(code: str) -> str:
    """Execute Python code in a subprocess and return stdout/stderr."""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            result = subprocess.run(
                [sys.executable, f.name],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=os.path.dirname(f.name)
            )
        os.unlink(f.name)
        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
        if result.returncode != 0:
            output += f"Exit code: {result.returncode}\n"
        return output.strip() or "✅ Code executed successfully (no output)."
    except subprocess.TimeoutExpired:
        return "❌ Code execution timed out (30s limit)."
    except Exception as e:
        return f"❌ Error executing code: {str(e)}"

# ─────────────────────────────────────────────
# 5. SHELL COMMANDS
# ─────────────────────────────────────────────
def run_shell_command(command: str) -> str:
    """Execute a shell command and return the output."""
    try:
        result = subprocess.run(
            command, shell=True,
            capture_output=True, text=True,
            timeout=30
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n(stderr): {result.stderr}"
        return output.strip()[:3000] or "✅ Command completed (no output)."
    except subprocess.TimeoutExpired:
        return "❌ Command timed out (30s limit)."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ─────────────────────────────────────────────
# 6. THINKING / REASONING SCRATCHPAD
# ─────────────────────────────────────────────
def think(thought: str) -> str:
    """Internal reasoning scratchpad. Use this to plan multi-step tasks before acting."""
    return f"💭 Thought recorded: {thought}"


# ═════════════════════════════════════════════
# TOOL REGISTRY
# ═════════════════════════════════════════════
TOOLS = {
    "google_search": google_search,
    "fetch_url": fetch_url,
    "write_file": write_file,
    "read_file": read_file,
    "list_files": list_files,
    "create_directory": create_directory,
    "run_python_code": run_python_code,
    "run_shell_command": run_shell_command,
    "think": think,
}

TOOL_SCHEMAS = [
    {
        "name": "google_search",
        "description": "Search the web for information. Returns titles, URLs, and snippets.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_url",
        "description": "Fetch a web page and extract its text content. Useful for reading articles, documentation, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch."}
            },
            "required": ["url"]
        }
    },
    {
        "name": "write_file",
        "description": "Write text content to a file. Creates parent directories automatically.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "The file path to write to."},
                "content": {"type": "string", "description": "The text content to write."}
            },
            "required": ["filename", "content"]
        }
    },
    {
        "name": "read_file",
        "description": "Read the content of a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "The file path to read."}
            },
            "required": ["filename"]
        }
    },
    {
        "name": "list_files",
        "description": "List files and folders in a directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory path (default: current dir)."}
            }
        }
    },
    {
        "name": "create_directory",
        "description": "Create a new directory and any parent directories.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The directory path to create."}
            },
            "required": ["path"]
        }
    },
    {
        "name": "run_python_code",
        "description": "Execute Python code and return the output. Use this for calculations, data processing, generating content, or any programmatic task.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The Python code to execute."}
            },
            "required": ["code"]
        }
    },
    {
        "name": "run_shell_command",
        "description": "Execute a shell command (bash) and return the output. Useful for system tasks, installing packages, git operations, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."}
            },
            "required": ["command"]
        }
    },
    {
        "name": "think",
        "description": "Internal reasoning scratchpad. Use this to plan complex multi-step tasks BEFORE taking action. No side effects.",
        "parameters": {
            "type": "object",
            "properties": {
                "thought": {"type": "string", "description": "Your internal reasoning, plan, or analysis."}
            },
            "required": ["thought"]
        }
    }
]
