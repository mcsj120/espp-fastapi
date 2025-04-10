import asyncio
import os
import sys
from datetime import datetime, timedelta
from functools import _make_key, wraps

from api_calls.fred import get_one_year_risk_free_rate
from api_calls.polygon import get_options_contract_for_iv, get_stock_price_now, get_stock_price_last_24_months


sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from stock_calculations import implied_volatility, get_expected_rate_of_return_from_capm

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
async def get_stock_price_and_volatility(ticker: str, today: str) -> tuple:
    stock_price, err = await get_stock_price_now(ticker, today)
    if err is not None:
        raise Exception(err)
    volatility = None
    try:
        # The function can still throw an exception, but if we return an error message,
        # the result of the function will be cached.
        options_contract, err = await get_options_contract_for_iv(ticker, stock_price, today)
        if err is not None:
            raise Exception(err)

        risk_free_rate = await get_one_year_risk_free_rate(today)

        today_dt = datetime.strptime(today, '%Y-%m-%d')
        volatility = implied_volatility(
            stock_price,
            options_contract["strike_price"],
            (datetime.strptime(options_contract["expiration_date"], '%Y-%m-%d') - today_dt).days
                / 365,
            risk_free_rate,
            options_contract["c"]
        )
    except Exception as e:
        print(f"Error getting volatility: {e}")
        volatility = e
    try:
        today_month_year = today_dt.strftime('%Y-%m')
        # Data is 24 months because that is what is free from polygon :)
        stock_price_last_24_months, err = await get_stock_price_last_24_months(ticker, today_month_year)
        if err is not None:
            raise Exception(err)
        spy_last_24_months, err = await get_stock_price_last_24_months("SPY", today_month_year)
        if err is not None:
            raise Exception(err)

        # Market return is 9% for now
        expected_return = get_expected_rate_of_return_from_capm(stock_price_last_24_months, spy_last_24_months, risk_free_rate, 0.09)
    except Exception as e:
        print(f"Error getting expected return: {e}")
        expected_return = e

    return (stock_price, volatility, expected_return)