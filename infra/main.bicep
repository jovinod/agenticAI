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

output staticWebAppHostname string = deployStaticWebApp ? staticWebApp.properties.defaultHostname : ''
output staticWebAppName string = deployStaticWebApp ? staticWebApp.name : ''
