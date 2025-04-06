import asyncio
import os
import sys
from datetime import datetime, timedelta
from functools import _make_key, wraps

from api_calls.fred import get_one_year_risk_free_rate
from api_calls.polygon import get_options_contract_for_iv, get_stock_price


sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from stock_calculations import implied_volatility

def cache_with_expiry(maxsize=2048, expiry=timedelta(days=2)):
    def decorator(func):
        cache = {}
        cache_times = {}

        async def evict_expired_items():
            while True:
                await asyncio.sleep(3600)  # Sleep for one hour
                now = datetime.now()
                expired_keys = [k for k, t in cache_times.items() if now - t > expiry]
                for k in expired_keys:
                    cache.pop(k, None)
                    cache_times.pop(k, None)

        asyncio.create_task(evict_expired_items())

        @wraps(func)
        async def wrapper(*args, **kwargs):
            now = datetime.now()
            key = _make_key(args, kwargs, typed=False)

            if key in cache:
                return cache[key]

            result = await func(*args, **kwargs)
            if len(cache) >= maxsize:
                oldest_key = min(cache_times.items(), key=lambda x: x[1])[0]
                cache.pop(oldest_key, None)
                cache_times.pop(oldest_key, None)

            cache[key] = result
            cache_times[key] = now
            return result

        return wrapper

    return decorator

@cache_with_expiry(maxsize=2048, expiry=timedelta(days=2))
async def get_stock_price_and_volatility(ticker: str, today: datetime) -> tuple[float, float]:
    # Convert datetime to string for consistent caching
    today_str = today.strftime('%Y-%m-%d')
    stock_price, err = await get_stock_price(ticker, today)
    if err is not None:
        raise Exception(err)
    options_contract = await get_options_contract_for_iv(ticker, stock_price, today)
    risk_free_rate = await get_one_year_risk_free_rate(today)

    volatility = implied_volatility(
        stock_price,
        options_contract["strike_price"],
        (datetime.strptime(options_contract["expiration_date"], '%Y-%m-%d') - today).days
            / 365,
        risk_free_rate,
        options_contract["c"]
    )

    return (stock_price, volatility)