-- WhatsApp session storage
CREATE TABLE whatsapp_sessions (
    id SERIAL PRIMARY KEY,
    session_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- WhatsApp conversations
CREATE TABLE whatsapp_conversations (
    id SERIAL PRIMARY KEY,
    whatsapp_id VARCHAR(255) NOT NULL UNIQUE,
    contact_name VARCHAR(255),
    contact_number VARCHAR(50),
    last_message_timestamp TIMESTAMP,
    unread_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'new', -- new, assessed, answered, closed
    confidence_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- WhatsApp messages
CREATE TABLE whatsapp_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES whatsapp_conversations(id),
    whatsapp_message_id VARCHAR(255) NOT NULL UNIQUE,
    direction VARCHAR(10) NOT NULL, -- inbound, outbound
    content TEXT NOT NULL,
    media_url VARCHAR(255),
    timestamp TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Generated responses
CREATE TABLE whatsapp_responses (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES whatsapp_conversations(id),
    generated_content TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected, sent
    confidence_score FLOAT,
    assessment_results JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);