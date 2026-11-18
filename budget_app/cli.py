"""용돈 기입장 명령줄 인터페이스"""

import argparse
import sqlite3
import sys
from collections.abc import Iterable, Sequence
from contextlib import closing

from .models import Transaction
from .repository import JsonlStore
from .service import CategoryService, TransactionService

DEFAULT_LIST_LIMIT = 10


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("양의 정수를 입력하세요.") from None
    if not value.isdecimal() or number <= 0:
        raise argparse.ArgumentTypeError("양의 정수를 입력하세요.")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
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

    for name, description in (
        ("add", "거래 추가"),
        ("summary","월별 요약"),
        ("update","거래 수정"),
        ("delete","거래 삭제"),
        ("import","CSV 가져오기"),
        ("export","CSV 내보내기"),
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
    budget_commands.add_parser("set", help = "월 예산 설정")

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
    tags = tuple(tag for tag in map(str.strip, input("태그(선택, 쉼표로 구분): ").split(",")) if tag)

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


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    store = JsonlStore(args.data_dir)
    try:
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
    except sqlite3.Error as exc:
        print(f"[오류] 검색 결과를 정렬할 수 없습니다: {exc}", file=sys.stderr)
        print("[힌트] 임시 폴더의 저장 공간과 쓰기 권한을 확인하세요.", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"[오류] 데이터 파일을 처리할 수 없습니다: {exc}", file=sys.stderr)
        print("[힌트] --data-dir 경로와 읽기·쓰기 권한을 확인하세요.", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        if args.command == "category":
            print("[힌트] category list로 등록된 카테고리를 확인하세요.", file=sys.stderr)
        elif args.command == "add":
            print("[힌트] 입력값을 확인한 뒤 add를 다시 실행하세요.", file=sys.stderr)
        elif args.command == "search":
            print("[힌트] 검색 조건과 transactions.jsonl 파일을 확인하세요.", file=sys.stderr)
        else:
            print("[힌트] --data-dir의 transactions.jsonl 파일을 확인하세요.", file=sys.stderr)
        return 1
    except EOFError:
        print("[오류] 필수 입력이 끝나기 전에 입력이 종료되었습니다.", file=sys.stderr)
        print("[힌트] 명령을 다시 실행하고 안내에 따라 입력하세요.", file=sys.stderr)
        return 1

    print(f"[오류] '{args.command}' 명령은 아직 구현되지 않았습니다.")
    print("[힌트] 현재는 명령별 --help로 실행 구조를 확인할 수 있습니다.")
    return 1
