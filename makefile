smoke-aapl:
	SMOKE_SYMBOL=AAPL SMOKE_TFS="1D,30m,5m" poetry run python tools/smoke_context.py

smoke:
	poetry run python tools/smoke_context.py
