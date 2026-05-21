from contextvars import ContextVar


_tenant_id: ContextVar[int] = ContextVar("tenant_id", default=1)


def set_current_tenant_id(tenant_id: int | None) -> None:
    _tenant_id.set(int(tenant_id or 1))


def get_current_tenant_id() -> int:
    return _tenant_id.get()

