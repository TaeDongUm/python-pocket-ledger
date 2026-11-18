"""카테고리와 거래 관리 규칙."""

import json
import sqlite3
from collections.abc import Generator, Iterator
from contextlib import closing
from dataclasses import asdict
from heapq import nlargest
from uuid import uuid4

from .models import Transaction, validate_date
from .repository import JsonlStore


class CategoryService:
    def __init__(self, store: JsonlStore) -> None:
        self.store = store

    def list_categories(self) -> list[str]:
        return list(self.store.iter_categories())

    def add(self, name: str) -> str:
        name = name.strip()
        if not name:
            raise ValueError("카테고리 이름을 입력하세요.")

        names = self.list_categories()
        if name in names:
            raise ValueError(f"이미 등록된 카테고리입니다: {name}")
        names.append(name)
        self.store.save_categories(names)
        return name

    def remove(self, name: str) -> str:
        name = name.strip()
        names = self.list_categories()
        if name not in names:
            raise ValueError(f"등록된 카테고리가 없습니다: {name!r}")
        if any(transaction.category == name for transaction in self.store.iter_tranactions()):
            raise ValueError(f"거래에서 사용 중인 카테고리입니다: {name}")

        self.store.save_categories(existing for existing in names if existing != name)
        return name


class TransactionService:
    def __init__(self, store: JsonlStore) -> None:
        self.store = store

    def list_recent(self, limit: int) -> list[Transaction]:
        if limit <= 0:
            raise ValueError("--limit은 양의 정수여야 합니다.")

        # 같은 거래 날짜에서는 파일 뒤쪽에 기록된 거래를 먼저 보여준다.
        newest = nlargest(
            limit,
            enumerate(self.store.iter_tranactions()),
            key=lambda entry: (entry[1].date, entry[0]),
        )
        return [transaction for _, transaction in newest]

    def search(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
        category: str | None = None,
        transaction_type: str | None = None,
        query: str | None = None,
        tag: str | None = None,
    ) -> Generator[Transaction, None, None]:
        if start is not None:
            validate_date(start)
        if end is not None:
            validate_date(end)
        if start is not None and end is not None and start > end:
            raise ValueError("--from은 --to보다 늦을 수 없습니다.")

        keyword = query.casefold() if query is not None else None

        def matching_rows() -> Iterator[tuple[str, int, str]]:
            for position, transaction in enumerate(self.store.iter_tranactions()):
                if start is not None and transaction.date < start:
                    continue
                if end is not None and transaction.date > end:
                    continue
                if category is not None and transaction.category != category:
                    continue
                if transaction_type is not None and transaction.type != transaction_type:
                    continue
                if keyword is not None and keyword not in transaction.memo.casefold():
                    continue
                if tag is not None and tag not in transaction.tags:
                    continue
                yield transaction.date, position, json.dumps(asdict(transaction), ensure_ascii=False)

        # 빈 경로의 SQLite 데이터베이스는 연결이 닫히면 자동으로 삭제된다.
        with closing(sqlite3.connect("")) as results:
            results.execute("PRAGMA temp_store = FILE")
            results.execute("PRAGMA cache_size = -1024")
            results.execute("PRAGMA cache_spill = ON")
            results.execute("""
                CREATE TABLE matches (
                    date TEXT,
                    position INTEGER,
                    record TEXT NOT NULL,
                    PRIMARY KEY (date DESC, position DESC)
                ) WITHOUT ROWID
            """)
            results.executemany("INSERT INTO matches VALUES (?, ?, ?)", matching_rows())
            for (record,) in results.execute(
                "SELECT record FROM matches ORDER BY date DESC, position DESC"
            ):
                fields = json.loads(record)
                fields["tags"] = tuple(fields["tags"])
                yield Transaction(**fields)

    def add(
        self,
        *,
        date: str,
        transaction_type: str,
        category: str,
        amount: int,
        memo: str,
        tags: tuple[str, ...],
    ) -> Transaction:
        transaction = Transaction(
            id=f"TX-{uuid4().hex}",
            type=transaction_type,
            date=date,
            amount=amount,
            category=category,
            memo=memo,
            tags=tags,
        )
        if category not in self.store.iter_categories():
            raise ValueError(f"등록된 카테고리가 없습니다: {category!r}. category list로 확인하세요.")

        self.store.append_transaction(transaction)
        return transaction
