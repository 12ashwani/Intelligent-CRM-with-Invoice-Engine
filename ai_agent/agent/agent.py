'''AI Agent Service Module

This module serves as the main entry point for the AI assistant.
It takes raw user input, determines the appropriate action using the planner,
executes it via the executor, and returns a standardized response.

Key responsibilities:
- Input validation
- Action decision (via planner)
- Execution coordination (via executor)
- Consistent response formatting

Note: Context management, user role/access control, and advanced personalization
are handled at higher layers (routes/middleware) or inside the planner/executor.
'''


"""
agent/agent.py - Main agent entry point
"""

from typing import Dict, Any

from ai_agent.agent.planner import decide
from ai_agent.agent.executor import execute


def run_agent(user_input: str, role: str = "", employee_id: str = "") -> Dict[str, Any]:
    """Run the AI agent for a given user query"""
    
    if not user_input or not user_input.strip():
        return {
            "error": "Empty input",
            "response": "Please enter a valid query.",
            "input": user_input,
            "action": None,
            "source": None
        }
    
    action = decide(user_input)
    print(f"[AGENT] Action decided: {action}")
    
    result = execute(action, user_input, role=role, employee_id=employee_id)
    print(f"[AGENT] Result source: {result.get('source', 'unknown')}")
    
    return {
        "input": user_input,
        "action": action,
        "source": result.get("source"),
        "response": result.get("response"),
        "data": result.get("data"),
        "error": result.get("error")
    }
