-- Cash-on-delivery orders waiting for a confirmation call, plus an audit log
-- of everything the voice agent did on each call.

CREATE TABLE IF NOT EXISTS orders (
    id              text PRIMARY KEY,
    customer_name   text        NOT NULL,
    phone           text        NOT NULL,
    city            text        NOT NULL,
    address         text        NOT NULL,
    items           jsonb       NOT NULL,           -- [{"name": "...", "qty": 1, "price_mad": 249}]
    total_mad       numeric(10,2) NOT NULL,
    status          text        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'confirmed', 'rescheduled', 'cancelled', 'no_answer')),
    delivery_date   date,
    cancel_reason   text,
    attempts        int         NOT NULL DEFAULT 0,
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS call_events (
    id          bigserial PRIMARY KEY,
    order_id    text        NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    action      text        NOT NULL,              -- call_started, confirmed, address_updated, ...
    detail      jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS call_events_order_idx ON call_events (order_id, created_at);
CREATE INDEX IF NOT EXISTS orders_status_idx ON orders (status, updated_at);
