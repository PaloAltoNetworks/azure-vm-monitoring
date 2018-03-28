import os
import sys
import urllib2
import urllib
import json
import collections
import itertools
import xml.etree.ElementTree as et
from datetime import datetime
import hmac
import ssl
import time
import logging
import subprocess
import getopt
import gzip
import shutil
import logging.handlers

PARAMETERS_FILE='parameters.json'
VERSION="Beta"

list_types = [ 'targetIps', 'targetApiKeys', 'targetVsys' ]
required_params = [ 
    "clientId",
    "clientSecret",
    "tenantId",
    "subscriptionId",
    "targetIps",
    "targetApiKeys",
    "targetVsys"
    ]

param_dict = {}
nsg_dict = {}

apiVersion = '2017-12-01'
access_token = ""
token_type = ""


NewIPTagList = collections.defaultdict(list)
CurrentIPTagList = collections.defaultdict(list)

# Limit URL POST data to 9MB
MAX_URL_CHARACTERS = 9000000

LOCKFILE = '/tmp/.vm_monitor.lck'
DEFAULT_LOG_DIR = '/tmp'
DEBUG_LOG = 'debug.log'
AUDIT_LOG = 'audit.log'
mylogger = None

class panFormatter(logging.Formatter):
    converter=datetime.fromtimestamp
    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        if datefmt:
            s = ct.strftime(datefmt)
        else:
            t = ct.strftime("%Y-%m-%d %H:%M:%S")
            z = time.strftime("%z")
            s = "%s.%03d %s" % (t, record.msecs, z)
        return s

class CompressedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """
        if self.stream:
            self.stream.close()
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = "%s.%d.gz" % (self.baseFilename, i)
                dfn = "%s.%d.gz" % (self.baseFilename, i + 1)
                if os.path.exists(sfn):
                    # print "%s -> %s" % (sfn, dfn)
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.baseFilename + ".1.gz"
            if os.path.exists(dfn):
                os.remove(dfn)
            # These two lines below are the only new lines. I commented out the os.rename(self.baseFilename, dfn) and
            #  replaced it with these two lines.
            with open(self.baseFilename, 'rb') as f_in, gzip.open(dfn, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            # os.rename(self.baseFilename, dfn)
            # print "%s -> %s" % (self.baseFilename, dfn)
        self.mode = 'w'
        self.stream = self._open()

def setup_log(logDir=DEFAULT_LOG_DIR):
    fmt="%(asctime)s %(name)s %(levelname)s: %(message)s"
    formatter = panFormatter(fmt)
    logger = logging.getLogger('VM Monitoring log') 
    logger.setLevel(logging.INFO)
    afh = CompressedRotatingFileHandler(logDir + '/' + AUDIT_LOG, mode='a', maxBytes=1073741824, backupCount=30)
    afh.setLevel(logging.INFO)
    afh.setFormatter(formatter)
    dfh = CompressedRotatingFileHandler(logDir + '/' + DEBUG_LOG, mode='a', maxBytes=1073741824, backupCount=30)
    dfh.setLevel(logging.ERROR)
    dfh.setFormatter(formatter)
    logger.addHandler(afh)
    logger.addHandler(dfh)
    return logger

def logit_info(logger, message):
    if not message:
        return

    if (logger is not None):
        msg = ': ' + message
        logger.info(msg)
    else:
        print message

def logit_error(logger, message):
    if not message:
        return

    if (logger is not None):
        msg = ': ' + message
        logger.error(msg)
    else:
        print message

def Send_Azure_REST(url):
    global access_token, token_type
    result = None
    while True:
        # Keep looping and making REST calls if Azure returns a nextLink entry:
        req = urllib2.Request(url)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', '%s %s' %(token_type, access_token))
        logit_info(mylogger, "Azure REST: %s" % url)
        try:
            f = urllib2.urlopen(req).read()
        except urllib2.HTTPError as err:
            logit_error(mylogger, "HTTPError: " + str(err))
            raise
        except urllib2.URLError as err:
            logit_error(mylogger, "URLError: " + str(err))
            raise
        except httplib.HTTPException as err:
            logit_error(mylogger, "HTTPException: " + str(err))
            raise
        except Exception as err:
            logit_error(mylogger, "Exception: " + str(err))
            raise

        logit_info(mylogger, "Azure REST response: %s" % f)
        w = json_loads_byteified(f)
        if not result:
            result = w
        else:
            result['value'] = result['value'] + w['value']
        if 'nextLink' not in w:
            break
        else:
            logit_info(mylogger, "Azure REST response includes nextLink value; need to retrieve additional results.")
            url = w['nextLink']
    logit_info(mylogger, "Azure REST final result: %s" % result)
    return result

def GetResourceGroups(subscription_id):
    global param_dict
    param_dict['resourceGroups'] = []
    url = "https://management.azure.com/subscriptions/"+param_dict['subscriptionId']+"/resourcegroups?api-version=2017-05-10"
    try:
        output = Send_Azure_REST(url)
    except:
        #print "Unable to retrieve resource group list from subscription"
        release_lock(LOCKFILE)
        sys.exit(1)
    #print output
    for dict in output['value']:
        for key,val in dict.iteritems():
            if key == 'name':
                param_dict['resourceGroups'].append(val)

def generate_nsg_dict():
    global nsg_dict
    if 'resourceGroupName' in param_dict and param_dict['resourceGroupName']:
        # Only retrieve Virtual Networks in specified Resource Group
        vnet_url = 'https://management.azure.com/subscriptions/%s/resourceGroups/%s/providers/Microsoft.Network/virtualNetworks?api-version=2017-10-01' % (param_dict['subscriptionId'], param_dict['resourceGroupName'])
    else:
        # Retrieve all Virtual Networks in subscription
        vnet_url = 'https://management.azure.com/subscriptions/%s/providers/Microsoft.Network/virtualNetworks?api-version=2017-10-01' % param_dict['subscriptionId']
    try:
        vnet_list = Send_Azure_REST(vnet_url)
    except:
        return 1
    for key in vnet_list['value']:
        try:
            vnet_rg = key['id'].split('/')[-5]
            vnet_name = key['name']
            for subnet in key['properties']['subnets']:
                if 'networkSecurityGroup' in subnet['properties']:
                    subnet_name = subnet['name']
                    nsg_name = subnet['properties']['networkSecurityGroup']['id'].split('/')[-1]
                    #print '%s %s %s %s' % (vnet_rg, vnet_name, subnet_name, nsg_name)
                    if vnet_rg not in nsg_dict:
                        nsg_dict[vnet_rg] = {}
                    if vnet_name not in nsg_dict[vnet_rg]:
                        nsg_dict[vnet_rg][vnet_name] = {}
                    if subnet_name not in nsg_dict[vnet_rg][vnet_name]:
                        nsg_dict[vnet_rg][vnet_name][subnet_name] = {}
                    nsg_dict[vnet_rg][vnet_name][subnet_name] = nsg_name
        except:
            pass
    return 0

def Build_Tags():
    global NewIPTagList
    global nsg_dict
    nic_url = "https://management.azure.com/subscriptions/"+param_dict['subscriptionId']+"/providers/Microsoft.Network/networkInterfaces?api-version=2017-10-01"
    try:
        nic_list = Send_Azure_REST(nic_url)
    except:
        logit_error(mylogger, "Unable to retrieve list of network interfaces from subscription")
        release_lock(LOCKFILE)
        sys.exit(1)
    # If resourceGroup specified, filter NIC list
    filtered_list = []
    if 'resourceGroupName' in param_dict and param_dict['resourceGroupName']:
        for key in nic_list['value']:
            try:
                if key['properties']['virtualMachine']['id'].split('/')[-5] != param_dict['resourceGroupName']:
                    logit_info(mylogger,'NIC %s not in RG %s - skipping' % (key['name'], param_dict['resourceGroupName']))
                    #nic_list['value'].remove(key)
                    pass
                else:
                    logit_info(mylogger, 'NIC %s in RG %s - keeping' % (key['name'], param_dict['resourceGroupName']))
                    filtered_list.append(key)
            except:
                logit_info(mylogger, "NIC %s not connected to any VM" % key['name'])
                #print 'NIC %s not connected to VM - removing' % key['name']
                #nic_list['value'].remove(key)
                pass
        nic_list['value'] = filtered_list[:]
    # If vnetName specified, filter NIC list
    if 'vnetName' in param_dict and param_dict['vnetName']:
        del filtered_list[:]
        for key in nic_list['value']:
            try:
                if key['properties']['ipConfigurations'][0]['properties']['subnet']['id'].split('/')[-3] != param_dict['vnetName']:
                    logit_info(mylogger, 'NIC %s not connected to vnet %s - skipping' % (key['name'], param_dict['vnetName']))
                    #nic_list['value'].remove(key)
                    pass
                else:
                    logit_info(mylogger, 'NIC %s in VNET %s - keeping' % (key['name'], param_dict['vnetName']))
                    filtered_list.append(key)
            except:
                logit_info(mylogger, "NIC %s has no VNET" % key['name'])
                #print 'NIC %s has no VNET - removing' % key['name']
                #nic_list['value'].remove(key)
                pass
        nic_list['value'] = filtered_list[:]
    logit_info(mylogger, "Filtered NIC list: %s" % nic_list)
    vm_url = "https://management.azure.com/subscriptions/"+param_dict['subscriptionId']+"/providers/Microsoft.Compute/virtualmachines?api-version="+apiVersion
    try:
        vm_list = Send_Azure_REST(vm_url)
    except:
        logit_error(mylogger, "Unable to retrieve list of virtual machines from subscription")
        release_lock(LOCKFILE)
        sys.exit(1)
    #print "Virtual Machines output: %s" % output
    for key in nic_list['value']:
        #Get ip address of the interface
        ipaddress = key['properties']['ipConfigurations'][0]['properties']['privateIPAddress']
        if ipaddress in NewIPTagList:
            logit_error(mylogger, "WARNING: IP Address %s exists in tag database" % ipaddress)
        #VM name that the interface is attached to
        try:
            vmname = key['properties']['virtualMachine']['id'].split('/')[-1]
            vm_rg = key['properties']['virtualMachine']['id'].split('/')[-5]
        except:
            logit_error(mylogger, "NIC %s not attached to any VM; skipping." % key['name'])
            continue
        #Subnet that the interface resides in 
        subnet = key['properties']['ipConfigurations'][0]['properties']['subnet']['id'].split('/')[-1]
        #VNET of the interface subnet
        vnet = key['properties']['ipConfigurations'][0]['properties']['subnet']['id'].split('/')[-3]
        #Azure Region
        region = key['location']

        #Populate the list of tags
        NewIPTagList[ipaddress].append('azure-tag.vm-name.'+str(vmname))
        NewIPTagList[ipaddress].append('azure-tag.resource-group.'+str(vm_rg))
        NewIPTagList[ipaddress].append('azure-tag.subnet.'+str(subnet))
        NewIPTagList[ipaddress].append('azure-tag.vnet.'+str(vnet))
        NewIPTagList[ipaddress].append('azure-tag.region.'+str(region))

        # Set tag for Network Security Group, if applicable
        nsg_name = None
        try:
            nsg_name = nsg_dict[vm_rg][vnet][subnet]
        except:
            pass

        if nsg_name:
            NewIPTagList[ipaddress].append('azure-tag.nsg-name.'+str(nsg_name))

        vm = None
        for x in vm_list['value']:
            if x['name'] == vmname:
                vm = x
                break;
        if not vm:
            logit_error(mylogger, "VM %s not found for network interface %s" % (vmname, key['name']))
            continue

        #Get the OS type
        try:
            NewIPTagList[ipaddress].append('azure-tag.vm-size.'+str(vm['properties']['hardwareProfile']['vmSize']))
        except:
            pass
        try:
            NewIPTagList[ipaddress].append('azure-tag.os-type.'+str(vm['properties']['storageProfile']['osDisk']['osType']))
        except:
            pass
        try:
            NewIPTagList[ipaddress].append('azure-tag.os-publisher.'+str(vm['properties']['storageProfile']['imageReference']['publisher']))
        except:
            pass
        try:
            NewIPTagList[ipaddress].append('azure-tag.os-offer.'+str(vm['properties']['storageProfile']['imageReference']['offer']))
        except:
            pass
        try:
            NewIPTagList[ipaddress].append('azure-tag.os-sku.'+str(vm['properties']['storageProfile']['imageReference']['sku']))
        except:
            pass
        #Get Running state of VM
        try:
            for status in vm['properties']['instanceView']['statuses']:
                if 'PowerState' in status['code']:
                    if status['code'].split('/')[-1] == 'deallocated':
                        NewIPTagList[ipaddress].append('azure-tag.vm-power-state.Stopped')
                    else: 
                        NewIPTagList[ipaddress].append('azure-tag.vm-power-state.'+str(status['code'].split('/')[-1]))
        except:
            logit_error(mylogger, "Unable to retrieve PowerState for VM %s" % vmname)

        #User defined tags
        if vm.get('tags') is not None:
                for k, v in vm.get('tags').iteritems():
                    NewIPTagList[ipaddress].append('azure-tag.tag.'+str(k)+"."+str(v))


def Get_Azure_Access_Token():
    global access_token, token_type
    #data = "grant_type=client_credentials&resource=https://management.core.windows.net/&client_id=%s&client_secret=%s" % (param_dict['clientId'], param_dict['clientSecret'])
    data_to_encode = { 'grant_type' : 'client_credentials', 'resource' : 'https://management.core.windows.net/', 'client_id' : param_dict['clientId'], 'client_secret' : param_dict['clientSecret'] }
    data = urllib.urlencode(data_to_encode)
    url = "https://login.microsoftonline.com/%s/oauth2/token?api-version=1.0" % (param_dict['tenantId'])
    req = urllib2.Request(url, data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        f = urllib2.urlopen(req)
    except urllib2.HTTPError, e:
        logit_error(mylogger, "HTTPError: " + str(e))
        raise
    except urllib2.URLError, e:
        logit_error(mylogger, "URLError: " + str(e))
        raise
    except httplib.HTTPException, e:
        logit_error(mylogger, "HTTPException: " + str(e))
        raise
    except Exception, e:
        logit_error(mylogger, "Exception: " + str(e))
        raise
    for x in f:
        y = json.loads(x)
        if y['token_type'] == 'Bearer':
            access_token = y['access_token']
            token_type = y['token_type']
    f.close()

def Generate_XML_and_Push_Tags(Firewall, api_key, vsys_id):    

#CurrentIPTagList is the list of IP to Tag mapping in the Firewall.
#NewIPTagList is the list of IP to Tag mapping in the Azure environment.
#This function will find the deltas between the new ip to tag mappings and register new IPs and tags 
#And unregister IPs from tags that have disappeared.
    logit_info(mylogger, "current: %s" % CurrentIPTagList.keys())
    logit_info(mylogger, "new: %s" % NewIPTagList.keys())

    FWXMLUpdate = []
    XMLHeader = "<uid-message><version>1.0</version><type>update</type><payload>"
    XMLFooter = "</payload></uid-message>"
    Unregister = ""
    Register = ""
    Current_Unregister = ""
    Current_Register = ""

    for k1 in CurrentIPTagList.keys():
        if k1 in NewIPTagList.keys():
            ip = k1
            tags = list(set(CurrentIPTagList[k1]) - set(NewIPTagList[k1]))
        elif k1 not in NewIPTagList.keys():
            ip = k1
            tags = CurrentIPTagList[k1]
        if tags:            
            Current_Unregister += '<entry ip="' + ip + '">'
            Current_Unregister += "<tag>"
            for i in tags:
                Current_Unregister += '<member>' + i + '</member>'
            Current_Unregister += "</tag>"
            Current_Unregister += "</entry>"
        if len(urllib.quote(Unregister + Current_Unregister)) < MAX_URL_CHARACTERS:
            Unregister += Current_Unregister
        else:
            # push current tag list
            Unregister = "<unregister>" + Unregister + "</unregister>"
            logit_info(mylogger, "Unregister: %s" % Unregister)
            FWXMLUpdate = XMLHeader + Unregister + XMLFooter
            logit_info(mylogger, "FWXMLUpdate: %s" % FWXMLUpdate)

            try:
                Firewall_Update_Tags(Firewall, api_key, vsys_id, FWXMLUpdate)
            except:
                logit_error(mylogger, "Failed to unregister tags")
                pass

            # Reset tag list to last set of tags
            Unregister = Current_Unregister
        Current_Unregister = ""
    if Unregister:
        # Still remaining unpushed tags, push last set of tags
        Unregister = "<unregister>" + Unregister + "</unregister>"
        logit_info(mylogger, "Unregister: %s" % Unregister)
        FWXMLUpdate = XMLHeader + Unregister + XMLFooter
        logit_info(mylogger, "FWXMLUpdate: %s" % FWXMLUpdate)

        try:
            Firewall_Update_Tags(Firewall, api_key, vsys_id, FWXMLUpdate)
        except:
            logit_error(mylogger, "Failed to unregister tags")
            pass

    #print "unregister: " + Unregister
    for k1 in NewIPTagList.keys():
        if k1 in CurrentIPTagList.keys():
            ip = k1
            tags = list(set(NewIPTagList[k1]) - set(CurrentIPTagList[k1]))
        elif k1 not in CurrentIPTagList.keys():
            ip = k1
            tags = NewIPTagList[k1]
        if tags:
            Current_Register += '<entry ip="' + ip + '">'
            Current_Register += "<tag>"
            for i in tags:
                Current_Register += '<member>' + i + '</member>'
            Current_Register += "</tag>"
            Current_Register += "</entry>"
        if len(urllib.quote(Register + Current_Register)) < MAX_URL_CHARACTERS:
            Register += Current_Register
        else:
            # push current tag list
            Register = "<register>" + Register + "</register>"
            logit_info(mylogger, "Register: %s" % Register)
            FWXMLUpdate = XMLHeader + Register + XMLFooter
            logit_info(mylogger, "FWXMLUpdate: %s" % FWXMLUpdate)

            try:
                Firewall_Update_Tags(Firewall, api_key, vsys_id, FWXMLUpdate)
            except:
                logit_error(mylogger, "Failed to register tags")
                pass

            # Reset tag list to last set of tags
            Register = Current_Register
        Current_Register = ""
    if Register:
        # Still remaining unpushed tags, push last set of tags
        Register = "<register>" + Register + "</register>"
        logit_info(mylogger, "Register: %s" % Register)
        FWXMLUpdate = XMLHeader + Register + XMLFooter
        logit_info(mylogger, "FWXMLUpdate: %s" % FWXMLUpdate)

        try:
            Firewall_Update_Tags(Firewall, api_key, vsys_id, FWXMLUpdate)
        except:
            logit_error(mylogger, "Failed to register tags")
            pass

    #print "register: " + Register
    #return Unregister, Register
    
#Get the list of IP to tag mappings that are in the firewall
def Firewall_Get_Tags(firewall_mgmt_ip, api_key, vsys_id):
    global CurrentIPTagList
    CurrentIPTagList.clear()

    # First set target vsys
    url = "https://%s/api/?type=op&cmd=<set><system><setting><target-vsys>%s</target-vsys></setting></system></set>&key=%s" % (firewall_mgmt_ip, vsys_id, api_key)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        response = urllib2.urlopen(url, context=ctx).read()
        #print response
    except urllib2.HTTPError as err:
        logit_error(mylogger, "HTTPError: " + str(err))
        raise
    except urllib2.URLError as err:
        logit_error(mylogger, "URLError: " + str(err))
        raise
    except httplib.HTTPException as err:
        logit_error(mylogger, "HTTPException: " + str(err))
        raise
    except Exception as err:
        logit_error(mylogger, "Exception: " + str(err))
        raise
    else:
        logit_info(mylogger, "Get Tags: %s" % response)

    # We can only retrieve a maximum of 500 tags per API call.
    start_point = 0
    limit = 500
    tag_count = 0

    while True:
        if start_point:
            url = "https://%s/api/?type=op&cmd=<show><object><registered-ip><limit>%d</limit><start-point>%d</start-point><all/></registered-ip></object></show>&key=%s" %(firewall_mgmt_ip, limit, start_point, api_key)
        else:
            url = "https://%s/api/?type=op&cmd=<show><object><registered-ip><limit>%d</limit><all/></registered-ip></object></show>&key=%s" %(firewall_mgmt_ip, limit, api_key)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            response = urllib2.urlopen(url, context=ctx).read()
            #print response
        except urllib2.HTTPError as err:
            logit_error(mylogger, "HTTPError: " + str(err))
            raise
        except urllib2.URLError as err:
            logit_error(mylogger, "URLError: " + str(err))
            raise
        except httplib.HTTPException as err:
            logit_error(mylogger, "HTTPException: " + str(err))
            raise
        except Exception as err:
            logit_error(mylogger, "Exception: " + str(err))
            raise
        else:
            logit_info(mylogger, "Get Tags: %s" % response)
            root = et.fromstring(response)
            if root.attrib['status'] == 'success':
                for entry in root.findall('./result/entry'):
                    for tag in entry.findall('./tag/member'):
                        if tag.text.startswith('azure-tag'):
                            CurrentIPTagList[entry.attrib['ip']].append(tag.text)
                count = 0
                entry = root.find('./result/count')
                if entry is not None:
                    count = int(entry.text)
                    logit_info(mylogger, "Get Tags: retrieved %d tags" % count)
                tag_count += count
                if count < limit:
                    # We've retrieved all the tags
                    break
                else:
                    start_point += limit

    logit_info(mylogger, "Get Tags: Retrieved total of %d tags" % tag_count)

    # Un-set target vsys
    url = "https://%s/api/?type=op&cmd=<set><system><setting><target-vsys>%s</target-vsys></setting></system></set>&key=%s" % (firewall_mgmt_ip, "none", api_key)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        response = urllib2.urlopen(url, context=ctx).read()
        #print response
    except urllib2.HTTPError as err:
        logit_error(mylogger, "HTTPError: " + str(err))
        raise
    except urllib2.URLError as err:
        logit_error(mylogger, "URLError: " + str(err))
        raise
    except httplib.HTTPException as err:
        logit_error(mylogger, "HTTPException: " + str(err))
        raise
    except Exception as err:
        logit_error(mylogger, "Exception: " + str(err))
        raise
    else:
        logit_info(mylogger, "Get Tags: %s" % response)


#Update the firewall with the latest IP to tag map
def Firewall_Update_Tags(firewall_mgmt_ip, api_key, vsys_id, FWXMLUpdate):
    url = "https://%s/api/?" % firewall_mgmt_ip
    data = "type=user-id&action=set&key=%s&vsys=%s&cmd=%s" % (api_key, vsys_id, urllib.quote(FWXMLUpdate))
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib2.Request(url, data)
    logit_info(mylogger, "FW request url: %s" % url)
    logit_info(mylogger, "FW request data: %s" % data)
    try:
        response = urllib2.urlopen(req, context=ctx).read()
        #print response
    except urllib2.HTTPError as err:
        logit_error(mylogger, "HTTPError: " + str(err))
        raise
    except urllib2.URLError as err:
        logit_error(mylogger, "URLError: " + str(err))
        raise
    except httplib.HTTPException as err:
        logit_error(mylogger, "HTTPException: " + str(err))
        raise
    except Exception as err:
        logit_error(mylogger, "Exception: " + str(err))
        raise
    else:
        logit_info(mylogger, "Update Tags: %s" % response)

#Check HA status.  Only push tags to Active or Active-Primary devices
def is_ha_primary(firewall_mgmt_ip, api_key):
    url = "https://%s/api/?type=op&cmd=<show><high-availability><state></state></high-availability></show>&key=%s" %(firewall_mgmt_ip, api_key)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    logit_info(mylogger, "FW request url: %s" % url)
    try:
        response = urllib2.urlopen(url, timeout=5, context=ctx).read()
        #print response
    except urllib2.HTTPError as err:
        logit_error(mylogger, "HTTPError: " + str(err))
        return False
    except urllib2.URLError as err:
        logit_error(mylogger, "URLError: " + str(err))
        return False
    except httplib.HTTPException as err:
        logit_error(mylogger, "HTTPException: " + str(err))
        return False
    except Exception as err:
        logit_error(mylogger, "Exception: " + str(err))
        return False
    else:
        logit_info(mylogger, "FW request response: %s" % response)

    root = et.fromstring(response)
    if root.attrib['status'] == 'success':
        for entry in root.findall('./result/enabled'):
            if entry.text == 'yes':
                logit_info(mylogger, "FW %s: HA enabled" % firewall_mgmt_ip)
                #for entry in root.findall('./result/group/mode'):
                #    print entry.text
                for entry in root.findall('./result/group/local-info/state'):
                    if entry.text.lower() == 'active' or entry.text.lower() == 'active-primary':
                        logit_info(mylogger, "Firewall %s is %s" % (firewall_mgmt_ip, entry.text))
                        return True
                    else:
                        logit_info(mylogger, "Firewall %s is %s; tags will not be pushed" % (firewall_mgmt_ip, entry.text))
                        return False
            else:
                logit_info(mylogger, "Firewall %s: HA disabled" % firewall_mgmt_ip)
                return True
    return False

#Helper functions to convert unicode strings
def json_load_byteified(file_handle):
    return _byteify(
        json.load(file_handle, object_hook=_byteify),
        ignore_dicts=True
    )

def json_loads_byteified(json_text):
    return _byteify(
        json.loads(json_text, object_hook=_byteify),
        ignore_dicts=True
    )

def _byteify(data, ignore_dicts = False):
    # if this is a unicode string, return its string representation
    if isinstance(data, unicode):
        return data.encode('utf-8')
    # if this is a list of values, return list of byteified values
    if isinstance(data, list):
        return [ _byteify(item, ignore_dicts=True) for item in data ]
    # if this is a dictionary, return dictionary of byteified keys and values
    # but only if we haven't already byteified it
    if isinstance(data, dict) and not ignore_dicts:
        return {
            _byteify(key, ignore_dicts=True): _byteify(value, ignore_dicts=True)
            for key, value in data.iteritems()
        }
    # if it's anything else, return it in its original form
    return data

#Retrieve parameters from parameters file
def read_parameters(filename=PARAMETERS_FILE):
    global param_dict

    data = json_load_byteified(open(filename))
    for key,val in data['parameters'].iteritems():
        if key in list_types:
            param_dict[key] = val['value'].split(',')
        else:
            param_dict[key] = val['value']
    for item in required_params:
        if item not in param_dict:
            logit_error(mylogger, "Missing required parameter: %s" % item)
            release_lock(LOCKFILE)
            sys.exit(1)
    logit_info(mylogger, 'Input Parameters: %s' % param_dict)

def acquire_lock(lockfile):
    logit_info(mylogger, 'Checking for running instances of VM monitoring script...')

    # Check if previous instance of script still running
    if os.path.exists(lockfile):
        with open(lockfile, 'r') as f:
            pid_infile = f.read().strip()
        # Check for the pid in the process list and make sure it matches
        # the script name as well.
        logit_info(mylogger, 'Checking for instance of Azure VM Monitoring script with PID %s...' % pid_infile)
        try:
            subprocess.check_call('ps a | grep -w %s | grep %s | grep -v grep' % (pid_infile, os.path.basename(__file__)), shell=True)
        except:
            logit_info(mylogger, 'No instance of Azure VM Monitoring script found.')
        else:
            logit_info(mylogger, 'Azure VM Monitoring script execution already in progress.')
            return 1

    logit_info(mylogger, 'Starting new instance of Azure VM Monitoring script')

    # Indicate that we are starting a new script instance.
    try:
        with open(lockfile, 'w') as f:
            metrics_pid = str(os.getpid())
            f.write(metrics_pid)
            logit_info(mylogger, 'Starting instance of Azure VM Monitoring script with PID %s.' % metrics_pid)
    except:
        logit_error(mylogger, 'Unable to write lockfile')
        return 1
    else:
        return 0

def release_lock(lockfile):
    try:
        os.remove(lockfile)
    except:
        logit_error(mylogger, 'Unable to remove lockfile')
        return 1
    return 0

def usage():
    print
    print 'usage: ', os.path.basename(sys.argv[0]), '-f <parameter file> -l <log directory>'

    print '''
    options:
      -h                  Print usage info
      -f                  Specify parameter file (required)
      -l                  Specify log directory (default='/tmp')
    '''

#Entry point
def main(argv):
    global mylogger

    filename = None
    loggingDir = None
    try:
        opts, args = getopt.getopt(argv, "hf:l:", [ "help", "parameters=", "logdir=" ])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage()
            sys.exit()
        elif opt in ('-f', '--parameters'):
            filename = arg
        elif opt in ('-l', '--logdir'):
            loggingDir = arg

    if loggingDir:
        logDir = loggingDir
        if not os.path.exists(loggingDir):
            os.makedirs(loggingDir)
    else:
        # Default log file directory location
        logDir = '/tmp'
    mylogger = setup_log(logDir)

    logit_info(mylogger, "Script Version: %s" % VERSION)
    logit_info(mylogger, "Log Directory: %s" % logDir)

    if acquire_lock(LOCKFILE) > 0:
        logit_error(mylogger, 'Unable to acquire lock; aborting this instance of script')
        sys.exit(1)

    if not filename:
        logit_error(mylogger, 'Missing required parameters file')
        usage()
        sys.exit(2)
    else:
        read_parameters(filename)


#check to see if firewall is reachable. If not, gracefully exit
    for Firewall in param_dict['targetIps']:
        url = "https://%s" %(Firewall)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            f = urllib2.urlopen(url, timeout=5, context=ctx)
        except urllib2.URLError as err:
            logit_error(mylogger, 'URLError: %s' % str(err))
            logit_error(mylogger, "FW %s not found..." % Firewall)
            pass

#Authenticate and get access token so we can make API calls into Azure
    try:
        Get_Azure_Access_Token()
    except:
        logit_error(mylogger, 'Unable to retrieve Azure access token; aborting.')
        sys.exit(1)

    logit_info(mylogger, "Access Token retrieved")

#Get resource group list
    #GetResourceGroups(param_dict['subscriptionId'])

    # Generate dictionary of Network Security Group entries
    if generate_nsg_dict():
        logit_error(mylogger, 'Unable to retrieve list of Virtual Networks; please check your provided parameters.') 

#Build the list of IP to tag
    Build_Tags()

#Get ip-to-tag mapping from the firewall
    for Firewall,api_key,vsys_id in itertools.izip(param_dict['targetIps'], param_dict['targetApiKeys'], param_dict['targetVsys']):
        if is_ha_primary(Firewall, api_key):
            try:
                Firewall_Get_Tags(Firewall, api_key, vsys_id)
            except Exception as err:
                logit_error(mylogger, 'Exception: %s' % str(err))
                continue

            Generate_XML_and_Push_Tags(Firewall, api_key, vsys_id)

    logit_info(mylogger, "Script completed normally.")
    release_lock(LOCKFILE)


if __name__ == "__main__":
    main(sys.argv[1:])
