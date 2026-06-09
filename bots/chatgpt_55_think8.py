import sys
import json
from collections import deque
from functools import lru_cache

N = 9
INF = 10**9
WIN = 10**8
DEPTH = 3


def parse_pos(s):
    if not isinstance(s, str) or len(s) < 2:
        return None

    c = s[0].lower()

    if c < "a" or c > "i":
        return None

    try:
        y = int(s[1:])
    except Exception:
        return None

    x = ord(c) - ord("a") + 1

    if 1 <= x <= N and 1 <= y <= N:
        return x, y

    return None


def pos_to_str(p):
    return chr(ord("a") + p[0] - 1) + str(p[1])


def opponent(p):
    return "P2" if p == "P1" else "P1"


def goal_row(p):
    return N if p == "P1" else 1


def is_goal(pos, p):
    return pos is not None and pos[1] == goal_row(p)


def action_kind(a):
    if not isinstance(a, dict):
        return None

    return a.get("action")


def norm_o(o):
    if not isinstance(o, str) or not o:
        return None

    o = o.lower()

    if o.startswith("h"):
        return "h"

    if o.startswith("v"):
        return "v"

    return None


def wall_info(a):
    if not isinstance(a, dict):
        return None

    p = parse_pos(a.get("at"))
    o = norm_o(a.get("orientation"))

    if p is None or o is None:
        return None

    x, y = p

    if not (1 <= x <= N - 1 and 1 <= y <= N - 1):
        return None

    return x, y, o


def edge(a, b):
    return tuple(sorted((a, b)))


def wall_edges(w):
    if w is None:
        return []

    x, y, o = w

    if o == "h":
        return [
            edge((x, y), (x, y + 1)),
            edge((x + 1, y), (x + 1, y + 1))
        ]

    return [
        edge((x, y), (x + 1, y)),
        edge((x, y + 1), (x + 1, y + 1))
    ]


def cross_wall(w):
    x, y, o = w

    return x, y, "v" if o == "h" else "h"


def pawn(raw, p):
    ps = raw.get("pawns", {})

    if not isinstance(ps, dict):
        return None

    return parse_pos(ps.get(p))


def remaining(raw, p):
    r = raw.get("remaining_walls", 0)

    if isinstance(r, dict):
        r = r.get(p, 0)

    try:
        return int(r)
    except Exception:
        return 0


def read_board(raw):
    blocked = set()
    placed = set()
    ws = raw.get("walls", [])

    if not isinstance(ws, list):
        return frozenset(), frozenset()

    for a in ws:
        w = wall_info(a)

        if w is None:
            continue

        placed.add(w)

        for e in wall_edges(w):
            blocked.add(e)

    return frozenset(blocked), frozenset(placed)


def make_state(raw):
    blocked, placed = read_board(raw)

    return {
        "pos": {
            "P1": pawn(raw, "P1"),
            "P2": pawn(raw, "P2")
        },
        "rem": {
            "P1": remaining(raw, "P1"),
            "P2": remaining(raw, "P2")
        },
        "blocked": blocked,
        "placed": placed
    }


def in_board(p):
    return p is not None and 1 <= p[0] <= N and 1 <= p[1] <= N


def can_step(a, b, blocked):
    return in_board(a) and in_board(b) and edge(a, b) not in blocked


def dirs(p):
    if p == "P1":
        return [(0, 1), (-1, 0), (1, 0), (0, -1)]

    return [(0, -1), (-1, 0), (1, 0), (0, 1)]


def basic_neighbors(pos, blocked, p=None):
    if pos is None:
        return []

    if p in ("P1", "P2"):
        ds = dirs(p)
    else:
        ds = [(0, 1), (0, -1), (-1, 0), (1, 0)]

    out = []

    for dx, dy in ds:
        q = (pos[0] + dx, pos[1] + dy)

        if can_step(pos, q, blocked):
            out.append(q)

    return out


@lru_cache(maxsize=200000)
def shortest_cached(start, p, blocked):
    if start is None:
        return INF, ()

    q = deque([start])
    dist = {start: 0}
    prev = {}

    while q:
        cur = q.popleft()

        if is_goal(cur, p):
            path = []
            x = cur

            while True:
                path.append(x)

                if x not in prev:
                    break

                x = prev[x]

            path.reverse()
            return dist[cur], tuple(path)

        for nxt in basic_neighbors(cur, blocked, p):
            if nxt in dist:
                continue

            dist[nxt] = dist[cur] + 1
            prev[nxt] = cur
            q.append(nxt)

    return INF, ()


def shortest(pos, p, blocked):
    return shortest_cached(pos, p, frozenset(blocked))


def legal_moves(actions):
    out = []

    if not isinstance(actions, list):
        return out

    for a in actions:
        if not isinstance(a, dict):
            continue

        if action_kind(a) != "move":
            continue

        if parse_pos(a.get("to")) is None:
            continue

        out.append(a)

    return out


def legal_walls(actions):
    out = []

    if not isinstance(actions, list):
        return out

    for a in actions:
        if not isinstance(a, dict):
            continue

        if action_kind(a) != "wall":
            continue

        if wall_info(a) is None:
            continue

        out.append(a)

    return out


def apply_action(st, p, a):
    pos = dict(st["pos"])
    rem = dict(st["rem"])
    blocked = set(st["blocked"])
    placed = set(st["placed"])

    if action_kind(a) == "move":
        to = parse_pos(a.get("to"))

        if to is not None:
            pos[p] = to

    elif action_kind(a) == "wall":
        w = wall_info(a)

        if w is not None:
            placed.add(w)

            for e in wall_edges(w):
                blocked.add(e)

            rem[p] = max(0, rem.get(p, 0) - 1)

    return {
        "pos": pos,
        "rem": rem,
        "blocked": frozenset(blocked),
        "placed": frozenset(placed)
    }


def make_wall_action(w):
    x, y, o = w

    return {
        "action": "wall",
        "at": pos_to_str((x, y)),
        "orientation": o
    }


def wall_legal(st, w):
    if w is None:
        return False

    if w in st["placed"]:
        return False

    if cross_wall(w) in st["placed"]:
        return False

    for e in wall_edges(w):
        if e in st["blocked"]:
            return False

    b = set(st["blocked"])

    for e in wall_edges(w):
        b.add(e)

    b = frozenset(b)

    d1, _ = shortest(st["pos"]["P1"], "P1", b)
    d2, _ = shortest(st["pos"]["P2"], "P2", b)

    return d1 < INF and d2 < INF


def generated_moves(st, p):
    me = st["pos"][p]
    enp = opponent(p)
    en = st["pos"][enp]
    b = st["blocked"]
    out = []
    seen = set()

    if me is None:
        return out

    for dx, dy in dirs(p):
        n = (me[0] + dx, me[1] + dy)

        if not can_step(me, n, b):
            continue

        if n != en:
            if n not in seen:
                seen.add(n)
                out.append({
                    "action": "move",
                    "to": pos_to_str(n)
                })

            continue

        j = (en[0] + dx, en[1] + dy)

        if can_step(en, j, b):
            if j not in seen:
                seen.add(j)
                out.append({
                    "action": "move",
                    "to": pos_to_str(j)
                })

            continue

        if dx == 0:
            sides = [(-1, 0), (1, 0)]
        else:
            sides = [(0, -1), (0, 1)]

        for sx, sy in sides:
            d = (en[0] + sx, en[1] + sy)

            if can_step(en, d, b) and d not in seen:
                seen.add(d)
                out.append({
                    "action": "move",
                    "to": pos_to_str(d)
                })

    return out


def path_block_count(path, a):
    w = wall_info(a)

    if w is None or not path or len(path) < 2:
        return 0

    es = set(wall_edges(w))
    c = 0

    for i in range(len(path) - 1):
        if edge(path[i], path[i + 1]) in es:
            c += 1

    return c


def near_path(path, a):
    w = wall_info(a)

    if w is None or not path:
        return 0

    x, y, _ = w

    cells = [
        (x, y),
        (x + 1, y),
        (x, y + 1),
        (x + 1, y + 1)
    ]

    best = 999

    for c in cells:
        for i, p in enumerate(path):
            v = (abs(c[0] - p[0]) + abs(c[1] - p[1])) * 10 + i

            if v < best:
                best = v

    return max(0, 130 - best * 3)


def center(p):
    if p is None:
        return 0

    return -abs(p[0] - 5)


def prog(a, b, p):
    if a is None or b is None:
        return 0

    if p == "P1":
        return b[1] - a[1]

    return a[1] - b[1]


def eval_state(st, root):
    enp = opponent(root)
    my = st["pos"][root]
    en = st["pos"][enp]
    b = st["blocked"]

    md, mp = shortest(my, root, b)
    ed, ep = shortest(en, enp, b)

    if md == 0:
        return WIN

    if ed == 0:
        return -WIN

    s = 0
    s += (ed - md) * 12000
    s -= md * 700
    s += ed * 600
    s += (st["rem"].get(root, 0) - st["rem"].get(enp, 0)) * 250
    s += center(my) * 70
    s -= center(en) * 40

    if mp and len(mp) <= 5:
        s += (6 - len(mp)) * 1600

    if ep and len(ep) <= 5:
        s -= (6 - len(ep)) * 2100

    if mp and len(mp) >= 2:
        s += prog(my, mp[1], root) * 300

    if ep and len(ep) >= 2:
        s -= prog(en, ep[1], enp) * 250

    return s


def score_move(st, a, p):
    to = parse_pos(a.get("to"))

    if to is None:
        return -INF

    enp = opponent(p)
    old = st["pos"][p]
    after = apply_action(st, p, a)

    md, mp = shortest(after["pos"][p], p, after["blocked"])
    ed, ep = shortest(after["pos"][enp], enp, after["blocked"])

    s = 0
    s += (ed - md) * 8500
    s -= md * 800
    s += ed * 450
    s += prog(old, to, p) * 1200
    s += center(to) * 80

    if is_goal(to, p):
        s += WIN

    if ep and len(ep) <= 3:
        s -= (4 - len(ep)) * 2200

    return s


def score_wall(st, a, p):
    if st["rem"].get(p, 0) <= 0:
        return -INF, 0, 0

    enp = opponent(p)
    my = st["pos"][p]
    en = st["pos"][enp]
    b = st["blocked"]

    bmd, bmp = shortest(my, p, b)
    bed, bep = shortest(en, enp, b)

    after = apply_action(st, p, a)

    md, _ = shortest(my, p, after["blocked"])
    ed, _ = shortest(en, enp, after["blocked"])

    if md >= INF or ed >= INF:
        return -INF, 0, 0

    gain = ed - bed
    pain = md - bmd

    s = 0
    s += gain * 6200
    s -= pain * 5200
    s += (ed - md) * 600
    s += path_block_count(bep, a) * 2800
    s -= path_block_count(bmp, a) * 2000
    s += near_path(bep, a) * 12

    if bed <= bmd:
        s += 2200

    if bed <= 4:
        s += 2200

    if bed <= 2:
        s += 5500

    if gain <= 0:
        s -= 6500

    if pain > gain:
        s -= (pain - gain) * 5000

    if gain >= 3 and pain <= 2:
        s += 4500

    return s, gain, pain


def candidate_walls(st, p, limit):
    if st["rem"].get(p, 0) <= 0:
        return []

    enp = opponent(p)
    my = st["pos"][p]
    en = st["pos"][enp]

    _, mp = shortest(my, p, st["blocked"])
    ed, ep = shortest(en, enp, st["blocked"])

    arr = []

    for x in range(1, N):
        for y in range(1, N):
            for o in ("h", "v"):
                w = (x, y, o)

                if not wall_legal(st, w):
                    continue

                a = make_wall_action(w)
                ne = near_path(ep, a)
                be = path_block_count(ep, a)
                bm = path_block_count(mp, a)

                if be == 0 and ne <= 0 and en is not None:
                    if abs(x - en[0]) + abs(y - en[1]) > 4 and ed > 4:
                        continue

                s, g, pain = score_wall(st, a, p)

                if g <= 0 and ed > 3:
                    continue

                if pain >= 4 and g < 4:
                    continue

                arr.append((s + be * 1600 - bm * 900, a))

    arr.sort(reverse=True, key=lambda z: z[0])

    return [a for _, a in arr[:limit]]


def gen_actions(st, p, depth):
    ms = generated_moves(st, p)

    sm = [
        (score_move(st, a, p), a)
        for a in ms
    ]

    sm.sort(reverse=True, key=lambda z: z[0])

    if depth >= 3:
        lim = 16
    else:
        lim = 28

    ws = candidate_walls(st, p, lim)

    sw = [
        (score_wall(st, a, p)[0], a)
        for a in ws
    ]

    sw.sort(reverse=True, key=lambda z: z[0])

    return [a for _, a in sm] + [a for _, a in sw]


def key_state(st, turn, depth):
    return (
        turn,
        depth,
        st["pos"]["P1"],
        st["pos"]["P2"],
        st["rem"].get("P1", 0),
        st["rem"].get("P2", 0),
        tuple(sorted(st["placed"]))
    )


def search(st, turn, root, depth, alpha, beta, cache):
    k = key_state(st, turn, depth)

    if k in cache:
        return cache[k]

    enp = opponent(root)

    md, _ = shortest(st["pos"][root], root, st["blocked"])
    ed, _ = shortest(st["pos"][enp], enp, st["blocked"])

    if md == 0:
        return WIN + depth

    if ed == 0:
        return -WIN - depth

    if depth <= 0:
        v = eval_state(st, root)
        cache[k] = v
        return v

    acts = gen_actions(st, turn, depth)

    if not acts:
        v = eval_state(st, root)
        cache[k] = v
        return v

    nt = opponent(turn)

    if turn == root:
        best = -INF

        for a in acts:
            v = search(
                apply_action(st, turn, a),
                nt,
                root,
                depth - 1,
                alpha,
                beta,
                cache
            )

            if v > best:
                best = v

            alpha = max(alpha, best)

            if alpha >= beta:
                break

        cache[k] = best
        return best

    best = INF

    for a in acts:
        v = search(
            apply_action(st, turn, a),
            nt,
            root,
            depth - 1,
            alpha,
            beta,
            cache
        )

        if v < best:
            best = v

        beta = min(beta, best)

        if alpha >= beta:
            break

    cache[k] = best
    return best


def output_action(a):
    if not isinstance(a, dict):
        return {
            "type": "action",
            "action": "move",
            "to": "e1"
        }

    if action_kind(a) == "move":
        return {
            "type": "action",
            "action": "move",
            "to": a.get("to")
        }

    if action_kind(a) == "wall":
        return {
            "type": "action",
            "action": "wall",
            "at": a.get("at"),
            "orientation": a.get("orientation")
        }

    r = {"type": "action"}

    for k, v in a.items():
        if k != "type":
            r[k] = v

    return r


def choose(raw):
    actions = raw.get("legal_actions", [])

    if not isinstance(actions, list) or not actions:
        return {
            "type": "action",
            "action": "move",
            "to": "e1"
        }

    you = raw.get("you")
    enp = opponent(you)
    st = make_state(raw)

    moves = legal_moves(actions)
    walls = legal_walls(actions)

    for a in moves:
        if is_goal(parse_pos(a.get("to")), you):
            return output_action(a)

    candidates = moves + walls

    if not candidates:
        return output_action(actions[0])

    md, _ = shortest(st["pos"][you], you, st["blocked"])
    ed, _ = shortest(st["pos"][enp], enp, st["blocked"])

    depth = DEPTH

    if md <= 4 or ed <= 4:
        depth = 4

    ordered = []

    for a in candidates:
        if action_kind(a) == "move":
            s = score_move(st, a, you)
        else:
            s = score_wall(st, a, you)[0]

        ordered.append((s, a))

    ordered.sort(reverse=True, key=lambda z: z[0])

    cache = {}
    best_a = ordered[0][1]
    best_s = -INF
    alpha = -INF
    beta = INF

    for _, a in ordered:
        v = search(
            apply_action(st, you, a),
            enp,
            you,
            depth - 1,
            alpha,
            beta,
            cache
        )

        if v > best_s:
            best_s = v
            best_a = a

        alpha = max(alpha, best_s)

    return output_action(best_a)


def main():
    for line in sys.stdin:
        line = line.strip()

        if not line:
            continue

        try:
            raw = json.loads(line)
            ans = choose(raw)

            print(
                json.dumps(
                    ans,
                    ensure_ascii=False,
                    separators=(",", ":")
                ),
                flush=True
            )

        except Exception as e:
            print(
                "error:",
                e,
                file=sys.stderr,
                flush=True
            )


if __name__ == "__main__":
    main()