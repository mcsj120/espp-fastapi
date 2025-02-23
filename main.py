from datetime import datetime
import os
import sys
from typing import Dict, Any
import uuid
from contextlib import asynccontextmanager



from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncpg
import httpx
import numpy as np

from base_models.base_model_requests import StockRequest
from base_models.suggestion import Suggestion

# Add the parent directory of 'models' to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from models.company_plan import CompanyStockPlan
from models.company_stock_start_parameters import CompanyStockStartParameters
from models.employee_options import EmployeeOptions
from stock_price import generate_scenarios, run_strategies_against_scenario
import json


@asynccontextmanager
async def lifespan(app: FastAPI):
    config_path = os.path.join(os.path.dirname(__file__), 'config-local.json')
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    app.state.pool = await asyncpg.create_pool(
        user=config['username'],
        password=config['password'],
        database='espp',
        host=config['host'],
        port=config['port']
    )
    yield
    await app.state.pool.close()

app = FastAPI(lifespan=lifespan)
main_router = APIRouter()

static_dir = "/static"
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), 'static')), name="static")

@main_router.get("/", response_class=HTMLResponse)
async def read_index():
    with open(os.path.join(os.path.dirname(__file__), 'static', 'index.html'), 'r', encoding='utf-8') as file:
        return HTMLResponse(content=file.read())
    
@main_router.get("/strategies", response_class=JSONResponse)
async def read_index():
    with open(os.path.join(os.path.dirname(__file__), 'static', 'strategies.json'), 'r', encoding='utf-8') as file:
        return HTMLResponse(content=file.read())
    
@main_router.get("/stock_data")
async def generate_stock_run(ticker: str):
    today_date = datetime.now().strftime("%Y-%m-%d")

    file_name = f'stock_data-{ticker}-{today_date}.json'
    file_path = os.path.join(os.path.dirname(__file__), 'stock_histories', file_name)

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return HTMLResponse(content=file.read())

    async with httpx.AsyncClient() as client:
        response = await client.get(f'https://esppvalue.com/stock-data/?ticker={ticker}')
        if response.status_code == 200:
            response_json = response.json()
            response_json.pop('price_history', None)
            response_json.pop('daily_percent_changes', None)
            response_json.pop('dates', None)
            
            with open(file_path, 'w', encoding='utf-8') as json_file:
                json.dump(response_json, json_file, ensure_ascii=False, indent=4)
            return response.json()
        else:
            return JSONResponse(content={"error": "Failed to fetch stock data"}, status_code=response.status_code)
    

@main_router.get("/time_series", response_class=JSONResponse)
async def read_index(job_id: str):
    if job_id is None:
        return JSONResponse(content={"error": "No job_id passed"}, status_code=400)
    
    file_path = os.path.join(os.path.dirname(__file__), f"prices_{job_id}.csv")
    if not os.path.exists(file_path):
        return JSONResponse(content={"error": "File doesn't exists"}, status_code=400)
    return FileResponse(file_path, media_type="text/csv", filename="time_series.csv")

@main_router.post("/stock_run")
async def generate_stock_run(request: StockRequest, job_id: str = None):
    company_stock_plan = CompanyStockPlan(
        name=request.employee_stock_plan.company,
        discount_rate=request.employee_stock_plan.discount_rate,
        offering_periods=request.employee_stock_plan.offering_periods,
        pay_periods_per_offering=request.employee_stock_plan.pay_periods_per_offering,
        cost_to_sell=request.employee_stock_plan.cost_to_sell
    )
    company_stock_start_parameters = CompanyStockStartParameters(
        initial_price=request.company_stock_params.initial_price,
        expected_rate_of_return=request.company_stock_params.expected_rate_of_return,
        volatility=request.company_stock_params.volatility
    )
    employee_options = EmployeeOptions(
        company_stock_plan=company_stock_plan,
        max_contribution=request.employee_options.max_contribution,
        steps_to_zero=request.employee_options.steps_to_zero,
        liquidity_preference_rate=request.employee_options.liquidity_preference_rate,
        capital_gains_tax_rate=request.employee_options.capital_gains_tax_rate
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
    
    response = run_strategies_against_scenario(price_sets, employee_options)
    response["job_id"] = job_id
    return response

@main_router.post("/suggestions")
async def generate_stock_run(suggestion: Suggestion):
    if suggestion is None:
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
