from __future__ import annotations

from src.config.settings import ExecutionSettings
from src.execution.adapters import build_mt5_admin_adapter


def main() -> None:
    settings = ExecutionSettings.from_env()
    settings.validate_mt5_credentials()

    adapter = build_mt5_admin_adapter(settings)
    snapshot = adapter.load_snapshot(instrument="DE30.pro", granularity="H1", count=5)
    print(f"source={snapshot.source_name}")
    print(f"account_id={snapshot.account_snapshot.account_id}")
    print(f"equity={snapshot.account_snapshot.equity}")
    print(f"positions={len(snapshot.positions)}")
    print(f"candles={len(snapshot.market_prices)}")


if __name__ == "__main__":
    main()
