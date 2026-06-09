import sys,json,random,time,math
from collections import deque

N=9
DIRS=[(-1,0),(1,0),(0,-1),(0,1)]
INF=10**9
SIMS=180
TIME_LIMIT=0.85
C=1.4

def eprint(*a):
    print(*a,file=sys.stderr,flush=True)

def pos_to_rc(s):
    if isinstance(s,(list,tuple)):
        return int(s[0]),int(s[1])
    if isinstance(s,dict):
        if "row" in s and "col" in s:
            return int(s["row"]),int(s["col"])
        if "r" in s and "c" in s:
            return int(s["r"]),int(s["c"])
    s=str(s).strip().lower()
    c=ord(s[0])-97
    r=int(s[1:])-1
    return r,c

def rc_to_pos(r,c):
    return chr(97+c)+str(r+1)

def norm_action(a):
    if isinstance(a,str):
        return {"type":"action","action":"move","to":a}
    b=dict(a)
    if "type" not in b:
        b["type"]="action"
    return b

def action_key(a):
    a=norm_action(a)
    if a.get("action")=="move":
        return ("m",a.get("to"))
    return ("w",a.get("at"),a.get("orientation"))

def same_action(a,b):
    return action_key(a)==action_key(b)

def get_player_ids(state):
    you=state.get("you","P1")
    opp="P2" if you=="P1" else "P1"
    return you,opp

def get_pawn(state,p):
    x=state.get("pawns",{}).get(p)
    if x is None:
        return None
    return pos_to_rc(x)

def parse_walls(state):
    walls=[]
    for w in state.get("walls",[]):
        if isinstance(w,dict):
            at=w.get("at") or w.get("position") or w.get("pos")
            o=w.get("orientation") or w.get("dir")
            if at is not None and o is not None:
                r,c=pos_to_rc(at)
                walls.append((r,c,str(o).lower()[0]))
        elif isinstance(w,(list,tuple)) and len(w)>=3:
            r,c=pos_to_rc(w[0])
            walls.append((r,c,str(w[1]).lower()[0]))
    return walls

def blocked_edges_from_walls(walls):
    b=set()
    for r,c,o in walls:
        if o=="h":
            for dc in (0,1):
                a=(r,c+dc)
                z=(r+1,c+dc)
                if 0<=a[0]<N and 0<=a[1]<N and 0<=z[0]<N and 0<=z[1]<N:
                    b.add((a,z))
                    b.add((z,a))
        else:
            for dr in (0,1):
                a=(r+dr,c)
                z=(r+dr,c+1)
                if 0<=a[0]<N and 0<=a[1]<N and 0<=z[0]<N and 0<=z[1]<N:
                    b.add((a,z))
                    b.add((z,a))
    return b

def infer_goal(state,p):
    r,c=get_pawn(state,p)
    if p=="P1":
        return 8
    return 0

def neighbors(r,c,blocked):
    for dr,dc in DIRS:
        nr,nc=r+dr,c+dc
        if 0<=nr<N and 0<=nc<N and ((r,c),(nr,nc)) not in blocked:
            yield nr,nc

def shortest_dist(start,goal,blocked):
    q=deque([start])
    d={start:0}
    while q:
        r,c=q.popleft()
        if r==goal:
            return d[(r,c)]
        for nr,nc in neighbors(r,c,blocked):
            if (nr,nc) not in d:
                d[(nr,nc)]=d[(r,c)]+1
                q.append((nr,nc))
    return INF

def shortest_nexts(start,goal,blocked,legal_moves):
    best=[]
    bd=INF
    for a in legal_moves:
        if norm_action(a).get("action")!="move":
            continue
        r,c=pos_to_rc(norm_action(a).get("to"))
        d=shortest_dist((r,c),goal,blocked)
        if d<bd:
            bd=d
            best=[a]
        elif d==bd:
            best.append(a)
    return best

def classify_actions(state):
    legal=[norm_action(a) for a in state.get("legal_actions",[])]
    moves=[a for a in legal if a.get("action")=="move"]
    walls=[a for a in legal if a.get("action")=="wall"]
    return legal,moves,walls

def wall_after(walls,a):
    a=norm_action(a)
    if a.get("action")!="wall":
        return walls
    r,c=pos_to_rc(a.get("at"))
    o=str(a.get("orientation")).lower()[0]
    return walls+[(r,c,o)]

def wall_features(state,a):
    you,opp=get_player_ids(state)
    my=get_pawn(state,you)
    op=get_pawn(state,opp)
    walls=parse_walls(state)
    b0=blocked_edges_from_walls(walls)
    md0=shortest_dist(my,infer_goal(state,you),b0)
    od0=shortest_dist(op,infer_goal(state,opp),b0)
    nw=wall_after(walls,a)
    b1=blocked_edges_from_walls(nw)
    md1=shortest_dist(my,infer_goal(state,you),b1)
    od1=shortest_dist(op,infer_goal(state,opp),b1)
    if md1>=INF or od1>=INF:
        return -INF
    gain=(od1-od0)*2.4-(md1-md0)*1.7
    ar,ac=pos_to_rc(norm_action(a).get("at"))
    orow,ocol=op
    mrow,mcol=my
    near_opp=max(0,4-(abs(ar-orow)+abs(ac-ocol)))*0.25
    near_me=max(0,3-(abs(ar-mrow)+abs(ac-mcol)))*0.08
    center=-(abs(ac-3.5))*0.03
    return gain+near_opp+near_me+center

def heuristic_score(state,a):
    you,opp=get_player_ids(state)
    my=get_pawn(state,you)
    op=get_pawn(state,opp)
    walls=parse_walls(state)
    blocked=blocked_edges_from_walls(walls)
    my_goal=infer_goal(state,you)
    op_goal=infer_goal(state,opp)
    md0=shortest_dist(my,my_goal,blocked)
    od0=shortest_dist(op,op_goal,blocked)
    a=norm_action(a)
    if a.get("action")=="move":
        nr,nc=pos_to_rc(a.get("to"))
        md=shortest_dist((nr,nc),my_goal,blocked)
        forward=md0-md
        side_penalty=abs(nc-4)*0.035
        return (od0-md)*1.8+forward*2.0-side_penalty+random.random()*0.01
    s=wall_features(state,a)
    remain=state.get("remaining_walls",{}).get(you,10)
    if remain<=0:
        return -INF
    if md0<=2:
        s-=4
    if od0<=3:
        s+=1.2
    return s+random.random()*0.01

def choose_candidate_actions(state):
    legal,moves,walls=classify_actions(state)
    if not legal:
        return []
    you,opp=get_player_ids(state)
    blocked=blocked_edges_from_walls(parse_walls(state))
    sm=shortest_nexts(get_pawn(state,you),infer_goal(state,you),blocked,moves)
    scored=[]
    for a in legal:
        scored.append((heuristic_score(state,a),a))
    scored.sort(key=lambda x:x[0],reverse=True)
    cand=[a for _,a in scored[:18]]
    for a in sm:
        if not any(same_action(a,x) for x in cand):
            cand.append(a)
    return cand or legal

def light_apply(state,a):
    s={
        "you":state.get("you","P1"),
        "pawns":dict(state.get("pawns",{})),
        "walls":list(state.get("walls",[])),
        "remaining_walls":json.loads(json.dumps(state.get("remaining_walls",{}))),
        "legal_actions":[]
    }
    you,opp=get_player_ids(state)
    a=norm_action(a)
    if a.get("action")=="move":
        s["pawns"][you]=a.get("to")
    else:
        s["walls"].append({"at":a.get("at"),"orientation":a.get("orientation")})
        if you in s["remaining_walls"]:
            s["remaining_walls"][you]=max(0,s["remaining_walls"][you]-1)
    s["you"]=opp
    return s

def terminal_value(state,root_you):
    you,opp=get_player_ids(state)
    for p in ("P1","P2"):
        pos=get_pawn(state,p)
        if pos is not None and pos[0]==infer_goal(state,p):
            return 1.0 if p==root_you else 0.0
    return None

def pseudo_legal_actions(state):
    legal=state.get("legal_actions")
    if legal:
        return [norm_action(a) for a in legal]
    you,opp=get_player_ids(state)
    my=get_pawn(state,you)
    op=get_pawn(state,opp)
    blocked=blocked_edges_from_walls(parse_walls(state))
    acts=[]
    for nr,nc in neighbors(my[0],my[1],blocked):
        if (nr,nc)==op:
            jr,jc=nr+(nr-my[0]),nc+(nc-my[1])
            if 0<=jr<N and 0<=jc<N and ((nr,nc),(jr,jc)) not in blocked:
                acts.append({"type":"action","action":"move","to":rc_to_pos(jr,jc)})
            else:
                for ar,ac in neighbors(nr,nc,blocked):
                    if (ar,ac)!=my:
                        acts.append({"type":"action","action":"move","to":rc_to_pos(ar,ac)})
        else:
            acts.append({"type":"action","action":"move","to":rc_to_pos(nr,nc)})
    return acts

def rollout(state,root_you,depth=34):
    s=json.loads(json.dumps(state))
    for _ in range(depth):
        v=terminal_value(s,root_you)
        if v is not None:
            return v
        acts=pseudo_legal_actions(s)
        if not acts:
            break
        if random.random()<0.78:
            a=max(acts,key=lambda x:heuristic_score(s,x))
        else:
            a=random.choice(acts)
        s=light_apply(s,a)
    you,opp=get_player_ids(s)
    blocked=blocked_edges_from_walls(parse_walls(s))
    d_root=shortest_dist(get_pawn(s,root_you),infer_goal(s,root_you),blocked)
    other="P2" if root_you=="P1" else "P1"
    d_other=shortest_dist(get_pawn(s,other),infer_goal(s,other),blocked)
    return 1/(1+math.exp((d_root-d_other)*0.9))

class Node:
    __slots__=("parent","action","children","untried","wins","visits")
    def __init__(self,parent=None,action=None,untried=None):
        self.parent=parent
        self.action=action
        self.children=[]
        self.untried=untried or []
        self.wins=0.0
        self.visits=0

    def uct_child(self):
        logp=math.log(max(1,self.visits))
        return max(self.children,key=lambda n:n.wins/max(1,n.visits)+C*math.sqrt(logp/max(1,n.visits))+random.random()*1e-9)

def mcts(state):
    root_you=state.get("you","P1")
    root=Node(untried=choose_candidate_actions(state))
    deadline=time.time()+TIME_LIMIT
    sims=0
    while sims<SIMS and time.time()<deadline:
        s=json.loads(json.dumps(state))
        node=root
        while not node.untried and node.children:
            node=node.uct_child()
            s=light_apply(s,node.action)
        if node.untried:
            a=node.untried.pop(random.randrange(len(node.untried)))
            s=light_apply(s,a)
            child=Node(parent=node,action=a,untried=choose_candidate_actions(s))
            node.children.append(child)
            node=child
        result=rollout(s,root_you)
        while node is not None:
            node.visits+=1
            node.wins+=result
            result=1.0-result
            node=node.parent
        sims+=1
    if not root.children:
        legal=state.get("legal_actions",[])
        return norm_action(random.choice(legal)) if legal else {"type":"action","action":"move","to":"e2"}
    return max(root.children,key=lambda n:(n.visits,n.wins/max(1,n.visits))).action

def opening_or_forced(state):
    legal,moves,walls=classify_actions(state)
    if not legal:
        return None
    you,opp=get_player_ids(state)
    blocked=blocked_edges_from_walls(parse_walls(state))
    my=get_pawn(state,you)
    op=get_pawn(state,opp)
    md=shortest_dist(my,infer_goal(state,you),blocked)
    od=shortest_dist(op,infer_goal(state,opp),blocked)
    sm=shortest_nexts(my,infer_goal(state,you),blocked,moves)
    if len(legal)==1:
        return legal[0]
    turn=state.get("turn",state.get("ply",0))
    if turn<2 and sm:
        return random.choice(sm)
    if md<=2 and sm:
        return random.choice(sm)
    if od<=2 and state.get("remaining_walls",{}).get(you,10)>0:
        ww=[a for a in walls if wall_features(state,a)>0.8]
        if ww:
            return max(ww,key=lambda a:wall_features(state,a))
    return None

def select_action(state):
    legal=[norm_action(a) for a in state.get("legal_actions",[])]
    if not legal:
        return {"type":"action","action":"move","to":"e2"}
    a=opening_or_forced(state)
    if a is None:
        try:
            a=mcts(state)
        except Exception as ex:
            eprint("fallback",repr(ex))
            a=max(legal,key=lambda x:heuristic_score(state,x))
    for x in legal:
        if same_action(a,x):
            return x
    return max(legal,key=lambda x:heuristic_score(state,x))

def main():
    random.seed()
    for line in sys.stdin:
        line=line.strip()
        if not line:
            continue
        try:
            state=json.loads(line)
            ans=select_action(state)
            print(json.dumps(ans,separators=(",",":")),flush=True)
        except Exception as ex:
            eprint("error",repr(ex))
            try:
                state=json.loads(line)
                legal=state.get("legal_actions",[])
                if legal:
                    print(json.dumps(norm_action(random.choice(legal)),separators=(",",":")),flush=True)
                else:
                    print(json.dumps({"type":"action","action":"move","to":"e2"},separators=(",",":")),flush=True)
            except Exception:
                print(json.dumps({"type":"action","action":"move","to":"e2"},separators=(",",":")),flush=True)

if __name__=="__main__":
    main()