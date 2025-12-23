import os


def load_prompt_template(template_name: str) -> str:
    """
    Loads a prompt template from rag_builder/llm/prompts/.
    """
    base_dir = os.path.join(os.path.dirname(__file__), "prompts")
    prompt_path = os.path.join(base_dir, template_name)
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()
