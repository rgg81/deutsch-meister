"""Entry point: python -m nanobot <command> [options]"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(prog="nanobot", description="NanoBot agent runner")
    subparsers = parser.add_subparsers(dest="command")

    agent_parser = subparsers.add_parser("agent", help="Run the agent")
    agent_parser.add_argument("-m", "--message", default="", help="Initial message")

    args = parser.parse_args()

    if args.command == "agent":
        from nanobot.agent import Agent
        agent = Agent()
        agent.run(args.message)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
