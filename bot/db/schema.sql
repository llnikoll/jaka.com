-- Jaka Bicicletería: datos operativos del chatbot.
-- El catálogo de productos NO se replica aquí. Los IDs apuntan al catálogo JSON.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_e164 TEXT NOT NULL UNIQUE,
    display_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (phone_e164 ~ '^\+[1-9][0-9]{7,14}$')
);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id UUID NOT NULL REFERENCES contacts(id),
    channel TEXT NOT NULL DEFAULT 'whatsapp',
    status TEXT NOT NULL DEFAULT 'bot_active'
        CHECK (status IN ('bot_active', 'human', 'closed')),
    assigned_to TEXT,
    last_message_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversations_contact_recent
    ON conversations(contact_id, updated_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_one_open_conversation_per_contact_channel
    ON conversations(contact_id, channel) WHERE status <> 'closed';

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound', 'internal')),
    body TEXT NOT NULL DEFAULT '',
    message_type TEXT NOT NULL DEFAULT 'text',
    provider TEXT,
    provider_message_id TEXT,
    delivery_status TEXT NOT NULL DEFAULT 'received'
        CHECK (delivery_status IN ('received', 'queued', 'sent', 'delivered', 'read', 'failed')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (provider_message_id IS NULL OR length(provider_message_id) <= 255)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_provider_id
    ON messages(provider, provider_message_id)
    WHERE provider IS NOT NULL AND provider_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_conversation_time
    ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    contact_id UUID NOT NULL REFERENCES contacts(id),
    status TEXT NOT NULL DEFAULT 'pending_confirmation'
        CHECK (status IN ('pending_confirmation', 'confirmed', 'rejected', 'cancelled')),
    customer_name TEXT,
    delivery_method TEXT CHECK (delivery_method IS NULL OR delivery_method IN ('pickup', 'delivery', 'to_coordinate')),
    delivery_address TEXT,
    customer_notes TEXT,
    currency TEXT NOT NULL DEFAULT 'PYG' CHECK (currency = 'PYG'),
    subtotal BIGINT NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at DESC);

CREATE TABLE IF NOT EXISTS order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL,
    product_name_snapshot TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price BIGINT CHECK (unit_price IS NULL OR unit_price >= 0),
    availability_snapshot TEXT NOT NULL DEFAULT 'confirm'
        CHECK (availability_snapshot IN ('available_in_catalog', 'out_of_stock', 'confirm', 'no_data')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_conversation_time
    ON audit_log(conversation_id, created_at DESC);

-- updated_at se gestiona explícitamente desde la capa de aplicación.
