import glob
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# --- 文字化け対策（Python 3.12対応 / OS標準フォントの設定） ---
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = [
    'Meiryo',
    'Yu Gothic',
    'Hiragino Sans',
    'IPAexGothic',
    'sans-serif',
]
plt.rcParams['axes.unicode_minus'] = False  # マイナス記号の文字化け防止

# --- 画面設定 ---
st.set_page_config(page_title="歩行分析・転倒予測システム", layout="wide")

st.title("🦵 高齢者転倒予測システム")
st.write(
    "スマートフォン（phyphox）の3軸加速度データから歩行のエラーを検知します。"
)

# ==========================================
# 1. サイドバーでモード選択 ＆ ファイル読み込み
# ==========================================
st.sidebar.header("📁 データ選択")

mode = st.sidebar.radio(
    "データの選択方法を選んでください",
    ["自分のファイルを選択（ファイルアップロード）", "サンプルデータから選択"],
)


# Z軸・Y軸・Timeのカラム名を自動検索する関数
def get_column_name(df, target_char):
  for col in df.columns:
    if target_char.lower() in col.lower():
      return col
  return None


df_normal = None
df_test = None
normal_name = ""
test_name = ""

if mode == "自分のファイルを選択（ファイルアップロード）":
  st.sidebar.subheader("📤 CSVファイルをアップロード")

  # 基準データ（正常）のアップロード
  uploaded_normal = st.sidebar.file_uploader(
      "1. 基準データ（正常歩行）を選択", type=["csv"], key="norm"
  )
  # 比較データ（分析対象）のアップロード
  uploaded_test = st.sidebar.file_uploader(
      "2. 比較・対象データ（分析対象）を選択", type=["csv"], key="test"
  )

  if uploaded_normal is not None and uploaded_test is not None:
    df_normal = pd.read_csv(uploaded_normal)
    df_test = pd.read_csv(uploaded_test)
    normal_name = uploaded_normal.name
    test_name = uploaded_test.name
  else:
    st.info(
        "👈 左側のサイドバーから「基準データ」と「対象データ」の2つのCSVファイルをアップロードしてください。"
    )
    st.stop()

else:
  # サンプルデータ（既存のCSVファイル）から選択するモード
  all_csv_files = glob.glob("*.csv")
  if len(all_csv_files) < 2:
    st.warning("⚠️ フォルダ内に 2つ 以上のサンプルCSVファイルが見つかりません。")
    st.stop()

  normal_file = st.sidebar.selectbox(
      "1. 基準データ（Normal）を選択", all_csv_files, index=0
  )
  default_test_idx = 1 if len(all_csv_files) > 1 else 0
  test_file = st.sidebar.selectbox(
      "2. 比較・対象データ（Test）を選択",
      all_csv_files,
      index=default_test_idx,
  )

  df_normal = pd.read_csv(normal_file)
  df_test = pd.read_csv(test_file)
  normal_name = normal_file
  test_name = test_file



# ==========================================
# センサー直接取得機能（JavaScript連携）
# ==========================================
st.subheader("📱 スマホで直接リアルタイム計測")

sensor_html = """
<div style="border: 1px solid #ccc; padding: 15px; border-radius: 8px;">
    <button id="startBtn" style="padding: 10px 20px; font-size: 16px; background-color: #007bff; color: white; border: none; border-radius: 5px;">計測開始（センサー許可）</button>
    <p id="status" style="margin-top: 10px; font-weight: bold;">ボタンを押して計測を開始してください</p>
    <div id="output" style="font-family: monospace;">
        Z軸 (上下): <span id="accZ">0.00</span> m/s²<br>
        Y軸 (左右): <span id="accY">0.00</span> m/s²
    </div>
</div>

<script>
const startBtn = document.getElementById('startBtn');
const status = document.getElementById('status');
const accZ = document.getElementById('accZ');
const accY = document.getElementById('accY');

startBtn.addEventListener('click', async () => {
    // iOS 13+ のパーミッション要求
    if (typeof DeviceMotionEvent !== 'undefined' && typeof DeviceMotionEvent.requestPermission === 'function') {
        try {
            const response = await DeviceMotionEvent.requestPermission();
            if (response === 'granted') {
                startListening();
            } else {
                status.innerText = ⚠️ センサーのアクセスが拒否されました';
            }
        } catch (e) {
            status.innerText = 'エラー: ' + e;
        }
    } else {
        // Android / 古いiOS
        startListening();
    }
});

function startListening() {
    status.innerText = '🟢 計測中... スマホを動かしてください';
    window.addEventListener('devicemotion', (event) => {
        const acc = event.accelerationIncludingGravity || event.acceleration;
        if (acc) {
            accZ.innerText = (acc.z || 0).toFixed(2);
            accY.innerText = (acc.y || 0).toFixed(2);
        }
    });
}
</script>
"""

components.html(sensor_html, height=180)


# ==========================================
# 2. カラム自動判別
# ==========================================
df_normal.columns = [c.strip() for c in df_normal.columns]
df_test.columns = [c.strip() for c in df_test.columns]

z_col_norm = get_column_name(df_normal, "z")
y_col_norm = get_column_name(df_normal, "y")
t_col_norm = get_column_name(df_normal, "time")

z_col_test = get_column_name(df_test, "z")
y_col_test = get_column_name(df_test, "y")
t_col_test = get_column_name(df_test, "time")

if not z_col_norm or not z_col_test:
  st.error(
      "🚨 Z軸（上下方向）のデータが見つかりません。CSVのカラム名を確認してください。"
  )
  st.stop()

st.success(f"📊 分析実行中: 基準【 {normal_name} 】 🆚 対象【 {test_name} 】")

# ==========================================
# 3. アルゴリズム計算（振幅・キープ率）
# ==========================================
z_normal_amp = df_normal[z_col_norm].max() - df_normal[z_col_norm].min()
y_normal_amp = df_normal[y_col_norm].max() - df_normal[y_col_norm].min()

z_test_amp = df_test[z_col_test].max() - df_test[z_col_test].min()
y_test_amp = df_test[y_col_test].max() - df_test[y_col_test].min()

z_score = (z_test_amp / z_normal_amp) * 100 if z_normal_amp != 0 else 100.0
y_score = (y_test_amp / y_normal_amp) * 100 if y_normal_amp != 0 else 100.0

# ==========================================
# 4. 画面表示の作成（スコア・危険度判定）
# ==========================================
col1, col2 = st.columns(2)

with col1:
  st.subheader("🦵 すり足リスク分析 (Z軸: 垂直方向)")
  st.metric(
      label="上下の足上げキープ率",
      value=f"{z_score:.1f} %",
      delta=f"{z_score - 100:.1f} %",
  )

  if z_score >= 85:
    st.success(
        "🟢 危険度【低】(正常・キープ)\n\n十分な高さまで足が上がっています。つまづきリスクは低いです。"
    )
  elif 70 <= z_score < 85:
    st.warning(
        "🟡"
        " 危険度【中】(注意・すり足兆候)\n\n無自覚に足の上がりが悪くなっています。小さな段差に注意が必要です。"
    )
  else:
    st.error(
        "🔴"
        " 危険度【高】(警告・骨折リスク)\n\n波形が著しく平坦化しています。すり足状態であり、転倒リスクが極めて高いです。"
    )

with col2:
  st.subheader("⚖️ ふらつきリスク分析 (Y軸: 左右方向)")
  st.metric(
      label="左右のブレ拡大率",
      value=f"{y_score:.1f} %",
      delta=f"{y_score - 100:.1f} %",
      delta_color="inverse",
  )

  if y_score <= 115:
    st.success(
        "🟢 危険度【低】(正常・キープ)\n\n左右のバランスが安定しています。体幹が維持されています。"
    )
  elif 115 < y_score <= 130:
    st.warning(
        "🟡"
        " 危険度【中】(注意・ふらつき兆候)\n\n歩行時の横揺れが大きくなっています。下肢の筋力低下の可能性があります。"
    )
  else:
    st.error(
        "🔴"
        " 危険度【高】(警告・転倒リスク)\n\n左右への重大なブレを検知しました。バランスを崩して横転する危険があります。"
    )

# ==========================================
# 5. 波形の可視化（グラフ表示）
# ==========================================
st.markdown("---")
st.subheader("📊 加速度データの波形比較（生体信号の可視化）")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))

time_norm = df_normal[t_col_norm] if t_col_norm else df_normal.index
time_test = df_test[t_col_test] if t_col_test else df_test.index

# Z軸プロット
ax1.plot(
    time_norm.head(500),
    df_normal[z_col_norm].head(500),
    label=f"基準 ({normal_name})",
    color="gray",
    alpha=0.7,
)
ax1.plot(
    time_test.head(500),
    df_test[z_col_test].head(500),
    label=f"対象 ({test_name})",
    color="blue",
)
ax1.set_title("Z軸: 上下の揺れ (すり足の判定データ)")
ax1.legend()
ax1.grid(True)

# Y軸プロット
ax2.plot(
    time_norm.head(500),
    df_normal[y_col_norm].head(500),
    label=f"基準 ({normal_name})",
    color="gray",
    alpha=0.7,
)
ax2.plot(
    time_test.head(500),
    df_test[y_col_test].head(500),
    label=f"対象 ({test_name})",
    color="orange",
)
ax2.set_title("Y軸: 左右のブレ (ふらつきの判定データ)")
ax2.legend()
ax2.grid(True)

plt.tight_layout()
st.pyplot(fig)
