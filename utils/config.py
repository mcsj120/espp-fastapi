class Config:
    _instance = None
    _polygon_api_key = None
    _fred_api_key = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_polygon_api_key(cls, polygon_api_key):
        cls._polygon_api_key = polygon_api_key

    @classmethod
    def get_polygon_api_key(cls):
        return cls._polygon_api_key

    @classmethod
    def set_fred_api_key(cls, fred_api_key):
        cls._fred_api_key = fred_api_key

    @classmethod
    def get_fred_api_key(cls):
        return cls._fred_api_key

