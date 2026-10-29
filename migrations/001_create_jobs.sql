CREATE TABLE tap_jobs (
    job_id UUID PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'error')),
    format TEXT NOT NULL CHECK (format IN ('txt', 'json')),
    input_object TEXT NOT NULL,
    model TEXT NOT NULL,
    language TEXT,
    diarization BOOLEAN NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL CHECK (max_attempts > 0),
    available_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    lease_token UUID,
    lease_until TIMESTAMPTZ,
    result_object TEXT,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX tap_jobs_claim_idx ON tap_jobs (available_at, created_at) WHERE status = 'queued';
CREATE INDEX tap_jobs_lease_idx ON tap_jobs (lease_until) WHERE status = 'processing';
CREATE INDEX tap_jobs_expiry_idx ON tap_jobs (expires_at) WHERE expires_at IS NOT NULL;
