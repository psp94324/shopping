# 2단계: 기능 추가

## 프롬프트

```
PRD.md와 현재 app.py를 읽고, 1단계에서 만든 뼈대의 TODO 함수들을 실제로 구현해줘.
UI 꾸미기는 3단계에서 할 거니까 이번엔 기본 Streamlit 위젯으로 기능만 정확히 동작하게 해줘.

[F5. 데이터 저장] — 먼저 구현
- load_items(): 파일이 없거나 JSON이 손상되었거나 형식이 잘못되면 빈 리스트 반환 (앱이 죽으면 안 됨)
- save_items(): UTF-8, ensure_ascii=False, indent=2로 저장
- 앱 시작 시 session_state에 shopping_items가 없을 때만 load_items()로 불러오기
- 모든 변경(추가/수정/삭제/체크) 직후 save_items() 호출

[F1. 아이템 추가]
- st.form(clear_on_submit=True) 사용 → Enter 키 제출 + 입력 필드 자동 초기화
- 이름 text_input(max_chars=50), 수량 number_input(min_value=1, value=1, step=1)
- 이름을 strip() 후 비어 있으면 st.warning 표시하고 추가하지 않기
- 새 아이템: id=uuid4, checked=False, created_at=현재 시각 ISO 문자열

[F2. 아이템 수정]
- 각 아이템의 "수정" 버튼 → session_state.editing_id에 해당 id 저장
- 편집 모드인 아이템은 이름/수량 입력칸 + "저장"/"취소" 버튼으로 표시
- 저장 시 빈 이름이면 경고하고 저장하지 않기
- 저장/취소 후 editing_id = None
- 한 번에 하나의 아이템만 편집 가능

[F3. 아이템 삭제]
- 각 아이템의 "삭제" 버튼으로 개별 삭제
- 편집 중인 아이템을 삭제하면 editing_id도 초기화
- "체크된 항목 모두 삭제" 버튼: 체크된 항목이 있을 때만 표시

[F4. 아이템 체크]
- st.checkbox로 checked 토글 (on_change 콜백 사용)
- 체크된 항목은 이름에 취소선(~~이름~~) 표시
- 정렬: 미체크 항목(최신순) 먼저, 체크된 항목 아래
- 상단에 "N / M 구매 완료" 텍스트와 st.progress 표시
- 리스트가 비어 있으면 st.info("리스트가 비어 있습니다") 표시

[구현 규칙]
- 모든 위젯 key는 아이템 id 기반으로 고유하게 (예: f"check_{id}", f"del_{id}")
- 버튼 동작은 on_click 콜백으로 처리해서 두 번 클릭해야 반영되는 문제가 없게 할 것
- 리스트를 순회하면서 같은 리스트를 수정하지 말 것
- 콜백 안에서 st.rerun() 호출하지 말 것

[완료 조건]
PRD 10장 인수 조건 중 UI 디자인을 제외한 모든 항목을 만족해야 해.
구현 후 `python -m py_compile app.py`로 문법 오류가 없는지 확인해줘.
```

## 확인 체크리스트
- [ ] 아이템 추가 / 빈 이름 경고
- [ ] 수정 → 저장 / 취소
- [ ] 개별 삭제, 체크 항목 일괄 삭제
- [ ] 체크 시 취소선 + 아래로 이동 + 진행률 갱신
- [ ] 새로고침 후에도 데이터 유지
- [ ] shopping_list.json을 지우거나 내용을 깨뜨려도 앱이 정상 실행
