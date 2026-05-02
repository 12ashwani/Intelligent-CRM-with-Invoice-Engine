from ai_agent.agent.agent import run_agent


def format_response(reply):
    """Format output nicely for terminal display."""

    if not reply:
        return "No data found."

    # If list of records
    if isinstance(reply, list):
        formatted = []

        for i, item in enumerate(reply, 1):
            if isinstance(item, dict):
                formatted.append(f"\nRecord {i}:")
                for k, v in item.items():
                    formatted.append(f"  {k}: {v}")
            else:
                formatted.append(str(item))

        return "\n".join(formatted)

    # If dictionary
    elif isinstance(reply, dict):
        formatted = []

        for key, value in reply.items():
            formatted.append(f"\n{key.upper()}:")

            if isinstance(value, list):
                for i, v in enumerate(value, 1):
                    formatted.append(f"  {i}. {v}")
            else:
                formatted.append(f"  {value}")

        return "\n".join(formatted)

    # If plain text
    return str(reply)


def main():
    """CLI Chat Interface"""

    print("=== AI CRM Assistant Started ===")

    while True:
        user = input("\nYou: ").strip()

        if user.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        result = run_agent(user)

        print("\nAI:", format_response(result.get("response")))


if __name__ == "__main__":
    main()