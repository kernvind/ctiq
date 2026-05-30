import uvicorn

# This function acts as the entrypoint for Poetry
def start_dev():
    uvicorn.run("src.app.main:app", host="127.0.0.1", port=8000, reload=True)