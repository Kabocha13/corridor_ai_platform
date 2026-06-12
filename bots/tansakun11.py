#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 9x9 Quoridor-style tournament bot v3.3 (Python standard library only).
# - Iterative-deepening alpha-beta with transposition table + killer moves
# - Fast incremental adjacency-bitmask board (no per-node set hashing)
# - Exact retrograde-analysis endgame solver once both players are out of
#   walls (the pawn race with standard jumps is then a solved game)
# - Standard Quoridor jump rules (straight jump; diagonals when the straight
#   landing is blocked by a wall or the board edge)
# Protocol: one JSON state per line on stdin -> one action JSON line on stdout.
# Time budget per move: env QBOT_TIME (seconds, default 4.0 for a 5s limit).

import sys
import os
import json
import time
import random
from collections import deque

N = 9
CELLS = N * N
GOAL_ROW = (8, 0)
WIN = 100000.0
MATE_TH = 90000.0
STEP_W = 10.0
PROG_W = 1.0
TEMPO_W = 5.0
REP_W = 8.0
BNECK_W = 3.0  # penalty per missing gap when the path to goal narrows (fence defense)
# diminishing wall values: the last walls in hand are the precious ones
_WALL_INC = (24.0, 20.0, 17.0, 15.0, 13.0, 12.0, 11.0, 11.0, 10.0, 10.0)
WALL_VAL = [0.0]
for _w in _WALL_INC:
    WALL_VAL.append(WALL_VAL[-1] + _w)
CAP_ROOT = 20
CAP_NODE = 10
MAX_DEPTH = 14
SOLVES_PER_TURN = 8

try:
    TIME_BUDGET = float(os.environ.get("QBOT_TIME", "4.0"))
except Exception:
    TIME_BUDGET = 4.0

HIST = deque(maxlen=12)
LAST_WALL_SIG = [None]
SOLVE_CACHE = {}  # wall_hash -> (status_list, dtm_list); persists across turns

# adjacency bit flags
UP, DOWN, RIGHT, LEFT = 1, 2, 4, 8

_rng = random.Random(123456789)
ZOB_WALL = {}
for _c in range(8):
    for _r in range(8):
        for _o in ("h", "v"):
            ZOB_WALL[(_c, _r, _o)] = _rng.getrandbits(61)


def parse_cell(s):
    s = str(s).strip().lower()
    c = ord(s[0]) - 97
    r = int(s[1:]) - 1
    if 0 <= c < N and 0 <= r < N:
        return r * N + c
    raise ValueError("bad cell")


def parse_wall(at, orientation):
    s = str(at).strip().lower()
    c = ord(s[0]) - 97
    r = int(s[1:]) - 1
    o = str(orientation).strip().lower()[:1]
    if not (0 <= c < N - 1 and 0 <= r < N - 1) or o not in ("h", "v"):
        raise ValueError("bad wall")
    return c, r, o


def fresh_adj():
    adj = [0] * CELLS
    for u in range(CELLS):
        r = u // N
        c = u - r * N
        m = 0
        if r < 8:
            m |= UP
        if r > 0:
            m |= DOWN
        if c < 8:
            m |= RIGHT
        if c > 0:
            m |= LEFT
        adj[u] = m
    return adj


def apply_wall(adj, c, r, o):
    b = r * N + c
    if o == "h":
        adj[b] &= ~UP
        adj[b + N] &= ~DOWN
        adj[b + 1] &= ~UP
        adj[b + 1 + N] &= ~DOWN
    else:
        adj[b] &= ~RIGHT
        adj[b + 1] &= ~LEFT
        adj[b + N] &= ~RIGHT
        adj[b + N + 1] &= ~LEFT


def undo_wall(adj, c, r, o):
    b = r * N + c
    if o == "h":
        adj[b] |= UP
        adj[b + N] |= DOWN
        adj[b + 1] |= UP
        adj[b + 1 + N] |= DOWN
    else:
        adj[b] |= RIGHT
        adj[b + 1] |= LEFT
        adj[b + N] |= RIGHT
        adj[b + N + 1] |= LEFT


def goal_field(adj, goal_row):
    """Multi-source BFS distance from every cell to goal_row (pawn-ignoring)."""
    dist = [-1] * CELLS
    dq = deque()
    base = goal_row * N
    for i in range(base, base + N):
        dist[i] = 0
        dq.append(i)
    while dq:
        u = dq.popleft()
        nd = dist[u] + 1
        m = adj[u]
        if m & UP:
            v = u + N
            if dist[v] < 0:
                dist[v] = nd
                dq.append(v)
        if m & DOWN:
            v = u - N
            if dist[v] < 0:
                dist[v] = nd
                dq.append(v)
        if m & RIGHT:
            v = u + 1
            if dist[v] < 0:
                dist[v] = nd
                dq.append(v)
        if m & LEFT:
            v = u - 1
            if dist[v] < 0:
                dist[v] = nd
                dq.append(v)
    return dist


def src_field(adj, start):
    """Single-source BFS distances from `start` (pawn-ignoring)."""
    dist = [-1] * CELLS
    dist[start] = 0
    dq = deque((start,))
    while dq:
        u = dq.popleft()
        nd = dist[u] + 1
        m = adj[u]
        if m & UP:
            v = u + N
            if dist[v] < 0:
                dist[v] = nd
                dq.append(v)
        if m & DOWN:
            v = u - N
            if dist[v] < 0:
                dist[v] = nd
                dq.append(v)
        if m & RIGHT:
            v = u + 1
            if dist[v] < 0:
                dist[v] = nd
                dq.append(v)
        if m & LEFT:
            v = u - 1
            if dist[v] < 0:
                dist[v] = nd
                dq.append(v)
    return dist


def blocked_dist(adj, start, goal_row, forbid):
    """Distance to goal_row with the opponent pawn treated as an obstacle."""
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
        m = adj[u]
        if m & UP:
            v = u + N
            if dist[v] == -1:
                if v // N == goal_row:
                    return nd
                dist[v] = nd
                dq.append(v)
        if m & DOWN:
            v = u - N
            if dist[v] == -1:
                if v // N == goal_row:
                    return nd
                dist[v] = nd
                dq.append(v)
        if m & RIGHT:
            v = u + 1
            if dist[v] == -1:
                if v // N == goal_row:
                    return nd
                dist[v] = nd
                dq.append(v)
        if m & LEFT:
            v = u - 1
            if dist[v] == -1:
                if v // N == goal_row:
                    return nd
                dist[v] = nd
                dq.append(v)
    return -1


def bottleneck(adj, pos, goal_row):
    """Minimum number of open crossings over the row boundaries still ahead."""
    r = pos // N
    best = 9
    if goal_row > r:
        rng = range(r, goal_row)      # boundaries k/k+1 for k in r..goal-1
    else:
        rng = range(goal_row, r)      # boundaries k/k+1 for k in goal..r-1
    for k in rng:
        base = k * N
        cnt = 0
        for u in range(base, base + N):
            if adj[u] & UP:
                cnt += 1
        if cnt < best:
            best = cnt
    return best


def gen_moves(adj, p, q):
    """Pawn moves for the pawn at p with opponent at q.
    Standard Quoridor jumps: straight jump over an adjacent opponent; if the
    straight landing is blocked by a wall OR the board edge, diagonal side
    steps are allowed (verified from tournament logs)."""
    res = []
    m = adj[p]
    for bit, d in ((UP, N), (DOWN, -N), (RIGHT, 1), (LEFT, -1)):
        if not (m & bit):
            continue
        n = p + d
        if n != q:
            res.append(n)
            continue
        if adj[q] & bit:
            res.append(q + d)  # straight jump
        else:
            sides = ((RIGHT, 1), (LEFT, -1)) if bit in (UP, DOWN) else ((UP, N), (DOWN, -N))
            for sbit, e in sides:
                if adj[q] & sbit:
                    res.append(q + e)  # diagonal jump
    return res


def neighbors_of(adj, u):
    m = adj[u]
    res = []
    if m & UP:
        res.append(u + N)
    if m & DOWN:
        res.append(u - N)
    if m & RIGHT:
        res.append(u + 1)
    if m & LEFT:
        res.append(u - 1)
    return res


# ---------------- exact endgame solver (no walls left on either side) -------

def solve_pawn_race(adj):
    """Retrograde analysis of the no-walls pawn race with body blocking.

    State index: s = (a*81 + b)*2 + m, a=P1 pos, b=P2 pos, m=side to move.
    Returns (status, dtm): status 1 = side to move wins, -1 = loses, 0 = draw.
    """
    SZ = CELLS * CELLS * 2
    status = [0] * SZ
    dtm = [0] * SZ
    deg = [0] * SZ
    rev = [[] for _ in range(SZ)]
    queue = deque()
    for a in range(CELLS):
        for b in range(CELLS):
            if a == b:
                continue
            ab2 = (a * CELLS + b) * 2
            for m in (0, 1):
                s = ab2 + m
                gr = GOAL_ROW[m]
                wins = False
                succ = []
                moves = gen_moves(adj, a, b) if m == 0 else gen_moves(adj, b, a)
                for v in moves:
                    if v // N == gr:
                        wins = True
                        break
                    if m == 0:
                        succ.append((v * CELLS + b) * 2 + 1)
                    else:
                        succ.append((a * CELLS + v) * 2 + 0)
                if wins:
                    status[s] = 1
                    dtm[s] = 1
                    queue.append(s)
                    continue
                if not succ:
                    succ = [ab2 + (1 - m)]  # boxed in: pass
                deg[s] = len(succ)
                for t in succ:
                    rev[t].append(s)
    while queue:
        s = queue.popleft()
        st = status[s]
        k = dtm[s]
        if st == 1:
            # s is a win for its mover -> a predecessor moving into s gave
            # the opponent a won position; one losing option consumed
            for p in rev[s]:
                if status[p] == 0:
                    deg[p] -= 1
                    if deg[p] == 0:
                        status[p] = -1
                        dtm[p] = k + 1
                        queue.append(p)
        else:
            # s is lost for its mover -> any predecessor can move into s and win
            for p in rev[s]:
                if status[p] == 0:
                    status[p] = 1
                    dtm[p] = k + 1
                    queue.append(p)
    return status, dtm


def get_solution(adj, whash):
    sol = SOLVE_CACHE.get(whash)
    if sol is None:
        sol = solve_pawn_race(adj)
        SOLVE_CACHE[whash] = sol
    return sol


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


EXACT, LOWER, UPPER = 0, 1, 2


class Searcher(object):
    def __init__(self, adj, pos, rem, slots, whash, deadline):
        self.adj = adj
        self.pos = pos
        self.rem = rem
        self.slots = slots
        self.whash = whash
        self.deadline = deadline
        self.nodes = 0
        self.fcache = {}
        self.tt = {}
        self.wcache = {}
        self.killers = [[] for _ in range(64)]
        self.solves_left = SOLVES_PER_TURN

    # ---- board helpers ----
    def fields(self):
        f = self.fcache.get(self.whash)
        if f is None:
            f = (goal_field(self.adj, 8), goal_field(self.adj, 0))
            if len(self.fcache) < 40000:
                self.fcache[self.whash] = f
        return f

    def pawn_moves(self, m):
        return gen_moves(self.adj, self.pos[m], self.pos[1 - m])

    def slot_ok(self, c, r, o):
        slots = self.slots
        if (c, r, "h") in slots or (c, r, "v") in slots:
            return False
        if o == "h":
            return (c - 1, r, "h") not in slots and (c + 1, r, "h") not in slots
        return (c, r - 1, "v") not in slots and (c, r + 1, "v") not in slots

    def wall_candidates(self, m, g_other, cap):
        other = 1 - m
        wkey = (self.whash, self.pos[other])
        hit = self.wcache.get(wkey)
        if hit is not None:
            return hit
        dp = src_field(self.adj, self.pos[other])
        total = g_other[self.pos[other]]
        cands = []
        for c in range(8):
            for r in range(8):
                b = r * N + c
                for o in ("h", "v"):
                    if not self.slot_ok(c, r, o):
                        continue
                    if o == "h":
                        pairs = ((b, b + N), (b + 1, b + N + 1))
                    else:
                        pairs = ((b, b + 1), (b + N, b + N + 1))
                    on_path = False
                    near = 99
                    for (u, v) in pairs:
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
                        cands.append((near, c, r, o))
        cands.sort()
        cands = cands[:cap]
        if len(self.wcache) < 60000:
            self.wcache[wkey] = cands
        return cands

    # ---- evaluation ----
    def evaluate(self, m, d_me, d_op):
        other = 1 - m
        de_me = d_me
        de_op = d_op
        score = (STEP_W * (de_op - de_me)
                 - PROG_W * de_me
                 + WALL_VAL[min(self.rem[m], 10)] - WALL_VAL[min(self.rem[other], 10)]
                 + TEMPO_W)
        # fence defense: a narrowing corridor of remaining row-crossings is
        # dangerous while the opponent still holds walls (and vice versa)
        if self.rem[other] > 0:
            b_me = bottleneck(self.adj, self.pos[m], GOAL_ROW[m])
            if b_me < 4:
                score -= BNECK_W * (4 - b_me) * min(self.rem[other], 3) / 3.0
        if self.rem[m] > 0:
            b_op = bottleneck(self.adj, self.pos[other], GOAL_ROW[other])
            if b_op < 4:
                score += BNECK_W * (4 - b_op) * min(self.rem[m], 3) / 3.0
        return score

    def endgame_score(self, m, ply, d_me, d_op):
        """Exact value when both players are out of walls; None if unavailable."""
        sol = SOLVE_CACHE.get(self.whash)
        if sol is None:
            if self.solves_left <= 0:
                return None
            if time.time() + 0.25 > self.deadline:
                return None
            self.solves_left -= 1
            sol = get_solution(self.adj, self.whash)
        status, dtm = sol
        s = (self.pos[0] * CELLS + self.pos[1]) * 2 + m
        st = status[s]
        if st == 1:
            return WIN - ply - min(dtm[s], 400)
        if st == -1:
            return -(WIN - ply - min(dtm[s], 400))
        # draw by mutual blocking: keep slight pressure via distances
        return 2.0 * (d_op - d_me)

    # ---- alpha-beta with TT ----
    def negamax(self, m, depth, alpha, beta, ply):
        if time.time() > self.deadline:
            raise SearchTimeout()
        self.nodes += 1
        g0, g1 = self.fields()
        d_me = (g0 if m == 0 else g1)[self.pos[m]]
        d_op = (g1 if m == 0 else g0)[self.pos[1 - m]]
        if d_me < 0 or d_op < 0:
            return None  # illegal wall by parent
        if d_op == 0:
            return -(WIN - ply)
        if d_me == 0:
            return WIN - ply

        if self.rem[0] == 0 and self.rem[1] == 0:
            es = self.endgame_score(m, ply, d_me, d_op)
            if es is not None:
                return es

        if depth <= 0:
            return self.evaluate(m, d_me, d_op)

        key = (self.whash, self.pos[0], self.pos[1], m, self.rem[0], self.rem[1])
        tt_move = None
        e = self.tt.get(key)
        if e is not None:
            e_depth, e_flag, e_score, e_move = e
            tt_move = e_move
            if e_depth >= depth:
                sc = e_score
                if sc > MATE_TH:
                    sc -= ply
                elif sc < -MATE_TH:
                    sc += ply
                if e_flag == EXACT:
                    return sc
                if e_flag == LOWER and sc >= beta:
                    return sc
                if e_flag == UPPER and sc <= alpha:
                    return sc

        g_me = g0 if m == 0 else g1
        g_op = g1 if m == 0 else g0
        other = 1 - m
        goal_row = GOAL_ROW[m]
        alpha0 = alpha
        best = None
        best_move = None

        # ---- build move list: TT move first, pawn moves by distance, walls ----
        actions = []
        targets = self.pawn_moves(m)
        targets.sort(key=lambda t: (g_me[t] if g_me[t] >= 0 else 999, t))
        for t in targets:
            actions.append(("m", t))
        if self.rem[m] > 0:
            kl = self.killers[ply] if ply < 64 else []
            walls = self.wall_candidates(m, g_op, CAP_NODE)
            kw = []
            ow = []
            for near, c, r, o in walls:
                wmv = ("w", c, r, o)
                (kw if wmv in kl else ow).append(wmv)
            actions.extend(kw)
            actions.extend(ow)
        if tt_move is not None and tt_move in actions:
            actions.remove(tt_move)
            actions.insert(0, tt_move)

        for mv in actions:
            if mv[0] == "m":
                t = mv[1]
                old = self.pos[m]
                self.pos[m] = t
                if t // N == goal_row:
                    score = WIN - ply
                else:
                    sc = self.negamax(other, depth - 1, -beta, -alpha, ply + 1)
                    score = None if sc is None else -sc
                self.pos[m] = old
            else:
                _, c, r, o = mv
                apply_wall(self.adj, c, r, o)
                self.slots.add((c, r, o))
                self.whash ^= ZOB_WALL[(c, r, o)]
                self.rem[m] -= 1
                sc = self.negamax(other, depth - 1, -beta, -alpha, ply + 1)
                self.rem[m] += 1
                self.whash ^= ZOB_WALL[(c, r, o)]
                self.slots.discard((c, r, o))
                undo_wall(self.adj, c, r, o)
                score = None if sc is None else -sc
            if score is None:
                continue
            if best is None or score > best:
                best = score
                best_move = mv
            if score > alpha:
                alpha = score
            if alpha >= beta:
                if mv[0] == "w" and ply < 64:
                    kl = self.killers[ply]
                    if mv not in kl:
                        kl.insert(0, mv)
                        if len(kl) > 2:
                            kl.pop()
                break

        if best is None:
            return self.evaluate(m, d_me, d_op) - 2.0 * STEP_W

        st_score = best
        if st_score > MATE_TH:
            st_score += ply
        elif st_score < -MATE_TH:
            st_score -= ply
        if best <= alpha0:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        else:
            flag = EXACT
        if depth >= 2 and len(self.tt) < 400000:
            self.tt[key] = (depth, flag, st_score, best_move)
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

    adj = fresh_adj()
    slots = set()
    whash = 0
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
        if (c, r, oo) in slots:
            continue
        apply_wall(adj, c, r, oo)
        slots.add((c, r, oo))
        whash ^= ZOB_WALL[(c, r, oo)]

    rem = [10, 10]
    rw = state.get("remaining_walls") or {}
    for i, k in enumerate(("P1", "P2")):
        try:
            rem[i] = int(rw.get(k, 10))
        except Exception:
            rem[i] = 10

    wall_sig = (len(slots), frozenset(slots))
    if wall_sig != LAST_WALL_SIG[0]:
        # board changed: fade (do not erase) revisit memory, so that a wall
        # barrage by the opponent cannot switch off the anti-oscillation rule
        for _ in range(len(HIST) // 2):
            HIST.popleft()
        LAST_WALL_SIG[0] = wall_sig
    if not slots and pos[0] == parse_cell("e1") and pos[1] == parse_cell("e9") and rem == [10, 10]:
        HIST.clear()
    HIST.append(pos[m])

    g0 = goal_field(adj, 8)
    g1 = goal_field(adj, 0)
    g_me = g0 if m == 0 else g1
    g_op = g1 if m == 0 else g0
    my_d = g_me[pos[m]]
    opp_d = g_op[pos[1 - m]]
    if my_d < 0 or opp_d < 0:
        return None

    # ---- parse root actions from the authoritative legal list ----
    root = []
    have_moves = False
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
            have_moves = True
            root.append({"kind": "move", "t": t, "raw": a,
                         "ord": g_me[t] if g_me[t] >= 0 else 999})
        elif act == "wall" and a.get("at") and a.get("orientation") and rem[m] > 0:
            try:
                c, r, o = parse_wall(a["at"], a["orientation"])
            except Exception:
                continue
            root.append({"kind": "wall", "c": c, "r": r, "o": o, "raw": a, "ord": 999})
    if not root:
        return None

    # ---- exact endgame play when both sides are out of walls ----
    if rem[0] == 0 and rem[1] == 0 and have_moves:
        try:
            status, dtm = get_solution(adj, whash)
            best = None
            best_key = None
            for act in root:
                if act["kind"] != "move":
                    continue
                t = act["t"]
                if m == 0:
                    cs = (t * CELLS + pos[1]) * 2 + 1
                else:
                    cs = (pos[0] * CELLS + t) * 2 + 0
                st = status[cs]  # value for the opponent after our move
                if st == -1:
                    cls, sub = 0, dtm[cs]          # opponent lost: fastest win
                elif st == 0:
                    nd = g_me[t] if g_me[t] >= 0 else 999
                    cls, sub = 1, nd                # draw: keep pressing
                else:
                    cls, sub = 2, -dtm[cs]          # losing: resist longest
                key = (cls, sub, str(act["raw"].get("to")))
                if best_key is None or key < best_key:
                    best_key = key
                    best = act
            if best is not None:
                return make_action(best["raw"])
        except Exception:
            pass  # fall through to normal search

    # ---- prune root walls: only those cutting an opponent shortest path ----
    dp = src_field(adj, pos[1 - m])
    total = opp_d
    kept = []
    for act in root:
        if act["kind"] == "move":
            kept.append(act)
            continue
        c, r, o = act["c"], act["r"], act["o"]
        b = r * N + c
        if o == "h":
            pairs = ((b, b + N), (b + 1, b + N + 1))
        else:
            pairs = ((b, b + 1), (b + N, b + N + 1))
        on_path = False
        for (u, v) in pairs:
            if dp[u] >= 0 and g_op[v] >= 0 and dp[u] + 1 + g_op[v] == total:
                on_path = True
            if dp[v] >= 0 and g_op[u] >= 0 and dp[v] + 1 + g_op[u] == total:
                on_path = True
        if not on_path:
            continue
        apply_wall(adj, c, r, o)
        nmy = goal_field(adj, 8 if m == 0 else 0)[pos[m]]
        nop = goal_field(adj, 8 if m == 1 else 0)[pos[1 - m]]
        undo_wall(adj, c, r, o)
        if nmy < 0 or nop < 0:
            continue
        act["ord"] = -((nop - opp_d) - (nmy - my_d))
        kept.append(act)
    lead = opp_d - my_d
    min_gain = 1
    if lead >= 5:
        min_gain = 3 if rem[m] <= 3 else 2
    moves_part = sorted([a for a in kept if a["kind"] == "move"], key=lambda x: x["ord"])
    walls_part = sorted([a for a in kept if a["kind"] == "wall" and -a["ord"] >= min_gain],
                        key=lambda x: x["ord"])[:CAP_ROOT]
    root = moves_part + walls_part
    if not root:
        root = moves_part if moves_part else [a for a in kept]
    if not root:
        return None

    deadline = time.time() + budget
    searcher = Searcher(adj, pos, rem, slots, whash, deadline)
    best_completed = None
    depth = 1
    try:
        while depth <= MAX_DEPTH:
            alpha = -1e18
            scored = []
            for act in root:
                if act["kind"] == "move":
                    old = pos[m]
                    pos[m] = act["t"]
                    sc = searcher.negamax(1 - m, depth - 1, -1e18, -alpha, 1)
                    pos[m] = old
                else:
                    c, r, o = act["c"], act["r"], act["o"]
                    apply_wall(adj, c, r, o)
                    slots.add((c, r, o))
                    searcher.whash ^= ZOB_WALL[(c, r, o)]
                    rem[m] -= 1
                    sc = searcher.negamax(1 - m, depth - 1, -1e18, -alpha, 1)
                    rem[m] += 1
                    searcher.whash ^= ZOB_WALL[(c, r, o)]
                    slots.discard((c, r, o))
                    undo_wall(adj, c, r, o)
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
            if scored[0][0] >= WIN - 1000:
                break
            depth += 1
    except SearchTimeout:
        pass
    if os.environ.get("QBOT_DEBUG"):
        try:
            sys.stderr.write("depth=%d nodes=%d\n" % (depth, searcher.nodes))
            sys.stderr.flush()
        except Exception:
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
    adj = fresh_adj()
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
        apply_wall(adj, c, r, oo)
    g_me = goal_field(adj, 8 if mi == 0 else 0)
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
        sys.stderr.write("tansakun5 v3.3 budget=%.2fs\n" % TIME_BUDGET)
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