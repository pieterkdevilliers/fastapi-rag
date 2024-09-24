from fastapi import FastAPI
import query_source_data

app = FastAPI()


############################################
# Main Routes
############################################

@app.get("/api/v1/root")
async def read_root():
    """
    Root Route
    """
    return {"Hello": "World"}


@app.get("/api/v1/query-data")
async def query_data(query):
    """
    Query Data
    """
    if not query:
        return {"error": "No query provided"}
    
    response = query_source_data.query_source_data(query)
    print(response)
    return {"query": query, 
            "response": response
            }
