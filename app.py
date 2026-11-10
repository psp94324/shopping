"""쇼핑 리스트 앱 (Streamlit) — 여러 기기 동시 사용 지원.

저장소: SQLAlchemy 데이터베이스
- 로컬 기본값: SQLite 파일 (shopping.db)
- 배포: .streamlit/secrets.toml 의 database_url (예: Supabase Postgres)

여러 기기가 같은 DB를 쓰므로, 리스트 전체를 덮어쓰지 않고
아이템 단위(INSERT / UPDATE / DELETE)로만 변경한다.
"""

import hmac
import html
import json
import uuid
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
import streamlit as st

BASE_DIR = Path(__file__).parent
LEGACY_JSON = BASE_DIR / "shopping_list.json"  # 1~3단계에서 쓰던 저장 파일 (자동 이전)
DEFAULT_DB_URL = f"sqlite:///{(BASE_DIR / 'shopping.db').as_posix()}"
MAX_NAME_LEN = 50
MAX_QTY = 999

st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")


def _secret(name: str, default=None):
    """secrets.toml이 없어도 에러 없이 값을 읽는다."""
    try:
        return st.secrets.get(name, default)
    except Exception:  # secrets 파일 없음 등
        return default


# ---------------------------------------------------------------------------
# 데이터베이스 (F5)
# ---------------------------------------------------------------------------
metadata = sa.MetaData()
items_table = sa.Table(
    "items",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(MAX_NAME_LEN), nullable=False),
    sa.Column("quantity", sa.Integer, nullable=False),
    sa.Column("checked", sa.Boolean, nullable=False, default=False),
    sa.Column("created_at", sa.String(32), nullable=False),
)


def _now() -> str:
    # 마이크로초까지 기록해 같은 초에 추가된 아이템도 순서가 보장되게 한다.
    return datetime.now().isoformat(timespec="microseconds")


def _clean_name(name: str) -> str:
    return name.strip()[:MAX_NAME_LEN]


def _clean_qty(quantity) -> int:
    return max(1, min(MAX_QTY, int(quantity)))


def _migrate_legacy_json(engine: sa.Engine) -> str | None:
    """예전 JSON 파일이 있으면 DB로 옮긴다. 화면에 띄울 안내 문구를 반환."""
    if not LEGACY_JSON.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        # utf-8-sig: 메모장/PowerShell이 붙이는 BOM이 있어도 읽힌다.
        data = json.loads(LEGACY_JSON.read_text(encoding="utf-8-sig"))
        if not isinstance(data, list):
            raise ValueError("JSON 최상위가 리스트가 아님")
    except (ValueError, UnicodeDecodeError, OSError):
        backup = LEGACY_JSON.with_name(f"shopping_list.corrupt-{stamp}.json")
        LEGACY_JSON.rename(backup)
        return f"기존 데이터 파일이 손상되어 불러오지 못했어요. 원본은 {backup.name}에 보관했어요."

    rows = []
    for it in data:
        try:
            name = _clean_name(str(it["name"]))
            if name:
                rows.append({
                    "id": str(it.get("id") or uuid.uuid4()),
                    "name": name,
                    "quantity": _clean_qty(it.get("quantity", 1)),
                    "checked": bool(it.get("checked", False)),
                    "created_at": str(it.get("created_at") or _now()),
                })
        except (KeyError, TypeError, ValueError):
            continue
    with engine.begin() as conn:
        existing = {r for (r,) in conn.execute(sa.select(items_table.c.id))}
        new_rows = [r for r in rows if r["id"] not in existing]
        if new_rows:
            conn.execute(sa.insert(items_table), new_rows)
    LEGACY_JSON.rename(LEGACY_JSON.with_name(f"shopping_list.migrated-{stamp}.json"))
    return f"기존 JSON 데이터 {len(new_rows)}개를 데이터베이스로 옮겼어요." if new_rows else None


@st.cache_resource
def get_db() -> tuple[sa.Engine, dict]:
    """DB 엔진을 만들고 테이블을 준비한다. (프로세스당 1회)
    두 번째 값은 이전(migration) 안내 문구로, 처음 접속한 한 명에게만 보여준다."""
    url = _secret("database_url", DEFAULT_DB_URL)
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
    engine = sa.create_engine(url, **kwargs)
    metadata.create_all(engine)
    return engine, {"message": _migrate_legacy_json(engine)}


def _engine() -> sa.Engine:
    return get_db()[0]


def load_items() -> list[dict]:
    """DB에서 최신 아이템 목록을 불러온다. (매 실행마다 호출 → 다른 기기 변경 반영)"""
    with _engine().connect() as conn:
        rows = conn.execute(sa.select(items_table).order_by(items_table.c.created_at))
        return [dict(r._mapping) for r in rows]


def add_item(name: str, quantity: int) -> None:
    """새 아이템을 추가한다. (F1)"""
    with _engine().begin() as conn:
        conn.execute(sa.insert(items_table).values(
            id=str(uuid.uuid4()), name=_clean_name(name), quantity=_clean_qty(quantity),
            checked=False, created_at=_now(),
        ))


def update_item(item_id: str, name: str, quantity: int) -> bool:
    """아이템 이름/수량을 수정한다. 다른 기기에서 이미 삭제됐으면 False. (F2)"""
    with _engine().begin() as conn:
        result = conn.execute(
            sa.update(items_table).where(items_table.c.id == item_id)
            .values(name=_clean_name(name), quantity=_clean_qty(quantity))
        )
    return result.rowcount > 0


def delete_item(item_id: str) -> None:
    """아이템을 삭제한다. (F3)"""
    with _engine().begin() as conn:
        conn.execute(sa.delete(items_table).where(items_table.c.id == item_id))


def set_checked(item_id: str, checked: bool) -> None:
    """구매 완료 여부를 지정한 값으로 설정한다. (F4)
    토글(NOT checked) 대신 값을 지정해, 두 기기가 동시에 눌러도 결과가 뒤집히지 않게 한다."""
    with _engine().begin() as conn:
        conn.execute(sa.update(items_table).where(items_table.c.id == item_id)
                     .values(checked=checked))


def clear_checked() -> int:
    """체크된 아이템을 모두 삭제하고 삭제한 개수를 반환한다. (F3)"""
    with _engine().begin() as conn:
        return conn.execute(sa.delete(items_table).where(items_table.c.checked.is_(True))).rowcount


# ---------------------------------------------------------------------------
# 위젯 콜백 — 콜백은 rerun 전에 실행되므로 한 번 클릭으로 반영됨
# ---------------------------------------------------------------------------
def _escape_md(text: str) -> str:
    """알림(toast) 등 마크다운으로 표시되는 곳에서 서식이 적용되지 않도록 이스케이프."""
    for ch in r"\`*_{}[]()#+-.!~|<>:":
        text = text.replace(ch, "\\" + ch)
    return text


def _toast(message: str, icon: str) -> None:
    st.session_state.toast = (message, icon)


def _qty_note(quantity) -> str:
    return f" (수량은 최대 {MAX_QTY}개라 {MAX_QTY}로 저장)" if quantity > MAX_QTY else ""


def _on_add() -> None:
    name = _clean_name(st.session_state.new_name)
    if not name:
        st.session_state.add_warning = "아이템 이름을 입력해주세요."
        return
    qty = st.session_state.new_qty
    add_item(name, qty)
    _toast(f"'{_escape_md(name)}' 추가했어요{_qty_note(qty)}", "➕")


def _on_toggle(item_id: str) -> None:
    set_checked(item_id, st.session_state[f"check_{item_id}"])


def _on_delete(item_id: str, name: str) -> None:
    delete_item(item_id)
    if st.session_state.editing_id == item_id:
        st.session_state.editing_id = None
    _toast(f"'{_escape_md(name)}' 삭제했어요", "🗑️")


def _on_clear_checked() -> None:
    count = clear_checked()
    _toast(f"구매 완료 항목 {count}개를 삭제했어요", "🧹")


def _edit_keys() -> tuple[str, str]:
    """편집 입력칸의 위젯 key. 편집을 열 때마다 새 토큰을 써서
    이전에 입력하다 만 값이 브라우저에 남아 있어도 섞이지 않게 한다."""
    token = st.session_state.edit_token
    return f"edit_name_{token}", f"edit_qty_{token}"


def _on_edit_start(item: dict) -> None:
    st.session_state.editing_id = item["id"]
    st.session_state.edit_warning = None
    st.session_state.edit_token = uuid.uuid4().hex[:8]
    name_key, qty_key = _edit_keys()
    # 편집 입력칸을 DB의 최신 값으로 채운다
    st.session_state[name_key] = item["name"]
    st.session_state[qty_key] = item["quantity"]


def _on_edit_save(item_id: str) -> None:
    name_key, qty_key = _edit_keys()
    name = _clean_name(st.session_state[name_key])
    if not name:
        st.session_state.edit_warning = "이름은 비워둘 수 없습니다."
        return
    qty = st.session_state[qty_key]
    if update_item(item_id, name, qty):
        note = _qty_note(qty)
        if note:
            _toast(f"'{_escape_md(name)}' 수정했어요{note}", "✏️")
    else:
        _toast("다른 기기에서 이미 삭제된 항목이에요", "⚠️")
    st.session_state.editing_id = None
    st.session_state.edit_warning = None


def _on_edit_cancel() -> None:
    st.session_state.editing_id = None
    st.session_state.edit_warning = None


# ---------------------------------------------------------------------------
# 스타일 (CSS) — 배경색은 지정하지 않아 라이트/다크 모드 모두에서 읽기 쉽게 유지
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
/* 한 줄 레이아웃(입력 폼, 아이템 행)은 좁은 화면에서도 세로로 쌓이지 않게 */
.st-key-add_row [data-testid="stHorizontalBlock"],
.st-key-progress_row [data-testid="stHorizontalBlock"],
[class*="st-key-row_"] [data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 0.5rem;
}
.st-key-add_row [data-testid="stColumn"],
.st-key-progress_row [data-testid="stColumn"],
[class*="st-key-row_"] [data-testid="stColumn"] {
    min-width: 0 !important;
}

/* 체크박스 칸은 체크박스 크기만큼만 */
[class*="st-key-row_"] [data-testid="stColumn"]:first-child {
    flex: 0 0 1.75rem !important;
}

/* 아이템 행: 일정한 간격 + 구분선 */
[class*="st-key-row_"] {
    padding: 0.35rem 0;
    border-bottom: 1px solid rgba(128, 128, 128, 0.2);
}

/* 아이템 이름 (st.html로 표시 → 마크다운/링크 변환 없음) */
.item-name {
    overflow-wrap: anywhere;
    word-break: break-word;
    line-height: 1.4;
}
.item-name.done {
    text-decoration: line-through;
}

/* 구매 완료 항목: 흐리게 */
[class*="st-key-row_done_"] {
    opacity: 0.5;
}

/* 행 안의 요소 여백 제거 → 세로 중앙 정렬 */
[class*="st-key-row_"] [data-testid="stMarkdownContainer"] {
    margin-bottom: 0 !important;
}
[class*="st-key-row_"] [data-testid="stMarkdownContainer"] p {
    margin: 0;
}
[class*="st-key-row_"] [data-testid="stCheckbox"] {
    min-height: 2.6rem;
    display: flex;
    align-items: center;
}

/* 수량 표시 */
.qty {
    font-weight: 600;
    white-space: nowrap;
    text-align: center;
    line-height: 2.6rem;
}

/* 손가락으로 누르기 쉬운 버튼 크기 */
.stButton button, .stFormSubmitButton button {
    min-height: 2.6rem;
    padding: 0.25rem 0.5rem;
}

/* 좁은 화면: 행 버튼은 아이콘만 보이고 글자는 화면 읽기 프로그램용으로만 남김 */
@media (max-width: 640px) {
    [class*="st-key-row_"] .stButton button [data-testid="stMarkdownContainer"] {
        position: absolute !important;
        width: 1px; height: 1px;
        overflow: hidden;
        clip: rect(0 0 0 0);
        white-space: nowrap;
    }
}

/* 상단 여백 축소 */
.block-container {
    padding-top: 2.5rem;
}
</style>
"""


# ---------------------------------------------------------------------------
# 화면 렌더링
# ---------------------------------------------------------------------------
def render_login() -> bool:
    """secrets에 app_password가 있으면 비밀번호를 확인한다. 통과하면 True."""
    password = _secret("app_password")
    if not password or st.session_state.get("authed"):
        return True
    st.title("🛒 쇼핑 리스트")
    with st.form("login"):
        entered = st.text_input("비밀번호", type="password")
        if st.form_submit_button("들어가기", type="primary"):
            if hmac.compare_digest(entered.encode(), str(password).encode()):
                st.session_state.authed = True
                st.rerun()
            st.error("비밀번호가 맞지 않아요.")
    return False


def render_progress(items: list[dict]) -> None:
    """구매 진행 현황을 그린다."""
    col_text, col_refresh = st.container(key="progress_row").columns(
        [7, 3], vertical_alignment="center"
    )
    if items:
        done = sum(item["checked"] for item in items)
        if done == len(items):
            col_text.success("🎉 모두 구매했어요!")
        else:
            col_text.markdown(f"🛍️ **{done} / {len(items)}** 구매 완료")
    # 다른 기기에서 바뀐 내용을 바로 보고 싶을 때 (버튼 클릭 = 다시 불러오기)
    col_refresh.button("새로고침", icon=":material/refresh:", key="refresh",
                       width="stretch", help="다른 기기에서 바뀐 내용 불러오기")
    if items:
        st.progress(done / len(items))


def render_input_form() -> None:
    """아이템 이름/수량 입력 폼을 그린다."""
    with st.form("add_form", clear_on_submit=True, border=False):
        with st.container(key="add_row"):
            col_name, col_qty, col_btn = st.columns(
                [5, 2.6, 2.4], vertical_alignment="bottom"
            )
            col_name.text_input(
                "아이템 이름", key="new_name", max_chars=MAX_NAME_LEN,
                placeholder="예: 우유",
            )
            # max_value를 주면 범위 밖 입력이 조용히 무시되므로, 상한은 저장 시 적용한다
            col_qty.number_input("수량", key="new_qty", min_value=1, value=1, step=1)
            col_btn.form_submit_button("추가", icon=":material/add:", on_click=_on_add,
                                       width="stretch", type="primary")
    if st.session_state.get("add_warning"):
        st.warning(st.session_state.add_warning, icon="⚠️")
        st.session_state.add_warning = None


def _render_edit_row(item: dict) -> None:
    """편집 모드 아이템 한 줄을 그린다."""
    item_id = item["id"]
    name_key, qty_key = _edit_keys()
    with st.container(key=f"row_edit_{item_id}"):
        col_name, col_qty = st.columns([5, 2.6], vertical_alignment="bottom")
        col_name.text_input("이름 수정", key=name_key, max_chars=MAX_NAME_LEN)
        # max_value를 주면 범위 밖 입력이 조용히 무시되므로, 상한은 저장 시 적용한다
        col_qty.number_input("수량 수정", min_value=1, step=1, key=qty_key)
        col_save, col_cancel = st.columns(2)
        col_save.button("저장", icon=":material/save:", key=f"save_{item_id}",
                        width="stretch", type="primary",
                        on_click=_on_edit_save, args=(item_id,))
        col_cancel.button("취소", icon=":material/close:", key=f"cancel_{item_id}",
                          width="stretch", on_click=_on_edit_cancel)
        if st.session_state.get("edit_warning"):
            st.warning(st.session_state.edit_warning, icon="⚠️")


def _render_item_row(item: dict) -> None:
    """일반 모드 아이템 한 줄. [체크박스 | 이름 | 수량 | 수정 | 삭제]"""
    item_id = item["id"]
    state = "done" if item["checked"] else "todo"
    check_key = f"check_{item_id}"
    # 다른 기기에서 체크 상태가 바뀌었을 수 있으므로 위젯 상태를 DB 값으로 맞춘다
    st.session_state[check_key] = item["checked"]
    editing_other = st.session_state.editing_id not in (None, item_id)

    with st.container(key=f"row_{state}_{item_id}"):
        col_check, col_name, col_qty, col_edit, col_del = st.columns(
            [0.5, 6, 1.4, 1.5, 1.5], vertical_alignment="center"
        )
        col_check.checkbox(
            item["name"], key=check_key, label_visibility="collapsed",
            on_change=_on_toggle, args=(item_id,),
        )
        # st.html은 마크다운을 처리하지 않으므로 URL·기호가 그대로 보인다
        col_name.html(
            f"<div class='item-name {state}'>{html.escape(item['name'])}</div>"
        )
        col_qty.html(f"<div class='qty'>x{item['quantity']}</div>")
        col_edit.button("수정", icon=":material/edit:", key=f"edit_{item_id}",
                        width="stretch", disabled=editing_other,
                        on_click=_on_edit_start, args=(item,))
        col_del.button("삭제", icon=":material/delete:", key=f"del_{item_id}",
                       width="stretch", on_click=_on_delete,
                       args=(item_id, item["name"]))


def _render_rows(items: list[dict]) -> None:
    for item in items:
        if item["id"] == st.session_state.editing_id:
            _render_edit_row(item)
        else:
            _render_item_row(item)


def render_item_list(items: list[dict]) -> None:
    """아이템 목록을 '구매할 항목' / '구매 완료' 영역으로 나눠 그린다."""
    if not items:
        st.info("아직 아이템이 없어요. 위에서 추가해보세요!", icon="📝")
        return

    # items는 created_at 오름차순 → 미체크는 최신순, 체크된 항목은 추가순
    unchecked = [i for i in reversed(items) if not i["checked"]]
    checked = [i for i in items if i["checked"]]

    if unchecked:
        st.markdown(f"##### 🧺 구매할 항목 ({len(unchecked)})")
        _render_rows(unchecked)

    if checked:
        st.markdown(f"##### ✅ 구매 완료 ({len(checked)})")
        _render_rows(checked)
        st.write("")
        st.button("체크된 항목 모두 삭제", icon=":material/delete_sweep:",
                  key="clear_checked", on_click=_on_clear_checked)


def init_state() -> None:
    """session_state를 초기화한다."""
    st.session_state.setdefault("editing_id", None)
    st.session_state.setdefault("edit_token", "")
    st.session_state.setdefault("add_warning", None)
    st.session_state.setdefault("edit_warning", None)
    st.session_state.setdefault("toast", None)


def main() -> None:
    """앱 진입점."""
    init_state()
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    if not render_login():
        return

    _, notice = get_db()
    message = notice.pop("message", None)  # 한 번 꺼내면 다른 접속자에게는 다시 안 뜸
    if message:
        st.warning(message, icon="ℹ️")

    if st.session_state.toast:
        message, icon = st.session_state.toast
        st.toast(message, icon=icon)
        st.session_state.toast = None

    items = load_items()  # 매 실행마다 DB에서 최신 상태를 읽는다
    # 편집 중이던 항목이 다른 기기에서 삭제됐으면 편집 모드 해제
    if st.session_state.editing_id not in {i["id"] for i in items}:
        st.session_state.editing_id = None

    st.title("🛒 쇼핑 리스트")
    render_progress(items)
    st.divider()
    render_input_form()
    st.divider()
    render_item_list(items)


main()
