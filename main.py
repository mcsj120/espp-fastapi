from datetime import datetime
import os
import sys
import base64
from typing import Optional
import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncpg
import numpy as np

from base_models.base_model_requests import StockRequest
from base_models.suggestion import Suggestion
from utils.api_request import LocalClient
from utils.config import Config
from stock_logic.fetch_data import get_stock_price_and_volatility

# Add the parent directory of 'models' to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from models.company_plan import CompanyStockPlan
from models.company_stock_start_parameters import CompanyStockStartParameters
from models.employee_options import EmployeeOptions
from stock_price import generate_scenarios, run_scenarios_against_strategies

from strategies import get_core_strategies, get_all_strategies, get_no_lookback_strategies
import json

@asynccontextmanager
async def lifespan(app: FastAPI):
    config_path = os.path.join(os.path.dirname(__file__), 'config-local.json')
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)
        Config()
        Config.set_polygon_api_key(config['polygon_api_key'])
        Config.set_fred_api_key(config['fred_api_key'])
    
    LocalClient()

    # app.state.pool = await asyncpg.create_pool(
    #     user=config['username'],
    #     password=config['password'],
    #     database='espp',
    #     host=config['host'],
    #     port=config['port']
    # )

    yield
    # await app.state.pool.close()

app = FastAPI(
    lifespan=lifespan,
    #TODO: figure out how to reload when espp python code changes
    # reload_dirs=[
    #     "espp_fastapi", 
    #     "models", 
    #     "strategies",
    #     os.path.dirname(os.path.dirname(__file__))  # Parent directory
    # ]
)
main_router = APIRouter()

static_dir = "/static"
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), 'static')), name="static")

@main_router.get("/", response_class=HTMLResponse)
async def read_index():
    with open(os.path.join(os.path.dirname(__file__), 'static', 'index.html'), 'r', encoding='utf-8') as file:
        content = file.read()
        insert_position_no_contribution_pic_bytes = content.find('id="no_contribution_pic_bytes"')
        if insert_position_no_contribution_pic_bytes != -1:
            content = content[:insert_position_no_contribution_pic_bytes] + ' src="/static/No contribution to ESPP_roi_distribution.png" ' + content[insert_position_no_contribution_pic_bytes:]
        else:
            print("No location for contribution pic bytes found in html file")
        
        insert_position_max_contribution_pic_bytes = content.find('id="max_contribution_pic_bytes"')
        if insert_position_max_contribution_pic_bytes != -1:
            content = (
                content[:insert_position_max_contribution_pic_bytes] + 
                ' src="/static/Max contribution to ESPP with company and IRS blocking overpayment_roi_distribution.png" ' + 
                content[insert_position_max_contribution_pic_bytes:]
            )
        else:
            print("No location for max contribution pic bytes found in html file")

        return HTMLResponse(content=content)
    

@main_router.get("/stock_data", response_class=JSONResponse)
async def get_stock_data(ticker: str):
    if len(ticker) == 0:
        return JSONResponse(content={"error": "No ticker passed"}, status_code=400)
    elif len(ticker) > 5:
        return JSONResponse(content={"error": "Ticker is too long"}, status_code=400)
    elif not ticker.isalpha():
        return JSONResponse(content={"error": "Ticker is not alphabetic"}, status_code=400)
    
    ticker = ticker.upper()
    
    # Passing in today as a parameter to easily utilize lru_cache
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        stock_price, volatility, expected_return = await get_stock_price_and_volatility(ticker, today)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

    #convert the error to a string so it can be sent to the frontend
    if type(volatility) != float:
        volatility = str(volatility)
    if type(expected_return) != float:
        expected_return = str(expected_return)
    return JSONResponse(content={"stock_price": stock_price, "volatility": volatility, "expected_return": expected_return})

@main_router.get("/time_series", response_class=JSONResponse)
async def get_time_series(job_id: str):
    if job_id is None or len(job_id) == 0:
        return JSONResponse(content={"error": "No job_id passed"}, status_code=400)
    
    file_path = os.path.join(os.path.dirname(__file__), f"prices_{job_id}.csv")
    if not os.path.exists(file_path):
        return JSONResponse(content={"error": "File doesn't exists"}, status_code=400)
    return FileResponse(file_path, media_type="text/csv", filename="time_series.csv")

@main_router.post("/stock_run")
async def generate_stock_run(request: StockRequest, strategies: Optional[str] = None, job_id: Optional[str] = None):
    company_stock_plan = CompanyStockPlan(
        name=request.employee_stock_plan.company,
        discount_rate=round(1 - request.employee_stock_plan.discount_rate, 2),
        offering_periods=request.employee_stock_plan.offering_periods,
        pay_periods_per_offering=request.employee_stock_plan.pay_periods_per_offering,
        allows_lookback=request.employee_stock_plan.allows_lookback
    )
    company_stock_start_parameters = CompanyStockStartParameters(
        initial_price=request.company_stock_params.initial_price,
        expected_rate_of_return=request.company_stock_params.expected_rate_of_return,
        volatility=request.company_stock_params.volatility
    )
    employee_options = EmployeeOptions(
        company_stock_plan=company_stock_plan,
        company_stock_parameters=company_stock_start_parameters,
        max_contribution=request.employee_options.max_contribution,
        steps_to_zero=request.employee_options.steps_to_zero,
        liquidity_preference_rate=request.employee_options.liquidity_preference_rate,
        capital_gains_tax_rate=request.employee_options.capital_gains_tax_rate,
        ignore_liquidity_preference=request.employee_options.ignore_liquidity_preference
    )
    
    if job_id is not None:
        file_path = os.path.join(os.path.dirname(__file__), f"prices_{job_id}.csv")
        if not os.path.exists(file_path):
            return JSONResponse(content={"error": "File doesn't exists"}, status_code=400)
        price_sets = np.loadtxt(file_path, delimiter=',')
    else:
        job_id = job_id or str(uuid.uuid4())
        price_sets = generate_scenarios(
            company_stock_plan,
            company_stock_start_parameters,
            file_name=f"prices_{job_id}"
        )

    if strategies is None or strategies == "simple":
        pulled_strategies = get_core_strategies()
    elif not company_stock_plan.allows_lookback:
        pulled_strategies = get_no_lookback_strategies()
    else:
        pulled_strategies = get_core_strategies()
    
    response = run_scenarios_against_strategies(price_sets, employee_options, pulled_strategies)
    for result in response:
        if 'strategy' in result:
            result['strategy'] = result['strategy'].__name__
        result['espp_result'] = {
            "baseline_value_sum": result['espp_result'].baseline_value_sum,
            "total_value_sum": result['espp_result'].total_value_sum,
            "money_contributed_sum": result['espp_result'].money_contributed_sum,
            "roi_sum": result['espp_result'].roi_sum,
            "money_refunded_sum": result['espp_result'].money_refunded_sum,
            "espp_return_sum": result['espp_result'].espp_return_sum,
            "baseline_value": result['espp_result'].baseline_value,
            "total_value": result['espp_result'].total_value,
            "money_contributed": result['espp_result'].money_contributed,
            "roi": result['espp_result'].roi,
            "money_refunded": result['espp_result'].money_refunded,
            "espp_return": result['espp_result'].espp_return
        }
        if 'pic_bytes' in result:
            result['pic_bytes'] = base64.b64encode(result['pic_bytes']).decode('utf-8')
        

    response_value = {
        "job_id": job_id,
        "results": response
    }
    return JSONResponse(content=response_value)

@main_router.post("/suggestions")
async def receive_suggestion(suggestion: Suggestion):
    if suggestion is None or len(suggestion.suggestion) == 0:
        return JSONResponse(content={"error": "No suggestion passed"}, status_code=400)
    
    query = """
        INSERT INTO suggestions (suggestion, name, email)
        VALUES ($1, $2, $3)
    """
    async with app.state.pool.acquire() as connection:
        await connection.execute(query, suggestion.suggestion,  suggestion.name,  suggestion.email)
    return JSONResponse(content={"message": "Suggestion added successfully"})

async def fetch_records(query):
    async with app.state.pool.acquire() as connection:
        records = await connection.fetch(query)
        return records
    

app.include_router(main_router)
