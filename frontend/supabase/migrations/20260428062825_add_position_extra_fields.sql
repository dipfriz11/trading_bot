/*
  # Add extra fields to positions and orders tables

  1. Positions table additions
    - `short_id` (text) - short human-readable position identifier (e.g. "5673700")
    - `opened_date` (text) - date portion of opening time (DD.MM)
    - `real_size` (numeric) - actual filled size on exchange (0 = virtual/pending)
    - `margin_mode` (text) - "cross" or "isolated"
    - `tp_pct` (numeric, nullable) - take profit percent
    - `sl_pct` (numeric, nullable) - stop loss percent
    - `tp_price` (numeric, nullable) - take profit price
    - `sl_price` (numeric, nullable) - stop loss price

  2. Orders table additions
    - `filled_at` (text, nullable) - HH:MM:SS DD.MM when order was filled
    - `filled_pct` (numeric, nullable) - 0-100 fill percentage

  3. No RLS changes needed (existing policies cover new columns)
*/

DO $$
BEGIN
  -- positions: short_id
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'positions' AND column_name = 'short_id'
  ) THEN
    ALTER TABLE positions ADD COLUMN short_id text NOT NULL DEFAULT '';
  END IF;

  -- positions: opened_date
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'positions' AND column_name = 'opened_date'
  ) THEN
    ALTER TABLE positions ADD COLUMN opened_date text NOT NULL DEFAULT '';
  END IF;

  -- positions: real_size
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'positions' AND column_name = 'real_size'
  ) THEN
    ALTER TABLE positions ADD COLUMN real_size numeric NOT NULL DEFAULT 0;
  END IF;

  -- positions: margin_mode
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'positions' AND column_name = 'margin_mode'
  ) THEN
    ALTER TABLE positions ADD COLUMN margin_mode text NOT NULL DEFAULT 'cross';
  END IF;

  -- positions: tp_pct
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'positions' AND column_name = 'tp_pct'
  ) THEN
    ALTER TABLE positions ADD COLUMN tp_pct numeric;
  END IF;

  -- positions: sl_pct
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'positions' AND column_name = 'sl_pct'
  ) THEN
    ALTER TABLE positions ADD COLUMN sl_pct numeric;
  END IF;

  -- positions: tp_price
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'positions' AND column_name = 'tp_price'
  ) THEN
    ALTER TABLE positions ADD COLUMN tp_price numeric;
  END IF;

  -- positions: sl_price
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'positions' AND column_name = 'sl_price'
  ) THEN
    ALTER TABLE positions ADD COLUMN sl_price numeric;
  END IF;

  -- orders: filled_at
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'orders' AND column_name = 'filled_at'
  ) THEN
    ALTER TABLE orders ADD COLUMN filled_at text;
  END IF;

  -- orders: filled_pct
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'orders' AND column_name = 'filled_pct'
  ) THEN
    ALTER TABLE orders ADD COLUMN filled_pct numeric;
  END IF;
END $$;
