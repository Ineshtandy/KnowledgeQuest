from fastapi import FastAPI

from adaptive_tutor.api.routes import router


app = FastAPI(title="Adaptive Tutor API", version="0.1.0")
app.include_router(router)
