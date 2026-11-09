"""Run from the plugin checkout: python hermie_cli.py status|feed|play|rest|rename."""
import argparse
import json
from hermie import interact, status

def main():
    p = argparse.ArgumentParser(description="Hermie virtual pet")
    p.add_argument("action", choices=["status", "feed", "play", "rest", "rename"])
    p.add_argument("name", nargs="?")
    args = p.parse_args()
    result = status() if args.action == "status" else interact(args.action, args.name)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
