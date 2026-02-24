// Azure Container App deployment for the LangGraph Foundry Agent.
// Deploys to Azure Container Apps with managed identity for Azure AI Foundry access.
//
// Deploy:
//   az deployment group create \
//     --resource-group <rg> \
//     --template-file deploy/azure-container-app.bicep \
//     --parameters containerImage=<acr>.azurecr.io/langgraph-foundry-agent:latest \
//                  foundryEndpoint=https://<project>.services.ai.azure.com \
//                  appInsightsConnectionString=<connection-string>

param location string = resourceGroup().location
param containerAppName string = 'langgraph-foundry-agent'
param containerImage string
param foundryEndpoint string
param foundryDeployment string = 'gpt-5.2'
param appInsightsConnectionString string = ''
param agent365AgentId string = 'langgraph-foundry-agent-001'

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${containerAppName}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'azure-monitor'
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
      }
    }
    template: {
      containers: [
        {
          name: containerAppName
          image: containerImage
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'AZURE_AI_FOUNDRY_PROJECT_ENDPOINT', value: foundryEndpoint }
            { name: 'AZURE_AI_FOUNDRY_DEPLOYMENT', value: foundryDeployment }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
            { name: 'AGENT365_AGENT_ID', value: agent365AgentId }
            { name: 'PORT', value: '8000' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '20'
              }
            }
          }
        ]
      }
    }
  }
}

// Grant the container app's managed identity access to Azure AI Foundry
// Role: Cognitive Services OpenAI User (5e0bd9bd-7b93-4f28-af87-19fc36ad61bd)
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerApp.id, 'CognitiveServicesOpenAIUser')
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    )
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output principalId string = containerApp.identity.principalId
