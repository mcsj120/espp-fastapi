from pydantic import BaseModel

class Suggestion(BaseModel):
    suggestion: str
    name: str
    email: str