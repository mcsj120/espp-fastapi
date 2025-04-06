from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import httpx

class LocalClient:
    _instance = None
    _client: httpx.AsyncClient | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._client = httpx.AsyncClient()
            cls._instance = super().__new__(cls)
        return cls._instance
       

    @classmethod
    async def get_api_request(cls, url: str) -> dict:
        
        if cls._client is None:
            raise Exception("LocalClient not initialized")
        response = await cls._client.get(url)
        return response.json()
    
    @staticmethod
    def print_url_no_key(url: str):
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        if 'apiKey' in query_params:
            del query_params['apiKey']
            new_query = urlencode(query_params, doseq=True)
            print(urlunparse(parsed_url._replace(query=new_query)))