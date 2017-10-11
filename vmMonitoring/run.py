import os
import sys
import urllib2
import urllib
import json
import collections
import itertools
import xml.etree.ElementTree as et
#sys.path.append(os.path.abspath(os.path.join(os.path.dirname( __file__ ), '.')))



#Create Service Principal
#https://docs.microsoft.com/en-us/azure/azure-resource-manager/resource-group-create-service-principal-portal

#ASE
#https://docs.microsoft.com/en-us/azure/vpn-gateway/vpn-gateway-howto-point-to-site-resource-manager-portal

#### USER INPUT ######
#Application ID
client_id = 'e916a561-bf5f-45d4-b0a8-da65b729e043'
#Key
client_secret = '7V/3Vnwf8EhMjy/RSDVkpIAm0H1w3zAt1uScXKlQAiM='
#Directory ID
tenant_id = '66b66353-3b76-4e41-9dc3-fee328bd400e'
#Azure subscription ID
subscription_id = '0f3ba96c-a3c7-4eac-b599-ed9882801672'

#Comma seperated list of resource groups to be monitored.
ResourceGroupList = ['Monitored-rg']
FirewallList= ["54.219.173.169"]
#Comma seperated list of API keys. Make sure the fw list and api key list match
apikeyList = ["LUFRPT1CU0dMRHIrOWFET0JUNzNaTmRoYmkwdjBkWWM9alUvUjBFTTNEQm93Vmx0OVhFRlNkOXdJNmVwYWk5Zmw4bEs3NjgwMkh5QT0="]



apiVersion = '2016-04-30-preview'
access_token = ""
token_type = ""

NewIPTagList = collections.defaultdict(list)
CurrentIPTagList = collections.defaultdict(list)
#comma seperated IP Address list  of firewalls to push the tags to




def Send_Azure_REST(url):
    global access_token, token_type
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', '%s %s' %(token_type, access_token))
    f = urllib2.urlopen(req).read()
    w = json.loads(f)
    #f.close()
    return w


def Build_Tags(RG):
    global NewIPTagList
    url = "https://management.azure.com/subscriptions/"+subscription_id+"/resourceGroups/"+RG+"/providers/Microsoft.Network/networkInterfaces?api-version=2017-08-01"
    output = Send_Azure_REST(url)
    for key in output['value']:
        #Get ip address of the interface
        ipaddress = key['properties']['ipConfigurations'][0]['properties']['privateIPAddress']
        #VM name that the interface is attached to
        vmname = key['properties']['virtualMachine']['id'].split('/')[-1]
        #Subnet tht the interface reside sin 
        subnet = key['properties']['ipConfigurations'][0]['properties']['subnet']['id'].split('/')[-1]

        #Populate the list of tags
        NewIPTagList[ipaddress].append('azure-tag.vmname.'+str(vmname))
        NewIPTagList[ipaddress].append('azure-tag.subnet.'+str(subnet))

        rg_url = "https://management.azure.com/subscriptions/"+subscription_id+"/resourceGroups/"+RG+"/providers/Microsoft.Compute/virtualmachines/"+vmname+"?$expand=instanceView&api-version="+apiVersion
        rg_output = Send_Azure_REST(rg_url)
        print rg_output
        sys.exit(0)
        #Get the OS type
        NewIPTagList[ipaddress].append('azure-tag.GuestOS.'+str(rg_output['properties']['storageProfile']['osDisk']['osType']))
        #Get Running state of VM
        NewIPTagList[ipaddress].append('azure-tag.vmPowerState.'+str(rg_output['properties']['statuses']['code']))

        #User defined tags
        if rg_output.get('tags') is not None:
                for k, v in rg_output.get('tags').iteritems():
                    NewIPTagList[ipaddress].append('azure-tag.'+str(k)+"."+str(v))


def Get_Azure_Access_Token():
    global access_token, token_type
    data = "grant_type=client_credentials&resource=https://management.core.windows.net/&client_id=%s&client_secret=%s" % (client_id, client_secret)
    url = "https://login.microsoftonline.com/%s/oauth2/token?api-version=1.0" % (tenant_id)
    req = urllib2.Request(url, data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    f = urllib2.urlopen(req)
    for x in f:
        y = json.loads(x)
        if y['token_type'] == 'Bearer':
            access_token = y['access_token']
            token_type = y['token_type']
    f.close()

def Generate_XML(Register, Unregister):    

#CurrentIPTagList is the list of IP to Tag mapping in the Firewall.
#NewIPTagList is the list of IP to Tag mapping in the Azure environment.
#This function will find the delats between the new ip to tag mappings and register new IPs and tags 
#And unregister IPs from tags that have disappeared.
    for k1 in CurrentIPTagList.keys():
        if k1 in NewIPTagList.keys():
            ip = k1
            tags = list(set(CurrentIPTagList[k1]) - set(NewIPTagList[k1]))
        elif k1 not in NewIPTagList.keys():
            ip = k1
            tags = CurrentIPTagList[k1]
        if tags:            
            Unregister += '<entry ip="' + ip + '">'
            Unregister += "<tag>"
            for i in tags:
                Unregister += '<member>' + i + '</member>'
            Unregister += "</tag>"
            Unregister += "</entry>"

    for k1 in NewIPTagList.keys():
        if k1 in CurrentIPTagList.keys():
            ip = k1
            tags = list(set(NewIPTagList[k1]) - set(CurrentIPTagList[k1]))
        elif k1 not in CurrentIPTagList.keys():
            ip = k1
            tags = NewIPTagList[k1]
        if tags:
            Register += '<entry ip="' + ip + '">'
            Register += "<tag>"
            for i in tags:
                Register += '<member>' + i + '</member>'
            Register += "</tag>"
            Register += "</entry>"
    return Unregister, Register
    
#Get the list of IP to tag mappings that are in the firewall
def Firewall_Get_Tags(firewall_mgmt_ip, api_key):
    global CurrentIPTagList
    url = "https://%s/api/?type=op&cmd=<show><object><registered-ip><all/></registered-ip></object></show>&key=%s" %(firewall_mgmt_ip, api_key)
    try:
        response = urllib2.urlopen(url).read()
        #print response
    except urllib2.HTTPError, e:
        print "HTTPError = " + str(e)
    else:
        root = et.fromstring(response)
        if root.attrib['status'] == 'success':
            for entry in root.findall('./result/entry'):
                for tag in entry.findall('./tag/member'):
                    CurrentIPTagList[entry.attrib['ip']].append(tag.text)



#Update the firewall with the latest IP to tag map
def Firewall_Update_Tags(firewall_mgmt_ip, api_key, FWXMLUpdate):
    url = "https://%s/api/?type=user-id&action=set&key=%s&cmd=%s" % (firewall_mgmt_ip, api_key,urllib.quote(FWXMLUpdate))
    try:
        response = urllib2.urlopen(url).read()
        #print response
    except urllib2.HTTPError, e:
        print "HTTPError = " + str(e)
    else:
        print response


#Entry point
def main():
    FWXMLUpdate = []
    XMLHeader = "<uid-message><version>1.0</version><type>update</type><payload>"
    XMLFooter = "</payload></uid-message>"
    Unregister = "<unregister>"
    Register = "<register>"


#Authenticate and get access token so we can make API calls into Azure
    Get_Azure_Access_Token()

#Build the list of IP to tag
    for ResourceGroup in ResourceGroupList:
        Build_Tags(ResourceGroup)

#Get ip-to-tag mapping from the firewall
    for Firewall,api_key in itertools.izip(FirewallList, apikeyList):
        Firewall_Get_Tags(Firewall, api_key)

    Unregister, Register = Generate_XML(Register, Unregister)

#For debug
    #file_name = os.path.dirname(os.path.abspath(__file__)) + "\\xml_updates"
    #f = open(file_name, 'w')
    #f.write(FWXMLUpdate)
    #f.close()
#End debug

    Register += "</register>"
    Unregister += "</unregister>"
    FWXMLUpdate = XMLHeader + Unregister + Register + XMLFooter

    print FWXMLUpdate
    for Firewall,api_key in itertools.izip(FirewallList, apikeyList):
        Firewall_Update_Tags(Firewall, api_key, FWXMLUpdate)


if __name__ == "__main__":
     main()
