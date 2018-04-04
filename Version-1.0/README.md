# azure-vm-monitoring

# Introduction
The dynamic nature of cloud environments means security also needs to be dynamic. Palo Alto Networks firewalls allow you to define dynamic address groups as core policy elements that can be programmatically updated, using the PAN-OS API, to reflect the changes in your cloud environment.

# How it Works

VM Monitoring uses a Python script that runs on a worker node (Linux virtual machine) within an Azure VNet to collect tags and associated IP addresses of VMs from specified Azure resource groups and register the information to the VM-Series or hardware-based firewalls.

You can then use this IP address and tag information in a dynamic address group to create security policies that adapt to workload changes in your Azure environment. As workloads are added or removed from the Azure Resource Group, the dynamic address group, and corresponding security policy are automatically updated. Automating security policy updates as your cloud environment changes key to ensuring security keeps pace with the speed of the cloud.

![alt_text](azure-vm-monitoring.png)

# Support Policy  
## Supported

This solution is released under the official support policy of Palo Alto Networks through the support 
options that you've purchased, for example Premium Support, support teams, or ASC (Authorized Support Centers) partners 
and Premium Partner Support options. The support scope is restricted to troubleshooting for the stated/intended use 
cases and product versions specified in the project documentation and does not cover customization of the scripts or templates. 

Only projects explicitly tagged with "Supported" information are officially supported. 
Unless explicitly tagged, all projects or work posted in our [GitHub repository](https://github.com/PaloAltoNetworks) or sites 
other than our official [Downloads page](https://support.paloaltonetworks.com/) are provided under the best effort policy.

# Documentation
* Release Notes: Included in this repository
* Technical Documentation: [VM Monitoring on Azure](https://www.paloaltonetworks.com/documentation/81/virtualization/virtualization/set-up-the-vm-series-firewall-on-azure/vm-monitoring-on-azure.html)
* More templates: [Palo Alto Networks Live Community](https://live.paloaltonetworks.com/t5/Cloud-Integration/ct-p/Cloud_Templates)
* About the [VM-Series Firewall for Azure](https://azure.paloaltonetworks.com).
