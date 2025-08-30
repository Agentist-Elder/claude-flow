# Database Migrations

This directory contains database migration files for the InciteRewrite platform. Migrations are numbered sequentially and should be run in order.

## Migration Files

### 001_initial_schema.sql
- **Purpose**: Initial database schema creation
- **Date**: 2024-01-15
- **Description**: Creates all tables, indexes, triggers, and initial data for the platform
- **Tables Created**:
  - Users and authentication (users, user_profiles, user_tokens, user_sessions, api_keys, user_usage)
  - Documents and collaboration (documents, document_versions, document_collaborators, etc.)
  - Analytics and metrics (system_metrics, user_analytics, document_analytics, etc.)

## Running Migrations

### Prerequisites
- PostgreSQL 14 or higher
- Required extensions: uuid-ossp, pg_trgm, pg_stat_statements

### Manual Execution
```bash
# Connect to your database
psql -h localhost -U postgres -d inciterewrite

# Run the migration
\i /path/to/migrations/001_initial_schema.sql
```

### Using Node.js Migration Runner (Future)
```javascript
const migrationRunner = require('./migration-runner');
await migrationRunner.run();
```

## Migration Best Practices

1. **Never modify existing migrations** - Always create new migration files
2. **Test migrations on staging** before applying to production
3. **Backup database** before running migrations in production
4. **Sequential naming** - Use 3-digit numbering (001, 002, 003, etc.)
5. **Descriptive names** - Include brief description in filename

## Schema Validation

After running migrations, validate the schema:

```sql
-- Check all tables exist
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;

-- Check indexes
SELECT indexname, tablename FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname;

-- Check constraints
SELECT conname, contype, conrelid::regclass FROM pg_constraint WHERE connamespace = 'public'::regnamespace;
```

## Rollback Strategy

For production rollbacks:
1. Stop application services
2. Restore from pre-migration backup
3. Verify data integrity
4. Restart services

## Future Migration Guidelines

### Adding Columns
```sql
-- Good: Add column with default value
ALTER TABLE users ADD COLUMN new_field VARCHAR(100) DEFAULT 'default_value';

-- Update existing rows if needed
UPDATE users SET new_field = 'calculated_value' WHERE condition;
```

### Modifying Columns
```sql
-- Good: Create new column, migrate data, drop old column
ALTER TABLE users ADD COLUMN email_new VARCHAR(320);
UPDATE users SET email_new = email;
ALTER TABLE users DROP COLUMN email;
ALTER TABLE users RENAME COLUMN email_new TO email;
```

### Adding Indexes
```sql
-- Good: Create indexes concurrently in production
CREATE INDEX CONCURRENTLY idx_new_index ON table_name(column_name);
```

### Data Migrations
```sql
-- Always include data validation
DO $$
DECLARE
    row_count INTEGER;
BEGIN
    -- Perform migration
    UPDATE table_name SET column = new_value WHERE condition;
    
    -- Validate
    SELECT COUNT(*) INTO row_count FROM table_name WHERE validation_condition;
    
    IF row_count != expected_count THEN
        RAISE EXCEPTION 'Migration validation failed: expected %, got %', expected_count, row_count;
    END IF;
END $$;
```

## Monitoring Migration Performance

Track migration execution:
```sql
-- Enable statement logging
SET log_statement = 'all';
SET log_duration = on;

-- Monitor long-running queries
SELECT query, query_start, state, wait_event 
FROM pg_stat_activity 
WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%';
```

## Emergency Contacts

- Database Admin: admin@inciterewrite.com
- DevOps Team: devops@inciterewrite.com
- On-call Engineer: +1-555-0123