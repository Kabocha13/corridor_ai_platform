import json
import random
import sys


def main() -> None:
    for line in sys.stdin:
        state = json.loads(line)
        action = random.choice(state["legal_actions"])
        action["type"] = "action"
        print(json.dumps(action), flush=True)


if __name__ == "__main__":
    main()
