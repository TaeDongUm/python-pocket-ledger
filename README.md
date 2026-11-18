# python-pocket-ledger

Python 표준 라이브러리로 만드는 콘솔 용돈 기입장입니다. 

`python -m budget_app list --limit 3`은 최근 거래를 최대 3건 표시합니다.
`--limit`을 생략하면 최대 10건을 표시합니다. 거래 날짜가 최근인 순서대로
표시하고, 날짜가 같으면 JSONL 파일에 나중에 기록된 거래를 먼저 표시합니다.

`python -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food --type expense --q lunch --tag meal`처럼 검색 조건을 조합할 수 있습니다.
날짜 범위에는 양 끝 날짜가 포함됩니다. 메모 키워드는 대소문자를 무시하고 부분 일치로, 태그는 이름이 정확히 일치하는지 확인합니다. 결과는 목록과 같은 최신순으로 표시합니다.

`python -m budget_app summary --month 2024-01 --top 3`은 해당 월의 총수입, 총지출, 잔액과 지출 상위 카테고리를 표시합니다.
`--top`의 기본값은 5이며, 지출 합계가 같으면 카테고리 이름 순으로 표시합니다.

`python -m budget_app budget set --month 2024-01 --amount 500000`으로 월 예산을 설정합니다.
같은 달의 예산을 다시 설정하면 기존 금액을 갱신합니다. `summary`에 예산 사용률이
표시되며, 지출이 예산을 넘으면 초과액을 안내합니다.

`python -m budget_app update --id <id> --amount 15000 --memo "점심"`은 지정한 필드만 수정합니다.
`--memo ""`와 `--tags ""`로 메모와 태그를 지울 수 있습니다. `python -m budget_app delete --id <id>`는 해당 거래를 삭제합니다.

### CSV 가져오기와 내보내기

- 가져오기 예시 `python -m budget_app import --from input.csv`
- 내보내기 예시 `python -m budget_app export --out output.csv --month 2024-01`
- 날짜 범위 예시 `python -m budget_app export --out output.csv --from 2024-01-01 --to 2024-01-31`

CSV는 UTF-8과 헤더를 사용합니다. 열 순서는 `date,type,category,amount,memo,tags`이며, 마지막 두 열은 가져올 때 생략할 수 있습니다. 날짜는 `YYYY-MM-DD`, 타입은 `income` 또는 `expense`, 카테고리는 등록된 이름, 금액은 양의 정수입니다. 태그가 여러 개면 한 필드에 쉼표로 구분합니다.

가져올 때 거래 ID를 새로 발급합니다. 잘못된 행이 하나라도 있으면 전체 가져오기를 취소하고 오류 위치를 표시합니다. 성공하면 `imported`와 `skipped` 건수를 출력합니다. 내보낼 때는 월이나 날짜 범위 중 하나를 지정하며, 날짜 범위는 양 끝을 포함합니다.

## 작업 체크리스트

0. 구현 정책 확정
- [x] Python 3.10 이상·표준 라이브러리만 사용
- [x] 실행 명령을 python -m budget_app <command> [options]로 확정
- [x] 기본 저장 위치를 실행 디렉터리의 ./data로 정하고 --data-dir 지원
- [x] 저장 파일을 transactions.jsonl, categories.jsonl, budgets.jsonl로 통일
- [x] 기본 카테고리 자동 생성 및 사용 중인 카테고리 삭제 거부 정책 확정
- [x] update는 옵션 방식으로 고정
- [x] “최신순”을 거래 날짜 내림차순, 같은 날짜일 때의 순서까지 정의
- [x] CSV import 오류 정책 확정: 유효 행만 반영할지, 파일 전체를 취소할지 결정
- [ ] 백업 파일 위치와 반복 거래의 중복 생성 방지 규칙 결정

1. 프로젝트 구조와 CLI
- [x] budget_app/__main__.py로 모듈 실행 지원
- [x] CLI·모델·저장소·서비스를 최소 3개 이상의 모듈로 분리
- [x] add/list/search/summary/budget/category/update/delete/import/export 명령 등록
- [x] 보너스 명령 backup과 반복 거래 명령 등록
- [x] 루트·모든 명령·하위 명령의 --help 확인
- [x] 옵션 이름을 --data-dir, --limit, --from처럼 --로 통일
- [x] 정상 종료 코드 0, 오류 종료 코드 0이 아닌 값 확인

2. 거래 모델과 공통 검증
- [x] Transaction을 dataclass로 정의하고 ID·타입·날짜·금액·카테고리·메모·태그 포함
- [x] 주요 함수와 반환값에 타입 힌트 적용
- [x] 실제 달력에 존재하는 YYYY-MM-DD 날짜만 허용
- [x] 월 입력은 YYYY-MM 형식과 유효한 월인지 검증
- [x] 타입은 income/`expense`만 허용
- [x] 금액과 예산은 양의 정수만 허용
- [x] 카테고리 존재 여부, 빈 이름, 중복 이름 검증
- [x] 태그의 입력·저장·CSV 변환 규칙 통일
- [x] --limit·`--top`은 양의 정수, 시작일은 종료일 이하인지 검증

3. JSONL 저장소와 첫 실행
- [x] ./data 및 JSONL 파일 3개를 첫 실행에 생성
- [x] 기본 카테고리를 최초 한 번만 등록
- [x] 거래·카테고리·예산을 각각 종료 후에도 유지
- [x] 거래를 한 줄씩 읽는 yield 기반 제너레이터 구현
- [x] 거래 추가 시 유일한 ID를 생성하고 한 줄씩 저장
- [x] 잘못된 JSONL 행은 파일명·행 번호·해결 힌트와 함께 오류 처리
- [x] 저장 파일이 없거나 읽기·쓰기 권한이 없을 때 사용자용 오류 처리

4. 카테고리와 거래 추가
- [x] category add/list/remove 구현
- [x] category add에서 대화형 입력 제공
- [x] 사용 중인 카테고리 삭제 차단
- [x] add에서 날짜·타입·카테고리·금액·메모·태그를 순서대로 입력
- [x] 미등록 카테고리와 잘못된 값은 재입력 또는 명확한 오류 안내
- [x] 추가 성공 시 생성된 거래 ID 출력
- [x] 재실행 후 카테고리와 거래가 유지되는지 확인

5. 목록과 검색
- [x] list --limit N 및 기본 제한 건수 구현
- [x] 거래를 최신순으로 출력
- [x] 파일 전체를 거래 객체 리스트로 적재하지 않는 정렬·조회 방식 구현
- [x] search에 --from, --to, --category, --type, --q, --tag 적용
- [x] 검색 조건을 동시에 적용하고 결과를 최신순 출력
- [x] 결과가 없을 때 안내 출력
- [x] 데이터가 많은 경우에도 스트리밍 처리가 유지되는지 확인

6. 월별 요약과 예산
- [x] summary --month YYYY-MM --top N 구현
- [x] 총수입·총지출·잔액 계산
- [x] 카테고리별 지출 합계 TOP N 출력
- [x] 해당 월 거래가 없으면 “데이터 없음” 출력
- [x] budget set --month YYYY-MM --amount 금액 구현 및 영구 저장
- [x] 예산이 있을 때 사용률 표시
- [x] 지출이 예산을 초과할 때 경고 표시
- [x] 프로그램 재실행 후에도 예산과 요약 결과 확인

7. 거래 수정과 삭제
- [x] update --id <id>와 변경할 필드 옵션 구현
- [x] 지정한 필드만 변경하고 수정 결과 전체를 다시 검증
- [x] delete --id <id> 구현
- [x] 존재하지 않는 ID는 “없는 데이터” 메시지와 오류 코드 반환
- [x] 변경 결과를 같은 폴더의 임시 파일에 스트리밍 기록
- [x] 쓰기가 끝난 뒤 os.replace로 원자적으로 교체
- [x] 실패 시 원본 보존과 임시 파일 정리 확인

8. CSV 가져오기와 내보내기
- [x] CSV 열을 date,type,category,amount,memo,tags로 고정
- [x] UTF-8, 헤더 포함, 필수 열 존재 여부 검증
- [x] import --from <csv>에서 행별 날짜·타입·카테고리·금액 검증
- [x] 가져온 거래에 새 ID 부여
- [x] 확정한 오류 행 정책에 따라 반영하고 imported·`skipped` 건수 출력
- [x] export --out <csv> 구현
- [x] export에 --month 또는 --from/`--to` 조건 필수화
- [x] 내보낸 CSV를 다시 가져와 스키마와 데이터가 맞는지 확인

9. 데코레이터와 오류 처리
- [x] 로그·실행 시간·예외 처리 중 공통 관심사 데코레이터 1개 이상 구현
- [x] functools.wraps를 적용하고 실제 함수에 데코레이터 사용
- [x] 예상 가능한 오류는 스택트레이스 대신 원인과 해결 힌트 출력
- [x] 잘못된 입력·손상된 파일·없는 ID·없는 CSV의 오류 종료 코드 확인
