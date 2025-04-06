from datetime import datetime, timedelta
from typing import Tuple, Optional

from utils.api_request import LocalClient
from utils.config import Config

from functools import lru_cache

@lru_cache(maxsize=2048)
async def get_stock_price(ticker: str, today: datetime) -> Tuple[Optional[float], Optional[str]]:
    """
    Get the current stock price. Using custom bars allows us to not worry about the day of the week and if the stock market is open
    Information: https://polygon.io/docs/rest/stocks/aggregates/custom-bars
    """
    from_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    to_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}?adjusted=true&sort=desc&limit=5&apiKey={Config.get_polygon_api_key()}"

    data = await LocalClient.get_api_request(url)

    # If the results are empty, we want to cache it because the data pull query is bad, like an invalid stock.
    if data.get("results") is None or len(data["results"]) == 0:
        return None, f"No data found for the contract {ticker}"

    return data["results"][0]["c"], None

@lru_cache(maxsize=2048)
async def get_options_contract_for_iv(ticker: str, stock_price: float, today_dt: datetime):
    """
        We will get implied volatility by looking at an options contract one year from now. Get contract with the closest strike price to the stock price
            and the closest to 1 year from now. Union between the two APIs
        Information: https://polygon.io/docs/rest/options/contracts/all-contracts
            https://polygon.io/docs/rest/options/aggregates/custom-bars

        return:
            contract: dict:
                {
                    "cfi": "OCASPS",
                    "contract_type": "call",
                    "exercise_style": "american",
                    "expiration_date": "2026-06-18",
                    "primary_exchange": "BATO",
                    "shares_per_contract": 100,
                    "strike_price": 32.5,
                    "ticker": "O:CVS260618C00032500",
                    "underlying_ticker": "CVS",
                    "v": 122,
                    "vw": 3.9256,
                    "o": 3.65,
                    "c": 3.61,
                    "h": 4.26,
                    "l": 3.42,
                    "t": 1743480000000,
                    "n": 68
                }
    """

    #Looking for the closest contract about 1 year from now
    to_date = (today_dt.replace(year=datetime.now().year + 1) - timedelta(weeks=4)).strftime('%Y-%m-%d')
    today = today_dt.strftime('%Y-%m-%d')

    url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&contract_type=call&expiration_date.gte={to_date}&order=asc&limit=100&sort=expiration_date&apiKey={Config.get_polygon_api_key()}"
    data = await LocalClient.get_api_request(url)

    if data.get("results") is None or len(data["results"]) == 0:
        raise Exception(f"No contracts found for the ticker {ticker}")

    date_of_closest_contract = None
    contract = {}
    for c in data["results"]:
        if date_of_closest_contract is None or contract is None:
            date_of_closest_contract = c["expiration_date"]
            contract = c
        # If the contract is closer to 1 year from now, update the closest contract
        elif abs((datetime.strptime(c["expiration_date"], '%Y-%m-%d') - datetime.strptime(today, '%Y-%m-%d')).days) < abs((datetime.strptime(date_of_closest_contract, '%Y-%m-%d') - datetime.strptime(today, '%Y-%m-%d')).days):
            date_of_closest_contract = c["expiration_date"]
            contract = c
        elif c["expiration_date"] == date_of_closest_contract and abs(c["strike_price"] - stock_price) < abs(contract["strike_price"] - stock_price):
            contract = c

    from_date = (today_dt - timedelta(days=7)).strftime('%Y-%m-%d')
    to_date = (today_dt - timedelta(days=1)).strftime('%Y-%m-%d')

    url = f"https://api.polygon.io/v2/aggs/ticker/{contract['ticker']}/range/1/day/{from_date}/{to_date}?adjusted=true&sort=desc&limit=1&apiKey={Config.get_polygon_api_key()}"
    data = await LocalClient.get_api_request(url)

    if data.get("results") is None or len(data["results"]) == 0:
        raise Exception(f"No data found for the optionscontract {contract['ticker']}")

    contract = contract | data["results"][0]

    return contract