from pydantic import BaseModel

class CompanyStockPlanValidation(BaseModel):
    company: str
    discount_rate: float
    offering_periods: int
    pay_periods_per_offering: int
    cost_to_sell: float

class CompanyStockParamsValidation(BaseModel):
    initial_price: float
    expected_rate_of_return: float
    volatility: float

class EmployeeOptionsValidation(BaseModel):
    max_contribution: float
    steps_to_zero: int
    liquidity_preference_rate: float
    capital_gains_tax_rate: float

class StockRequest(BaseModel):
    company_stock_params: CompanyStockParamsValidation
    employee_stock_plan: CompanyStockPlanValidation
    employee_options: EmployeeOptionsValidation