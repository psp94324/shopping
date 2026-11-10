# 1단계: 기본 뼈대 작성

## 프롬프트

```
PRD.md를 읽고 쇼핑 리스트 앱의 기본 뼈대를 만들어줘.
이번 단계에서는 실제 기능 구현 없이 구조만 잡는 게 목표야.

[만들 파일]
1. app.py
   - st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")
   - 제목 "🛒 쇼핑 리스트" 표시
   - 아래 함수들을 정의만 하고, 내부는 TODO 주석과 pass(또는 최소 반환값)로 둘 것
     - load_items() -> list[dict]          # JSON 파일에서 불러오기
     - save_items(items: list[dict]) -> None  # JSON 파일에 저장
     - add_item(name: str, quantity: int) -> None
     - update_item(item_id: str, name: str, quantity: int) -> None
     - delete_item(item_id: str) -> None
     - toggle_item(item_id: str) -> None
     - clear_checked() -> None
     - render_input_form() -> None
     - render_item_list() -> None
     - main() -> None
   - st.session_state 초기화 코드 작성 (shopping_items, editing_id)
     ※ "items"는 session_state의 .items() 메서드와 충돌하므로 사용 금지
   - 데이터 파일 경로는 pathlib로 app.py 기준 "shopping_list.json"으로 상수 정의
   - 각 함수에 한 줄 docstring 작성
2. requirements.txt  — streamlit
3. .gitignore         — shopping_list.json, __pycache__/, .venv/, .streamlit/secrets.toml
4. README.md          — 프로젝트 소개, 로컬 실행 방법(pip install / streamlit run app.py)

[데이터 모델]
PRD 5장의 구조를 따름: id(uuid4 str), name(str), quantity(int), checked(bool), created_at(ISO 8601 str)

[완료 조건]
- `streamlit run app.py` 실행 시 에러 없이 제목이 화면에 표시된다.
- 함수 구조가 PRD 4장의 F1~F5 기능과 1:1로 대응된다.
```

## 확인 체크리스트
- [ ] `streamlit run app.py`가 에러 없이 실행된다.
- [ ] requirements.txt, .gitignore, README.md가 생성되었다.
- [ ] 함수 시그니처가 위 목록과 일치한다.
