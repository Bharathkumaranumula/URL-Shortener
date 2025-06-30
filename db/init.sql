CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE urls (
  id SERIAL PRIMARY KEY,
  original_url TEXT NOT NULL,
  short_code VARCHAR(8) UNIQUE,
  user_id INT REFERENCES users(id),
  created_at TIMESTAMP DEFAULT now(),
  expires_at TIMESTAMP
);

CREATE TABLE clicks (
  id SERIAL PRIMARY KEY,
  url_id INT REFERENCES urls(id),
  ip_address VARCHAR(45),
  referrer TEXT,
  user_agent TEXT,
  timestamp TIMESTAMP DEFAULT now(),
  country VARCHAR(64)
);


CREATE INDEX idx_urls_short_code ON urls(short_code);
CREATE INDEX idx_clicks_url_id ON clicks(url_id);
