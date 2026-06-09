import sys
import json
import random

def get_action():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            state = json.loads(line)
        except json.JSONDecodeError:
            continue

        legal_actions = state.get("legal_actions", [])
        if not legal_actions:
            continue

        # 移動アクションを優先（move）
        moves = [a for a in legal_actions if a.get("type") == "move"]
        
        selected_action = None
        if moves:
            # 優先して移動を選択
            selected_action = moves[0]
        else:
            # 移動がない場合は合法手からランダムに選択
            selected_action = random.choice(legal_actions)

        # 出力用JSONの作成
        response = {"type": "action"}
        response.update(selected_action)

        # 標準出力へ結果を送信
        print(json.dumps(response), flush=True)
        
        # デバッグ用（標準エラー）
        sys.stderr.write(f"DEBUG: Selected {selected_action}\n")
        sys.stderr.flush()

if __name__ == "__main__":
    try:
        get_action()
    except Exception as e:
        sys.stderr.write(f"ERROR: {str(e)}\n")
        sys.stderr.flush()