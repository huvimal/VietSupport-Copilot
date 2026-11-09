import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from app import ConfirmationRequest, create_app
from copilot import handle
from store import Store


class CancellationTests(unittest.TestCase):
    def test_confirm_is_explicit_customer_bound_and_one_time(self):
        with TemporaryDirectory() as temp:
            store = Store(Path(temp) / "test.sqlite3")
            app = create_app()
            app.state.store = store
            confirm = next(route.endpoint for route in app.routes if route.path == "/orders/cancel/confirm")
            self.assertEqual(handle(store, "demo-a", "Tra cứu đơn VN2001")["action"], "not_found")
            proposal = handle(store, "demo-a", "Hủy đơn VN1001")
            self.assertEqual(proposal["action"], "confirmation_required")
            self.assertEqual(store.status("demo-a", "VN1001"), "processing")
            token = proposal["confirmation_token"]
            with self.assertRaises(ValidationError):
                ConfirmationRequest(customer_id="demo-a", confirmation_token=token, confirm="true")
            with self.assertRaises(HTTPException) as declined:
                confirm(ConfirmationRequest(customer_id="demo-a", confirmation_token=token, confirm=False))
            self.assertEqual(declined.exception.status_code, 422)
            with self.assertRaises(HTTPException) as wrong_customer:
                confirm(ConfirmationRequest(customer_id="demo-b", confirmation_token=token, confirm=True))
            self.assertEqual(wrong_customer.exception.status_code, 409)
            self.assertEqual(store.status("demo-a", "VN1001"), "processing")
            request = ConfirmationRequest(customer_id="demo-a", confirmation_token=token, confirm=True)
            self.assertEqual(confirm(request)["action"], "cancelled")
            self.assertEqual(store.status("demo-a", "VN1001"), "cancelled")
            with self.assertRaises(HTTPException) as reused:
                confirm(request)
            self.assertEqual(reused.exception.status_code, 409)

    def test_fabricated_id_and_expired_approval(self):
        with TemporaryDirectory() as temp:
            store = Store(Path(temp) / "test.sqlite3")

            def fabricated_route(message):
                return "request_cancellation", {"order_id": "VN1001"}

            denied = handle(store, "demo-a", "Hủy VN2001", fabricated_route)
            self.assertEqual(denied["action"], "handoff")
            with patch("store.time.time", return_value=1000):
                proposal = handle(store, "demo-a", "Hủy VN1001")
            with patch("store.time.time", return_value=1300):
                self.assertIsNone(store.confirm("demo-a", proposal["confirmation_token"]))
            self.assertEqual(store.status("demo-a", "VN1001"), "processing")
