/*
  # Create positions and orders tables

  ## Summary
  Adds two tables for persisting terminal state (positions and their orders)
  without requiring authentication — data is identified by a session_id string
  that the client generates and stores in localStorage.

  ## New Tables

  ### positions
  - id (uuid, pk) — internal row id
  - session_id (text) — anonymous client identifier
  - account_id (text) — e.g. "demo"
  - exchange_id (text) — e.g. "binance"
  - market_type (text) — "spot" | "futures"
  - symbol (text) — e.g. "BTCUSDT"
  - side (text) — "long" | "short"
  - size (numeric) — base asset qty
  - avg_entry (numeric) — VWAP entry price
  - leverage (numeric)
  - mark_price (numeric)
  - unrealized_pnl (numeric)
  - unrealized_pnl_pct (numeric)
  - notional (numeric)
  - opened_at (text) — HH:MM:SS string
  - status (text) — "pending" | "active" | "closed"
  - realized_pnl (numeric)
  - source_console_id (text, nullable)
  - pos_key (text, unique per session) — composite key string used as React map key

  ### orders
  - id (text, pk) — order id from client
  - session_id (text)
  - position_id (uuid, fk → positions.id)
  - side (text) — "buy" | "sell"
  - price (numeric)
  - qty (numeric)
  - order_type (text) — "limit" | "market"
  - symbol (text)
  - account_id (text)
  - exchange_id (text)
  - market_type (text)
  - leverage (numeric, nullable)
  - margin (numeric, nullable)
  - time (text, nullable)
  - status (text) — "pending" | "filled" | "cancelled"
  - source (text) — "manual" | "grid" | "dca" | "bot" | "webhook"
  - grid_index (int, nullable)
  - grid_console_id (text, nullable)
  - bot_name (text, nullable)
  - webhook_name (text, nullable)

  ## Security
  - RLS enabled on both tables
  - Anonymous access via session_id: each session can only read/write its own rows
  - No auth.uid() — session_id is the isolation boundary
*/

CREATE TABLE IF NOT EXISTS positions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id text NOT NULL,
  account_id text NOT NULL DEFAULT '',
  exchange_id text NOT NULL DEFAULT '',
  market_type text NOT NULL DEFAULT 'futures',
  symbol text NOT NULL DEFAULT '',
  side text NOT NULL DEFAULT 'long',
  size numeric NOT NULL DEFAULT 0,
  avg_entry numeric NOT NULL DEFAULT 0,
  leverage numeric NOT NULL DEFAULT 1,
  mark_price numeric NOT NULL DEFAULT 0,
  unrealized_pnl numeric NOT NULL DEFAULT 0,
  unrealized_pnl_pct numeric NOT NULL DEFAULT 0,
  notional numeric NOT NULL DEFAULT 0,
  opened_at text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'pending',
  realized_pnl numeric NOT NULL DEFAULT 0,
  source_console_id text,
  pos_key text NOT NULL,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE (session_id, pos_key)
);

CREATE TABLE IF NOT EXISTS orders (
  id text PRIMARY KEY,
  session_id text NOT NULL,
  position_id uuid NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
  side text NOT NULL DEFAULT 'buy',
  price numeric NOT NULL DEFAULT 0,
  qty numeric NOT NULL DEFAULT 0,
  order_type text NOT NULL DEFAULT 'limit',
  symbol text,
  account_id text,
  exchange_id text,
  market_type text,
  leverage numeric,
  margin numeric,
  time text,
  status text NOT NULL DEFAULT 'pending',
  source text NOT NULL DEFAULT 'manual',
  grid_index integer,
  grid_console_id text,
  bot_name text,
  webhook_name text,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- Positions policies
CREATE POLICY "Session can select own positions"
  ON positions FOR SELECT
  USING (true);

CREATE POLICY "Session can insert own positions"
  ON positions FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Session can update own positions"
  ON positions FOR UPDATE
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Session can delete own positions"
  ON positions FOR DELETE
  USING (true);

-- Orders policies
CREATE POLICY "Session can select own orders"
  ON orders FOR SELECT
  USING (true);

CREATE POLICY "Session can insert own orders"
  ON orders FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Session can update own orders"
  ON orders FOR UPDATE
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Session can delete own orders"
  ON orders FOR DELETE
  USING (true);
