"""용돈 기입장 명령줄 인터페이스"""

import argparse
import sqlite3
import sys
from collections.abc import Callable, Iterable, Sequence
from contextlib import closing
from functools import wraps
from pathlib import Path

from .csv_io import export_csv, import_csv
from .models import Transaction, parse_tags
from .repository import JsonlStore
from .service import CategoryService, TransactionService

DEFAULT_LIST_LIMIT = 10
DEFAULT_SUMMARY_TOP = 5


class LedgerArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, f"[오류] {message}\n[힌트] --help로 사용 방법을 확인하세요.\n")


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("양의 정수를 입력하세요.") from None
    if not value.isdecimal() or number <= 0:
        raise argparse.ArgumentTypeError("양의 정수를 입력하세요.")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = LedgerArgumentParser(
        prog = "python -m budget_app",
        description="파일 기반 용돈 기입장", 
    )
    parser.add_argument(
        "--data-dir",
        default = "./data",
        metavar = "PATH",
        help = "데이터 저장 폴더 (기본값: ./data)",        
    )
    commands = parser.add_subparsers(dest="command", required = True)

    listing = commands.add_parser("list", help="거래 목록")
    listing.add_argument(
        "--limit",
        type=positive_int,
        default=DEFAULT_LIST_LIMIT,
        metavar="N",
        help="표시할 최대 거래 건수 (기본값: %(default)s)",
    )

    search = commands.add_parser("search", help="거래 검색")
    search.add_argument("--from", dest="start", metavar="YYYY-MM-DD", help="시작일 (포함)")
    search.add_argument("--to", dest="end", metavar="YYYY-MM-DD", help="종료일 (포함)")
    search.add_argument("--category", help="카테고리 이름")
    search.add_argument("--type", choices=("income", "expense"), help="거래 타입")
    search.add_argument("--q", help="메모에 포함된 키워드 (대소문자 무시)")
    search.add_argument("--tag", help="태그 이름")

    summary = commands.add_parser("summary", help="월별 요약")
    summary.add_argument("--month", required=True, metavar="YYYY-MM", help="요약할 거래 월")
    summary.add_argument(
        "--top",
        type=positive_int,
        default=DEFAULT_SUMMARY_TOP,
        metavar="N",
        help="표시할 지출 카테고리 최대 개수 (기본값: %(default)s)",
    )

    update = commands.add_parser("update", help="거래 수정")
    update.add_argument("--id", required=True, help="수정할 거래 ID")
    update.add_argument("--date", metavar="YYYY-MM-DD", help="변경할 거래 날짜")
    update.add_argument("--type", choices=("income", "expense"), help="변경할 거래 타입")
    update.add_argument("--category", help="변경할 카테고리 이름")
    update.add_argument("--amount", type=positive_int, help="변경할 거래 금액")
    update.add_argument("--memo", help="변경할 메모 (빈 문자열이면 지움)")
    update.add_argument("--tags", type=parse_tags, help="쉼표로 구분한 태그 (빈 문자열이면 지움)")

    delete = commands.add_parser("delete", help="거래 삭제")
    delete.add_argument("--id", required=True, help="삭제할 거래 ID")

    csv_import = commands.add_parser("import", help="CSV 가져오기")
    csv_import.add_argument("--from", dest="source", type=Path, required=True, help="읽을 CSV 파일")

    csv_export = commands.add_parser("export", help="CSV 내보내기")
    csv_export.add_argument("--out", type=Path, required=True, help="저장할 CSV 파일")
    csv_export.add_argument("--month", metavar="YYYY-MM", help="내보낼 거래 월")
    csv_export.add_argument("--from", dest="start", metavar="YYYY-MM-DD", help="시작일 (포함)")
    csv_export.add_argument("--to", dest="end", metavar="YYYY-MM-DD", help="종료일 (포함)")

    for name, description in (
        ("add", "거래 추가"),
        ("backup","데이터 백업"),
        ("recurring","반복 거래 관리"),
    ):
        commands.add_parser(name, help = description)

    category = commands.add_parser("category", help = "카테고리 관리")
    category_commands = category.add_subparsers(
        dest = "category_command",
        required = True,
    )

    for name, description in (
        ("add", "카테고리 추가"),
        ("list", "카테고리 목록"),
    ):
        category_commands.add_parser(name, help = description)

    remove = category_commands.add_parser("remove", help="카테고리 삭제")
    remove.add_argument("--name", required=True, help="삭제할 카테고리 이름")

    budget = commands.add_parser("budget", help = "월 예산 관리")
    budget_commands = budget.add_subparsers(
        dest = "budget_command",
        required = True,
    )
    budget_set = budget_commands.add_parser("set", help="월 예산 설정")
    budget_set.add_argument("--month", required=True, metavar="YYYY-MM", help="예산을 설정할 월")
    budget_set.add_argument("--amount", required=True, type=positive_int, help="월 예산 금액")

    return parser

def run_category(args: argparse.Namespace, service: CategoryService) -> None:
    if args.category_command == "add":
        name = service.add(input("카테고리명: "))
        print(f"[저장 완료] category={name}")
    elif args.category_command == "remove":
        name = service.remove(args.name)
        print(f"[삭제 완료] category={name}")
    else:
        names = service.list_categories()
        if names:
            for name in names:
                print(f"- {name}")
        else:
            print("등록된 카테고리가 없습니다. category add로 추가하세요.")


def run_add(service: TransactionService) -> None:
    date = input("날짜(YYYY-MM-DD): ").strip()
    transaction_type = input("타입(income/expense): ").strip()
    category = input("카테고리: ").strip()
    amount_text = input("금액(양의 정수): ").strip()
    try:
        if not amount_text.isdecimal():
            raise ValueError
        amount = int(amount_text)
    except ValueError:
        raise ValueError("금액은 15000처럼 0보다 큰 정수로 입력하세요.") from None
    memo = input("메모(선택): ")
    tags = parse_tags(input("태그(선택, 쉼표로 구분): "))

    transaction = service.add(
        date=date,
        transaction_type=transaction_type,
        category=category,
        amount=amount,
        memo=memo,
        tags=tags,
    )
    print(f"[저장 완료] id={transaction.id}")


def print_transactions(transactions: Iterable[Transaction], empty_message: str) -> None:
    found = False
    for transaction in transactions:
        found = True
        print(
            f"{transaction.id} | {transaction.date} | {transaction.type} | "
            f"{transaction.category} | {transaction.amount} | {transaction.memo}"
        )
    if not found:
        print(empty_message)


def run_summary(service: TransactionService, month: str, top: int) -> None:
    summary = service.summarize_month(month, top)
    budget = service.get_budget(month)
    if summary is None:
        print(f"{month} 데이터 없음")
    else:
        print(f"총 수입: {summary.income}원")
        print(f"총 지출: {summary.expenses}원")
        print(f"잔액: {summary.balance}원")
    if budget is not None:
        expenses = summary.expenses if summary is not None else 0
        # 사용률을 0.1% 단위로 반올림한다.
        percent, decimal = divmod((expenses * 2000 + budget) // (2 * budget), 10)
        print(f"예산: {budget}원 (사용률 {percent}.{decimal}%)")
        if expenses > budget:
            print(f"[경고] 월 예산을 {expenses - budget}원 초과했습니다.")
    if summary is None:
        return
    if summary.top_expenses:
        print(f"지출 TOP {top}")
        for rank, (category, total) in enumerate(summary.top_expenses, start=1):
            print(f"{rank}) {category} {total}원")
    else:
        print("카테고리별 지출 없음")


VALIDATION_HINTS = {
    "add": "입력값을 확인한 뒤 add를 다시 실행하세요.",
    "category": "category list로 등록된 카테고리를 확인하세요.",
    "list": "거래 파일을 확인하세요.",
    "search": "검색 조건과 거래 파일을 확인하세요.",
    "summary": "--month 값과 거래·예산 파일을 확인하세요.",
    "budget": "--month 값과 예산 파일을 확인하세요.",
    "update": "거래 ID와 변경 옵션을 확인하세요.",
    "delete": "거래 ID를 확인하세요.",
    "import": "가져오기 전체가 취소되었습니다. 입력 파일을 확인하세요.",
    "export": "기간 조건, 출력 경로와 거래 파일을 확인하세요.",
}


def handle_command_errors(
    command: Callable[[argparse.Namespace], int],
) -> Callable[[argparse.Namespace], int]:
    @wraps(command)
    def wrapped(args: argparse.Namespace) -> int:
        try:
            return command(args)
        except sqlite3.Error as exc:
            message = f"검색 결과를 정렬할 수 없습니다: {exc}"
            hint = "임시 폴더의 저장 공간과 쓰기 권한을 확인하세요."
        except OSError as exc:
            message = f"데이터 파일을 처리할 수 없습니다: {exc}"
            hint = "표시된 파일 경로와 읽기·쓰기 권한을 확인하세요."
        except ValueError as exc:
            message = str(exc)
            hint = VALIDATION_HINTS.get(args.command, "--help로 사용 방법을 확인하세요.")
        except EOFError:
            message = "필수 입력이 끝나기 전에 입력이 종료되었습니다."
            hint = "명령을 다시 실행하고 안내에 따라 입력하세요."
        except KeyboardInterrupt:
            message = "명령 실행이 중단되었습니다."
            hint = "작업을 계속하려면 명령을 다시 실행하세요."

        print(f"[오류] {message}", file=sys.stderr)
        print(f"[힌트] {hint}", file=sys.stderr)
        return 1

    return wrapped


@handle_command_errors
def run_command(args: argparse.Namespace) -> int:
    store = JsonlStore(args.data_dir)
    store.initialize()
    if args.command == "category":
        run_category(args, CategoryService(store))
        return 0
    if args.command == "add":
        run_add(TransactionService(store))
        return 0
    if args.command == "list":
        print_transactions(
            TransactionService(store).list_recent(args.limit), "등록된 거래가 없습니다."
        )
        return 0
    if args.command == "search":
        with closing(TransactionService(store).search(
            start=args.start,
            end=args.end,
            category=args.category,
            transaction_type=args.type,
            query=args.q,
            tag=args.tag,
        )) as matches:
            print_transactions(matches, "검색 조건에 맞는 거래가 없습니다.")
        return 0
    if args.command == "summary":
        run_summary(TransactionService(store), args.month, args.top)
        return 0
    if args.command == "budget":
        TransactionService(store).set_budget(args.month, args.amount)
        print(f"[저장 완료] {args.month} 예산 {args.amount}원")
        return 0
    if args.command == "update":
        TransactionService(store).update(
            args.id,
            date=args.date,
            transaction_type=args.type,
            category=args.category,
            amount=args.amount,
            memo=args.memo,
            tags=args.tags,
        )
        print(f"[수정 완료] id={args.id}")
        return 0
    if args.command == "delete":
        TransactionService(store).delete(args.id)
        print(f"[삭제 완료] id={args.id}")
        return 0
    if args.command == "import":
        count = import_csv(store, args.source)
        print(f"[완료] imported={count}, skipped=0")
        return 0
    if args.command == "export":
        count = export_csv(store, args.out, month=args.month, start=args.start, end=args.end)
        print(f"[완료] {args.out} ({count}건)")
        return 0

    raise ValueError(f"'{args.command}' 명령은 아직 구현되지 않았습니다.")


def main(argv: Sequence[str] | None = None) -> int:
    return run_command(build_parser().parse_args(argv))
