import json
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------
# 기본 설정 (브라우저 탭 제목과 아이콘)
# ---------------------------------------------------------------
APP_TITLE = "고혈압·당뇨병 의료이용률 실습실"
APP_ICON = "🩺"

st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "국민건강보험공단_고혈압_당뇨병_의료이용률_20241231.CSV"
# 이 파일은 UTF-8이 아니라 cp949(한글 윈도우 기본 인코딩)로 저장되어 있어요.
ENCODINGS = ["utf-8-sig", "cp949"]

SAVE_DIR = BASE_DIR / "내_기록"
SAVE_FILE = SAVE_DIR / "기록.json"

# 큰 숫자 카드 스타일
st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] { font-size: 2.3rem; font-weight: 700; }
    [data-testid="stMetricLabel"] p { font-size: 1.1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------
# 저장 / 불러오기 (내_기록/기록.json)
# ---------------------------------------------------------------
def load_notes() -> dict:
    """저장된 기록을 불러온다. 파일이 없거나 깨졌으면 빈 기록을 돌려준다."""
    empty = {"meanings": {}, "source": ""}
    if not SAVE_FILE.exists():
        return empty
    try:
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        return {
            "meanings": dict(data.get("meanings", {})),
            "source": str(data.get("source", "")),
        }
    except (json.JSONDecodeError, OSError, AttributeError, TypeError, ValueError):
        return empty


def save_notes(meanings: dict | None = None, source: str | None = None) -> None:
    """바뀐 부분만 갱신해서 json 파일에 저장한다."""
    notes = load_notes()
    if meanings is not None:
        notes["meanings"] = meanings
    if source is not None:
        notes["source"] = source
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    SAVE_FILE.write_text(
        json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------
# 데이터 불러오기
# ---------------------------------------------------------------
@st.cache_data(show_spinner="데이터를 불러오는 중...")
def load_data() -> pd.DataFrame:
    last_error = None
    for enc in ENCODINGS:
        try:
            # 성별(1, 2, ALL)과 연령그룹(00, 10, ... ALL)은 글자 그대로 읽는다.
            return pd.read_csv(DATA_FILE, encoding=enc, dtype={"성별": str, "연령그룹": str})
        except UnicodeDecodeError as e:
            last_error = e
    raise last_error


def fmt(v, comma: bool = False) -> str:
    """3.0 -> 3 처럼 보기 좋게 바꾼다."""
    f = float(v)
    if f.is_integer():
        return f"{int(f):,}" if comma else str(int(f))
    return f"{f:g}"


def describe_values(s: pd.Series) -> str:
    """열의 '값의 종류'를 글로 설명한다."""
    nonnull = s.dropna()
    n = nonnull.nunique()
    if n == 0:
        return "값 없음"
    if not pd.api.types.is_numeric_dtype(s):
        if n <= 10:
            return f"{n}가지: " + ", ".join(sorted(str(v) for v in nonnull.unique()))
        first = [str(v) for v in nonnull.unique()[:5]]
        return f"{n}가지: " + ", ".join(first) + " …"
    if n <= 5:
        return f"{n}가지: " + ", ".join(fmt(v) for v in sorted(nonnull.unique()))
    return (
        f"숫자 (서로 다른 값 {n:,}개, "
        f"최소 {fmt(nonnull.min(), True)} ~ 최대 {fmt(nonnull.max(), True)})"
    )


if not DATA_FILE.exists():
    st.error(
        "데이터 파일을 찾을 수 없어요. 아래 파일을 main.py와 같은 폴더에 넣어 주세요.\n\n"
        f"`{DATA_FILE.name}`"
    )
    st.stop()

try:
    df = load_data()
except Exception as e:
    st.error(f"데이터를 읽지 못했어요.\n\n{e}")
    st.stop()

notes = load_notes()

# ---------------------------------------------------------------
# 화면 맨 위: 제목
# ---------------------------------------------------------------
st.title(f"{APP_ICON} {APP_TITLE}")
st.caption("첫 화면 · 이 데이터는 무엇일까요?")

# ---------------------------------------------------------------
# 1) 큰 숫자 카드 네 개
#    전국 · 전체 시군구 · 모든 성별 · 모든 연령 줄(합계 줄)의 값을 쓴다.
# ---------------------------------------------------------------
n_rows = len(df)
n_cols = df.shape[1]

national = df[
    (df["시도"] == "전국")
    & (df["시군구"] == "전체")
    & (df["성별"] == "ALL")
    & (df["연령그룹"] == "ALL")
]
if len(national) == 1:
    users = int(national["분자(명)"].iloc[0])
    base = int(national["분모(명)"].iloc[0])
    users_text = f"{users:,}명"
    ratio_text = f"{users / base * 100:.2f}%" if base else "-"
else:
    users_text = ratio_text = "-"

c1, c2, c3, c4 = st.columns(4)
c1.metric("전체 줄 수", f"{n_rows:,}줄", border=True)
c2.metric("열 개수", f"{n_cols}개", border=True)
c3.metric("전국 의료이용자 수(분자)", users_text, border=True)
c4.metric("전국 의료이용률", ratio_text, border=True)
st.caption(
    "이 표의 한 줄은 사람 한 명이 아니라 (지역·성별·연령대) 집단 하나예요. "
    "카드의 셋째·넷째 값은 '전국 · 전체 · 성별 ALL · 연령그룹 ALL' 줄에서 가져왔어요."
)

# ---------------------------------------------------------------
# 2) 열 설명 표 (우리말 뜻 칸은 직접 입력)
# ---------------------------------------------------------------
st.subheader("열 설명표")
st.write("교재를 보고 **우리말 뜻** 칸을 채운 뒤 **저장하기**를 눌러 주세요.")

table = pd.DataFrame(
    {
        "열 이름": df.columns,
        "우리말 뜻": [notes["meanings"].get(c, "") for c in df.columns],
        "값의 종류": [describe_values(df[c]) for c in df.columns],
        "빈 값 개수": [int(df[c].isna().sum()) for c in df.columns],
    }
)

with st.form("meaning_form"):
    edited = st.data_editor(
        table,
        hide_index=True,
        disabled=["열 이름", "값의 종류", "빈 값 개수"],
        column_config={
            "열 이름": st.column_config.TextColumn("열 이름"),
            "우리말 뜻": st.column_config.TextColumn(
                "우리말 뜻", help="교재를 보고 직접 적어 주세요."
            ),
            "값의 종류": st.column_config.TextColumn("값의 종류", width="large"),
            "빈 값 개수": st.column_config.NumberColumn("빈 값 개수"),
        },
        key="meaning_editor",
    )
    saved_meaning = st.form_submit_button("💾 저장하기")

if saved_meaning:
    new_meanings = {
        row["열 이름"]: ("" if pd.isna(row["우리말 뜻"]) else str(row["우리말 뜻"]))
        for _, row in edited.iterrows()
    }
    try:
        save_notes(meanings=new_meanings)
        st.success("우리말 뜻을 저장했어요.")
    except OSError as e:
        st.error(f"저장하지 못했어요: {e}")

# ---------------------------------------------------------------
# 3) 데이터 처음 다섯 줄 (원본 그대로)
# ---------------------------------------------------------------
st.subheader("데이터 처음 다섯 줄")
st.dataframe(df.head(5), hide_index=True)

# ---------------------------------------------------------------
# 4) 데이터 출처
# ---------------------------------------------------------------
st.subheader("데이터 출처")
with st.form("source_form"):
    source_text = st.text_area(
        "교재에 나온 출처를 적어 주세요.",
        value=notes["source"],
        height=120,
        placeholder="여기에 출처를 적어 주세요.",
    )
    saved_source = st.form_submit_button("💾 저장하기")

if saved_source:
    try:
        save_notes(source=source_text)
        st.success("출처를 저장했어요.")
    except OSError as e:
        st.error(f"저장하지 못했어요: {e}")
