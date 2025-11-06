/*
  # UMA (Universal Multi-Agent Upgrader) Database Schema

  1. New Tables
    - `projects`
      - `id` (uuid, primary key) - Unique project identifier
      - `name` (text) - Project name
      - `description` (text) - Optional project description
      - `created_at` (timestamptz) - Project creation timestamp
      - `updated_at` (timestamptz) - Last update timestamp
      - `user_id` (uuid) - Owner of the project
      - `file_count` (integer) - Number of files in project
      - `status` (text) - Current status: 'active', 'archived'

    - `upgrade_runs`
      - `id` (uuid, primary key) - Unique run identifier
      - `project_id` (uuid, foreign key) - Associated project
      - `status` (text) - Run status: 'queued', 'running', 'completed', 'failed'
      - `started_at` (timestamptz) - When the upgrade started
      - `completed_at` (timestamptz) - When the upgrade finished
      - `files_processed` (integer) - Number of files processed
      - `issues_found` (integer) - Number of issues detected
      - `issues_fixed` (integer) - Number of issues resolved
      - `validation_passed` (boolean) - Whether validation passed
      - `report_url` (text) - URL/path to generated report
      - `error_message` (text) - Error details if failed
      - `logs` (jsonb) - Structured log data

    - `settings`
      - `id` (uuid, primary key) - Settings identifier
      - `user_id` (uuid) - User these settings belong to
      - `api_provider` (text) - LLM provider: 'openai', 'anthropic', 'gemini'
      - `api_key_encrypted` (text) - Encrypted API key
      - `model_name` (text) - Model to use
      - `temperature` (numeric) - Model temperature setting
      - `max_retries` (integer) - Maximum retry attempts
      - `auto_validate` (boolean) - Enable auto-validation
      - `created_at` (timestamptz) - Settings creation time
      - `updated_at` (timestamptz) - Last update time

  2. Security
    - Enable RLS on all tables
    - Add policies for authenticated users to manage their own data
*/

-- Create projects table
CREATE TABLE IF NOT EXISTS projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text DEFAULT '',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  user_id uuid NOT NULL,
  file_count integer DEFAULT 0,
  status text DEFAULT 'active'
);

-- Create upgrade_runs table
CREATE TABLE IF NOT EXISTS upgrade_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  status text DEFAULT 'queued',
  started_at timestamptz DEFAULT now(),
  completed_at timestamptz,
  files_processed integer DEFAULT 0,
  issues_found integer DEFAULT 0,
  issues_fixed integer DEFAULT 0,
  validation_passed boolean DEFAULT false,
  report_url text DEFAULT '',
  error_message text DEFAULT '',
  logs jsonb DEFAULT '[]'::jsonb
);

-- Create settings table
CREATE TABLE IF NOT EXISTS settings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL UNIQUE,
  api_provider text DEFAULT 'openai',
  api_key_encrypted text DEFAULT '',
  model_name text DEFAULT 'gpt-4',
  temperature numeric DEFAULT 0.7,
  max_retries integer DEFAULT 3,
  auto_validate boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Enable RLS
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE upgrade_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;

-- Projects policies
CREATE POLICY "Users can view own projects"
  ON projects FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create own projects"
  ON projects FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own projects"
  ON projects FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own projects"
  ON projects FOR DELETE
  TO authenticated
  USING (auth.uid() = user_id);

-- Upgrade runs policies
CREATE POLICY "Users can view own upgrade runs"
  ON upgrade_runs FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM projects
      WHERE projects.id = upgrade_runs.project_id
      AND projects.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can create upgrade runs for own projects"
  ON upgrade_runs FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM projects
      WHERE projects.id = upgrade_runs.project_id
      AND projects.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can update own upgrade runs"
  ON upgrade_runs FOR UPDATE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM projects
      WHERE projects.id = upgrade_runs.project_id
      AND projects.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM projects
      WHERE projects.id = upgrade_runs.project_id
      AND projects.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can delete own upgrade runs"
  ON upgrade_runs FOR DELETE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM projects
      WHERE projects.id = upgrade_runs.project_id
      AND projects.user_id = auth.uid()
    )
  );

-- Settings policies
CREATE POLICY "Users can view own settings"
  ON settings FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create own settings"
  ON settings FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own settings"
  ON settings FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own settings"
  ON settings FOR DELETE
  TO authenticated
  USING (auth.uid() = user_id);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS projects_user_id_idx ON projects(user_id);
CREATE INDEX IF NOT EXISTS upgrade_runs_project_id_idx ON upgrade_runs(project_id);
CREATE INDEX IF NOT EXISTS upgrade_runs_status_idx ON upgrade_runs(status);
CREATE INDEX IF NOT EXISTS settings_user_id_idx ON settings(user_id);