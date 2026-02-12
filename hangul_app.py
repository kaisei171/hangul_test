import streamlit as st
import pandas as pd
import sqlite3
import os
import random

# --- データベース設定 ---
def init_db():
    conn = sqlite3.connect('hangul_quiz.db', check_same_thread=False)
    c = conn.cursor()

    # 韓国語単語テーブル（ハングル検定4級）
    c.execute('''CREATE TABLE IF NOT EXISTS items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  word TEXT,
                  meaning TEXT)''')

    # 解答記録テーブル
    c.execute('''CREATE TABLE IF NOT EXISTS records
                 (item_id INTEGER,
                  is_correct INTEGER,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    # CSVから初期データ読み込み
    if os.path.exists('hangul4_vocab.csv'):
        c.execute("SELECT count(*) FROM items")
        if c.fetchone()[0] == 0:
            df_csv = pd.read_csv('hangul4_vocab.csv')
            df_csv.to_sql('items', conn, if_exists='append', index=False)

    conn.commit()
    return conn

conn = init_db()


# --- データ取得 ---
def get_items(mode='all'):
    if mode == 'review':
        query = """
        SELECT DISTINCT i.id, i.word, i.meaning
        FROM items i
        JOIN records r ON i.id = r.item_id
        WHERE r.is_correct = 0
        """
    else:
        query = "SELECT id, word, meaning FROM items"

    return pd.read_sql(query, conn)


def save_record(item_id, is_correct):
    c = conn.cursor()
    c.execute(
        "INSERT INTO records (item_id, is_correct) VALUES (?, ?)",
        (int(item_id), is_correct)
    )
    conn.commit()


# --- クイズ生成 ---
def prepare_quiz(df):
    if df.empty:
        return None

    correct_row = df.sample(n=1).iloc[0]

    all_meanings = pd.read_sql(
        "SELECT meaning FROM items", conn
    )['meaning'].tolist()

    all_meanings.remove(correct_row['meaning'])
    distractors = random.sample(all_meanings, 3)

    options = distractors + [correct_row['meaning']]
    random.shuffle(options)

    return {
        "id": correct_row['id'],
        "word": correct_row['word'],
        "answer": correct_row['meaning'],
        "options": options
    }


# --- UI ---
st.set_page_config(page_title="ハングル検定4級単語クイズ", layout="centered")
st.title("🇰🇷 ハングル検定4級 単語マスター")

menu = st.sidebar.radio(
    "メニュー",
    ["クイズに挑戦", "復習モード", "学習記録"]
)

if menu in ["クイズに挑戦", "復習モード"]:

    df_pool = get_items(
        mode='all' if menu == "クイズに挑戦" else 'review'
    )

    if df_pool.empty:
        st.warning("対象となる問題がありません。")

    else:
        if 'quiz_data' not in st.session_state:
            st.session_state.quiz_data = prepare_quiz(df_pool)
            st.session_state.answered = False
            st.session_state.feedback = None

        quiz = st.session_state.quiz_data

        st.info(f"現在のモード: {menu}")
        st.markdown(f"### Q: **{quiz['word']}** の意味は？")
        st.write("正しい日本語訳を選んでください：")

        for option in quiz['options']:
            if st.button(
                option,
                key=option,
                use_container_width=True,
                disabled=st.session_state.answered
            ):
                st.session_state.answered = True

                if option == quiz['answer']:
                    st.session_state.feedback = (
                        "correct",
                        f"⭕️ 正解！: {quiz['answer']}"
                    )
                    save_record(quiz['id'], 1)

                else:
                    st.session_state.feedback = (
                        "error",
                        f"❌ 不正解... 正解は: {quiz['answer']}"
                    )
                    save_record(quiz['id'], 0)

        if st.session_state.answered:
            t, msg = st.session_state.feedback
            if t == "correct":
                st.success(msg)
            else:
                st.error(msg)

            if st.button("次の問題へ ➡️"):
                del st.session_state.quiz_data
                del st.session_state.answered
                del st.session_state.feedback
                st.rerun()

elif menu == "学習記録":

    st.subheader("📊 苦手単語ランキング")

    query = """
    SELECT i.word, i.meaning,
           COUNT(*) as '間違い回数'
    FROM records r
    JOIN items i ON r.item_id = i.id
    WHERE r.is_correct = 0
    GROUP BY i.id
    ORDER BY COUNT(*) DESC
    """

    history_df = pd.read_sql(query, conn)

    if history_df.empty:
        st.write("まだ記録がありません。クイズを解いてみましょう！")
    else:
        st.table(history_df.head(15))
