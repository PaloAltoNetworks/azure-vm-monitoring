import os
import sys
import urllib2
import urllib
import json
import collections
import itertools
import xml.etree.ElementTree as et




##### TO DO ####
# LOOK INTO AZURE KEY VAULT 
# USE IN PYTHON?


#### BEGIN USER INPUT ######
#Application ID
client_id = 'ENTER THE APPLICATION ID IN BETWEEN THE SINGLE QUOTES'
#Key
client_secret = 'ENTER THE SECRET KEY IN BETWEEN THE SINGLE QUOTES'
#Directory ID
tenant_id = 'ENTER THE DIRECTORY ID IN BETWEEN THE SINGLE QUOTES'
#Azure subscription ID
subscription_id = 'ENTER YOUR SUBCRIPTION ID IN BETWEEN THE SINGLE QUOTES'

#Comma separated list of resource groups to be monitored.
#For example ResourceGroupList = ['rg1', 'rg2']
ResourceGroupList = ['Enter a comma separated list of resource groups to be monitored']

#Comma separated list of Firewall IPs or FQDNs of the management interface
#For example FirewallLsit = ['1.1.1.1', '2.2.2.2']
FirewallList= ['Comma separated list of firewall IPs or FQDNs']


#Comma separated list of API keys. Make sure the fw list and api key list match
#For example apikeyList = ['api key for fw with ip 1.1.1.1', 'api key for fw with ip 2.2.2.2']
apikeyList = ['Comma separated list of API keys for firewalls in FirewallList']
##### END USER INPUT ########



apiVersion = '2016-04-30-preview'
access_token = ""
token_type = ""


NewIPTagList = collections.defaultdict(list)
CurrentIPTagList = collections.defaultdict(list)





def Send_Azure_REST(url):
    global access_token, token_type
    req = urllib2.Request(url)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', '%s %s' %(token_type, access_token))
    try:
        f = urllib2.urlopen(req).read()
    except urllib2.HTTPError as err:
        if err.code == 404:
            print ("Resource Group not found...maybe? Got a 404 error. going to exit for now")
            sys.exit(0)
    else:
        w = json.loads(f)
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
         #Get the OS type
        NewIPTagList[ipaddress].append('azure-tag.GuestOS.'+str(rg_output['properties']['storageProfile']['osDisk']['osType']))
        #Get Running state of VM
        for status in rg_output['properties']['instanceView']['statuses']:
            if 'PowerState' in status['code']:
                if status['code'].split('/')[-1] == 'deallocated':
                    NewIPTagList[ipaddress].append('azure-tag.vmPowerState.Stopped')
                else: 
                    NewIPTagList[ipaddress].append('azure-tag.vmPowerState.'+str(status['code'].split('/')[-1]))
       

        #User defined tags
        if rg_output.get('tags') is not None:
                for k, v in rg_output.get('tags').iteritems():
                    NewIPTagList[ipaddress].append('azure-tag.'+str(k)+"."+str(v))


def Get_Azure_Access_Token():
    global access_token, token_type
    #data = "grant_type=client_credentials&resource=https://management.core.windows.net/&client_id=%s&client_secret=%s" % (client_id, client_secret)
    data_to_encode = { 'grant_type' : 'client_credentials', 'resource' : 'https://management.core.windows.net/', 'client_id' : client_id, 'client_secret' : client_secret }
    data = urllib.urlencode(data_to_encode)
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
    #else:
    #    print response


#Entry point
def main():
    FWXMLUpdate = []
    XMLHeader = "<uid-message><version>1.0</version><type>update</type><payload>"
    XMLFooter = "</payload></uid-message>"
    Unregister = "<unregister>"
    Register = "<register>"


#check to see if firewall is reachable. If not, gracefully exit
    for Firewall in FirewallList:
        url = "https://%s" %(Firewall)
        try:
            f = urllib2.urlopen(url, timeout=5)
        except urllib2.URLError as err:
            print err
            print ("FW not found...Exiting for now")
            sys.exit(0)
            

            

#Authenticate and get access token so we can make API calls into Azure
    Get_Azure_Access_Token()

#Build the list of IP to tag
    for ResourceGroup in ResourceGroupList:
        Build_Tags(ResourceGroup)

#Get ip-to-tag mapping from the firewall
    for Firewall,api_key in itertools.izip(FirewallList, apikeyList):
        Firewall_Get_Tags(Firewall, api_key)

    Unregister, Register = Generate_XML(Register, Unregister)

    Register += "</register>"
    Unregister += "</unregister>"
    FWXMLUpdate = XMLHeader + Unregister + Register + XMLFooter

    #print FWXMLUpdate
    for Firewall,api_key in itertools.izip(FirewallList, apikeyList):
        Firewall_Update_Tags(Firewall, api_key, FWXMLUpdate)


if __name__ == "__main__":
     main()
