// Stock Research Assistant -- cumulative infrastructure template.
//
// One shared template for every chapter. Each chapter's parameter file
// (params/chapter-NN.json) turns on exactly the resources that chapter's
// cumulative state needs -- nothing is duplicated per chapter, and
// re-running an earlier chapter's parameters against a later chapter's
// resource group is a safe no-op for anything already deployed, since
// ARM deployments are idempotent by construction.
//
// Naming: every resource is prefixed with `namePrefix` so this template
// can be deployed into a fresh resource group per test run without
// colliding with anything else, including the project's own real,
// separately-deployed system.

@description('Prefix applied to every resource name in this deployment.')
param namePrefix string = 'stockresearch'

@description('Azure region for most resources.')
param location string = resourceGroup().location

@description('Azure region for Azure Static Web Apps (a separate, more limited region list).')
param staticWebAppLocation string = 'eastasia'

// Container Registry and Service Bus namespace names must be globally
// unique across all of Azure, not just this resource group -- this
// suffix, derived from the resource group's own ID, makes that likely
// without requiring a manually-chosen name.
var uniqueSuffix = uniqueString(resourceGroup().id)

@description('Chapter 1: host the frontend build.')
param deployStaticWebApp bool = true

resource staticWebApp 'Microsoft.Web/staticSites@2024-04-01' = if (deployStaticWebApp) {
  name: '${namePrefix}-swa'
  location: staticWebAppLocation
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    buildProperties: {
      skipGithubActionWorkflowGeneration: true
    }
  }
}

output staticWebAppHostname string = deployStaticWebApp ? staticWebApp!.properties.defaultHostname : ''
output staticWebAppName string = deployStaticWebApp ? staticWebApp!.name : ''

// ---------------------------------------------------------------------
// Chapter 3: durable job store (Postgres), message delivery (Service
// Bus), image storage (Container Registry), and compute (Container Apps)
// for the API and worker.
// ---------------------------------------------------------------------

@description('Chapter 3: durable job status and results.')
param deployPostgres bool = false

@description('Chapter 3: administrator login for the Postgres flexible server.')
param postgresAdminLogin string = 'pgadmin'

@secure()
@description('Chapter 3: administrator password for the Postgres flexible server. Required when deployPostgres is true.')
param postgresAdminPassword string = ''

@description('Chapter 3: deliver work between the API and worker.')
param deployServiceBus bool = false

@description('Chapter 3: store container images for the API and worker.')
param deployContainerRegistry bool = false

@description('Chapter 3: host the API and worker as container apps.')
param deployContainerApps bool = false

@description('API container image, e.g. <registry>.azurecr.io/api:<tag>. Required when deployContainerApps is true.')
param apiImage string = ''

@description('Worker container image. Required when deployContainerApps is true.')
param workerImage string = ''

@description('Value of the API\'s ALLOWED_ORIGIN setting. Required when deployContainerApps is true.')
param allowedOrigin string = 'http://localhost:5173'

@description('Chapter 13: Microsoft Entra ID app registration (client) ID used for token validation.')
param entraClientId string = ''

@description('Chapter 13: Microsoft Entra ID tenant ID used for token validation.')
param entraTenantId string = ''

@description('Chapter 13: comma-separated allow-listed user emails permitted to use the application.')
param allowedUsers string = ''

@description('Chapter 5: real web-search tool credential, passed to the worker for its MCP search subprocess.')
@secure()
param tavilyApiKey string = ''

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = if (deployPostgres) {
  name: '${namePrefix}-pg'
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    version: '16'
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

resource postgresDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = if (deployPostgres) {
  parent: postgres
  name: 'alpha'
}

// Teaching-scoped: allows any Azure resource (including the Container
// Apps below) to reach this server. A real deployment would scope this
// to the Container Apps environment's outbound addresses instead.
resource postgresFirewallAllowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = if (deployPostgres) {
  parent: postgres
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2024-01-01' = if (deployServiceBus) {
  name: '${namePrefix}-bus-${uniqueSuffix}'
  location: location
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
}

resource serviceBusQueue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = if (deployServiceBus) {
  parent: serviceBusNamespace
  name: 'research-jobs'
}

resource serviceBusSendListenRule 'Microsoft.ServiceBus/namespaces/AuthorizationRules@2024-01-01' = if (deployServiceBus) {
  parent: serviceBusNamespace
  name: 'SendListen'
  properties: {
    rights: [
      'Send'
      'Listen'
    ]
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = if (deployContainerRegistry) {
  name: '${namePrefix}acr${uniqueSuffix}'
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (deployContainerApps) {
  name: '${namePrefix}-logs'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = if (deployContainerApps) {
  name: '${namePrefix}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics!.properties.customerId
        sharedKey: logAnalytics!.listKeys().primarySharedKey
      }
    }
  }
}

resource apiApp 'Microsoft.App/containerApps@2024-03-01' = if (deployContainerApps) {
  name: '${namePrefix}-api'
  location: location
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
      }
      registries: [
        {
          server: '${containerRegistry!.name}.azurecr.io'
          username: containerRegistry!.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: containerRegistry!.listCredentials().passwords[0].value
        }
        {
          name: 'database-url'
          value: 'postgresql+psycopg://${postgresAdminLogin}:${postgresAdminPassword}@${postgres!.properties.fullyQualifiedDomainName}:5432/alpha'
        }
        {
          name: 'servicebus-connection-string'
          value: serviceBusSendListenRule!.listKeys().primaryConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'SERVICEBUS_CONNECTION_STRING', secretRef: 'servicebus-connection-string' }
            { name: 'ALLOWED_ORIGIN', value: allowedOrigin }
            { name: 'ENTRA_CLIENT_ID', value: entraClientId }
            { name: 'ENTRA_TENANT_ID', value: entraTenantId }
            { name: 'ALLOWED_USERS', value: allowedUsers }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

resource workerApp 'Microsoft.App/containerApps@2024-03-01' = if (deployContainerApps) {
  name: '${namePrefix}-worker'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      registries: [
        {
          server: '${containerRegistry!.name}.azurecr.io'
          username: containerRegistry!.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: containerRegistry!.listCredentials().passwords[0].value
        }
        {
          name: 'database-url'
          value: 'postgresql+psycopg://${postgresAdminLogin}:${postgresAdminPassword}@${postgres!.properties.fullyQualifiedDomainName}:5432/alpha'
        }
        {
          name: 'servicebus-connection-string'
          value: serviceBusSendListenRule!.listKeys().primaryConnectionString
        }
        {
          name: 'tavily-api-key'
          value: tavilyApiKey
        }
        {
          name: 'apim-subscription-key'
          value: deployApim ? apimSubscription!.listSecrets().primaryKey : ''
        }
        {
          name: 'redis-url'
          value: deployRedis ? 'rediss://:${redisDatabase!.listKeys().primaryKey}@${redisEnterprise!.properties.hostName}:10000' : ''
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: workerImage
          env: concat(
            [
              { name: 'DATABASE_URL', secretRef: 'database-url' }
              { name: 'DATABASE_HOST', value: deployPostgres ? postgres!.properties.fullyQualifiedDomainName : '' }
              { name: 'DATABASE_NAME', value: 'alpha' }
              { name: 'DATABASE_USER', value: 'stockresearch-worker' }
              { name: 'SERVICEBUS_CONNECTION_STRING', secretRef: 'servicebus-connection-string' }
              { name: 'SERVICEBUS_FQDN', value: deployServiceBus ? '${serviceBusNamespace!.name}.servicebus.windows.net' : '' }
              { name: 'TAVILY_API_KEY', secretRef: 'tavily-api-key' }
              { name: 'SERVICEBUS_EMBEDDING_QUEUE_NAME', value: 'embedding-jobs' }
            ],
            deployApim
              ? [
                  { name: 'APIM_BASE_URL', value: apim!.properties.gatewayUrl }
                  { name: 'APIM_SUBSCRIPTION_KEY', secretRef: 'apim-subscription-key' }
                ]
              : [],
            deployRedis ? [{ name: 'REDIS_URL', secretRef: 'redis-url' }] : [],
            deployKeyVault ? [{ name: 'KEY_VAULT_URI', value: keyVault!.properties.vaultUri }] : [],
            deployContentSafety ? [{ name: 'CONTENT_SAFETY_ENDPOINT', value: contentSafety!.properties.endpoint }] : []
          )
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output postgresHostname string = deployPostgres ? postgres!.properties.fullyQualifiedDomainName : ''
output containerRegistryLoginServer string = deployContainerRegistry ? containerRegistry!.properties.loginServer : ''
output apiFqdn string = deployContainerApps ? apiApp!.properties.configuration.ingress.fqdn : ''

// ---------------------------------------------------------------------
// Chapter 7: a hosted model deployment (Azure OpenAI / Microsoft
// Foundry) behind Azure API Management, which authenticates to the
// model with its own managed identity rather than an embedded key.
// ---------------------------------------------------------------------

@description('Chapter 7: hosted chat model deployment.')
param deployFoundryModel bool = false

@description('Chapter 9: hosted embedding model deployment. Uses the same OpenAI account as deployFoundryModel.')
param deployFoundryEmbedding bool = false

@description('Chapter 7: API Management gateway in front of the model deployment.')
param deployApim bool = false

@description('Publisher email required by API Management. Required when deployApim is true.')
param apimPublisherEmail string = ''

@description('Azure region for the OpenAI account -- GlobalStandard model availability varies by region independently of where other resources live.')
param foundryLocation string = 'southindia'

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = if (deployFoundryModel) {
  name: '${namePrefix}-openai'
  location: foundryLocation
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: '${namePrefix}-openai-${uniqueSuffix}'
    publicNetworkAccess: 'Enabled'
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (deployFoundryModel) {
  parent: openAiAccount
  name: 'chat'
  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: '2025-08-07'
    }
  }
}

resource embedDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (deployFoundryEmbedding) {
  parent: openAiAccount
  name: 'embed'
  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
  }
  dependsOn: [
    chatDeployment
  ]
}

resource apim 'Microsoft.ApiManagement/service@2023-05-01-preview' = if (deployApim) {
  name: '${namePrefix}-apim-${uniqueSuffix}'
  location: location
  sku: {
    name: 'Consumption'
    capacity: 0
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: apimPublisherEmail
    publisherName: 'Stock Research Book'
  }
}

// Lets APIM's own managed identity call the model deployment -- the
// worker holds an APIM subscription key, never an OpenAI account key.
resource openAiRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployApim && deployFoundryModel) {
  name: guid(openAiAccount.id, apim.id, 'CognitiveServicesOpenAIUser')
  scope: openAiAccount
  properties: {
    principalId: apim!.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    )
  }
}

resource openAiApi 'Microsoft.ApiManagement/service/apis@2023-05-01-preview' = if (deployApim) {
  parent: apim
  name: 'openai'
  properties: {
    displayName: 'OpenAI'
    path: 'openai'
    protocols: ['https']
    serviceUrl: deployFoundryModel ? '${openAiAccount!.properties.endpoint}openai' : ''
    subscriptionRequired: true
  }
}

resource openAiApiPassthrough 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = if (deployApim) {
  parent: openAiApi
  name: 'passthrough'
  properties: {
    displayName: 'Passthrough'
    method: 'POST'
    urlTemplate: '/*'
  }
}

resource openAiApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-05-01-preview' = if (deployApim) {
  parent: openAiApi
  name: 'policy'
  properties: {
    format: 'xml'
    value: '''
      <policies>
        <inbound>
          <base />
          <authentication-managed-identity resource="https://cognitiveservices.azure.com" output-token-variable-name="msi-access-token" ignore-error="false" />
          <set-header name="Authorization" exists-action="override">
            <value>@("Bearer " + (string)context.Variables["msi-access-token"])</value>
          </set-header>
          <set-header name="api-key" exists-action="delete" />
        </inbound>
        <backend>
          <base />
        </backend>
        <outbound>
          <base />
        </outbound>
        <on-error>
          <base />
        </on-error>
      </policies>
    '''
  }
  dependsOn: [
    openAiApiPassthrough
  ]
}

resource apimProduct 'Microsoft.ApiManagement/service/products@2023-05-01-preview' = if (deployApim) {
  parent: apim
  name: 'openai-product'
  properties: {
    displayName: 'OpenAI'
    subscriptionRequired: true
    state: 'published'
  }
}

resource apimProductApi 'Microsoft.ApiManagement/service/products/apis@2023-05-01-preview' = if (deployApim) {
  parent: apimProduct
  name: 'openai'
  dependsOn: [
    openAiApi
  ]
}

resource apimSubscription 'Microsoft.ApiManagement/service/subscriptions@2023-05-01-preview' = if (deployApim) {
  parent: apim
  name: 'worker-subscription'
  properties: {
    scope: apimProduct!.id
    displayName: 'Worker subscription'
    state: 'active'
  }
}

output apimGatewayUrl string = deployApim ? apim!.properties.gatewayUrl : ''
#disable-next-line outputs-should-not-contain-secrets
output apimSubscriptionKey string = deployApim ? apimSubscription!.listSecrets().primaryKey : ''

// ---------------------------------------------------------------------
// Chapter 9: in-flight progress (Redis), the pgvector extension on the
// existing Postgres server, an embedding delivery queue, and the
// embed worker that consumes it.
// ---------------------------------------------------------------------

@description('Chapter 9: in-flight progress and the completed-result cache.')
param deployRedis bool = false

@description('Chapter 9: allow the vector extension on the existing Postgres server, for semantic report search.')
param deployPgVector bool = false

@description('Chapter 9: deliver completed reports to the embed worker.')
param deployEmbeddingQueue bool = false

@description('Chapter 9: host the embed worker as a container app.')
param deployEmbedWorker bool = false

@description('Embed worker container image. Required when deployEmbedWorker is true.')
param embedWorkerImage string = ''

// Classic Azure Cache for Redis is being retired -- Azure Managed
// Redis (redisEnterprise) is the replacement, at its smallest SKU.
resource redisEnterprise 'Microsoft.Cache/redisEnterprise@2025-07-01' = if (deployRedis) {
  name: '${namePrefix}-redis'
  location: location
  sku: {
    name: 'Balanced_B0'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
  }
}

resource redisDatabase 'Microsoft.Cache/redisEnterprise/databases@2025-07-01' = if (deployRedis) {
  parent: redisEnterprise
  name: 'default'
  properties: {
    clusteringPolicy: 'OSSCluster'
    evictionPolicy: 'NoEviction'
    port: 10000
    accessKeysAuthentication: 'Enabled'
  }
}

// Enables `CREATE EXTENSION vector` on the database -- Postgres flexible
// server requires the extension to be explicitly allow-listed first.
resource pgVectorExtension 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = if (deployPgVector) {
  parent: postgres
  name: 'azure.extensions'
  properties: {
    value: 'VECTOR'
    source: 'user-override'
  }
}

resource embeddingQueue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = if (deployEmbeddingQueue) {
  parent: serviceBusNamespace
  name: 'embedding-jobs'
}

resource embedWorkerApp 'Microsoft.App/containerApps@2024-03-01' = if (deployEmbedWorker) {
  name: '${namePrefix}-embed-worker'
  location: location
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      registries: [
        {
          server: '${containerRegistry!.name}.azurecr.io'
          username: containerRegistry!.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: containerRegistry!.listCredentials().passwords[0].value
        }
        {
          name: 'database-url'
          value: 'postgresql+psycopg://${postgresAdminLogin}:${postgresAdminPassword}@${postgres!.properties.fullyQualifiedDomainName}:5432/alpha'
        }
        {
          name: 'servicebus-connection-string'
          value: serviceBusSendListenRule!.listKeys().primaryConnectionString
        }
        {
          name: 'apim-subscription-key'
          value: deployApim ? apimSubscription!.listSecrets().primaryKey : ''
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'embed-worker'
          image: embedWorkerImage
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'SERVICEBUS_CONNECTION_STRING', secretRef: 'servicebus-connection-string' }
            { name: 'SERVICEBUS_EMBEDDING_QUEUE_NAME', value: 'embedding-jobs' }
            { name: 'APIM_BASE_URL', value: deployApim ? apim!.properties.gatewayUrl : '' }
            { name: 'APIM_SUBSCRIPTION_KEY', secretRef: 'apim-subscription-key' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output redisHostname string = deployRedis ? redisEnterprise!.properties.hostName : ''
#disable-next-line outputs-should-not-contain-secrets
output redisAccessKey string = deployRedis ? redisDatabase!.listKeys().primaryKey : ''

// ---------------------------------------------------------------------
// Chapter 14: workload identity and secrets. The worker's own RBAC
// (Key Vault, Service Bus queue roles) and its Postgres Entra role are
// assigned imperatively, not here -- these are not reproducible from
// repository infrastructure as code, the same real limitation the
// original chapter documents. The vault resource and the worker's
// managed identity itself are declared here.
// ---------------------------------------------------------------------

@description('Chapter 14: store the third-party Tavily API key for the search boundary, owned by Key Vault instead of a plain container secret.')
param deployKeyVault bool = false

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = if (deployKeyVault) {
  name: 'kv-${uniqueSuffix}'
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
  }
}

resource tavilySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (deployKeyVault) {
  parent: keyVault
  name: 'tavily-api-key'
  properties: {
    value: tavilyApiKey
  }
}

output keyVaultUri string = deployKeyVault ? keyVault!.properties.vaultUri : ''
output keyVaultName string = deployKeyVault ? keyVault!.name : ''

// ---------------------------------------------------------------------
// Chapter 16: guardrails at the content boundary. Prompt Shields for
// Documents classifies open-web text before it reaches model context.
// ---------------------------------------------------------------------

@description('Chapter 16: classify retrieved documents for indirect prompt injection.')
param deployContentSafety bool = false

@description('Azure region for Content Safety -- not available in every region (rejected in centralindia).')
param contentSafetyLocation string = 'southindia'

resource contentSafety 'Microsoft.CognitiveServices/accounts@2024-10-01' = if (deployContentSafety) {
  name: '${namePrefix}-contentsafety-${uniqueSuffix}'
  location: contentSafetyLocation
  kind: 'ContentSafety'
  sku: {
    name: 'S0'
  }
  properties: {
    // Bearer-token authentication requires a custom subdomain --
    // without one, role assignments alone still fail with a generic
    // permission error that looks identical to a propagation delay.
    customSubDomainName: '${namePrefix}-contentsafety-${uniqueSuffix}'
    publicNetworkAccess: 'Enabled'
  }
}

output contentSafetyEndpoint string = deployContentSafety ? contentSafety!.properties.endpoint : ''
