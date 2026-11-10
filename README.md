# 🛒 쇼핑 리스트

Streamlit으로 만든 쇼핑 리스트 웹 앱입니다.
아이템 추가·수정·삭제·체크(구매 완료)를 지원하고, **여러 기기에서 같은 리스트를 함께** 쓸 수 있습니다.
자세한 요구사항은 [PRD.md](PRD.md)를 참고하세요.

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 http://localhost:8501 로 접속합니다.
같은 와이파이의 휴대폰에서는 터미널에 표시되는 `Network URL`로 접속하면 PC와 같은 리스트를 씁니다.

- 데이터는 `shopping.db`(SQLite) 파일에 저장됩니다.
- 예전 버전의 `shopping_list.json`이 있으면 첫 실행 때 자동으로 DB로 옮기고, 원본은 `shopping_list.migrated-<시각>.json`으로 남깁니다.
- 다른 기기에서 바꾼 내용은 아무 버튼을 누르거나 **새로고침** 버튼을 누르면 반영됩니다.

## 설정 (`.streamlit/secrets.toml`)

`.streamlit/secrets.toml.example`을 `secrets.toml`로 복사해 사용합니다. 두 값 모두 선택입니다.

| 키 | 설명 | 없을 때 |
|---|---|---|
| `database_url` | SQLAlchemy DB 주소 (예: Supabase Postgres) | 로컬 `shopping.db` 사용 |
| `app_password` | 앱 접속 비밀번호 | 비밀번호 없이 열림 |

## 배포 (Streamlit Community Cloud + Supabase)

Cloud는 앱이 재시작되면 로컬 파일이 지워지므로, 배포할 때는 외부 DB를 연결해야 합니다.

1. **Supabase 프로젝트 만들기** — [supabase.com](https://supabase.com)에서 무료 프로젝트 생성
2. **연결 주소 복사** — 프로젝트 상단 **Connect** → Connection string → **Session pooler** URI 복사 (`[YOUR-PASSWORD]`를 DB 비밀번호로 바꾸기)
3. **GitHub에 올리기** — 이 폴더를 저장소로 push (`secrets.toml`, `shopping.db`는 `.gitignore`로 제외됨)
4. **앱 배포** — [share.streamlit.io](https://share.streamlit.io) → New app → 저장소 / 브랜치 / `app.py` 선택
5. **Secrets 입력** — Advanced settings(또는 배포 후 앱 Settings) → Secrets에 붙여넣기:
   ```toml
   database_url = "postgresql://...(2번에서 복사한 주소)"
   app_password = "원하는-비밀번호"
   ```
6. 발급된 `https://<앱이름>.streamlit.app` 주소를 각 기기에서 열기

테이블(`items`)은 앱이 처음 실행될 때 자동으로 만들어집니다.

## 파일 구조

```
shopping/
├── app.py                         # Streamlit 앱 (DB 저장, 여러 기기 동시 사용)
├── requirements.txt
├── .streamlit/config.toml         # 라이트/다크 테마
├── .streamlit/secrets.toml.example
├── PRD.md                         # 제품 요구사항
├── review_report.md               # Playwright 검토 보고서 + 수정 결과
└── prompts/                       # 단계별 개발 프롬프트
```
