"""Server-owned provider selection; runtime failures never trigger provider failover."""
import os

PROVIDER_ORDER_DEFAULT = ('jev', 'openai')


def _configured(name: str) -> bool:
    if name == 'jev':
        return (os.environ.get('JEV_ENABLED', 'false').lower() == 'true'
                and bool(os.environ.get('JEV_API_KEY', '').strip()))
    if name == 'openai':
        return (os.environ.get('OPENAI_DECISIONS_ENABLED', 'false').lower() == 'true'
                and bool(os.environ.get('OPENAI_API_KEY', '').strip()))
    return False


def select_provider(mode: str | None = None, order: str | None = None) -> str | None:
    """Return one configured provider, or None to retain deterministic rules only."""
    selected_mode = (mode if mode is not None else os.environ.get('DECISION_PROVIDER', 'rules')).strip().lower()
    configured_order = order if order is not None else os.environ.get('DECISION_PROVIDER_ORDER', ','.join(PROVIDER_ORDER_DEFAULT))
    requested = tuple(part.strip().lower() for part in configured_order.split(',') if part.strip())
    if selected_mode == 'rules':
        return None
    if selected_mode in {'jev', 'openai'}:
        return selected_mode if _configured(selected_mode) else None
    if selected_mode != 'auto':
        return None
    if not requested or any(name not in {'jev', 'openai'} for name in requested):
        return None
    if len(set(requested)) != len(requested):
        return None
    return next((name for name in requested if _configured(name)), None)
