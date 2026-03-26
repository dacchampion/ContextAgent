-- =========================================================
-- ChartAgent – MySQL 8 schema (AWS RDS / Aurora compatible)
-- Híbrido: indicators (wide) + indicator_series (tall)
-- =========================================================

-- 1) Catálogo de símbolos y proveedores
CREATE TABLE IF NOT EXISTS symbols (
  symbol_id   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  symbol      VARCHAR(32) NOT NULL,
  asset_class ENUM('equity','etf','index','crypto','fx') NOT NULL DEFAULT 'equity',
  exchange    VARCHAR(32) NULL,
  description VARCHAR(255) NULL,
  CONSTRAINT uq_symbols_symbol UNIQUE (symbol)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS providers (
  provider_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(32) NOT NULL,      
  base_url    VARCHAR(255) NULL,
  CONSTRAINT uq_providers_name UNIQUE (name)
) ENGINE=InnoDB;

-- 2) OHLCV canónico
CREATE TABLE IF NOT EXISTS ohlcv (
  symbol_id   BIGINT UNSIGNED NOT NULL,
  candle_width    ENUM('1d','30m','5m','1m') NOT NULL,
  timestamp_utc      DATETIME(3) NOT NULL,  
  open_price        DECIMAL(18,6) NOT NULL,
  high_price        DECIMAL(18,6) NOT NULL,
  low_price         DECIMAL(18,6) NOT NULL,
  close_price       DECIMAL(18,6) NOT NULL,
  volume      DECIMAL(20,6) NULL,
  provider_id TINYINT UNSIGNED NOT NULL,
  trading_date    DATE AS (DATE(timestamp_utc)) STORED,

  PRIMARY KEY (symbol_id, candle_width, timestamp_utc),
  INDEX idx_ohlcv_lookup (symbol_id, candle_width, timestamp_utc),
  INDEX idx_ohlcv_date   (trading_date),
  CONSTRAINT fk_ohlcv_symbol   FOREIGN KEY (symbol_id)  REFERENCES symbols(symbol_id),
  CONSTRAINT fk_ohlcv_provider FOREIGN KEY (provider_id) REFERENCES providers(provider_id)
) ENGINE=InnoDB;

-- 3) Indicadores “core” (tabla ancha para la UI)
CREATE TABLE IF NOT EXISTS indicators (
  symbol_id  BIGINT UNSIGNED NOT NULL,
  candle_width   ENUM('1d','30m','5m','1m') NOT NULL,
  timestamp_utc     DATETIME(3) NOT NULL,

  vwap       DECIMAL(18,6) NULL,
  ema8       DECIMAL(18,6) NULL,
  ema21      DECIMAL(18,6) NULL,
  ema50      DECIMAL(18,6) NULL,
  sma20      DECIMAL(18,6) NULL,
  sma50      DECIMAL(18,6) NULL,

  kc_mid     DECIMAL(18,6) NULL,
  kc_up      DECIMAL(18,6) NULL,
  kc_dn      DECIMAL(18,6) NULL,

  updated_utc DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),

  PRIMARY KEY (symbol_id, candle_width, timestamp_utc),
  INDEX idx_indicators_lookup (symbol_id, candle_width, timestamp_utc),
  CONSTRAINT fk_ind_symbol FOREIGN KEY (symbol_id) REFERENCES symbols(symbol_id)
) ENGINE=InnoDB;

-- 4) Serie flexible de indicadores (tabla alta)
CREATE TABLE IF NOT EXISTS indicator_series (
  symbol_id  BIGINT UNSIGNED NOT NULL,
  candle_width   ENUM('1d','30m','5m','1m') NOT NULL,
  timestamp_utc     DATETIME(3) NOT NULL,
  indicator_name       VARCHAR(32) NOT NULL,     
  window_size     INT NOT NULL,             
  indicator_value      DECIMAL(18,6) NOT NULL,
  indicator_method     VARCHAR(64) NULL,         
  updated_utc DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),

  PRIMARY KEY (symbol_id, candle_width, timestamp_utc, indicator_name, window_size),
  INDEX idx_is_time   (symbol_id, candle_width, timestamp_utc),
  INDEX idx_is_family (symbol_id, candle_width, indicator_name, window_size, timestamp_utc),
  CONSTRAINT fk_is_symbol FOREIGN KEY (symbol_id) REFERENCES symbols(symbol_id)
) ENGINE=InnoDB;

-- 5) Anclas VWAP
CREATE TABLE IF NOT EXISTS avwap_anchors (
  anchor_id      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  symbol_id      BIGINT UNSIGNED NOT NULL,
  candle_width       ENUM('1d','30m','5m','1m') NOT NULL,
  anchor_ts_utc  DATETIME(3) NOT NULL,    
  anchor_type         ENUM('session_open','weekly_open','monthly_open','swing_high','swing_low','custom_event') NOT NULL,
  anchor_label          VARCHAR(64) NULL,
  created_utc    DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),

  CONSTRAINT uq_anchor UNIQUE (symbol_id, candle_width, anchor_ts_utc, anchor_type),
  INDEX idx_anchor_lookup (symbol_id, candle_width, anchor_ts_utc),
  CONSTRAINT fk_anchor_symbol FOREIGN KEY (symbol_id) REFERENCES symbols(symbol_id)
) ENGINE=InnoDB;

-- 6) Metadatos de sincronización
CREATE TABLE IF NOT EXISTS sync_meta (
  symbol_id         BIGINT UNSIGNED NOT NULL,
  candle_width          ENUM('1d','30m','5m','1m') NOT NULL,
  last_backfill_utc DATETIME(3) NULL,    
  last_realtime_utc DATETIME(3) NULL,    
  updated_utc  DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),

  PRIMARY KEY (symbol_id, candle_width),
  CONSTRAINT fk_sync_symbol FOREIGN KEY (symbol_id) REFERENCES symbols(symbol_id)
) ENGINE=InnoDB;

-- 7) Bitácora de ETL/Jobs
CREATE TABLE IF NOT EXISTS job_runs (
  job_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  job_name      VARCHAR(64) NOT NULL,        
  symbol_id     BIGINT UNSIGNED NULL,
  candle_width      ENUM('1d','30m','5m','1m') NULL,
  started_utc   DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
  finished_utc  DATETIME(3) NULL,
  run_status        ENUM('success','warning','error') NOT NULL DEFAULT 'success',
  rows_affected BIGINT NULL,
  log_message       TEXT NULL,
  INDEX idx_jobs_lookup (job_name, started_utc),
  CONSTRAINT fk_jobs_symbol FOREIGN KEY (symbol_id) REFERENCES symbols(symbol_id)
) ENGINE=InnoDB;

-- 8) Semillas de proveedores
INSERT INTO providers (name, base_url)
VALUES ('yfinance','https://finance.yahoo.com'),
       ('twelvedata','https://api.twelvedata.com')
ON DUPLICATE KEY UPDATE base_url = VALUES(base_url);
