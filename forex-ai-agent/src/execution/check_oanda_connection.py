from __future__ import annotations

from src.config.settings import ExecutionSettings
from src.execution.gateway import MarketGateway


def main() -> None:
    settings = ExecutionSettings.from_env()
    settings.validate_credentials()

    gateway = MarketGateway(settings)
    try:
        account = gateway.fetch_oanda_account_summary()
        candles = gateway.fetch_oanda_candles(instrument="EUR_USD", granularity="H1", count=5)
    finally:
        gateway.close()

    print(f"broker={account.broker}")
    print(f"account_id={account.account_id}")
    print(f"equity={account.equity}")
    print(f"candles={len(candles)}")
    if not candles.empty:
        print(f"last_close={candles['close'].iloc[-1]}")


if __name__ == "__main__":
    main()
