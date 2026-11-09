"""Local FastAPI entry point. Customer IDs are simulated test profiles."""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, StrictBool

from copilot import handle, route_demo, route_groq
from store import Store

Customer = Literal["demo-a", "demo-b"]


class ChatRequest(BaseModel):
    customer_id: Customer
    message: str = Field(min_length=1, max_length=1500, pattern=r"\S")


class ConfirmationRequest(BaseModel):
    customer_id: Customer
    confirmation_token: str = Field(min_length=20, max_length=100)
    confirm: StrictBool


def create_app(db_path=None, router=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.store = Store(db_path or Path(__file__).with_name("orders.sqlite3"))
        yield

    app = FastAPI(title="VietSupport Copilot", version="0.1.0", lifespan=lifespan)
    key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
    route = router or route_demo
    if router is None and key:
        def route(message):
            return route_groq(message, model, key)

    @app.post("/chat")
    def chat(payload: ChatRequest):
        return handle(app.state.store, payload.customer_id, payload.message, route)

    @app.post("/orders/cancel/confirm")
    def confirm(payload: ConfirmationRequest):
        if not payload.confirm:
            raise HTTPException(422, "Explicit confirmation is required.")
        order_id = app.state.store.confirm(payload.customer_id, payload.confirmation_token)
        if order_id is None:
            raise HTTPException(409, "Confirmation is invalid, expired, used, or no longer applicable.")
        return {"action": "cancelled", "order_id": order_id, "reply": f"Đã hủy đơn {order_id}."}

    return app


app = create_app()
