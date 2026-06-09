# Corridor AI Platform

Python製AI同士をローカルで大量対戦させる、9x9のコリドール風ボードゲーム基盤です。人間の対戦操作はなく、AI対戦、CSV結果保存、JSONLログ保存、ブラウザでのログ再生に絞っています。

AIを作るプレイヤー向けの説明は [PLAYER_README.md](PLAYER_README.md) を見てください。

## File Structure

```txt
corridor_ai_platform/
  engine/
    __init__.py
    action.py
    pathfinding.py
    rules.py
    serializer.py
    state.py
  runner/
    __init__.py
    bot_process.py
    match_runner.py
    tournament_runner.py
  bots/
    random_bot.py
    shortest_path_bot.py
    greedy_bot.py
  visualizer/
    index.html
    style.css
    app.js
  logs/
    matches/
  results/
    results.csv
  tests/
    test_match_runner.py
    test_pathfinding.py
    test_rules.py
  main.py
  README.md
  PLAYER_README.md
  requirements.txt
```

## Setup

```bash
cd corridor_ai_platform
python -m pip install -r requirements.txt
```

## Run

1試合だけ実行:

```bash
python main.py match --p1 bots/random_bot.py --p2 bots/shortest_path_bot.py
```

ログファイルを指定して1試合:

```bash
python main.py match --p1 bots/random_bot.py --p2 bots/shortest_path_bot.py --log logs/matches/test.jsonl
```

100戦の大会:

```bash
python main.py tournament --p1 bots/random_bot.py --p2 bots/shortest_path_bot.py --games 100
```

結果は `results/results.csv` に保存されます。各試合ログは `logs/matches/match_000001.jsonl` のように保存されます。大会では先手後手を交互に入れ替えます。実行中は1試合ごとに試合番号と勝者が表示され、大会終了後のターミナルには、Botごとの勝敗、勝率、先手勝ち、後手勝ち、不正手合計も表示されます。

## Bot Protocol

Botは標準入力からJSON stateを1行ずつ受け取り、標準出力へJSON actionを1行返します。標準エラーはデバッグ出力に使えます。

移動:

```json
{"type":"action","action":"move","to":"e2"}
```

壁配置:

```json
{"type":"action","action":"wall","at":"e3","orientation":"h"}
```

Botはstate内の `legal_actions` から1つ選ぶだけで動作できます。エンジンはBotの出力を信用せず、JSON不正、形式不正、非合法手、タイムアウト、クラッシュをすべて不正手として扱います。不正手は即負けではなく、その局面のランダムな合法手に置換され、CSVとJSONLログに回数と詳細が記録されます。

## Add A Bot

`bots/my_bot.py` を作成し、次の形にします。

```python
import json
import sys

for line in sys.stdin:
    state = json.loads(line)
    action = state["legal_actions"][0]
    print(json.dumps({"type": "action", **action}), flush=True)
```

実行:

```bash
python main.py tournament --p1 bots/my_bot.py --p2 bots/greedy_bot.py --games 100
```

## Visualizer

`visualizer/index.html` をブラウザで開き、`logs/matches/*.jsonl` をファイル選択してください。

機能:

- 9x9盤表示
- P1/P2の位置表示
- 壁表示
- 1手進む、1手戻る、最初、最後
- 自動再生
- 再生速度変更
- 現在手数、手番、勝者表示
- action表示
- 不正手のハイライト

## Tests

```bash
python -m pytest
```

## Docker Direction

現在のAI実行境界は `runner/bot_process.py` の `BotProcess` に閉じ込めています。将来的に `DockerBotProcess` を追加し、同じ `request_action(state_json)` インターフェイスで置き換えれば、ランナー側を大きく変えずに隔離実行できます。

想定コマンド:

```bash
docker run --rm -i --network none --memory 256m --cpus 0.5 bot-image
```
