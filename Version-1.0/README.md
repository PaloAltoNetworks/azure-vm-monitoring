# azure-vm-monitoring


# NOTE: THIS SOLUTION HAS BEEN DEPRECATED AND HENCE MOVED TO A COMMUNITY SUPPORTED MODEL


# Introduction
The dynamic nature of cloud environments means security also needs to be dynamic. Palo Alto Networks firewalls allow you to define dynamic address groups as core policy elements that can be programmatically updated, using the PAN-OS API, to reflect the changes in your cloud environment.

# How it Works

VM Monitoring uses a Python script that runs on a worker node (Linux virtual machine) within an Azure VNet to collect tags and associated IP addresses of VMs from specified Azure resource groups and register the information to the VM-Series or hardware-based firewalls.

You can then use this IP address and tag information in a dynamic address group to create security policies that adapt to workload changes in your Azure environment. As workloads are added or removed from the Azure Resource Group, the dynamic address group, and corresponding security policy are automatically updated. Automating security policy updates as your cloud environment changes key to ensuring security keeps pace with the speed of the cloud.

![alt_text](azure-vm-monitoring.png)

# Support Policy  
Support: Community Supported
--------
Unless otherwise noted, these templates are released under an as-is, best effort, support policy. These scripts should be seen as community supported and Palo Alto Networks will contribute our expertise as and when possible. We do not provide technical support or help in using or troubleshooting the components of the project through our normal support options such as Palo Alto Networks support teams, or ASC (Authorized Support Centers) partners and backline support options. The underlying product used (the VM-Series firewall) by the scripts or templates are still supported, but the support is only for the product functionality and not for help in deploying or using the template or script itself. Unless explicitly tagged, all projects or work posted in our GitHub repository (at https://github.com/PaloAltoNetworks) or sites other than our official Downloads page on https://support.paloaltonetworks.com are provided under a community supported, best effort, policy.

# Documentation
* Technical Documentation: [VM Monitoring on Azure](https://github.com/PaloAltoNetworks/azure-vm-monitoring/blob/master/Version-1.0/VM%20Monitoring%20on%20Azure.pdf)
* More templates: [Palo Alto Networks Live Community](https://live.paloaltonetworks.com/t5/Cloud-Integration/ct-p/Cloud_Templates)
* About the [VM-Series Firewall for Azure](https://azure.paloaltonetworks.com).
