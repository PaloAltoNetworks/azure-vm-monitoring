import os
import json
import sys
sys.path.append(os.getcwd()+"\env\Lib\site-packages")
import azure

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource.resources import ResourceManagementClient


subscription_id = "0f3ba96c-a3c7-4eac-b599-ed9882801672"
credentials = ServicePrincipalCredentials(
    client_id = 'e916a561-bf5f-45d4-b0a8-da65b729e043',
    secret = '8LDuurgo/trTGui9oLxfNEX2RyJ4xtGsA3/M51BnWrU=',
    tenant = '66b66353-3b76-4e41-9dc3-fee328bd400e'
)

resource_client = ResourceManagementClient(credentials,subscription_id)

print ("hello world\n")
