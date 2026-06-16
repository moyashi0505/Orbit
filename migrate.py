import pandas as pd
from sqlalchemy import create_engine, text

# 1. 2つの金庫の鍵（URL）を準備します
# Renderのダッシュボードからコピーした External Database URL (postgres://...)
RENDER_URL = "postgresql://orbit_db_ukn1_user:8mmRODuzOuNQukGtOjvxogWY9iJossT8@dpg-d8duo7urnols739oe8eg-a.virginia-postgres.render.com/orbit_db_ukn1"

# Hugging Faceに入力した、SupabaseのURL (ポート6543のもの)
SUPABASE_URL = "postgresql://postgres.xybqjdhnfplcrspegwpj:Piis1592L19S98S@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"

# SQLAlchemy用にURLの先頭を補正
if RENDER_URL.startswith("postgres://"):
    RENDER_URL = RENDER_URL.replace("postgres://", "postgresql://", 1)

try:
    engine_render = create_engine(RENDER_URL)
    engine_supabase = create_engine(SUPABASE_URL)

    # Orbit_app.py で定義されている全6テーブル
    tables = ["users", "boards", "columns", "tasks", "checklist_items", "comments"]

    with engine_supabase.begin() as conn_supa:
        for table in tables:
            print(f"[{table}] テーブルのデータを抽出中...")
            
            # Render側からデータを一括読み込み
            df = pd.read_sql_table(table, con=engine_render)
            
            if not df.empty:
                # 移行先（Supabase）にテストデータ等がある場合の重複エラーを防ぐため、一旦空にする
                conn_supa.execute(text(f"DELETE FROM {table};"))
                
                # データを一気に流し込む
                df.to_sql(table, con=conn_supa, if_exists="append", index=False)
                
                # PostgreSQL特有の「ID自動採番のズレ」を修正する魔法の呪文
                conn_supa.execute(text(f"SELECT setval('{table}_id_seq', COALESCE((SELECT MAX(id) FROM {table}), 1));"))
                
                print(f"  -> ✅ {len(df)}件の移行とインデックス同期が完了しました")
            else:
                print(f"  -> データが空のためスキップしました")

    print("\n🎉 すべてのデータ引っ越しが完了しました！")

except Exception as e:
    print(f"\n❌ エラーが発生しました: {e}")