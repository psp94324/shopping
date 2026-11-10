# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Single-file Streamlit shopping-list app (add / edit / delete / check items) shared across multiple devices, intended for Streamlit Community Cloud + an external Postgres (e.g. Supabase). Requirements live in `PRD.md` (v1.1); the user communicates in Korean and UI text is Korean.

History: built via staged prompts in `prompts/` (skeleton → features → UI → Playwright review). `review_report.md` holds the review findings (#1–#10) and, in §7, how each was fixed and re-tested. The original JSON-file storage was replaced by a database because multi-device use overwrote data. `prompts/*.md` and `review_report.md` §1–6 still describe the old JSON/`session_state` design and line numbers. Treat them as history, not as the current spec; `PRD.md` v1.1 and `app.py` are authoritative.

## Commands

```bash
pip install -r requirements.txt
streamlit run app.py                                             # http://localhost:8501
streamlit run app.py --server.headless true --server.port 8502   # no browser auto-open (for Playwright)
python -W error -m py_compile app.py                             # syntax check
curl -s http://localhost:8501/_stcore/health                     # "ok" when ready
```

There is no test suite or linter. Verification is done by driving the running app with the Playwright MCP tools (`browser_run_code_unsafe` for multi-step scenarios; screenshots go to `screenshots/`). Multi-device behavior is tested with two `browser.newContext()` sessions.

To test without touching the user's data, copy `app.py` and `.streamlit/config.toml` into a scratch directory and run it there on another port: storage paths resolve relative to `app.py`, so the copy gets its own `shopping.db`.

Changes to `.streamlit/config.toml` or `secrets.toml` need a server restart; `app.py` changes only need a browser rerun. `get_db()` is `@st.cache_resource`, so migration and engine setup run once per process.

## Architecture (app.py)

- **Storage:** SQLAlchemy Core, one table `items` (id uuid4 PK, name ≤50, quantity 1–999, checked bool, created_at ISO string with microseconds). The URL comes from `st.secrets["database_url"]` and defaults to SQLite `shopping.db` next to `app.py`. `_secret()` wraps `st.secrets` so a missing secrets file isn't an error.
- **The DB is the source of truth:** `main()` calls `load_items()` on every run. Writes are per-item statements (`add_item`, `update_item`, `delete_item`, `set_checked`, `clear_checked`), never a whole-list overwrite. This is what makes concurrent devices safe. `set_checked` writes an explicit value instead of `NOT checked`, so simultaneous taps don't flip twice. `update_item` returns False when another device already deleted the row.
- **Legacy migration:** on first engine creation, `_migrate_legacy_json` imports `shopping_list.json` (read as `utf-8-sig`), then renames it to `.migrated-<ts>.json`. A corrupt file is renamed to `.corrupt-<ts>.json` instead. The notice is shown once per process (popped from the cached dict).
- **Mutations happen only in widget callbacks** (`on_click` / `on_change`), never inline and never with `st.rerun()` (except after login). Warnings and toasts pass from callbacks to the next render through `session_state` (`add_warning`, `edit_warning`, `toast`).
- **Widget state is re-synced from the DB every run:** each `check_<id>` key is assigned from the DB before the checkbox is created, without passing `value=`. Edit inputs use keys suffixed with `edit_token`, regenerated on every edit start and pre-filled in `_on_edit_start`. This avoids stale browser-side values.
- **Item names render through `col.html(html.escape(name))`, not markdown.** Checkbox labels are collapsed, because markdown labels autolink URLs and expose escape backslashes. Toast text uses `_escape_md()`.
- **Quantity:** `number_input` has `min_value=1` but deliberately no `max_value`, because an out-of-range value is silently dropped by the frontend. The cap is applied server-side in `_clean_qty`, with a toast.
- **Styling:** `CUSTOM_CSS` targets keyed containers (`st.container(key=...)` emits a `st-key-<key>` class). Row keys encode state (`row_todo_<id>`, `row_done_<id>`, `row_edit_<id>`, `add_row`, `progress_row`) to fade done rows and force `nowrap` columns on mobile. The CSS also relies on Streamlit internals (`data-testid="stColumn"`, `stHorizontalBlock`, `stMarkdownContainer`); re-verify layout after a Streamlit upgrade (pinned `>=1.58,<2`).
- **Theme:** `.streamlit/config.toml` uses `[theme.light]` / `[theme.dark]`. Colors directly under `[theme]` force light mode.
- **Optional password gate:** `render_login()` uses `st.secrets["app_password"]`, compared with `hmac.compare_digest`, and is remembered per session.

## Gotchas

- Never use `st.session_state.items`; it resolves to the mapping's `.items()` method.
- In Playwright, select buttons with `button:visible` + `hasText` rather than `nth()`. Item names are in `.item-name`; checkboxes are clicked via `[data-testid="stCheckbox"] label`.
- Playwright full-page screenshots of Streamlit often come out blank. Take viewport screenshots after waiting for `[data-testid="stApp"]` to leave `data-test-script-state="running"`.
- Windows PowerShell `Set-Content -Encoding utf8` writes a BOM; use Python or `printf` when generating test data.
