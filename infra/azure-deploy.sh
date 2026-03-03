#!/bin/bash
# Azure deployment script for hr-policy-rag
set -e

RESOURCE_GROUP="rg-hr-rag"
LOCATION="uksouth"
APP_NAME="hr-policy-rag"

echo "Deploying HR Policy RAG System to Azure..."

az group create --name $RESOURCE_GROUP --location $LOCATION

az acr create --resource-group $RESOURCE_GROUP --name "${APP_NAME}acr" --sku Basic
az acr build --registry "${APP_NAME}acr" --image hr-policy-rag:latest .

az containerapp env create --name "${APP_NAME}-env" --resource-group $RESOURCE_GROUP --location $LOCATION

az containerapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment "${APP_NAME}-env" \
  --image "${APP_NAME}acr.azurecr.io/hr-policy-rag:latest" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 5

echo "Deployment complete!"
