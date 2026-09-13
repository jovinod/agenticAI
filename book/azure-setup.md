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

## Later Azure Stages

Later chapters add their Azure changes to this file as named stages. The conceptual chapters should link here instead of repeating resource-creation and deployment commands.

Each future stage should state:

- The chapter completion tag it deploys.
- New or changed Azure resources.
- Required secrets and identities.
- The immutable image tags.
- A falsifiable deployment check.
- The additional cost and cleanup effect.
