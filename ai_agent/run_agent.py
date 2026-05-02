#!/usr/bin/env python3
"""
AI Agent Runner for CRM Integration
Sets up environment variables and runs the AI agent
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from ai_agent.main import main

if __name__ == "__main__":
    main()
