# AI Player Manual

このREADMEは、ゲームAIを作るプレイヤー向けのマニュアルです。大会運営、ログ保存、ビジュアライザの内部実装を知らなくても、ここだけ読めばBotを作れるようにしています。

## まず最短で動かす

実行確認:

```bash
python main.py match --p1 bots/my_bot.py --p2 bots/random_bot.py
```

100戦:

```bash
python main.py tournament --p1 bots/my_bot.py --p2 bots/shortest_path_bot.py --games 100
```

## Botの入出力

Botは標準入力から1行ずつJSONを受け取ります。1行につき1手をJSONで標準出力へ返してください。

重要:

- 標準出力には手のJSONだけを出す
- デバッグ表示は標準エラーに出す
- 返すJSONは必ず1行で出す
- `print(..., flush=True)` を付ける
- Botは1試合中、起動したまま複数回stateを受け取る

デバッグ出力例:

```python
print("thinking...", file=sys.stderr)
```

## 受け取るState

例:

```json
{
  "type": "state",
  "match_id": "match_000001",
  "turn_index": 12,
  "you": "P1",
  "turn": "P1",
  "board_size": 9,
  "pawns": {
    "P1": "e4",
    "P2": "e7"
  },
  "walls": [
    {"action": "wall", "at": "e3", "orientation": "h"},
    {"action": "wall", "at": "d5", "orientation": "v"}
  ],
  "remaining_walls": {
    "P1": 8,
    "P2": 9
  },
  "legal_actions": [
    {"action": "move", "to": "e5"},
    {"action": "move", "to": "d4"},
    {"action": "wall", "at": "f5", "orientation": "h"}
  ]
}
```

よく使う値:

- `you`: 自分が `P1` か `P2` か
- `pawns`: 現在の駒位置
- `walls`: 置かれている壁
- `remaining_walls`: 残り壁枚数
- `legal_actions`: 今すぐ出せる合法手の一覧

基本方針として、最初は `legal_actions` から選べば十分です。合法手判定はエンジン側が行います。

## 返すAction

移動:

```json
{"type": "action", "action": "move", "to": "e2"}
```

壁配置:

```json
{"type": "action", "action": "wall", "at": "e3", "orientation": "h"}
```

`legal_actions` に入っている辞書には `type` が付いていないので、返すときに足してください。

```python
action = state["legal_actions"][0]
print(json.dumps({"type": "action", **action}), flush=True)
```

## 座標とルール

盤面は9x9です。

- 左から右へ `a` から `i`
- 下から上へ `1` から `9`
- P1初期位置: `e1`
- P2初期位置: `e9`
- P1のゴール: 9段目
- P2のゴール: 1段目
- 各プレイヤーの壁は10枚
- 最大300手で引き分け

壁:

- `orientation: "h"` は横向き
- `orientation: "v"` は縦向き
- 壁の基準座標は `a1` から `h8`
- 壁は2マス分の移動経路を塞ぐ
- どちらのプレイヤーもゴールまでの経路が残る壁だけ合法

## 不正手の扱い

次は不正手になります。

- JSONとして読めない
- `type` が `action` ではない
- `action` が `move` または `wall` ではない
- `legal_actions` に含まれていない
- 制限時間を超える
- Botがクラッシュする

不正手を出しても即負けにはなりません。その場面のランダムな合法手に置換されます。ただし、不正手回数はCSVとJSONLログに記録されます。大会では不正手が少ないBotのほうがデバッグしやすく、成績も安定します。

## 例: 前に進めるなら進むBot

```python
import json
import random
import sys


def rank(coord):
    return int(coord[1])


for line in sys.stdin:
    state = json.loads(line)
    you = state["you"]
    current = state["pawns"][you]

    moves = [a for a in state["legal_actions"] if a["action"] == "move"]
    if you == "P1":
        forward = [a for a in moves if rank(a["to"]) > rank(current)]
    else:
        forward = [a for a in moves if rank(a["to"]) < rank(current)]

    action = random.choice(forward or moves or state["legal_actions"])
    print(json.dumps({"type": "action", **action}), flush=True)
```

## 例: 壁より移動を優先するBot

```python
import json
import random
import sys


for line in sys.stdin:
    state = json.loads(line)
    moves = [a for a in state["legal_actions"] if a["action"] == "move"]
    action = random.choice(moves or state["legal_actions"])
    print(json.dumps({"type": "action", **action}), flush=True)
```

## ローカルで強さを見る

1試合:

```bash
python main.py match --p1 bots/my_bot.py --p2 bots/greedy_bot.py --log logs/matches/my_test.jsonl
```

100戦:

```bash
python main.py tournament --p1 bots/my_bot.py --p2 bots/greedy_bot.py --games 100
```

結果CSV:

```txt
results/results.csv
```

実行中は1試合ごとに試合番号と勝者が表示されます。大会終了後のターミナルにも、Botごとの勝敗、勝率、先手勝ち、後手勝ち、不正手合計が表示されます。

ログ:

```txt
logs/matches/match_000001.jsonl
```

## ログを再生する

`visualizer/index.html` をブラウザで開き、`logs/matches/*.jsonl` を選択してください。

確認できること:

- 盤面
- 駒位置
- 壁
- 各手のaction
- 不正手だったか
- 勝者

## よくあるミス

- `type: "action"` を付け忘れる
- `flush=True` を付け忘れてタイムアウトする
- デバッグ文字列を標準出力に出してJSON不正になる
- `legal_actions` にない壁を自作して返す
- 1回だけ `sys.stdin.read()` して終了するBotにしてしまう

Botは次のように `for line in sys.stdin:` で書くのがおすすめです。

```python
for line in sys.stdin:
    state = json.loads(line)
    ...
```

## 提出前チェック

```bash
python main.py match --p1 bots/my_bot.py --p2 bots/random_bot.py
python main.py tournament --p1 bots/my_bot.py --p2 bots/shortest_path_bot.py --games 20
```

`results/results.csv` の `p1_invalid_count` または `p2_invalid_count` が増えていないか確認してください。
