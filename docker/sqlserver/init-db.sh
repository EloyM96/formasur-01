#!/bin/bash
set -euo pipefail

if [ -z "${SA_PASSWORD:-}" ]; then
  echo "SA_PASSWORD environment variable must be set" >&2
  exit 1
fi

if [ -z "${SQLSERVER_DB:-}" ]; then
  echo "SQLSERVER_DB environment variable must be set" >&2
  exit 1
fi

/opt/mssql/bin/sqlservr &
sqlservr_pid=$!

# Wait for SQL Server to become available
for i in {1..60}; do
  if /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P "${SA_PASSWORD}" -Q "SELECT 1" >/dev/null 2>&1; then
    break
  fi
  echo "Waiting for SQL Server to be available..."
  sleep 2
  if [ "$i" -eq 60 ]; then
    echo "SQL Server did not become available in time" >&2
    exit 1
  fi
done

echo "SQL Server is available."

# Create the database if it does not exist
/opt/mssql-tools/bin/sqlcmd \
  -S localhost \
  -U sa \
  -P "${SA_PASSWORD}" \
  -v DB_NAME="${SQLSERVER_DB}" \
  -i /usr/src/app/init-db.sql

wait "${sqlservr_pid}"
