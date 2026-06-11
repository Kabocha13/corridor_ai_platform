#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 9x9 Quoridor-style tournament bot v2.2 (Python standard library only).
# Iterative-deepening alpha-beta search with pruned wall candidates.
# Rule model (verified against tournament logs): there are NO jumps in this
# ruleset - the opponent's square is simply impassable, so body-blocking is
# a legal and important tactic.
# Protocol: read one JSON state per line from stdin,
# write exactly one {"type":"action", ...} JSON line to stdout (flushed).
# Time budget per move: env QBOT_TIME (seconds, default 4.0 for a 5s limit).

import sys
import os
import json
import time
from collections import deque

N = 9
CELLS = N * N
GOAL_ROW = (8, 0)  # index 0 = P1 (row 9), index 1 = P2 (row 1)
WIN = 100000.0
STEP_W = 10.0
WALL_W = 14.0
PROG_W = 1.0
TEMPO_W = 5.0
# body-block handling is done via effective distances in evaluate()
RESERVE_W = 6.0   # extra value for keeping at least one wall in hand
CAP_ROOT = 20
CAP_NODE = 10

try:
    TIME_BUDGET = float(os.environ.get("QBOT_TIME", "4.0"))
except Exception:
    TIME_BUDGET = 4.0

REP_W = 7.0           # penalty per recent visit to a square (anti-oscillation)
HIST = deque(maxlen=12)  # our recent pawn positions across turns
LAST_WALL_SIG = [None]   # wall layout signature; history resets when walls change


def parse_cell(s):
    s = str(s).strip().lower()
    c = ord(s[0]) - 97
    r = int(s[1:]) - 1
    if 0 <= c < N and 0 <= r < N:
        return r * N + c
    raise ValueError("bad cell")


def ekey(a, b):
    return (a, b) if a < b else (b, a)


def wall_edges_cr(c, r, o):
    base = r * N + c
    if o == "h":
        return (ekey(base, base + N), ekey(base + 1, base + N + 1))
    return (ekey(base, base + 1), ekey(base + N, base + N + 1))


def parse_wall(at, orientation):
    s = str(at).strip().lower()
    c = ord(s[0]) - 97
    r = int(s[1:]) - 1
    o = str(orientation).strip().lower()[:1]
    if not (0 <= c < N - 1 and 0 <= r < N - 1) or o not in ("h", "v"):
        raise ValueError("bad wall")
    return c, r, o


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
        if r < 8:
            v = u + N
            if dist[v] < 0 and (u, v) not in blocked:
                dist[v] = nd
                dq.append(v)
        if c > 0:
            v = u - 1
            if dist[v] < 0 and (v, u) not in blocked:
                dist[v] = nd
                dq.append(v)
        if c < 8:
            v = u + 1
            if dist[v] < 0 and (u, v) not in blocked:
                dist[v] = nd
                dq.append(v)
    return dist


def blocked_dist(start, goal_row, blocked, forbid):
    """Shortest distance to goal_row treating `forbid` (opponent pawn) as an obstacle."""
    if start // N == goal_row:
        return 0
    dist = [-1] * CELLS
    dist[start] = 0
    if 0 <= forbid < CELLS:
        dist[forbid] = -2
    dq = deque((start,))
    while dq:
        u = dq.popleft()
        nd = dist[u] + 1
        r = u // N
        c = u - r * N
        if r > 0:
            v = u - N
            if dist[v] == -1 and (v, u) not in blocked:
                if v // N == goal_row:
                    return nd
                dist[v] = nd
                dq.append(v)
        if r < 8:
            v = u + N
            if dist[v] == -1 and (u, v) not in blocked:
                if v // N == goal_row:
                    return nd
                dist[v] = nd
                dq.append(v)
        if c > 0:
            v = u - 1
            if dist[v] == -1 and (v, u) not in blocked:
                if v // N == goal_row:
                    return nd
                dist[v] = nd
                dq.append(v)
        if c < 8:
            v = u + 1
            if dist[v] == -1 and (u, v) not in blocked:
                if v // N == goal_row:
                    return nd
                dist[v] = nd
                dq.append(v)
    return -1


GOAL_SRC = (tuple(range(8 * N, 8 * N + N)), tuple(range(0, N)))


def make_action(a):
    act = a.get("action")
    if act == "move" and a.get("to") is not None:
        return {"type": "action", "action": "move", "to": a["to"]}
    if act == "wall" and a.get("at") is not None:
        return {"type": "action", "action": "wall", "at": a["at"], "orientation": a.get("orientation")}
    out = dict(a)
    out["type"] = "action"
    return out


class SearchTimeout(Exception):
    pass


class Searcher(object):
    def __init__(self, pos, rem, blocked, slots, deadline):
        self.pos = pos          # [P1_idx, P2_idx]
        self.rem = rem          # [P1_walls, P2_walls]
        self.blocked = blocked  # set of edge keys
        self.slots = slots      # set of (c, r, o) placed walls
        self.deadline = deadline
        self.nodes = 0
        self.fcache = {}

    def pawn_moves(self, m):
        # No jumps in this ruleset: the opponent's square is simply impassable.
        p = self.pos[m]
        q = self.pos[1 - m]
        blocked = self.blocked
        res = []
        pr, pc = divmod(p, N)
        if pr > 0:
            n = p - N
            if n != q and (n, p) not in blocked:
                res.append(n)
        if pr < 8:
            n = p + N
            if n != q and (p, n) not in blocked:
                res.append(n)
        if pc > 0:
            n = p - 1
            if n != q and (n, p) not in blocked:
                res.append(n)
        if pc < 8:
            n = p + 1
            if n != q and (p, n) not in blocked:
                res.append(n)
        return res

    def slot_ok(self, c, r, o):
        slots = self.slots
        if (c, r, "h") in slots or (c, r, "v") in slots:
            return False
        if o == "h":
            return (c - 1, r, "h") not in slots and (c + 1, r, "h") not in slots
        return (c, r - 1, "v") not in slots and (c, r + 1, "v") not in slots

    def wall_candidates(self, m, g_other, cap):
        # Walls that cut at least one edge of some current shortest path of
        # the other player; other walls cannot increase their distance.
        other = 1 - m
        dp = bfs_field((self.pos[other],), self.blocked)
        total = g_other[self.pos[other]]
        cands = []
        for c in range(8):
            for r in range(8):
                for o in ("h", "v"):
                    if not self.slot_ok(c, r, o):
                        continue
                    e1, e2 = wall_edges_cr(c, r, o)
                    on_path = False
                    near = 99
                    for (u, v) in (e1, e2):
                        du = dp[u]
                        dv = dp[v]
                        gu = g_other[u]
                        gv = g_other[v]
                        if du >= 0 and gv >= 0 and du + 1 + gv == total:
                            on_path = True
                        if dv >= 0 and gu >= 0 and dv + 1 + gu == total:
                            on_path = True
                        if 0 <= du < near:
                            near = du
                        if 0 <= dv < near:
                            near = dv
                    if on_path:
                        cands.append((near, c, r, o, e1, e2))
        cands.sort()
        return cands[:cap]

    def evaluate(self, m, d_me, d_op):
        # Body-block awareness: in this no-jump ruleset a pawn standing on a
        # 1-wide corridor can seal the opponent out completely. The plain
        # pawn-ignoring BFS distance is a lie in such positions, so replace
        # it with an "effective" distance.
        other = 1 - m
        de_me = d_me
        de_op = d_op
        if d_me <= 6:
            db = blocked_dist(self.pos[m], GOAL_ROW[m], self.blocked, self.pos[other])
            if db < 0:
                # fully sealed by the opponent pawn: realistically we only get
                # in after they have moved on, i.e. roughly when they finish
                de_me = max(d_me, d_op + 2)
            elif db > d_me:
                de_me = min(db, d_me + 4)
        if d_op <= 6:
            db = blocked_dist(self.pos[other], GOAL_ROW[other], self.blocked, self.pos[m])
            if db < 0:
                de_op = max(d_op, d_me + 2)
            elif db > d_op:
                de_op = min(db, d_op + 4)
        return (STEP_W * (de_op - de_me)
                - PROG_W * de_me
                + WALL_W * (self.rem[m] - self.rem[other])
                + RESERVE_W * ((1 if self.rem[m] > 0 else 0) - (1 if self.rem[other] > 0 else 0))
                + TEMPO_W)

    def negamax(self, m, depth, alpha, beta, ply):
        if time.time() > self.deadline:
            raise SearchTimeout()
        self.nodes += 1
        blocked = self.blocked
        fkey = frozenset(blocked)
        cached = self.fcache.get(fkey)
        if cached is None:
            g0 = bfs_field(GOAL_SRC[0], blocked)
            g1 = bfs_field(GOAL_SRC[1], blocked)
            if len(self.fcache) < 30000:
                self.fcache[fkey] = (g0, g1)
        else:
            g0, g1 = cached
        d_me = (g0 if m == 0 else g1)[self.pos[m]]
        d_op = (g1 if m == 0 else g0)[self.pos[1 - m]]
        if d_me < 0 or d_op < 0:
            return None  # the wall just placed by the parent is illegal
        if d_op == 0:
            return -(WIN - ply)
        if d_me == 0:
            return WIN - ply
        if depth <= 0:
            return self.evaluate(m, d_me, d_op)
        g_me = g0 if m == 0 else g1
        g_op = g1 if m == 0 else g0
        other = 1 - m
        goal_row = GOAL_ROW[m]
        best = None

        # pawn moves, nearest-to-goal first
        targets = self.pawn_moves(m)
        targets.sort(key=lambda t: (g_me[t] if g_me[t] >= 0 else 999, t))
        old = self.pos[m]
        for t in targets:
            self.pos[m] = t
            if t // N == goal_row:
                score = WIN - ply
            else:
                sc = self.negamax(other, depth - 1, -beta, -alpha, ply + 1)
                score = None if sc is None else -sc
            self.pos[m] = old
            if score is None:
                continue
            if best is None or score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                return best

        # wall placements
        if self.rem[m] > 0:
            for near, c, r, o, e1, e2 in self.wall_candidates(m, g_op, CAP_NODE):
                blocked.add(e1)
                blocked.add(e2)
                self.slots.add((c, r, o))
                self.rem[m] -= 1
                sc = self.negamax(other, depth - 1, -beta, -alpha, ply + 1)
                self.rem[m] += 1
                self.slots.discard((c, r, o))
                blocked.discard(e1)
                blocked.discard(e2)
                if sc is None:
                    continue
                score = -sc
                if best is None or score > best:
                    best = score
                if score > alpha:
                    alpha = score
                if alpha >= beta:
                    return best

        if best is None:
            # no legal action for the mover (fully boxed in): treat as a
            # heavily penalized stand-still rather than crashing
            return self.evaluate(m, d_me, d_op) - 2.0 * STEP_W
        return best


def search_decide(state, budget):
    legal = state["legal_actions"]
    me_s = state.get("you")
    if me_s not in ("P1", "P2"):
        t = state.get("turn")
        me_s = t if t in ("P1", "P2") else "P1"
    m = 0 if me_s == "P1" else 1
    pawns = state.get("pawns") or {}
    pos = [parse_cell(pawns.get("P1") or "e1"), parse_cell(pawns.get("P2") or "e9")]

    blocked = set()
    slots = set()
    for w in state.get("walls") or []:
        if not isinstance(w, dict):
            continue
        at = w.get("at") or w.get("position") or w.get("pos")
        o = w.get("orientation") or w.get("dir") or w.get("o")
        if at is None or o is None:
            continue
        try:
            c, r, oo = parse_wall(at, o)
        except Exception:
            continue
        e1, e2 = wall_edges_cr(c, r, oo)
        blocked.add(e1)
        blocked.add(e2)
        slots.add((c, r, oo))

    rem = [10, 10]
    rw = state.get("remaining_walls") or {}
    for i, k in enumerate(("P1", "P2")):
        try:
            rem[i] = int(rw.get(k, 10))
        except Exception:
            rem[i] = 10

    wall_sig = (len(slots), frozenset(slots))
    if wall_sig != LAST_WALL_SIG[0]:
        HIST.clear()  # board changed (new wall or new game): old revisit info is stale
        LAST_WALL_SIG[0] = wall_sig
    if not slots and pos[0] == parse_cell("e1") and pos[1] == parse_cell("e9") and rem == [10, 10]:
        HIST.clear()
    HIST.append(pos[m])

    g0 = bfs_field(GOAL_SRC[0], blocked)
    g1 = bfs_field(GOAL_SRC[1], blocked)
    g_me = g0 if m == 0 else g1
    g_op = g1 if m == 0 else g0
    my_d = g_me[pos[m]]
    opp_d = g_op[pos[1 - m]]
    if my_d < 0 or opp_d < 0:
        return None

    # parse root actions from the authoritative legal list
    root = []
    for a in legal:
        if not isinstance(a, dict):
            continue
        act = a.get("action")
        if act == "move" and a.get("to"):
            try:
                t = parse_cell(a["to"])
            except Exception:
                continue
            if t // N == GOAL_ROW[m]:
                return make_action(a)  # immediate win
            root.append({"kind": "move", "t": t, "raw": a,
                         "ord": g_me[t] if g_me[t] >= 0 else 999})
        elif act == "wall" and a.get("at") and a.get("orientation") and rem[m] > 0:
            try:
                c, r, o = parse_wall(a["at"], a["orientation"])
            except Exception:
                continue
            root.append({"kind": "wall", "c": c, "r": r, "o": o,
                         "e": wall_edges_cr(c, r, o), "raw": a, "ord": 999})
    if not root:
        return None

    # prune root walls: keep only those cutting an opponent shortest path,
    # ordered by 1-ply gain, capped
    dp = bfs_field((pos[1 - m],), blocked)
    total = opp_d
    kept = []
    for act in root:
        if act["kind"] == "move":
            kept.append(act)
            continue
        e1, e2 = act["e"]
        on_path = False
        for (u, v) in (e1, e2):
            if dp[u] >= 0 and g_op[v] >= 0 and dp[u] + 1 + g_op[v] == total:
                on_path = True
            if dp[v] >= 0 and g_op[u] >= 0 and dp[v] + 1 + g_op[u] == total:
                on_path = True
        if not on_path:
            continue
        nb = set(blocked)
        nb.add(e1)
        nb.add(e2)
        nmy = bfs_field(GOAL_SRC[m], nb)[pos[m]]
        nop = bfs_field(GOAL_SRC[1 - m], nb)[pos[1 - m]]
        if nmy < 0 or nop < 0:
            continue
        act["ord"] = -((nop - opp_d) - (nmy - my_d))  # ascending sort => best gain first
        kept.append(act)
    moves_part = sorted([a for a in kept if a["kind"] == "move"], key=lambda x: x["ord"])
    walls_part = sorted([a for a in kept if a["kind"] == "wall"], key=lambda x: x["ord"])[:CAP_ROOT]
    root = moves_part + walls_part

    deadline = time.time() + budget
    searcher = Searcher(pos, rem, blocked, slots, deadline)
    best_completed = None
    depth = 1
    try:
        while depth <= 8:
            alpha = -1e18
            scored = []
            for act in root:
                if act["kind"] == "move":
                    old = pos[m]
                    pos[m] = act["t"]
                    sc = searcher.negamax(1 - m, depth - 1, -1e18, -alpha, 1)
                    pos[m] = old
                else:
                    e1, e2 = act["e"]
                    blocked.add(e1)
                    blocked.add(e2)
                    slots.add((act["c"], act["r"], act["o"]))
                    rem[m] -= 1
                    sc = searcher.negamax(1 - m, depth - 1, -1e18, -alpha, 1)
                    rem[m] += 1
                    slots.discard((act["c"], act["r"], act["o"]))
                    blocked.discard(e1)
                    blocked.discard(e2)
                if sc is None:
                    continue
                score = -sc
                if act["kind"] == "move":
                    score -= REP_W * sum(1 for h in HIST if h == act["t"])
                scored.append((score, act))
                if score > alpha:
                    alpha = score
            if not scored:
                break
            scored.sort(key=lambda x: -x[0])
            best_completed = scored[0][1]
            root = [a for _, a in scored]
            if scored[0][0] >= WIN - 50:
                break
            depth += 1
    except SearchTimeout:
        pass
    if best_completed is None:
        return None
    return make_action(best_completed["raw"])


# ---------------- greedy fallback (always fast, always legal) ----------------

def greedy_decide(state):
    legal = state.get("legal_actions")
    if not isinstance(legal, list) or not legal:
        return None
    me = state.get("you")
    if me not in ("P1", "P2"):
        t = state.get("turn")
        me = t if t in ("P1", "P2") else "P1"
    mi = 0 if me == "P1" else 1
    blocked = set()
    for w in state.get("walls") or []:
        if not isinstance(w, dict):
            continue
        at = w.get("at") or w.get("position") or w.get("pos")
        o = w.get("orientation") or w.get("dir") or w.get("o")
        if at is None or o is None:
            continue
        try:
            c, r, oo = parse_wall(at, o)
        except Exception:
            continue
        e1, e2 = wall_edges_cr(c, r, oo)
        blocked.add(e1)
        blocked.add(e2)
    g_me = bfs_field(GOAL_SRC[mi], blocked)
    best = None
    best_key = None
    for a in legal:
        if not isinstance(a, dict) or a.get("action") != "move" or not a.get("to"):
            continue
        try:
            t = parse_cell(a["to"])
        except Exception:
            continue
        nd = g_me[t]
        if nd < 0:
            nd = 999
        key = (nd, str(a["to"]))
        if best_key is None or key < best_key:
            best_key = key
            best = a
    if best is not None:
        return make_action(best)
    return make_action(legal[0])


def main():
    out = sys.stdout
    try:
        # deployment check banner (stderr only; never stdout)
        sys.stderr.write("tansakun5 v2.2 budget=%.2fs\n" % TIME_BUDGET)
        sys.stderr.flush()
    except Exception:
        pass
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
        action = None
        try:
            action = search_decide(state, TIME_BUDGET)
        except Exception:
            action = None
        if action is None:
            try:
                action = greedy_decide(state)
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