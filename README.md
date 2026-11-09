# VietSupport Copilot

A Vietnamese customer support API for a fictional store. It answers policy questions,
looks up order status, prepares cancellation approvals, and recommends human review
for requests it cannot handle.

## Run locally on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8503
```

Open http://127.0.0.1:8503/docs. The API defaults to a local rules-based router
when GROQ_API_KEY is absent. In `POST /chat`, click Try it out and send:

```json
{"customer_id":"demo-a","message":"Tra cứu đơn VN1001"}
```

| Profile | Order | Initial status |
| --- | --- | --- |
| demo-a | VN1001 | processing |
| demo-a | VN1002 | shipped |
| demo-b | VN2001 | processing |

To try a cancellation, send `Hủy đơn VN1001`. Copy the returned
`confirmation_token` to `POST /orders/cancel/confirm`, pass the same customer ID
and set `confirm` to the JSON boolean `true`. Query the order again to verify
the status. Confirmations expire after 5 minutes and can only be used once.
SQLite persists the state between restarts. The tests and evaluator create
temporary databases with fresh data.

## Groq tool calling

To activate model routing, stop the server and set the environment variable
before starting it again in the same terminal:

```powershell
$vietSupportKey = Read-Host "Groq API key" -AsSecureString
$env:GROQ_API_KEY = [System.Net.NetworkCredential]::new('', $vietSupportKey).Password
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8503
```

The default model is `openai/gpt-oss-120b`; set `GROQ_MODEL` if needed.
The model receives the chat message and tool definitions. The server validates
the selected tool and its arguments, reads the store data and formats the reply.
The confirmation endpoint is separate from the tools available to the model.
If the model request fails, the API recommends human review.

## Verify and evaluate

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe evaluate.py --mode demo --output reports/demo.json
.\.venv\Scripts\python.exe evaluate.py --mode groq --output reports/groq.json
```

The Groq run needs the environment variable and sends ten requests.
Inspect the report for failed routes and router errors. The cases check selected
actions plus policy facts or order status where applicable. Separate tests exercise
the confirmation handler and SQLite state. This is a small synthetic pilot.

## Scope

Customer IDs are selectable fictional profiles and do not authenticate callers.
The handoff response recommends contacting support; it does not create a ticket
or send a notification. Use synthetic messages in live mode. API usage is subject
to provider limits. Keep this prototype on localhost.

## Files

- `app.py` defines the chat and confirmation endpoints.
- `copilot.py` defines routing, allowed tool names and reply templates.
- `store.py` owns scoped reads and transactional cancellation.
- `evaluate.py` compares behavior against labeled synthetic support requests.
