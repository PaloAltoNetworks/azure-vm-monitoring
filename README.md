# azure-vm-monitoring

Harvest Tags from Azure Resource Groups and push that ip to tag mapping to PaloAlto networks firewalls.


The script published in this repo is designed to be run as an Azure Function and harvets tags from specified Azure Aesource Groups.
These tags and associated IP addresses are then pushed to one or more Palo Alto Networks firewalls.
These tags can then be used in Dynamic Address groups to create logical secuirty policies.

Deployment guide can be found [here](https://github.com/PaloAltoNetworks/azure-vm-monitoring/blob/master/Azure%20VM%20Monitoring%20Setup%20Instructions.pdf)

Support: Community Supported
--------
Unless otherwise noted, these templates are released under an as-is, best effort, support policy. These scripts should be seen as community supported and Palo Alto Networks will contribute our expertise as and when possible. We do not provide technical support or help in using or troubleshooting the components of the project through our normal support options such as Palo Alto Networks support teams, or ASC (Authorized Support Centers) partners and backline support options. The underlying product used (the VM-Series firewall) by the scripts or templates are still supported, but the support is only for the product functionality and not for help in deploying or using the template or script itself. Unless explicitly tagged, all projects or work posted in our GitHub repository (at https://github.com/PaloAltoNetworks) or sites other than our official Downloads page on https://support.paloaltonetworks.com are provided under a community supported, best effort, policy.
