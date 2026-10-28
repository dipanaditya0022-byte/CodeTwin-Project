#!/usr/bin/env bash
# Provision CodeTwin on Azure with the az CLI (single region, managed services).
#
# NOT YET RUN against a real subscription: read each step, set the variables,
# and run it section by section the first time. Needs: az login, a resource
# group name that is free, and sqlcmd for the schema step.
set -euo pipefail

LOCATION="${LOCATION:-centralindia}"
RG="${RG:-codetwin-rg}"
SUFFIX="${SUFFIX:-$RANDOM}"                    # keeps global names unique
SQL_SERVER="codetwin-sql-$SUFFIX"
SQL_DB="codetwin"
SQL_ADMIN="codetwinadmin"
STORAGE="codetwinst$SUFFIX"
COSMOS="codetwin-cosmos-$SUFFIX"
VAULT="codetwin-kv-$SUFFIX"
PLAN="codetwin-plan"
API_APP="codetwin-api-$SUFFIX"
WORKER_APP="codetwin-worker-$SUFFIX"
WEB_APP="codetwin-web-$SUFFIX"

read -rsp "SQL admin password: " SQL_ADMIN_PASSWORD; echo
read -rsp "Password for the codetwin_app database user: " APP_DB_PASSWORD; echo
read -rsp "Password for the codetwin_report (Power BI) user: " REPORT_DB_PASSWORD; echo

az group create -n "$RG" -l "$LOCATION"

# ---- Azure SQL Database (public access off except the App Service addresses, added below)
az sql server create -g "$RG" -n "$SQL_SERVER" -l "$LOCATION" -u "$SQL_ADMIN" -p "$SQL_ADMIN_PASSWORD" --minimal-tls-version 1.2
az sql db create -g "$RG" -s "$SQL_SERVER" -n "$SQL_DB" --service-objective S0

# ---- Storage: private blob container and the run queue
az storage account create -g "$RG" -n "$STORAGE" -l "$LOCATION" --sku Standard_LRS \
  --allow-blob-public-access false --min-tls-version TLS1_2 --https-only true
STORAGE_CONN=$(az storage account show-connection-string -g "$RG" -n "$STORAGE" --query connectionString -o tsv)
az storage container create --name codetwin --connection-string "$STORAGE_CONN" --public-access off
az storage queue create --name similarity-runs --connection-string "$STORAGE_CONN"

# ---- Cosmos DB (NoSQL API): match reports partitioned by run_id
az cosmosdb create -g "$RG" -n "$COSMOS" --locations regionName="$LOCATION" --capabilities EnableServerless
az cosmosdb sql database create -g "$RG" -a "$COSMOS" -n codetwin
az cosmosdb sql container create -g "$RG" -a "$COSMOS" -d codetwin -n match_reports --partition-key-path /run_id
COSMOS_KEY=$(az cosmosdb keys list -g "$RG" -n "$COSMOS" --query primaryMasterKey -o tsv)

# ---- App Service: one plan, two apps from the same code (API and worker)
az appservice plan create -g "$RG" -n "$PLAN" --is-linux --sku B2
for APP in "$API_APP" "$WORKER_APP"; do
  az webapp create -g "$RG" -p "$PLAN" -n "$APP" --runtime "PYTHON:3.12"
  az webapp update -g "$RG" -n "$APP" --https-only true
  az webapp identity assign -g "$RG" -n "$APP"
done
az webapp config set -g "$RG" -n "$API_APP" --always-on true \
  --startup-file "python -m uvicorn codetwin.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"
az webapp config set -g "$RG" -n "$WORKER_APP" --always-on true --startup-file "python -m codetwin.worker"

# ---- Key Vault: secrets read by both apps through their managed identities
az keyvault create -g "$RG" -n "$VAULT" -l "$LOCATION" --enable-rbac-authorization true
ME=$(az ad signed-in-user show --query id -o tsv)
VAULT_ID=$(az keyvault show -n "$VAULT" --query id -o tsv)
az role assignment create --assignee "$ME" --role "Key Vault Secrets Officer" --scope "$VAULT_ID"
DB_URL="mssql://Driver={ODBC Driver 18 for SQL Server};Server=tcp:$SQL_SERVER.database.windows.net,1433;Database=$SQL_DB;Uid=codetwin_app;Pwd=$APP_DB_PASSWORD;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
az keyvault secret set --vault-name "$VAULT" -n codetwin-database-url --value "$DB_URL" > /dev/null
az keyvault secret set --vault-name "$VAULT" -n codetwin-jwt-secret --value "$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" > /dev/null
az keyvault secret set --vault-name "$VAULT" -n codetwin-storage-connection --value "$STORAGE_CONN" > /dev/null
az keyvault secret set --vault-name "$VAULT" -n codetwin-cosmos-key --value "$COSMOS_KEY" > /dev/null
for APP in "$API_APP" "$WORKER_APP"; do
  PRINCIPAL=$(az webapp identity show -g "$RG" -n "$APP" --query principalId -o tsv)
  az role assignment create --assignee "$PRINCIPAL" --role "Key Vault Secrets User" --scope "$VAULT_ID"
  az webapp config appsettings set -g "$RG" -n "$APP" --settings \
    CODETWIN_KEY_VAULT_URL="https://$VAULT.vault.azure.net/" \
    CODETWIN_STORAGE_BACKEND=azure \
    CODETWIN_COSMOS_URL="https://$COSMOS.documents.azure.com:443/" \
    CODETWIN_CORS_ORIGINS="[\"https://$WEB_APP.azurestaticapps.net\"]" \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true > /dev/null
done
# the worker needs the UniXcoder packages; set CODETWIN_EMBEDDER=unixcoder on BOTH apps once
# requirements-ml.txt is deployed (the API stamps the model version on each run)

# ---- Database firewall: only the App Service outbound addresses
for IP in $(az webapp show -g "$RG" -n "$API_APP" --query possibleOutboundIpAddresses -o tsv | tr ',' ' '); do
  az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" -n "appsvc-${IP//./-}" --start-ip-address "$IP" --end-ip-address "$IP" > /dev/null
done
echo "Add your own IP for the next step, then remove it:"
echo "  az sql server firewall-rule create -g $RG -s $SQL_SERVER -n setup --start-ip-address <ip> --end-ip-address <ip>"

# ---- Schema and least-privilege database users (run from your machine)
cat <<EOF

Next steps:
1. sqlcmd -S $SQL_SERVER.database.windows.net -d $SQL_DB -U $SQL_ADMIN -i db/codetwin_schema.sql
2. Uncomment section 7 of db/codetwin_schema.sql with the two passwords you entered, and run it the same way.
3. Deploy the backend to both apps. App Service installs requirements.txt, so the build
   folder gets one file with the base, Azure and model packages together:
     rm -rf build && mkdir build && cp -r backend/codetwin build/
     cat backend/requirements*.txt | grep -v '^-r' | sort -u > build/requirements.txt
     (cd build && zip -qr ../backend.zip .)
     az webapp deploy -g $RG -n $API_APP --src-path backend.zip --type zip
     az webapp deploy -g $RG -n $WORKER_APP --src-path backend.zip --type zip
4. Create the first admin from your machine with CODETWIN_DATABASE_URL pointing at Azure SQL:
     python -m codetwin.cli create-user --role admin --email you@college.edu --name "You"
5. Frontend: az staticwebapp create -g $RG -n $WEB_APP -l eastasia --sku Free
     cd frontend && VITE_API_URL=https://$API_APP.azurewebsites.net npm run build
     npx @azure/static-web-apps-cli deploy ./dist --deployment-token <token from the portal>
EOF
