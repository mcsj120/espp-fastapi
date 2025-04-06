from datetime import datetime, timedelta

from utils.api_request import LocalClient
from utils.config import Config

from async_lru import alru_cache

@alru_cache(maxsize=1)
async def get_one_year_risk_free_rate(today: str) -> float:
    """
    Market Yield on U.S. Treasury Securities at 1-Year Constant Maturity, Quoted on an Investment Basis 
    """
    today_dt = datetime.strptime(today, '%Y-%m-%d')
    first_day_last_month = (today_dt.replace(day=1) - timedelta(days=1)).replace(day=1).strftime('%Y-%m-%d')
        
    url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS1&api_key={Config.get_fred_api_key()}&file_type=json&observation_start={first_day_last_month}"
    
    data = await LocalClient.get_api_request(url)
    return float(data["observations"][-1]["value"]) * 0.01
