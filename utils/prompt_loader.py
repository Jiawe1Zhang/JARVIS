from pathlib import Path

def load_prompt(prompt_name: str) -> str:
    """
    Load a prompt from the prompts/ directory.
    
    Args:
        prompt_name: The name of the prompt file (e.g., "agent_system.md").
        
    Returns:
        The content of the prompt file.
    """
    # Assuming prompts directory is in the root of the project
    # Adjust the path resolution logic if necessary based on where this function is called from
    root_dir = Path(__file__).resolve().parent.parent
    prompt_path = root_dir / "prompts" / prompt_name
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()
