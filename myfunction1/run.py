import os
import json
import sys
sys.path.append(os.getcwd()+"\env\Lib\site-packages")
sys.path.append("D:\home\SiteExtensions\python2712x64\Python27\Lib\site-packages")
import azure
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings()

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient


subscription_id =  "0f3ba96c-a3c7-4eac-b599-ed9882801672"
credentials = ServicePrincipalCredentials(
    client_id = 'e916a561-bf5f-45d4-b0a8-da65b729e043',
    secret = 'jfBWvXiaVzwTMt3FCBHYjje2QW3T+/T5E81qaU7GplE=',
    tenant = '66b66353-3b76-4e41-9dc3-fee328bd400e'
)

def print_item(group):
    """Print a ResourceGroup instance."""
    print("\tName: {}".format(group.name))
    print("\tId: {}".format(group.id))
    print("\tLocation: {}".format(group.location))
    print("\tTags: {}".format(group.tags))
    print_properties(group.properties)

def print_properties(props):
    """Print a ResourceGroup propertyies instance."""
    if props and props.provisioning_state:
        print("\tProperties:")
        print("\t\tProvisioning State: {}".format(props.provisioning_state))
    print("\n\n")
    
    

def run_example():
    print("Print Resource Group Names in this subscription")
    client = ResourceManagementClient(credentials, subscription_id)
    for item in client.resource_groups.list():
       print_item(item)
       
    



if __name__ == "__main__":
    run_example()    
    print ("hello world\n")




