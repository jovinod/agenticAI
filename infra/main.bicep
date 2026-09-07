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
      ]
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: workerImage
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'SERVICEBUS_CONNECTION_STRING', secretRef: 'servicebus-connection-string' }
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

output postgresHostname string = deployPostgres ? postgres!.properties.fullyQualifiedDomainName : ''
output containerRegistryLoginServer string = deployContainerRegistry ? containerRegistry!.properties.loginServer : ''
output apiFqdn string = deployContainerApps ? apiApp!.properties.configuration.ingress.fqdn : ''
