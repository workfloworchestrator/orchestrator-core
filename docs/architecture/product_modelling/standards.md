# Standards

There are many standards describing how network service products and their
attributes can be modelled. Most of these are very detailed as they try to
cover as many use cases as possible, which can prove overwhelming. Here we aim
to do the opposite and only model the bare minimum. This makes it easier to see
the relationship between the network service models, and how each model can be
extended with attributes that are specific to the organisation that uses them.

A common way of modelling products is to split the models into a
customer-facing part that contains all the attributes that are significant to
the customer, and a resource-facing part that extends that set of attributes
with all the attributes that are needed to actually deploy a service on the
network. We assume here that such a separation is being used, where the
customer-facing part lives in the Workflow Orchestrator and the resource-facing
part lives in a provisioning system such as NSO or Ansible.
