import os
from typing import Dict, Any
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncpg

from base_models.base_model_requests import StockRequest
from models.company_plan import CompanyStockPlan
from models.company_stock_start_parameters import CompanyStockStartParameters
from stock_price import generate_scenarios, run_strategies_against_scenario




@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(
        user='your_username',
        password='your_password',
        database='your_dbname',
        host='your_host',
        port='your_port'
    )
    yield
    await app.state.pool.close()

app = FastAPI(lifespan=lifespan)
main_router = APIRouter()

app.mount("/static", StaticFiles(directory="static"), name="static")

@main_router.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(index_path, "r") as file:
        return HTMLResponse(content=file.read(), status_code=200)

@main_router.post("/stock_run")
def generate_stock_run(request: StockRequest):
    company_stock_plan=CompanyStockPlan(
            name=request.employee_stock_plan.name,
            discount_rate=request.employee_stock_plan.discount_rate,
            offering_periods=request.employee_stock_plan.offering_periods,
            pay_periods_per_offering=request.employee_stock_plan.pay_periods_per_offering,
            cost_to_sell=request.employee_stock_plan.cost_to_sell
    )
    company_stock_start_parameters=CompanyStockStartParameters(
        initial_price=request.company_stock_params.initial_price,
        expected_rate_of_return=request.company_stock_params.expected_rate_of_return,
        volatility=request.company_stock_params.volatility
    ),
    prices = generate_scenarios(
        company_stock_plan,
        company_stock_start_parameters
    )
    run_strategies_against_scenario(prices)
    return request

async def fetch_records(query):
    async with app.state.pool.acquire() as connection:
        records = await connection.fetch(query)
        return records

app.include_router(main_router)
