import json
import sys
import os
from pathlib import Path

def pos_to_rc(p):
    return int(p[1:])-1,ord(p[0])-97

def same_action(a,b):
    if a is None or b is None:
        return False
    if a.get("action")!=b.get("action"):
        return False
    if a.get("action")=="move":
        return a.get("to")==b.get("to")
    if a.get("action")=="wall":
        return a.get("at")==b.get("at") and a.get("orientation")==b.get("orientation")
    return False

def with_type(a):
    b=dict(a)
    b["type"]="action"
    return b

def fallback_score(state,a):
    you=state["you"]
    op="P2" if you=="P1" else "P1"

    if a["action"]=="move":
        r,c=pos_to_rc(a["to"])
        return r if you=="P1" else -r

    r,c=pos_to_rc(a["at"])
    pr,pc=pos_to_rc(state["pawns"][op])

    score=0

    if abs(c-pc)<=1:
        score+=2

    if op=="P1" and r>=pr:
        score+=2

    if op=="P2" and r<=pr:
        score+=2

    score-=0.04*len(state.get("walls",[]))

    return score

agent=None

try:
    from model import QTableAgent
    p=Path(__file__).with_name("model1000.pkl")
    if p.exists():
        agent=QTableAgent.load(str(p))
        agent.epsilon=0.0
except Exception:
    agent=None

def choose(state):
    legal=state.get("legal_actions",[])

    if not legal:
        return {"action":"move","to":state["pawns"][state["you"]]}

    if agent is not None:
        try:
            a=agent.choose_action(state,training=False)

            for x in legal:
                if same_action(a,x):
                    return x

        except Exception:
            pass

    return max(legal,key=lambda a:fallback_score(state,a))

def main():
    for line in sys.stdin:
        try:
            state=json.loads(line)
            action=choose(state)
            action=with_type(action)
            print(json.dumps(action,separators=(",",":")),flush=True)

        except Exception as e:
            print("error:",e,file=sys.stderr,flush=True)

            try:
                state=json.loads(line)
                legal=state.get("legal_actions",[])
                if legal:
                    action=with_type(legal[0])
                    print(json.dumps(action,separators=(",",":")),flush=True)
                else:
                    you=state.get("you","P1")
                    pos=state.get("pawns",{}).get(you,"e1")
                    print(json.dumps({"type":"action","action":"move","to":pos},separators=(",",":")),flush=True)

            except Exception:
                print(json.dumps({"type":"action","action":"move","to":"e1"},separators=(",",":")),flush=True)

if __name__=="__main__":
    main()