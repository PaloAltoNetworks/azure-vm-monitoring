# azure-vm-monitoring

# Introduction
The dynamic nature of cloud environments means security also needs to be dynamic. Plao Alto Networks firewalls allow for the creation of dynamic address groups which can be programatically updated via APIs to reflect the changes in your cloud environment.
This automation is key in keeping up with the dynamic cloud environment.

Also when writing firewall security policies to secure assests deployed in Azure, it makes sense to write policies that are logical.

For example: Allow traffic from web-server running linux to db-server running windows

This can be accomplished by harvesting ip and tag information from various cloud resources and making them available in the firewall.

The harvested ip and tags information can then be used in Dynamic Address Groups to create dynamic security policies. 
As workloads are added or removed from the Azure Resource Group, the policy is dynamically updated.


# The solution

The published solution uses a script that can be run on a worker node (Linux VM) within an Azure VNet to harvest tags and associated IP addresses of VMs from specified Azure resource groups and pushes them to one or more firewalls.

![alt_text](azure-vm-monitoring.png)



# Support Policy  
## Supported

Thissolution is released under the official support policy of Palo Alto Networks through the support 
options that you've purchased, for example Premium Support, support teams, or ASC (Authorized Support Centers) partners 
and Premium Partner Support options. The support scope is restricted to troubleshooting for the stated/intended use 
cases and product versions specified in the project documentation and does not cover customization of the scripts or templates. 

Only projects explicitly tagged with "Supported" information are officially supported. 
Unless explicitly tagged, all projects or work posted in our [GitHub repository](https://github.com/PaloAltoNetworks) or sites 
other than our official [Downloads page](https://support.paloaltonetworks.com/) are provided under the best effort policy.

# Documentation
* Release Notes: Included in this repository
* Techincal Documentation: [Deployment Guide]
* About the [VM-Series Firewall for Azure](https://azure.paloaltonetworks.com).
