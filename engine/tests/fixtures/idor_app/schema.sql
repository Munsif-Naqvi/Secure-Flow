-- Read by the ownership-check rule: invoices belong to users through "owner".
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY,
    owner INTEGER NOT NULL REFERENCES users(id),
    total DECIMAL(10, 2)
);
