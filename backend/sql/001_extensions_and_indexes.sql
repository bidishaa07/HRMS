-- Aurora HR PostgreSQL bootstrap. SQLAlchemy/Alembic owns tables; this script owns extensions
-- and indexes that are PostgreSQL-specific.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS document_embeddings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  content text NOT NULL,
  embedding vector(384) NOT NULL,
  acl jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS ix_document_embeddings_hnsw
  ON document_embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS ix_attendance_employee_date
  ON attendance (employee_id, work_date DESC);
CREATE INDEX IF NOT EXISTS ix_leave_employee_dates
  ON leave_requests (employee_id, start_date, end_date);
CREATE INDEX IF NOT EXISTS ix_audit_entity
  ON audit_logs (entity_type, entity_id, occurred_at DESC);

