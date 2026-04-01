import os
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from agent_core import MultiModelAgent
from dotenv import load_dotenv

load_dotenv()

console = Console()

def main():
    console.print(Panel.fit(
        "[bold cyan]Multi-Model Agent (Qwen 2.5 / OpenRouter)[/bold cyan]\n"
        "Type 'exit' to quit. Type 'model <name>' to change model.",
        title="Welcome",
        subtitle="Version 0.1"
    ))
    
    agent = MultiModelAgent()
    
    while True:
        user_input = Prompt.ask("[bold green]You[/bold green]")
        
        if user_input.lower() in ["exit", "quit"]:
            break
            
        if user_input.lower().startswith("model "):
            new_model = user_input.split(" ", 1)[1]
            agent.model = f"openrouter/{new_model}"
            console.print(f"[yellow]Changed model to: {agent.model}[/yellow]")
            continue
            
        with console.status("[bold blue]Agent is thinking...[/bold blue]"):
            response = agent.chat(user_input)
            
        console.print(Panel(response, title="[bold magenta]Agent[/bold magenta]", border_style="magenta"))

if __name__ == "__main__":
    main()
