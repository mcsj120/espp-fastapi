from pydantic import BaseModel, Field

class CompanyStockPlanValidation(BaseModel):
    company: str
    discount_rate: float = Field(..., ge=0, le=1)
    offering_periods: int = Field(..., gt=0)
    pay_periods_per_offering: int = Field(..., gt=0)
    # cost_to_sell: float = Field(..., ge=0)
    allows_lookback: bool

class CompanyStockParamsValidation(BaseModel):
    initial_price: float = Field(..., gt=0)
    expected_rate_of_return: float
    volatility: float = Field(..., ge=0)

class EmployeeOptionsValidation(BaseModel):
    max_contribution: float = Field(..., ge=0)
    steps_to_zero: int = Field(..., ge=0)
    liquidity_preference_rate: float = Field(..., ge=0, le=1)
    ignore_liquidity_preference: bool
    capital_gains_tax_rate: float = Field(..., ge=0, le=1)

class StockRequest(BaseModel):
    company_stock_params: CompanyStockParamsValidation
    employee_stock_plan: CompanyStockPlanValidation
    employee_options: EmployeeOptionsValidation