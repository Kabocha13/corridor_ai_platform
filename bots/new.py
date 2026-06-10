#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 9x9 Quoridor-style tournament bot (Python standard library only).
# Protocol: read one JSON state per line from stdin,
# write exactly one {"type":"action", ...} JSON line to stdout (flushed).

import sys
import json
from collections import deque

N = 9
CELLS = N * N
GOAL_ROW = {"P1": N - 1, "P2": 0}
FWD = {"P1": 1, "P2": -1}


def parse_cell(s):
    s = str(s).strip().lower()
    c = ord(s[0]) - 97
    r = int(s[1:]) - 1
    if 0 <= c < N and 0 <= r < N:
        return r * N + c
    raise ValueError("bad cell")


def ekey(a, b):
    return (a, b) if a < b else (b, a)


def wall_edges(at, orientation):
    s = str(at).strip().lower()
    c = ord(s[0]) - 97
    r = int(s[1:]) - 1
    if not (0 <= c < N - 1 and 0 <= r < N - 1):
        raise ValueError("bad wall")
    base = r * N + c
    o = str(orientation).strip().lower()[:1]
    if o == "h":
        return (ekey(base, base + N), ekey(base + 1, base + N + 1))
    if o == "v":
        return (ekey(base, base + 1), ekey(base + N, base + N + 1))
    raise ValueError("bad orientation")


def bfs_field(sources, blocked):
    dist = [-1] * CELLS
    dq = deque()
    for i in sources:
        if dist[i] < 0:
            dist[i] = 0
            dq.append(i)
    while dq:
        u = dq.popleft()
        nd = dist[u] + 1
        r = u // N
        c = u - r * N
        if r > 0:
            v = u - N
            if dist[v] < 0 and (v, u) not in blocked:
                dist[v] = nd
                dq.append(v)
        if r < N - 1:
            v = u + N
            if dist[v] < 0 and (u, v) not in blocked:
                dist[v] = nd
                dq.append(v)
        if c > 0:
            v = u - 1
            if dist[v] < 0 and (v, u) not in blocked:
                dist[v] = nd
                dq.append(v)
        if c < N - 1:
            v = u + 1
            if dist[v] < 0 and (u, v) not in blocked:
                dist[v] = nd
                dq.append(v)
    return dist


def goal_sources(row):
    s = row * N
    return range(s, s + N)


def make_action(a):
    act = a.get("action")
    if act == "move" and a.get("to") is not None:
        return {"type": "action", "action": "move", "to": a["to"]}
    if act == "wall" and a.get("at") is not None:
        return {"type": "action", "action": "wall", "at": a["at"], "orientation": a.get("orientation")}
    out = dict(a)
    out["type"] = "action"
    return out


def decide(state):
    legal = state.get("legal_actions")
    if not isinstance(legal, list) or not legal:
        return None

    me = state.get("you")
    if me not in ("P1", "P2"):
        t = state.get("turn")
        me = t if t in ("P1", "P2") else "P1"
    opp = "P2" if me == "P1" else "P1"

    pawns = state.get("pawns") or {}
    my_idx = parse_cell(pawns.get(me) or ("e1" if me == "P1" else "e9"))
    opp_idx = parse_cell(pawns.get(opp) or ("e9" if opp == "P2" else "e1"))

    blocked = set()
    for w in state.get("walls") or []:
        if not isinstance(w, dict):
            continue
        at = w.get("at") or w.get("position") or w.get("pos")
        o = w.get("orientation") or w.get("dir") or w.get("o")
        if at is None or o is None:
            continue
        try:
            e1, e2 = wall_edges(at, o)
        except Exception:
            continue
        blocked.add(e1)
        blocked.add(e2)

    moves = []
    wall_acts = []
    for a in legal:
        if not isinstance(a, dict):
            continue
        act = a.get("action")
        if act == "move" and a.get("to"):
            moves.append(a)
        elif act == "wall" and a.get("at") and a.get("orientation"):
            wall_acts.append(a)

    f_my = bfs_field(goal_sources(GOAL_ROW[me]), blocked)
    f_op = bfs_field(goal_sources(GOAL_ROW[opp]), blocked)
    my_d = f_my[my_idx]
    opp_d = f_op[opp_idx]
    if my_d < 0:
        my_d = 999
    if opp_d < 0:
        opp_d = 999

    rem = state.get("remaining_walls") or {}
    mw = rem.get(me)
    if mw is None:
        mw = 10 if wall_acts else 0
    try:
        mw = int(mw)
    except Exception:
        mw = 0

    # moves: minimize own shortest distance to goal after stepping
    best_move = None
    best_mkey = None
    fdir = FWD[opp]
    opp_r = opp_idx // N
    opp_c = opp_idx - opp_r * N
    front = -1
    fr = opp_r + fdir
    if 0 <= fr < N and ekey(opp_idx, fr * N + opp_c) not in blocked:
        front = fr * N + opp_c
    for a in moves:
        try:
            t = parse_cell(a["to"])
        except Exception:
            continue
        nd = f_my[t]
        if nd < 0:
            nd = 999
        s = float(nd)
        if t == front:  # standing right in front of the opponent lets them jump us
            br = opp_r + 2 * fdir
            if 0 <= br < N and ekey(t, br * N + opp_c) not in blocked:
                s += 0.45
            else:
                s += 0.15
        s += 0.01 * abs(t % N - 4)  # slight central preference as a tie-break
        key = (s, str(a["to"]))
        if best_mkey is None or key < best_mkey:
            best_mkey = key
            best_move = a

    # walls: evaluate only those cutting an edge of some current
    # shortest path of the opponent (others cannot slow them down)
    best_gain_wall = None
    bg_key = None
    bg_gain = bg_md = bg_od = 0
    best_block_wall = None
    bb_key = None
    bb_od = 0
    if mw > 0 and wall_acts and opp_d < 999 and my_d < 999:
        dp = bfs_field((opp_idx,), blocked)
        total = opp_d
        cands = []
        for a in wall_acts:
            try:
                e1, e2 = wall_edges(a["at"], a["orientation"])
            except Exception:
                continue
            on_path = False
            near = 99
            for (u, v) in (e1, e2):
                du = dp[u]
                dv = dp[v]
                gu = f_op[u]
                gv = f_op[v]
                if du >= 0 and gv >= 0 and du + 1 + gv == total:
                    on_path = True
                if dv >= 0 and gu >= 0 and dv + 1 + gu == total:
                    on_path = True
                if 0 <= du < near:
                    near = du
                if 0 <= dv < near:
                    near = dv
            if on_path:
                cands.append((near, str(a["at"]), str(a["orientation"]), a, e1, e2))
        cands.sort(key=lambda x: (x[0], x[1], x[2]))
        if len(cands) > 64:
            cands = cands[:64]
        gs_my = goal_sources(GOAL_ROW[me])
        gs_op = goal_sources(GOAL_ROW[opp])
        for near, at_s, o_s, a, e1, e2 in cands:
            nb = set(blocked)
            nb.add(e1)
            nb.add(e2)
            nmy = bfs_field(gs_my, nb)[my_idx]
            nop = bfs_field(gs_op, nb)[opp_idx]
            if nmy < 0 or nop < 0:
                continue
            md = nmy - my_d
            od = nop - opp_d
            gain = od - md
            k1 = (-gain, md, at_s, o_s)
            if bg_key is None or k1 < bg_key:
                bg_key = k1
                best_gain_wall = a
                bg_gain, bg_md, bg_od = gain, md, od
            k2 = (-od, md, at_s, o_s)
            if bb_key is None or k2 < bb_key:
                bb_key = k2
                best_block_wall = a
                bb_od = od

    # choose between best move and best wall
    if best_move is None and best_gain_wall is None:
        return make_action(legal[0])
    if best_move is None:
        return make_action(best_gain_wall)
    if best_gain_wall is None or mw <= 0:
        return make_action(best_move)

    margin = opp_d - my_d  # >= 0: we win a pure race because we move first
    if margin < 0:
        # Behind: a wall only changes the race if (od - md) >= 2,
        # since placing it costs us one tempo.
        if bg_gain >= 2:
            return make_action(best_gain_wall)
        if opp_d <= 2 and best_block_wall is not None and bb_od >= 1:
            return make_action(best_block_wall)
    else:
        # Ahead: mostly race, but in a tight race grab a cheap strong wall.
        if my_d > 2 and bg_md <= 0:
            if (margin <= 1 and bg_gain >= 2) or (margin <= 2 and bg_gain >= 3):
                return make_action(best_gain_wall)
    return make_action(best_move)


def main():
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            state = json.loads(line)
        except Exception:
            continue
        if not isinstance(state, dict):
            continue
        legal = state.get("legal_actions")
        if not isinstance(legal, list) or not legal:
            continue
        try:
            action = decide(state)
        except Exception:
            action = None
        if action is None:
            try:
                action = make_action(legal[0])
            except Exception:
                action = {"type": "action", "action": "move", "to": "e5"}
        try:
            out.write(json.dumps(action) + "\n")
            out.flush()
        except Exception:
            pass


if __name__ == "__main__":
    main()