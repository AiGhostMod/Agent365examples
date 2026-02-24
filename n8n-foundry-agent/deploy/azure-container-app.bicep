// Azure Container App deployment for the n8n Foundry Agent.
// Deploys to Azure Container Apps with the n8n workflow engine and
// Agent365 wrapper server.
//
// Deploy:
//   az deployment group create \
//     --resource-group <rg> \
//     --template-file deploy/azure-container-app.bicep \
//     --parameters containerImage=<acr>.azurecr.io/n8n-foundry-agent:latest \
//                  azureOpenAiEndpoint=https://<project>.services.ai.azure.com \
//                  azureOpenAiKey=<key> \
//                  appInsightsConnectionString=<connection-string>

param location string = resourceGroup().location
param containerAppName string = 'n8n-foundry-agent'
param containerImage string
param azureOpenAiEndpoint string
param azureOpenAiKey string
@secure()
param n8nEncryptionKey string
param azureOpenAiDeployment string = 'gpt-5.2'
param appInsightsConnectionString string = ''
param agent365AgentId string = 'n8n-foundry-agent-001'

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
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8001  // Agent365 wrapper port (proxies to n8n internally)
        transport: 'http'
      }
      secrets: [
        { name: 'azure-openai-key', value: azureOpenAiKey }
        { name: 'n8n-encryption-key', value: n8nEncryptionKey }
      ]
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
            { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAiEndpoint }
            { name: 'AZURE_OPENAI_API_KEY', secretRef: 'azure-openai-key' }
            { name: 'AZURE_OPENAI_DEPLOYMENT', value: azureOpenAiDeployment }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
            { name: 'AGENT365_AGENT_ID', value: agent365AgentId }
            { name: 'N8N_ENCRYPTION_KEY', secretRef: 'n8n-encryption-key' }
            { name: 'N8N_PORT', value: '5678' }
            { name: 'WRAPPER_PORT', value: '8001' }
            { name: 'N8N_WEBHOOK_URL', value: 'http://localhost:5678/webhook/agent' }
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

output fqdn string = containerApp.properties.configuration.ingress.fqdn
