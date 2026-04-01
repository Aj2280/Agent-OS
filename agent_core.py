import os
import json
from dotenv import load_dotenv
from litellm import completion
from tools import TOOLS, TOOL_SCHEMAS

load_dotenv()

SYSTEM_PROMPT = """You are Agent OS — an elite autonomous AI assistant capable of doing ANYTHING.

## Your Capabilities
You have access to powerful tools:
- **google_search**: Search the web for real-time information.
- **fetch_url**: Read web pages and extract content.
- **write_file**: Create and write files (code, documents, configs).
- **read_file**: Read existing files.
- **list_files**: Browse directories.
- **create_directory**: Create folders.
- **run_python_code**: Execute Python code for computation, data processing, or generation.
- **run_shell_command**: Run shell commands for system operations, git, installs, etc.
- **think**: Plan complex tasks internally before acting.

## Your Behavior
1. **ALWAYS think first** for complex tasks. Use the `think` tool to plan your approach.
2. **Be autonomous**: Complete multi-step tasks without asking the user for help.
3. **Be thorough**: When creating files, write complete, production-quality code.
4. **Be creative**: When asked to "create anything," build something impressive and functional.
5. **Handle errors gracefully**: If a tool fails, try an alternative approach.
6. **Provide clear summaries**: After completing a task, explain what you did.

## Output Style
- Use **markdown** formatting in your responses.
- Include code blocks with syntax highlighting when showing code.
- Be concise but comprehensive.
"""

# Provider configurations — how litellm routes to each provider
PROVIDER_CONFIG = {
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "prefix": "openrouter/",
        "models": [
            {"id": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 2.5 72B"},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet"},
            {"id": "anthropic/claude-3-haiku", "name": "Claude 3 Haiku"},
            {"id": "openai/gpt-4o", "name": "GPT-4o"},
            {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini"},
            {"id": "meta-llama/llama-3.1-70b-instruct", "name": "Llama 3.1 70B"},
            {"id": "google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash"},
        ]
    },
    "openai": {
        "name": "OpenAI",
        "base_url": None,  # litellm handles natively
        "env_key": "OPENAI_API_KEY",
        "prefix": "",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"},
        ]
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": None,
        "env_key": "GEMINI_API_KEY",
        "prefix": "gemini/",
        "models": [
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
        ]
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": None,
        "env_key": "ANTHROPIC_API_KEY",
        "prefix": "",
        "models": [
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
        ]
    },
    "groq": {
        "name": "Groq",
        "base_url": None,
        "env_key": "GROQ_API_KEY",
        "prefix": "groq/",
        "models": [
            {"id": "llama-3.1-70b-versatile", "name": "Llama 3.1 70B"},
            {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B"},
        ]
    },
    "ollama": {
        "name": "Ollama (Local)",
        "base_url": "http://localhost:11434",
        "env_key": None,
        "prefix": "ollama/",
        "models": [
            {"id": "llama3.1", "name": "Llama 3.1"},
            {"id": "mistral", "name": "Mistral"},
            {"id": "codellama", "name": "Code Llama"},
            {"id": "qwen2.5", "name": "Qwen 2.5"},
        ]
    },
    "lmstudio": {
        "name": "LM Studio (Local)",
        "base_url": "http://localhost:1234/v1",
        "env_key": None,
        "prefix": "openai/",
        "models": [
            {"id": "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF", "name": "Llama 3.1 8B"},
            {"id": "lmstudio-community/Qwen2.5-7B-Instruct-GGUF", "name": "Qwen 2.5 7B"},
            {"id": "lmstudio-community/Mistral-7B-Instruct-v0.3-GGUF", "name": "Mistral 7B"},
        ]
    },
}


class MultiModelAgent:
    MAX_ITERATIONS = 15

    def __init__(self, model: str = None):
        self.model = model or os.getenv("DEFAULT_MODEL", "openrouter/qwen/qwen-2.5-72b-instruct")
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.tool_logs = []

        # Store API keys per provider
        self.api_keys = {}
        for pid, pconfig in PROVIDER_CONFIG.items():
            env_key = pconfig.get("env_key")
            if env_key:
                val = os.getenv(env_key)
                if val:
                    self.api_keys[pid] = val

        # Custom models added by user
        self.custom_models = []

    def get_provider_for_model(self, model_str: str):
        """Determine which provider a model string belongs to."""
        for pid, pconfig in PROVIDER_CONFIG.items():
            prefix = pconfig.get("prefix", "")
            if prefix and model_str.startswith(prefix):
                return pid
        # Check by known name patterns
        if model_str.startswith("gpt-") or model_str.startswith("o1-"):
            return "openai"
        if model_str.startswith("claude-"):
            return "anthropic"
        if model_str.startswith("gemini"):
            return "gemini"
        if model_str.startswith("groq/"):
            return "groq"
        if model_str.startswith("ollama/"):
            return "ollama"
        if model_str.startswith("openrouter/"):
            return "openrouter"
        return "openrouter"  # default fallback

    def get_completion_params(self, model_str: str):
        """Get the right api_key, base_url, and model name for litellm."""
        provider = self.get_provider_for_model(model_str)
        pconfig = PROVIDER_CONFIG.get(provider, {})

        params = {"model": model_str}

        # Set API key
        api_key = self.api_keys.get(provider)
        if api_key:
            params["api_key"] = api_key

        # Set base URL
        base_url = pconfig.get("base_url")
        if base_url:
            params["base_url"] = base_url

        return params

    def reset(self):
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.tool_logs = []

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def chat(self, user_input: str):
        self.add_message("user", user_input)
        self.tool_logs = []
        iterations = 0

        while iterations < self.MAX_ITERATIONS:
            iterations += 1

            try:
                params = self.get_completion_params(self.model)
                response = completion(
                    **params,
                    messages=self.history,
                    tools=[{"type": "function", "function": s} for s in TOOL_SCHEMAS],
                    tool_choice="auto",
                )
            except Exception as e:
                error_msg = f"❌ API Error: {str(e)}"
                self.add_message("assistant", error_msg)
                return error_msg

            message = response.choices[0].message
            self.history.append(message)

            if not message.tool_calls:
                return message.content

            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                log_entry = {"name": function_name, "args": {}, "result": "", "status": "running"}
                self.tool_logs.append(log_entry)

                try:
                    function_args = json.loads(tool_call.function.arguments)
                    log_entry["args"] = function_args
                except json.JSONDecodeError:
                    log_entry["result"] = "❌ Invalid JSON arguments"
                    log_entry["status"] = "error"
                    self.history.append({
                        "role": "tool", "tool_call_id": tool_call.id,
                        "name": function_name, "content": "Error: Could not parse arguments."
                    })
                    continue

                if function_name not in TOOLS:
                    log_entry["result"] = f"❌ Unknown tool: {function_name}"
                    log_entry["status"] = "error"
                    self.history.append({
                        "role": "tool", "tool_call_id": tool_call.id,
                        "name": function_name, "content": f"Error: Unknown tool '{function_name}'."
                    })
                    continue

                print(f"  🔧 [{iterations}] {function_name}({json.dumps(function_args)[:80]})")

                try:
                    observation = TOOLS[function_name](**function_args)
                    log_entry["result"] = str(observation)[:500]
                    log_entry["status"] = "success"
                except Exception as e:
                    observation = f"❌ Tool error: {str(e)}"
                    log_entry["result"] = observation
                    log_entry["status"] = "error"

                self.history.append({
                    "role": "tool", "tool_call_id": tool_call.id,
                    "name": function_name, "content": str(observation)
                })

        return "⚠️ Reached maximum iterations. Task may be partially complete."
