"""JSONL 파일 생성과 거래 스트리밍 읽기"""

import json
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path

from .models import Transaction

DEFAULT_CATEGORIES = (
    "food",
    "transport",
    "housing",
    "salary",
    "etc",
)

class JsonlStore:
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.transactions_path = self.data_dir / "transactions.jsonl"
        self.categories_path = self.data_dir / "categories.jsonl"
        self.budgets_path = self.data_dir / "budgets.jsonl"

    def initialize(self) -> None:
        """저장 폴더와 파일을 준비하고 기본 카테고리를 등록한다."""
        self.data_dir.mkdir(parents = True, exist_ok = True)

        for path in (
            self.transactions_path,
            self.categories_path,
            self.budgets_path,
        ):
            path.touch(exist_ok = True)

        if self.categories_path.stat().st_size == 0:
            for name in DEFAULT_CATEGORIES:
                self._append_json(self.categories_path, {"name": name})

    def iter_tranactions(self) -> Iterator[Transaction]:
        """거래 파일을 한 줄씩 읽어 Transaction 객체로 변환한다."""
        with self.transactions_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start = 1):
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)
                    yield Transaction(
                        id = record["id"],
                        type = record["type"],
                        date = record["date"],
                        amount = record["amount"],
                        category = record["category"],
                        memo = record.get("memo", ""),
                        tags = tuple(record.get("tags", [])),
                    )
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"거래 파일 {line_number}번째 줄을 읽을 수 없습니다."
                        "파일 내용을 확인해주세요."
                    ) from exc
    def append_transaction(self, transaction: Transaction) -> None:
        self._append_json(self.transaction_path, asdict(transaction))

    def iter_categories(self) -> Iterator[str]:
        """등록된 카테고리를 한 줄씩 읽는다."""
        with self.categories_path.open("r", encoding = "utf-8") as file:
            for line_number, line in enumerate(file, start = 1):
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)
                    name = record["name"]
                    if not isinstance(name, str) or not name.strip():
                        raise ValueError("빈 카테고리명")
                    yield name
                except(json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"카테고리 파일 {line_number}번째 줄을 읽을 수 없습니다."
                        "파일 내용을 확인해주세요."
                    ) from exc

    @staticmethod
    def _append_json(path: Path, record: dict[str, object]) -> None:
        with path.open("a", encoding = "utf-8") as file:
            file.write(json.dumps(record, ensure_ascii = False) + "\n")
                