import os

from azure.identity.aio import DefaultAzureCredential
from azure.servicebus.aio import ServiceBusClient

SERVICEBUS_CONNECTION_STRING = os.environ.get("SERVICEBUS_CONNECTION_STRING")
SERVICEBUS_FQDN = os.environ.get("SERVICEBUS_FQDN")


def build_servicebus_client() -> ServiceBusClient:
    if SERVICEBUS_FQDN:
        credential = DefaultAzureCredential()
        return ServiceBusClient(
            fully_qualified_namespace=SERVICEBUS_FQDN,
            credential=credential,
        )
    return ServiceBusClient.from_connection_string(SERVICEBUS_CONNECTION_STRING)
