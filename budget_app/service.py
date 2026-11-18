"""카테고리와 거래 관리 규칙."""

from heapq import nlargest
from uuid import uuid4

from .models import Transaction
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
