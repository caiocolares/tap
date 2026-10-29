ALTER TABLE tap_jobs
    ADD COLUMN owner_email TEXT,
    ADD COLUMN notification_status TEXT NOT NULL DEFAULT 'disabled'
        CHECK (notification_status IN ('disabled', 'pending', 'sending', 'sent', 'error')),
    ADD COLUMN notification_attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN notification_available_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    ADD COLUMN notification_lease_token UUID,
    ADD COLUMN notification_lease_until TIMESTAMPTZ;

CREATE INDEX tap_jobs_notification_idx ON tap_jobs (notification_available_at)
    WHERE status = 'completed' AND notification_status IN ('pending', 'sending');

CREATE TABLE tap_auth_limits (
    key TEXT PRIMARY KEY,
    hits INTEGER NOT NULL,
    window_until TIMESTAMPTZ NOT NULL
);
