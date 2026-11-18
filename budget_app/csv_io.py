"""CSV 거래 가져오기와 내보내기."""

import csv
import os
from collections.abc import Iterator
from itertools import chain
from pathlib import Path
from tempfile import NamedTemporaryFile

from .models import Transaction, new_transaction_id, parse_tags, validate_date, validate_month
from .repository import JsonlStore

CSV_FIELDS = ("date", "type", "category", "amount", "memo", "tags")


def import_csv(store: JsonlStore, source: Path) -> int:
    categories = set(store.iter_categories())
    count = 0
    with source.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, strict=True)

        def transactions() -> Iterator[Transaction]:
            nonlocal count
            try:
                header = next(reader, [])
                if tuple(header[:4]) != CSV_FIELDS[:4] or header[4:] not in (
                    [], ["memo"], ["tags"], ["memo", "tags"]
                ):
                    raise ValueError("date,type,category,amount 헤더와 선택 열 memo,tags를 확인하세요.")
                for row in reader:
                    if not row:
                        continue
                    if len(row) != len(header):
                        raise ValueError("헤더와 데이터 열 개수가 다릅니다.")
                    fields = dict(zip(header, row))
                    category = fields["category"].strip()
                    if category not in categories:
                        raise ValueError(f"등록된 카테고리가 없습니다: {category!r}")
                    amount = fields["amount"].strip()
                    if not amount.isdecimal():
                        raise ValueError("금액은 양의 정수로 입력하세요.")
                    transaction = Transaction(
                        id=new_transaction_id(),
                        date=fields["date"].strip(),
                        type=fields["type"].strip(),
                        category=category,
                        amount=int(amount),
                        memo=fields.get("memo", ""),
                        tags=parse_tags(fields.get("tags", "")),
                    )
                    count += 1
                    yield transaction
            except (csv.Error, UnicodeError, ValueError) as exc:
                raise ValueError(f"{source} {max(1, reader.line_num)}행 부근: {exc}") from exc

        records = transactions()
        first = next(records, None)
        if first is not None:
            store.append_transactions(chain((first,), records))
    return count


def export_csv(
    store: JsonlStore,
    destination: Path,
    *,
    month: str | None,
    start: str | None,
    end: str | None,
) -> int:
    if month is not None:
        validate_month(month)
        if start is not None or end is not None:
            raise ValueError("--month와 --from/--to는 둘 중 하나만 지정하세요.")
    elif start is None or end is None:
        raise ValueError("--month 또는 --from과 --to를 함께 지정하세요.")
    else:
        validate_date(start)
        validate_date(end)
        if start > end:
            raise ValueError("--from은 --to보다 늦을 수 없습니다.")

    if destination.resolve() in {
        path.resolve() for path in (store.transactions_path, store.categories_path, store.budgets_path)
    }:
        raise ValueError("가계부 저장 파일을 출력 경로로 사용할 수 없습니다.")

    count = 0
    temp_path = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=destination.parent, delete=False
        ) as file:
            temp_path = Path(file.name)
            writer = csv.writer(file)
            writer.writerow(CSV_FIELDS)
            for row in store.iter_tranactions():
                if month is not None and row.date[:7] != month:
                    continue
                if start is not None and end is not None and not start <= row.date <= end:
                    continue
                writer.writerow((row.date, row.type, row.category, row.amount, row.memo, ",".join(row.tags)))
                count += 1
        os.replace(temp_path, destination)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return count
