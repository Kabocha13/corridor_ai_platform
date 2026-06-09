import sys
import json
from collections import deque

N=9
COLS="abcdefghi"
INF=10**9

def pos_to_xy(p):
    if isinstance(p,str):
        s=p.strip().lower()
        if len(s)>=2:
            x=COLS.find(s[0])
            try:
                y=int(s[1:])-1
            except:
                return None
            if 0<=x<N and 0<=y<N:
                return (x,y)
    if isinstance(p,dict):
        for k in ("at","to","pos","position","cell"):
            if k in p:
                r=pos_to_xy(p[k])
                if r is not None:
                    return r
        if "x" in p and "y" in p:
            try:
                x=int(p["x"])
                y=int(p["y"])
                if 0<=x<N and 0<=y<N:
                    return (x,y)
                if 1<=x<=N and 1<=y<=N:
                    return (x-1,y-1)
            except:
                pass
    if isinstance(p,(list,tuple)) and len(p)>=2:
        try:
            x=int(p[0])
            y=int(p[1])
            if 0<=x<N and 0<=y<N:
                return (x,y)
            if 1<=x<=N and 1<=y<=N:
                return (x-1,y-1)
        except:
            pass
    return None

def xy_to_pos(x,y):
    return COLS[x]+str(y+1)

def action_kind(a):
    if isinstance(a,dict) and a.get("action") in ("move","wall"):
        return a.get("action")
    return None

def wall_key(a):
    if not isinstance(a,dict) or a.get("action")!="wall":
        return None
    p=pos_to_xy(a.get("at"))
    o=a.get("orientation")
    if isinstance(o,str):
        o=o.lower()[:1]
    if p is None or o not in ("h","v"):
        return None
    return (xy_to_pos(p[0],p[1]),o)

def parse_wall(w):
    if isinstance(w,dict):
        p=pos_to_xy(w.get("at") or w.get("pos") or w.get("position") or w.get("cell"))
        o=w.get("orientation") or w.get("dir")
        if isinstance(o,str):
            o=o.lower()[:1]
        if p is not None and o in ("h","v"):
            return (p[0],p[1],o)
    if isinstance(w,str):
        s=w.strip().lower().replace("_","").replace("-","").replace(" ","")
        o=None
        if s.endswith("h") or s.endswith("v"):
            o=s[-1]
            s=s[:-1]
        elif s.startswith("h") or s.startswith("v"):
            o=s[0]
            s=s[1:]
        p=pos_to_xy(s)
        if p is not None and o in ("h","v"):
            return (p[0],p[1],o)
    return None

def build_blocks(walls):
    b=set()
    if not isinstance(walls,list):
        return b
    for w in walls:
        t=parse_wall(w)
        if t is None:
            continue
        x,y,o=t
        if not (0<=x<N-1 and 0<=y<N-1):
            continue
        if o=="h":
            b.add(((x,y),(x,y+1)))
            b.add(((x+1,y),(x+1,y+1)))
        else:
            b.add(((x,y),(x+1,y)))
            b.add(((x,y+1),(x+1,y+1)))
    return b

def is_blocked(b,a,c):
    return (a,c) in b or (c,a) in b

def neighbors(p,b):
    x,y=p
    r=[]
    for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)):
        q=(x+dx,y+dy)
        if 0<=q[0]<N and 0<=q[1]<N and not is_blocked(b,p,q):
            r.append(q)
    return r

def goal_y(player):
    return N-1 if player=="P1" else 0

def goal_dir(player):
    return 1 if player=="P1" else -1

def advancement(player,p):
    if p is None:
        return 0
    return p[1] if player=="P1" else N-1-p[1]

def dist_to_goal(start,player,b):
    if start is None:
        return 99
    gy=goal_y(player)
    q=deque([start])
    d={start:0}
    while q:
        p=q.popleft()
        if p[1]==gy:
            return d[p]
        ns=neighbors(p,b)
        ns.sort(key=lambda z:(abs(z[0]-4),-z[1] if player=="P1" else z[1]))
        for n in ns:
            if n not in d:
                d[n]=d[p]+1
                q.append(n)
    return 99

def shortest_path(start,player,b):
    if start is None:
        return []
    gy=goal_y(player)
    q=deque([start])
    prev={start:None}
    while q:
        p=q.popleft()
        if p[1]==gy:
            path=[]
            while p is not None:
                path.append(p)
                p=prev[p]
            path.reverse()
            return path
        ns=neighbors(p,b)
        ns.sort(key=lambda z:(abs(z[0]-4),-z[1] if player=="P1" else z[1]))
        for n in ns:
            if n not in prev:
                prev[n]=p
                q.append(n)
    return []

def shortest_path_count(start,player,b,cap=300):
    if start is None:
        return cap
    gy=goal_y(player)
    q=deque([start])
    d={start:0}
    cnt={start:1}
    best=None
    total=0
    while q:
        p=q.popleft()
        if best is not None and d[p]>best:
            continue
        if p[1]==gy:
            best=d[p]
            total=min(cap,total+cnt[p])
            continue
        for n in neighbors(p,b):
            nd=d[p]+1
            if best is not None and nd>best:
                continue
            if n not in d:
                d[n]=nd
                cnt[n]=cnt[p]
                q.append(n)
            elif d[n]==nd:
                cnt[n]=min(cap,cnt[n]+cnt[p])
    return max(1,total) if total else cap

def remaining_walls(rem,you):
    if isinstance(rem,dict):
        try:
            return int(rem.get(you,0))
        except:
            return 0
    try:
        return int(rem)
    except:
        return 0

def legal_output(a):
    if not isinstance(a,dict):
        return {"type":"action","action":"move","to":"e1"}
    if a.get("action")=="move":
        return {"type":"action","action":"move","to":a.get("to")}
    if a.get("action")=="wall":
        return {"type":"action","action":"wall","at":a.get("at"),"orientation":a.get("orientation")}
    r=dict(a)
    r["type"]="action"
    return r

def add_wall_blocks(walls,a):
    nw=list(walls) if isinstance(walls,list) else []
    nw.append({"at":a.get("at"),"orientation":a.get("orientation")})
    return build_blocks(nw)

def center_bonus(p):
    if p is None:
        return 0
    x,y=p
    return 18-4*(abs(x-4)+abs(y-4))

def blocks_path_bonus(a,path):
    p=pos_to_xy(a.get("at"))
    o=a.get("orientation")
    if isinstance(o,str):
        o=o.lower()[:1]
    if p is None or o not in ("h","v") or len(path)<2:
        return 0
    x,y=p
    es=set()
    if o=="h":
        es.add(((x,y),(x,y+1)))
        es.add(((x+1,y),(x+1,y+1)))
    else:
        es.add(((x,y),(x+1,y)))
        es.add(((x,y+1),(x+1,y+1)))
    s=0
    for i in range(len(path)-1):
        e=(path[i],path[i+1])
        if e in es or (e[1],e[0]) in es:
            s+=900
    return s

def shiller_rear_keys(you):
    if you=="P1":
        return [("e1","v"),("d1","v"),("f1","v"),("c1","v")]
    return [("d8","v"),("e8","v"),("c8","v"),("f8","v")]

def shiller_block_keys(you):
    if you=="P1":
        return [("d5","v"),("e5","v"),("d4","v"),("e4","v"),("c5","v"),("f5","v")]
    return [("e4","v"),("d4","v"),("e5","v"),("d5","v"),("f4","v"),("c4","v")]

def shiller_side_keys(you):
    if you=="P1":
        return [("e2","v"),("d2","v"),("e3","v"),("d3","v"),("e4","v"),("d4","v")]
    return [("d7","v"),("e7","v"),("d6","v"),("e6","v"),("d5","v"),("e5","v")]

def shiller_key_bonus(a,you,myp,oppp,total_walls):
    k=wall_key(a)
    if k is None:
        return 0
    adv=advancement(you,myp)
    rear=shiller_rear_keys(you)
    block=shiller_block_keys(you)
    side=shiller_side_keys(you)
    if k in rear:
        i=rear.index(k)
        s=9000-i*600
        if adv>=3:
            s+=6000
        if total_walls<=2:
            s+=4000
        if myp is not None and myp[0] in (3,4,5):
            s+=1200
        return s
    if k in block:
        i=block.index(k)
        return 3200-i*250
    if k in side:
        i=side.index(k)
        return 1800-i*180
    return 0

def pick_strict_shiller(valid,you,opp,myp,oppp,walls,b,myd,oppd,rem,total_walls):
    if rem<=0 or total_walls>3 or advancement(you,myp)<3:
        return None
    candidates=[]
    for a in valid:
        if action_kind(a)!="wall":
            continue
        k=wall_key(a)
        if k not in shiller_rear_keys(you):
            continue
        nb=add_wall_blocks(walls,a)
        nmy=dist_to_goal(myp,you,nb)
        nop=dist_to_goal(oppp,opp,nb)
        if nmy>=99 or nop>=99:
            continue
        my_loss=nmy-myd
        opp_loss=nop-oppd
        if my_loss<=0:
            candidates.append((shiller_key_bonus(a,you,myp,oppp,total_walls)+opp_loss*1000-my_loss*3000,a))
    if candidates:
        candidates.sort(key=lambda x:x[0],reverse=True)
        return candidates[0][1]
    return None

def move_score(a,you,myp,oppp,myd,b):
    to=pos_to_xy(a.get("to"))
    nd=dist_to_goal(to,you,b)
    s=0
    s+=(myd-nd)*1700
    s-=nd*220
    if myp is not None and to is not None:
        s+=(to[1]-myp[1])*goal_dir(you)*1250
        s+=center_bonus(to)*10
        if abs(to[0]-4)<=1:
            s+=120
    if oppp is not None and to is not None:
        md=abs(to[0]-oppp[0])+abs(to[1]-oppp[1])
        if md==1:
            s+=100
        elif md==0:
            s+=180
    if nd>=myd:
        s-=650
    return s

def wall_score(a,you,opp,myp,oppp,walls,b,myd,oppd,opp_path,rem,total_walls,my_path_count,opp_path_count):
    if rem<=0:
        return -INF
    nb=add_wall_blocks(walls,a)
    nmy=dist_to_goal(myp,you,nb)
    nop=dist_to_goal(oppp,opp,nb)
    if nmy>=99 or nop>=99:
        return -INF
    my_loss=nmy-myd
    opp_loss=nop-oppd
    gain=opp_loss-my_loss
    p=pos_to_xy(a.get("at"))
    nmy_paths=shortest_path_count(myp,you,nb)
    nop_paths=shortest_path_count(oppp,opp,nb)
    s=0
    s+=opp_loss*5200
    s-=my_loss*3600
    s+=gain*2300
    s+=(nop-nmy)*300
    s+=blocks_path_bonus(a,opp_path)
    s+=center_bonus(p)*16
    s+=shiller_key_bonus(a,you,myp,oppp,total_walls)
    s+=(my_path_count-nmy_paths)*35
    s+=(nop_paths-opp_path_count)*35
    if my_loss==0:
        s+=1300
    if opp_loss>=1:
        s+=4200
    if opp_loss>=2:
        s+=3500
    if gain>=1:
        s+=2200
    if gain<=0:
        s-=1100
    if oppd<=5:
        s+=3000
    elif oppd<=7:
        s+=1700
    if oppd<=myd+1:
        s+=2600
    if myd<=oppd-2:
        s-=1700
    if total_walls<2:
        s+=1200
    elif total_walls<6:
        s+=700
    return s

def choose_action(state):
    legal=state.get("legal_actions",[])
    if not isinstance(legal,list) or not legal:
        return {"action":"move","to":"e1"}
    valid=[a for a in legal if isinstance(a,dict) and action_kind(a) in ("move","wall")]
    if not valid:
        return legal[0] if isinstance(legal[0],dict) else {"action":"move","to":"e1"}

    you=state.get("you","P1")
    opp="P2" if you=="P1" else "P1"
    pawns=state.get("pawns",{})
    myp=pos_to_xy(pawns.get(you)) if isinstance(pawns,dict) else None
    oppp=pos_to_xy(pawns.get(opp)) if isinstance(pawns,dict) else None
    walls=state.get("walls",[])
    total_walls=len(walls) if isinstance(walls,list) else 0
    b=build_blocks(walls)
    myd=dist_to_goal(myp,you,b)
    oppd=dist_to_goal(oppp,opp,b)
    opp_path=shortest_path(oppp,opp,b)
    rem=remaining_walls(state.get("remaining_walls",0),you)

    strict=pick_strict_shiller(valid,you,opp,myp,oppp,walls,b,myd,oppd,rem,total_walls)
    if strict is not None:
        return strict

    moves=[a for a in valid if action_kind(a)=="move"]
    wall_actions=[a for a in valid if action_kind(a)=="wall"]

    best_move=None
    best_move_score=-INF
    for a in moves:
        s=move_score(a,you,myp,oppp,myd,b)
        s+=sum(ord(c) for c in json.dumps(a,sort_keys=True,ensure_ascii=False))%17
        if s>best_move_score:
            best_move_score=s
            best_move=a

    my_path_count=shortest_path_count(myp,you,b)
    opp_path_count=shortest_path_count(oppp,opp,b)
    best_wall=None
    best_wall_score=-INF
    for a in wall_actions:
        s=wall_score(a,you,opp,myp,oppp,walls,b,myd,oppd,opp_path,rem,total_walls,my_path_count,opp_path_count)
        s+=sum(ord(c) for c in json.dumps(a,sort_keys=True,ensure_ascii=False))%17
        if s>best_wall_score:
            best_wall_score=s
            best_wall=a

    if best_wall is not None and rem>0:
        force_wall=False
        if shiller_key_bonus(best_wall,you,myp,oppp,total_walls)>=4000 and best_wall_score>-5000:
            force_wall=True
        if total_walls<4 and advancement(you,myp)>=3 and best_wall_score>-3000:
            force_wall=True
        if oppd<=6 and best_wall_score>-2500:
            force_wall=True
        if oppd<=myd+1 and best_wall_score>-3000:
            force_wall=True
        if best_wall_score>=best_move_score-1800:
            force_wall=True
        if force_wall:
            return best_wall

    if best_move is not None:
        return best_move
    if best_wall is not None:
        return best_wall
    return valid[0]

def main():
    for line in sys.stdin:
        line=line.strip()
        if not line:
            continue
        state=None
        try:
            state=json.loads(line)
            chosen=choose_action(state)
            ans=legal_output(chosen)
        except Exception as e:
            print(str(e),file=sys.stderr,flush=True)
            try:
                legal=state.get("legal_actions",[]) if isinstance(state,dict) else []
                if isinstance(legal,list) and legal and isinstance(legal[0],dict):
                    ans=legal_output(legal[0])
                else:
                    ans={"type":"action","action":"move","to":"e1"}
            except:
                ans={"type":"action","action":"move","to":"e1"}
        print(json.dumps(ans,separators=(",",":"),ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()