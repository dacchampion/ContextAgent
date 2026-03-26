# Makefile

.PHONY: install run sync-ohlcv sync-indicators test test-cov

# Variables
PYTHON = .venv/bin/python
UV = uv

# Default target
all: install

# Creates a virtual environment and installs dependencies
install:
	$(UV) venv
	$(UV) pip install -r requirements.txt
	$(UV) pip install -r requirements-dev.txt

# Runs the FastAPI application
run:
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Syncs OHLCV data
sync-ohlcv:
	$(UV) run python etl/recent_update.py --symbol $(SYMBOL) --provider twelve_data

# Syncs indicators data
sync-indicators:
	$(UV) run python etl/calc_indicators.py --symbol $(SYMBOL) --candle-width $(CANDLE_WIDTH)

# Runs tests
test:
	$(UV) run pytest

# Runs tests with coverage report
test-cov:
	$(UV) run pytest --cov=app
