"""용돈 기입장 명령줄 인터페이스"""

import argparse
import sys
from collections.abc import Sequence
from .repository import JsonlStore

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

    for name, description in (
        ("add", "거래 추가"),
        ("list", "거래 목록"),
        ("search", "거래 검색"),
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
        ("remove", "카테고리 삭제"),
    ):
        category_commands.add_parser(name, help = description)

    budget = commands.add_parser("budget", help = "월 예산 관리")
    budget_commands = budget.add_subparsers(
        dest = "budget_command",
        required = True,
    )
    budget_commands.add_parser("set", help = "월 예산 설정")

    return parser

def main(argv: Sequence[str] | None = None) -> init:
    args = build_parser().parse_args(argv)

    try:
        JsonlStore(args.data_dir).initialize()
    except OSError as exc:
        print(f"[오류] 데이터 폴더를 준비할 수 없습니다: {exc}", file = sys.stderr)
        print("[힌트] --data-dir 경로와 쓰기 권한을 확인해주세요.", file = sys.stderr)
        return 1

    print(f"[오류] '{args.command}' 명령은 아직 구현되지 않았습니다.")
    print("[힌트] 현재는 명령별 --help로 실행 구조를 확인할 수 있습니다.")
    return 1