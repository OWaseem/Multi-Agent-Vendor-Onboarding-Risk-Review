-- schema.sql — Mocked persistence for the vendor onboarding & risk review workflow.
-- Every "side-effect" write is local to this SQLite file; nothing external.
-- Vocabulary matches models.py. Run via db.init_db().

-- ---------------------------------------------------------------------------
-- vendors: the mock vendor master DB used by the vendor_lookup tool.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Legal/trade name of the vendor; used for lookups and watchlist matching.
    name TEXT NOT NULL UNIQUE,
    -- Vendor category; must be one of the VendorCategory enum values.
    category TEXT NOT NULL,
    -- Country of operation; a non-US value can trip the foreign_entity risk flag.
    country TEXT NOT NULL,
    -- True if the org has worked with this vendor before; feeds new_vendor risk.
    prior_relationship BOOLEAN NOT NULL DEFAULT 0,
    -- Comma-separated certifications on file, e.g. "SOC 2, ISO 27001".
    certifications TEXT,
    -- ISO timestamp of when the mock record was seeded.
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- watchlist: mock sanctions/watchlist checked by the watchlist_check tool.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Entity name as it appears on the watchlist; matched case-insensitively.
    name TEXT NOT NULL,
    -- Why the entity is listed (e.g. "Sanctioned entity", "Regulatory action").
    reason TEXT NOT NULL,
    -- ISO timestamp of when the entity was added.
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- approval_requests: written by create_approval_request and resolved by the
-- human-approval gate (or auto-approved on the standard path).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS approval_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- The workflow request_id this approval belongs to.
    request_id TEXT NOT NULL,
    -- Vendor under review (denormalized for easy reporting).
    vendor_name TEXT NOT NULL,
    -- ISO timestamp when the approval request was created.
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    -- ApprovalStatus: pending | approved | rejected.
    status TEXT NOT NULL DEFAULT 'pending',
    -- Who decided: 'auto' (reviewer approved) or 'human' (gate resolved it).
    decided_by TEXT,
    -- Free-text notes from the decision (e.g. human reviewer comments).
    decision_notes TEXT
);

-- ---------------------------------------------------------------------------
-- vendor_status_log: append-only log written by update_vendor_status with the
-- final onboarding status of each request.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vendor_status_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- The workflow request_id that produced this status write.
    request_id TEXT NOT NULL,
    -- Vendor name (denormalized).
    vendor_name TEXT NOT NULL,
    -- OnboardingStatus value, e.g. standard_onboarding | approved | rejected.
    final_status TEXT NOT NULL,
    -- ISO timestamp of the write.
    written_at TEXT NOT NULL DEFAULT (datetime('now')),
    -- Optional notes (e.g. final risk score, human decision reference).
    notes TEXT
);

-- Lookups by request_id are the common access pattern.
CREATE INDEX IF NOT EXISTS idx_approval_request_id ON approval_requests(request_id);
CREATE INDEX IF NOT EXISTS idx_status_log_request_id ON vendor_status_log(request_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_name ON watchlist(name);
