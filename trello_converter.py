import json
from datetime import datetime

def convert_trello_to_orbit(trello_filename, output_filename):
    print("🚀 Trelloデータの解析を開始します...")
    
    with open(trello_filename, 'r', encoding='utf-8') as f:
        trello = json.load(f)

    orbit_data = {
        "export_date": datetime.now().isoformat(),
        "users": [], 
        "boards": [],
        "columns": [],
        "tasks": [],
        "checklists": [],
        "comments": []
    }

    # ==========================================
    # 1. ボード（Board）の変換
    # ==========================================
    board_id = 1
    orbit_data["boards"].append({
        "id": board_id,
        "title": trello.get("name", "Trelloからの移行ボード"),
        "background_url": ""
    })

    # ==========================================
    # 2. リスト（Columns）の変換
    # ==========================================
    col_map = {}
    for idx, lst in enumerate(trello.get("lists", [])):
        col_id = idx + 1
        col_map[lst["id"]] = col_id
        orbit_data["columns"].append({
            "id": col_id,
            "board_id": board_id,
            "title": lst["name"],
            "color": "#0b0d22",
            "order_idx": idx
        })

    # ==========================================
    # 3. カード（Tasks）の変換
    # ==========================================
    task_map = {}
    col_order_counters = {} # ★修正箇所：列ごとに順番を「0」から数えるための辞書

    for idx, card in enumerate(trello.get("cards", [])):
        task_id = idx + 1
        task_map[card["id"]] = task_id

        due_date = ""
        if card.get("due"):
            due_date = card["due"][:10]

        col_id = col_map.get(card["idList"], 1)

        # ★修正箇所：Trelloのバカデカい数字を無視し、Orbit用に 0, 1, 2... と綺麗な連番を振る
        current_order = col_order_counters.get(col_id, 0)
        col_order_counters[col_id] = current_order + 1

        orbit_data["tasks"].append({
            "id": task_id,
            "board_id": board_id,
            "column_id": col_id,
            "title": card["name"],
            "description": card.get("desc", ""),
            "due_date": due_date,
            "is_archived": card.get("closed", False),
            "order_idx": current_order
        })

    # ==========================================
    # 4. チェックリストの変換
    # ==========================================
    chk_id_counter = 1
    for cl in trello.get("checklists", []):
        task_id = task_map.get(cl["idCard"])
        if not task_id: continue

        for item in cl.get("checkItems", []):
            orbit_data["checklists"].append({
                "id": chk_id_counter,
                "task_id": task_id,
                "title": item["name"],
                "is_checked": (item["state"] == "complete")
            })
            chk_id_counter += 1

    # ==========================================
    # 5. コメント（Actions履歴）の変換
    # ==========================================
    comment_id_counter = 1
    for action in trello.get("actions", []):
        if action.get("type") == "commentCard":
            card_id = action.get("data", {}).get("card", {}).get("id")
            task_id = task_map.get(card_id)
            if not task_id: continue

            content = action.get("data", {}).get("text", "")
            author_info = action.get("memberCreator", {})
            author = author_info.get("fullName") or author_info.get("username") or "Trello User"
            created_at = action.get("date", "").replace("Z", "")

            orbit_data["comments"].append({
                "id": comment_id_counter,
                "task_id": task_id,
                "content": content,
                "author": f"{author} (Trello)",
                "created_at": created_at
            })
            comment_id_counter += 1

    # Orbit用のJSONとして書き出し
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(orbit_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 変換完了！ '{output_filename}' を出力しました。")

# ==========================================
# 実行部分
# ==========================================
INPUT_FILE = "7tUscu2u - graphium.json"
OUTPUT_FILE = "orbit_import.json"

convert_trello_to_orbit(INPUT_FILE, OUTPUT_FILE)