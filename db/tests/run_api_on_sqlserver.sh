#!/usr/bin/env bash
# Run the whole API test suite against SQL Server 2022 instead of SQLite, in Docker.
# This exercises the production database path (pyodbc, T-SQL procedures, OUTPUT, OFFSET paging,
# filtered indexes) that the normal local run never touches. Each test gets a fresh database.
#   db/tests/run_api_on_sqlserver.sh              # all tests
#   db/tests/run_api_on_sqlserver.sh -k forms     # extra arguments go to pytest
set -euo pipefail
cd "$(dirname "$0")/../.."
NET=codetwin-apitest
SQL=codetwin-apitest-sql
PW="Ct9!$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"   # never written to disk
cleanup() { docker rm -f "$SQL" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker network create "$NET" >/dev/null
docker run -d --name "$SQL" --network "$NET" --platform linux/amd64 -e ACCEPT_EULA=Y -e "MSSQL_SA_PASSWORD=$PW" \
  -e MSSQL_PID=Developer mcr.microsoft.com/mssql/server:2022-latest >/dev/null
docker build -q -f db/tests/Dockerfile.api-tests -t codetwin-api-tests . >/dev/null
printf 'waiting for SQL Server'
for _ in $(seq 1 90); do
  docker exec "$SQL" /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$PW" -Q "SELECT 1" >/dev/null 2>&1 && break
  printf .; sleep 2
done; echo

docker run --rm --network "$NET" -v "$PWD:/src:ro" \
  -e "CODETWIN_TEST_MSSQL=Driver={ODBC Driver 18 for SQL Server};Server=tcp:$SQL,1433;Uid=sa;Pwd=$PW;Encrypt=yes;TrustServerCertificate=yes" \
  codetwin-api-tests python -m pytest -q -p no:cacheprovider "$@"
