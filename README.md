## Installation

`pip install -r requirements.txt`

## Development

`pip install -r requirements-dev.txt`

```bash
$ RPC_MAINNET_URL='https://...' uvicorn rolesapi.main:app --reload --workers 4
```

Go to http://127.0.0.1:8000/ or http://127.0.0.1:8000/docs for the API docs.

