"""JSONL 파일 생성과 거래 스트리밍 읽기"""

import json
import os
from collections.abc import Iterable, Iterator
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile

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
        budgets: dict[str, int] = {}
        with self.budgets_path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    month = validate_month(record["month"])
                    budgets[month] = validate_amount(record["amount"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"budgets.jsonl {line_number}번째 줄의 월 또는 금액이 올바르지 않습니다."
                    ) from exc
        return budgets

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
        self._append_json(self.transactions_path, asdict(transaction))

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
        line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
        with path.open("a+b") as file:
            if file.seek(0, os.SEEK_END):
                file.seek(-1, os.SEEK_END)
                if file.read(1) != b"\n":
                    line = b"\n" + line
            file.write(line)
