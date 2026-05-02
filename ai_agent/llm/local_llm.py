"""
Local LLM wrapper using Ollama.
"""

try:
    import ollama
except ImportError:
    ollama = None

DEFAULT_MODEL = "gemma2:2b" # "llama3.2:1b" 

def ask_llm(prompt: str, model: str = DEFAULT_MODEL) -> str:
    if ollama is None:
        return (
            "The CRM tools are connected, but the optional 'ollama' package is not "
            "installed for general AI replies."
        )

    try:
        response = ollama.generate(model=model, prompt=prompt)
        return response["response"]
    except Exception as e:
        return f"I'm sorry, I encountered an error: {e}"
