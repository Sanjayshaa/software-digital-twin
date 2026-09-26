# Infrastructure database adapter
class PostgresDatabaseAdapter:
    def execute_query(self, query: str):
        return {"status": "executed", "query": query}
