from dataclasses import dataclass
from datetime import date

def validate_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "날짜가 올바르지 않습니다. YYYY-MM-DD 형식으로 입력하세요."
        ) from exc
    if parsed.isoformat() != value:
        raise ValueError(
            "날짜가 올바르지 않습니다. YYYY-MM-DD 형식으로 입력하세요."
        )
    return value

def validate_amount(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("금액은 0보다 큰 정수여야 합니다.")
    return value

@dataclass(frozen=True)
class Transaction:
    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("거래 ID가 비어 있습니다.")

        if self.type not in ("income", "expense"):
            raise ValueError("거래 타입은 income 또는 expense여야 합니다.")
        validate_date(self.date)
        validate_amount(self.amount)

        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("카테고리를 입력하세요.")

        if not isinstance(self.memo, str):
            raise ValueError("메모는 문자열이어야 합니다.")

        if not isinstance(self.tags, tuple) or any(
            not isinstance(tag, str) or not tag.strip() for tag in self.tags
        ):
            raise ValueError("태그는 비어 있지 않은 문자열의 묶응이어야 합니다.")