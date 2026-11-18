"""JSONL 파일 생성과 거래 스트리밍 읽기"""

import json
import os
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict
from itertools import chain
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, TypeVar

from .models import Transaction, validate_amount, validate_month

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

        for path in (self.transactions_path, self.budgets_path):
            try:
                path.touch(exist_ok=False)
            except FileExistsError:
                pass

        if not self.categories_path.exists():
            self.save_categories(DEFAULT_CATEGORIES, initialize=True)

    def save_categories(self, names: Iterable[str], *, initialize: bool = False) -> None:
        self._replace_jsonl(
            self.categories_path, ({"name": name} for name in names), initialize=initialize
        )

    def load_budgets(self) -> dict[str, int]:
        def parse_budget(record: dict[str, object]) -> tuple[str, int]:
            month, amount = record["month"], record["amount"]
            if not isinstance(month, str) or not isinstance(amount, int):
                raise ValueError("월과 금액의 형식이 올바르지 않습니다.")
            return validate_month(month), validate_amount(amount)

        return dict(_read_jsonl(self.budgets_path, parse_budget))

    def save_budget(self, month: str, amount: int) -> None:
        budgets = self.load_budgets()
        budgets[month] = amount
        self._replace_jsonl(
            self.budgets_path,
            ({"month": key, "amount": value} for key, value in budgets.items()),
        )

    def _replace_jsonl(
        self, path: Path, records: Iterable[dict[str, object]], *, initialize: bool = False
    ) -> None:
        """완성된 JSONL 파일을 반영하고 임시 파일을 정리한다."""
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=self.data_dir, delete=False
        ) as file:
            temp_path = Path(file.name)
            try:
                for record in records:
                    file.write(json.dumps(record, ensure_ascii=False) + "\n")
                file.close()
                if initialize:
                    # 다른 실행에서 먼저 만든 파일이 있으면 그대로 사용한다.
                    try:
                        os.link(temp_path, path)
                    except FileExistsError:
                        pass
                else:
                    os.replace(temp_path, path)
            finally:
                temp_path.unlink(missing_ok=True)

    def iter_tranactions(self) -> Iterator[Transaction]:
        """거래 파일을 한 줄씩 읽어 Transaction 객체로 변환한다."""
        return _read_jsonl(self.transactions_path, _parse_transaction)

    def append_transaction(self, transaction: Transaction) -> None:
        self._append_json(self.transactions_path, asdict(transaction))

    def append_transactions(self, transactions: Iterable[Transaction]) -> None:
        all_transactions = chain(self.iter_tranactions(), transactions)
        self._replace_jsonl(self.transactions_path, (asdict(row) for row in all_transactions))

    def change_transaction(
        self, transaction_id: str, change: Callable[[Transaction], Transaction | None]
    ) -> None:
        def records() -> Iterator[dict[str, object]]:
            found = False
            for transaction in self.iter_tranactions():
                if transaction.id == transaction_id:
                    if found:
                        raise ValueError(f"거래 ID가 중복되어 있습니다: {transaction_id}")
                    found = True
                    changed = change(transaction)
                    if changed is not None:
                        yield asdict(changed)
                else:
                    yield asdict(transaction)
            if not found:
                raise ValueError(f"해당 ID의 거래가 없습니다: {transaction_id}")

        self._replace_jsonl(self.transactions_path, records())

    def iter_categories(self) -> Iterator[str]:
        """등록된 카테고리를 한 줄씩 읽는다."""
        def parse_category(record: dict[str, object]) -> str:
            name = record["name"]
            if not isinstance(name, str) or not name.strip():
                raise ValueError("카테고리 이름이 올바르지 않습니다.")
            return name

        return _read_jsonl(self.categories_path, parse_category)

    @staticmethod
    def _append_json(path: Path, record: dict[str, object]) -> None:
        line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
        with path.open("a+b") as file:
            if file.seek(0, os.SEEK_END):
                file.seek(-1, os.SEEK_END)
                if file.read(1) != b"\n":
                    line = b"\n" + line
            file.write(line)


Record = TypeVar("Record")


def _read_jsonl(path: Path, parse: Callable[[dict[str, Any]], Record]) -> Iterator[Record]:
    # 줄별로 디코딩해 UTF-8이 깨진 경우에도 정확한 행 번호를 보여준다.
    with path.open("rb") as file:
        for line_number, raw_line in enumerate(file, start=1):
            try:
                line = raw_line.decode("utf-8")
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("각 행은 JSON 객체여야 합니다.")
                parsed = parse(record)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"{path.name} {line_number}번째 줄을 읽을 수 없습니다. "
                    "해당 줄의 UTF-8 인코딩, JSON 형식과 필드 값을 확인하세요."
                ) from exc
            yield parsed


def _parse_transaction(record: dict[str, Any]) -> Transaction:
    tags = record.get("tags", [])
    if not isinstance(tags, list):
        raise ValueError("태그는 JSON 배열이어야 합니다.")
    return Transaction(
        id=record["id"],
        type=record["type"],
        date=record["date"],
        amount=record["amount"],
        category=record["category"],
        memo=record.get("memo", ""),
        tags=tuple(tags),
    )
