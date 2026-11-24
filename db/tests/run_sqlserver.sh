#!/usr/bin/env bash
# Check the Azure SQL scripts on a real SQL Server (in Docker), without Azure:
#   1. the fresh schema (db/codetwin_schema.sql) loads
#   2. the October schema (db/tests/october_schema.sql) plus db/migrations/001-006 loads, twice (idempotent)
#   3. both databases have identical tables, columns, constraints, indexes, views, procedures, triggers
#   4. db/tests/behaviour.sql passes on both (procedures, triggers, constraints, views)
#
# Needs Docker. On Apple Silicon the image runs under emulation (slower, same results).
#   db/tests/run_sqlserver.sh            # starts a throwaway container, removes it at the end
#   KEEP=1 db/tests/run_sqlserver.sh     # leaves the container running for inspection
set -euo pipefail
cd "$(dirname "$0")/../.."
NAME=codetwin-sqltest
IMAGE=mcr.microsoft.com/mssql/server:2022-latest
PW="Ct9!$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"   # never written to disk
WORK=$(mktemp -d)
cleanup() { rm -rf "$WORK"; [ "${KEEP:-0}" = 1 ] || docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --platform linux/amd64 -e ACCEPT_EULA=Y -e "MSSQL_SA_PASSWORD=$PW" \
  -e MSSQL_PID=Developer "$IMAGE" >/dev/null
sq() { docker exec "$NAME" /opt/mssql-tools18/bin/sqlcmd -C -b -S localhost -U sa -P "$PW" "$@"; }
step() { local what="$1"; shift; if out=$("$@" 2>&1); then echo "PASS $what"; else echo "FAIL $what"; echo "$out" | tail -5; exit 1; fi; }
printf 'waiting for SQL Server'
for _ in $(seq 1 90); do sq -Q "SELECT 1" >/dev/null 2>&1 && break; printf .; sleep 2; done; echo

cp db/tests/october_schema.sql "$WORK/old_schema.sql"
cp db/codetwin_schema.sql db/tests/behaviour.sql "$WORK/"
for f in db/migrations/0*.sql; do case "$f" in *_sqlite.sql) ;; *) cp "$f" "$WORK/" ;; esac; done
docker exec "$NAME" mkdir -p /tmp/ct
docker cp "$WORK/." "$NAME:/tmp/ct/"

sq -Q "CREATE DATABASE ct_fresh; CREATE DATABASE ct_migrated;"
step "fresh schema loads" sq -d ct_fresh -i /tmp/ct/codetwin_schema.sql
step "October schema loads" sq -d ct_migrated -i /tmp/ct/old_schema.sql
for pass in 1 2; do
  for m in $(cd "$WORK" && ls 0*.sql | sort); do step "migration ${m%.sql} (run $pass)" sq -d ct_migrated -i "/tmp/ct/$m"; done
done

STRUCTURE="SET NOCOUNT ON; SELECT x COLLATE DATABASE_DEFAULT FROM (
 SELECT ('col '+t.name+'.'+c.name+' '+ty.name+'('+CAST(c.max_length AS varchar)+') null='+CAST(c.is_nullable AS varchar)) COLLATE DATABASE_DEFAULT AS x
   FROM sys.columns c JOIN sys.tables t ON t.object_id=c.object_id JOIN sys.types ty ON ty.user_type_id=c.user_type_id
 UNION ALL SELECT ('idx '+OBJECT_NAME(i.object_id)+'.'+i.name+' unique='+CAST(i.is_unique AS varchar)+' filter='+ISNULL(i.filter_definition,'')) COLLATE DATABASE_DEFAULT
   FROM sys.indexes i JOIN sys.tables t ON t.object_id=i.object_id WHERE i.name IS NOT NULL
 UNION ALL SELECT ('chk '+OBJECT_NAME(parent_object_id)+' '+definition) COLLATE DATABASE_DEFAULT FROM sys.check_constraints
 UNION ALL SELECT ('fk '+OBJECT_NAME(parent_object_id)+'.'+name) COLLATE DATABASE_DEFAULT FROM sys.foreign_keys
 UNION ALL SELECT ('uq '+OBJECT_NAME(parent_object_id)+'.'+name) COLLATE DATABASE_DEFAULT FROM sys.key_constraints WHERE type='UQ'
 UNION ALL SELECT ('obj '+type_desc+' '+name) COLLATE DATABASE_DEFAULT FROM sys.objects WHERE type IN ('V','P','TR')) AS o ORDER BY 1"
sq -d ct_fresh -h -1 -W -Q "$STRUCTURE" > "$WORK/fresh.txt"
sq -d ct_migrated -h -1 -W -Q "$STRUCTURE" > "$WORK/migrated.txt"
if diff "$WORK/fresh.txt" "$WORK/migrated.txt"; then
  echo "PASS migrated database is identical to a fresh one ($(wc -l < "$WORK/fresh.txt" | tr -d ' ') objects)"
else echo "FAIL migrated and fresh databases differ (see diff above)"; exit 1; fi

failed=0
for db in ct_fresh ct_migrated; do
  out=$(sq -d "$db" -i /tmp/ct/behaviour.sql 2>&1) || true
  echo "$out" | grep -E '^(PASS|FAIL|Msg)' | sed "s/^/[$db] /"
  echo "$out" | grep -qE '^(FAIL|Msg)' && failed=1
done
[ "$failed" = 0 ] && echo "ALL SQL SERVER CHECKS PASSED" || { echo "SOME SQL SERVER CHECKS FAILED"; exit 1; }
