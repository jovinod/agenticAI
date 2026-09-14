# Azure Setup and Deployment

This is the operational companion to **Building Agentic AI Systems**. The chapters explain architecture and design. This file contains the Azure commands needed to run the corresponding repository stages.

Use only the stage required by the chapter you are reading. Later stages will extend this file as the system adds Azure services.

> **Cost and safety:** These commands create billable resources. Check the selected subscription, use development-sized resources, set a budget, and remove the resource group when you finish. Never commit passwords, connection strings, access keys, or generated environment files.

## How the Stages Relate to Git

Each deployable chapter has a completion tag. Check out that tag before building:

```powershell
git switch --detach chapter-03-complete
git status --short
```

The working tree must be clean. Both application images use the current Git commit SHA:

```powershell
$fullCommitSha = git rev-parse HEAD
$commitSha = git rev-parse --short=12 HEAD
```

This creates a traceable path:

```text
chapter completion tag -> Git commit -> image tags -> Container Apps revisions
```

Do not use `latest` for application images. A mutable tag cannot identify the source running in a revision.

## Shared Prerequisites

Install these tools before using any deployment stage:

- Git
- Azure CLI
- The Azure CLI Container Apps extension
- Access to an Azure subscription in which you may create resources

Sign in, inspect the selected subscription, and install or update the extension:

```powershell
az login
az account show --output table
az extension add --name containerapp --upgrade
```

If the displayed subscription is wrong, select the intended one explicitly:

```powershell
az account set --subscription "SUBSCRIPTION_NAME_OR_ID"
az account show --output table
```

## Chapter 3: Distributed Job Path

Chapter 3 uses:

- Azure Container Registry for the API and worker images.
- Azure Container Apps for the API and worker processes.
- Azure Service Bus for job delivery.
- Azure Database for PostgreSQL Flexible Server for durable job state.

The API has external ingress. The worker has no ingress. Both use PostgreSQL. The API receives a send-only Service Bus credential, while the worker receives a listen-only credential.

### 1. Choose Names

Resource names must be unique where Azure requires it. Replace the suffix with lowercase letters and numbers.

```powershell
$location = "eastus"
$suffix = "replacewithuniquevalue"

$resourceGroup = "rg-stock-research-ch03-$suffix"
$environmentName = "cae-stock-research-$suffix"
$registryName = "acrstockresearch$suffix"
$serviceBusNamespace = "sb-stock-research-$suffix"
$queueName = "research-jobs"
$postgresServer = "pg-stock-research-$suffix"
$databaseName = "alpha"
$dbAdmin = "alphaadmin"
$apiName = "stock-research-api"
$workerName = "stock-research-worker"
```

Confirm the values before creating resources:

```powershell
$resourceGroup
$registryName
$serviceBusNamespace
$postgresServer
```

### 2. Create the Shared Resources

Create the resource group, registry, Container Apps environment, Service Bus namespace, and queue:

```powershell
az group create `
  --name $resourceGroup `
  --location $location

az acr create `
  --resource-group $resourceGroup `
  --name $registryName `
  --sku Basic `
  --admin-enabled true

az containerapp env create `
  --resource-group $resourceGroup `
  --name $environmentName `
  --location $location

az servicebus namespace create `
  --resource-group $resourceGroup `
  --name $serviceBusNamespace `
  --location $location `
  --sku Standard

az servicebus queue create `
  --resource-group $resourceGroup `
  --namespace-name $serviceBusNamespace `
  --name $queueName
```

The registry admin credential keeps this early deployment direct. Chapter 14 replaces service credentials with workload identities where supported.

### 3. Create Least-Privilege Queue Credentials

Create one rule that can only send and another that can only listen:

```powershell
az servicebus queue authorization-rule create `
  --resource-group $resourceGroup `
  --namespace-name $serviceBusNamespace `
  --queue-name $queueName `
  --name api-send `
  --rights Send

az servicebus queue authorization-rule create `
  --resource-group $resourceGroup `
  --namespace-name $serviceBusNamespace `
  --queue-name $queueName `
  --name worker-listen `
  --rights Listen
```

Read the connection strings into the current PowerShell process. Do not print or save them:

```powershell
$sendConnection = az servicebus queue authorization-rule keys list `
  --resource-group $resourceGroup `
  --namespace-name $serviceBusNamespace `
  --queue-name $queueName `
  --name api-send `
  --query primaryConnectionString `
  --output tsv

$listenConnection = az servicebus queue authorization-rule keys list `
  --resource-group $resourceGroup `
  --namespace-name $serviceBusNamespace `
  --queue-name $queueName `
  --name worker-listen `
  --query primaryConnectionString `
  --output tsv
```

### 4. Create PostgreSQL

Choose a strong URL-safe password for this learning deployment. `Read-Host` keeps the value out of the saved command text, but the following Azure CLI process receives it as an argument. Use this only in a trusted development environment.

```powershell
$dbPassword = Read-Host "Enter a new PostgreSQL administrator password"

az postgres flexible-server create `
  --resource-group $resourceGroup `
  --name $postgresServer `
  --location $location `
  --admin-user $dbAdmin `
  --admin-password $dbPassword `
  --sku-name Standard_B1ms `
  --tier Burstable `
  --storage-size 32 `
  --version 16

az postgres flexible-server db create `
  --resource-group $resourceGroup `
  --server-name $postgresServer `
  --database-name $databaseName
```

Allow connections from Azure services for this chapter deployment:

```powershell
az postgres flexible-server firewall-rule create `
  --resource-group $resourceGroup `
  --name $postgresServer `
  --rule-name AllowAzureServices `
  --start-ip-address 0.0.0.0 `
  --end-ip-address 0.0.0.0
```

This broad Azure-services rule is a learning-stage compromise. A production environment should use private networking and stronger identity controls.

Build the SQLAlchemy connection URL without printing it:

```powershell
$dbHost = az postgres flexible-server show `
  --resource-group $resourceGroup `
  --name $postgresServer `
  --query fullyQualifiedDomainName `
  --output tsv

$databaseUrl = "postgresql+psycopg://${dbAdmin}:${dbPassword}@${dbHost}:5432/${databaseName}?sslmode=require"
```

### 5. Confirm the Source State

Run these commands from the companion repository:

```powershell
git switch --detach chapter-03-complete

if (git status --porcelain) {
  throw "The working tree must be clean before images are built."
}

$fullCommitSha = git rev-parse HEAD
$commitSha = git rev-parse --short=12 HEAD

$fullCommitSha
$commitSha
```

For the curated Chapter 3 repository, the tag resolves to:

```text
a2effa48bad2636d286269a16251bc91ba38905f
```

The corresponding 12-character image suffix is `a2effa48bad2`.

### 6. Build Immutable Images

Azure Container Registry can build the images remotely, so local Docker is not required:

```powershell
az acr build `
  --registry $registryName `
  --image "stock-research-api:$commitSha" `
  backend/api

az acr build `
  --registry $registryName `
  --image "stock-research-worker:$commitSha" `
  backend/worker
```

Read the registry values and construct the full image names:

```powershell
$registryServer = az acr show `
  --name $registryName `
  --query loginServer `
  --output tsv

$registryUser = az acr credential show `
  --name $registryName `
  --query username `
  --output tsv

$registryPassword = az acr credential show `
  --name $registryName `
  --query passwords[0].value `
  --output tsv

$apiImage = "${registryServer}/stock-research-api:$commitSha"
$workerImage = "${registryServer}/stock-research-worker:$commitSha"
```

### 7. Deploy the API

The API receives external HTTPS traffic and uses the send-only queue credential:

```powershell
az containerapp create `
  --resource-group $resourceGroup `
  --environment $environmentName `
  --name $apiName `
  --image $apiImage `
  --ingress external `
  --target-port 8000 `
  --min-replicas 1 `
  --max-replicas 1 `
  --registry-server $registryServer `
  --registry-username $registryUser `
  --registry-password $registryPassword `
  --secrets `
    "database-url=$databaseUrl" `
    "servicebus-connection-string=$sendConnection" `
  --env-vars `
    "DATABASE_URL=secretref:database-url" `
    "SERVICEBUS_CONNECTION_STRING=secretref:servicebus-connection-string" `
    "SERVICEBUS_QUEUE_NAME=$queueName" `
    "ALLOWED_ORIGIN=http://localhost:5173"
```

### 8. Deploy the Worker

The worker has no ingress and uses the listen-only queue credential:

```powershell
az containerapp create `
  --resource-group $resourceGroup `
  --environment $environmentName `
  --name $workerName `
  --image $workerImage `
  --min-replicas 1 `
  --max-replicas 1 `
  --registry-server $registryServer `
  --registry-username $registryUser `
  --registry-password $registryPassword `
  --secrets `
    "database-url=$databaseUrl" `
    "servicebus-connection-string=$listenConnection" `
  --env-vars `
    "DATABASE_URL=secretref:database-url" `
    "SERVICEBUS_CONNECTION_STRING=secretref:servicebus-connection-string" `
    "SERVICEBUS_QUEUE_NAME=$queueName"
```

### 9. Verify the Deployed Source

Read the image associated with each active application template:

```powershell
$deployedApiImage = az containerapp show `
  --resource-group $resourceGroup `
  --name $apiName `
  --query "properties.template.containers[0].image" `
  --output tsv

$deployedWorkerImage = az containerapp show `
  --resource-group $resourceGroup `
  --name $workerName `
  --query "properties.template.containers[0].image" `
  --output tsv

$deployedApiImage
$deployedWorkerImage
```

Both values must end with `:$commitSha`. Inspect revision health as separate evidence:

```powershell
az containerapp revision list `
  --resource-group $resourceGroup `
  --name $apiName `
  --query "[].{name:name,active:properties.active,health:properties.healthState,image:properties.template.containers[0].image}" `
  --output table

az containerapp revision list `
  --resource-group $resourceGroup `
  --name $workerName `
  --query "[].{name:name,active:properties.active,health:properties.healthState,image:properties.template.containers[0].image}" `
  --output table
```

### 10. Verify the Live Job Path

Find the public API address and create a job:

```powershell
$apiHost = az containerapp show `
  --resource-group $resourceGroup `
  --name $apiName `
  --query properties.configuration.ingress.fqdn `
  --output tsv

$apiUrl = "https://$apiHost"

$created = Invoke-RestMethod `
  -Method Post `
  -Uri "$apiUrl/research" `
  -ContentType "application/json" `
  -Body '{"tickers":["AAPL","MSFT"]}'

$created
```

Request the returned job until it reaches `done`:

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "$apiUrl/research/$($created.job_id)"
```

The final response should contain two sample summary lines, one for each ticker. A first response of `queued` or `running` is normal because the API and worker operate independently.

### 11. Troubleshoot

If the job remains queued, inspect worker logs:

```powershell
az containerapp logs show `
  --resource-group $resourceGroup `
  --name $workerName `
  --follow
```

If the API does not start or cannot create a job, inspect its logs:

```powershell
az containerapp logs show `
  --resource-group $resourceGroup `
  --name $apiName `
  --follow
```

Check these likely causes:

- The active image does not end with the expected commit SHA.
- A secret reference or environment-variable name is misspelled.
- PostgreSQL does not permit the Container Apps connection.
- The API has the listen credential or the worker has the send credential.
- The queue name differs between the resource and application configuration.

### 12. Clean Up

Delete the chapter resource group when you no longer need the deployment:

```powershell
az group delete `
  --name $resourceGroup `
  --yes `
  --no-wait
```

This removes every Chapter 3 Azure resource created by this guide. Local Git tags and repository files are not affected.

## Chapter 4 Onward: One Deployment Script

Every stage from Chapter 4 to Chapter 20 shares one Bicep template and one deploy script, instead of a separate `az` walkthrough per chapter:

| File | Role |
|---|---|
| `infra/main.bicep` | The cumulative template. Each resource is behind its own `deploy*` boolean parameter (`deployRedis`, `deployApim`, `deployKeyVault`, and so on), so one template can express every stage. |
| `infra/params/chapter-NN.json` | One parameters file per chapter, turning on exactly the flags that chapter needs. Later files are supersets of earlier ones. |
| `infra/deploy.sh <params-file> [resource-group]` | Applies one parameters file to one resource group with `az deployment group create`. ARM deployments are idempotent, so re-running it — including with an earlier or later chapter's file — only creates or updates what's actually missing. |
| `infra/teardown.sh [resource-group]` | Deletes the whole resource group, with a typed confirmation. Run it once, after you are done testing, not between chapters. |

Deploying any chapter from 4 onward is one command:

```bash
git switch --detach chapter-NN-complete
./infra/deploy.sh infra/params/chapter-NN.json
```

The default resource group name is `stock-research-book-rg`; pass a second argument to use another one.

### What the script needs from you

The checked-in parameter files hold no reader-specific values. Anywhere a registry, email, or identity is needed, the file has a placeholder token instead — `YOUR_REGISTRY.azurecr.io`, `YOUR_EMAIL@example.com`, `YOUR_ENTRA_CLIENT_ID`, `YOUR_ENTRA_TENANT_ID`, `YOUR_ALLOWED_USERS@example.com`, or `https://YOUR_STATIC_WEB_APP_HOSTNAME`. `deploy.sh` fills those in from one local, gitignored config file, so your own values never touch a tracked file:

```bash
cp infra/.local-config.example infra/.local-config
```

Then edit `infra/.local-config` and fill in only what the chapter you're deploying needs:

- **`REGISTRY_LOGIN_SERVER`**, from Chapter 3 on — your own Azure Container Registry's login server (`az acr show --name <registry> --query loginServer -o tsv`). Build and push your own images first, the same way as Chapter 3's "Build Immutable Images" step, tagged with the same `chapter-NN` convention the params files use. `infra/deploy.sh` does not build images; it only substitutes whatever registry you give it into the image references already in the params file.
- **`APIM_PUBLISHER_EMAIL`**, from Chapter 7 on — Azure API Management requires a real publisher email at creation time; use your own.
- **`ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, `ALLOWED_USERS`, `ALLOWED_ORIGIN`**, from Chapter 13 on — register your own Entra ID app (Chapter 13 explains what it needs), set `ALLOWED_ORIGIN` to your own deployment's `staticWebAppHostname` output from Chapter 1 (with an `https://` prefix), and set `ALLOWED_USERS` to your own comma-separated allow-list of sign-in identities.

`deploy.sh` only substitutes a token if the matching variable is set and non-empty, so filling in nothing is safe for chapters that don't need it — the deployment fails with an unresolved `YOUR_...` placeholder in that case, which is your signal that a value is still missing.

Two further local secret files stay separate from `.local-config` because they are one-line credentials, not identifiers — both gitignored, both never committed: `infra/.postgres-admin-password` (the script generates one on first use) and `infra/.tavily-api-key` (you create this yourself, from Chapter 5 onward — one line containing your Tavily key).

**Region parameters** (`foundryLocation`, `staticWebAppLocation`) default to the regions the author used for Microsoft Foundry model availability. Confirm your target region still supports the model deployment before relying on the default.

### Checking what a deployment produced

`main.bicep` exposes outputs for the resources each stage activates — read them without re-deploying:

```bash
az deployment group show \
  --resource-group stock-research-book-rg \
  --name main \
  --query properties.outputs
```

Relevant outputs by stage: `apiFqdn` (Chapter 3 on), `apimGatewayUrl` / `apimSubscriptionKey` (Chapter 7), `redisHostname` (Chapter 9), `keyVaultUri` (Chapter 14), `contentSafetyEndpoint` (Chapter 16), `appInsightsConnectionString` / `logAnalyticsWorkspaceId` (Chapter 17), `mcpSearchFqdn` (Chapter 18).

### Stage-by-stage reference

Each row is what a chapter's parameters file newly turns on relative to the one before it — not the full cumulative resource list, which is in that chapter's own "Azure Resources for This Stage" section.

| Chapter | Tag | Params file | Newly activated | Falsifiable check |
|---|---|---|---|---|
| 4 | `chapter-04-complete` | `chapter-04.json` | Nothing new; worker image only | `POST /research` returns real `yfinance` data instead of the Chapter 3 placeholder text |
| 5 | `chapter-05-complete` | `chapter-05.json` | Nothing new; worker image only, now reads `infra/.tavily-api-key` | A submitted ticker's result includes real search-derived content, not just fundamentals |
| 6 | `chapter-06-complete` | `chapter-06.json` | Nothing new; worker image only | Worker logs show the bounded tool loop; no live model call exists yet at this tag |
| 7 | `chapter-07-complete` | `chapter-07.json` | Microsoft Foundry model deployment, Azure API Management | `curl $apimGatewayUrl` with the subscription key returns a model response; worker logs show model calls routed through APIM |
| 8 | `chapter-08-complete` | `chapter-08.json` | Nothing new; worker image only | A submitted ticker produces fundamentals, technical, and news content from three parallel specialists |
| 9 | `chapter-09-complete` | `chapter-09.json` | Azure Cache for Redis, pgvector on PostgreSQL, `embedding-jobs` Service Bus queue, embed-worker Container App, Foundry embedding deployment | `redisHostname` responds to `PING`; a completed report's embedding appears in the `Report` table after a short delay |
| 10 | `chapter-10-complete` | `chapter-10.json` | Nothing new; worker image only | A completed report includes a structured Decision and a Devil's Advocate dissent |
| 11 | `chapter-11-complete` | `chapter-11.json` | Nothing new; worker image only | Killing and restarting the worker mid-run resumes from the last completed graph super-step instead of repeating it |
| 12 | `chapter-12-complete` | `chapter-12.json` | Nothing new; worker image only | Injecting a transient failure (for example, blocking one dependency briefly) shows a retry in worker logs instead of an immediate failed job |
| 13 | `chapter-13-complete` | `chapter-13.json` | Entra ID enforcement on the API (`entraClientId`, `entraTenantId`, `allowedUsers`, `allowedOrigin`) | An unauthenticated request to the API is rejected; a signed-in browser session succeeds |
| 14 | `chapter-14-complete` | `chapter-14.json` | Azure Key Vault | The worker resolves the Tavily key from Key Vault via Managed Identity, with no `TAVILY_API_KEY` secret on the Container App |
| 15 | `chapter-15-complete` | `chapter-15.json` | Nothing new; worker image only (a trust-boundary review, not a code change) | Same checks as Chapter 14 |
| 16 | `chapter-16-complete` | `chapter-16.json` | Azure AI Content Safety | Submitting a ticker whose search results contain an injection pattern shows a scan-and-reject in worker logs |
| 17 | `chapter-17-complete` | `chapter-17.json` | Application Insights, Log Analytics workspace | A submitted ticker's `job_id` finds a matching trace in Application Insights within a few minutes |
| 18 | `chapter-18-complete` | `chapter-18.json` | Standalone MCP search Container App, worker queue-depth scaling | `mcpSearchFqdn` responds on its internal endpoint; queuing several tickers at once increases worker replica count, visible with `az containerapp revision list` |
| 19 | `chapter-19-complete` | `chapter-19.json` | Nothing new; API image only | History and per-ticker terminal states appear in the deployed frontend |
| 20 | `chapter-20-complete` | `chapter-20.json` | Nothing new; this is the cumulative final state | Every check above still passes together |

### Cost and Cleanup

Every stage from Chapter 4 on reuses the same resource group opened in Chapter 3, so there is nothing to clean up between chapters — only after you are finished testing:

```bash
./infra/teardown.sh
```

Azure API Management, Azure Cache for Redis, and Azure AI Content Safety are the more expensive additions in this range; do not leave them running unattended. Set a budget alert before working through Chapter 7 onward.
