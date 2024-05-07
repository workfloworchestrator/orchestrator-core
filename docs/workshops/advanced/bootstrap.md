# Bootstrapping the environment
The Example orchestrator used in this workshop already has a number of products pre-configured and ready to be used:

* Nodes
* Core-links
* Ports
* L2VPN

Once you have successfully started the docker environment with `docker compose up -d` you should be able to view the 
applications here:

1. Orchestrator ui: [Frontend: http://localhost:3000](http://localhost:3000)
2. Orchestrator backend: [REST api: http://localhost:8080/api/redoc](http://localhost:8080/api/redoc) and  
   [Graphql API: http://localbost:8080/api/graphql](http://localbost:8080/api/graphql)
3. Netbox (admin|admin): [Netbox: http://localhost:8000](http://localhost:8000)

!!! note
    Take your time to familiarise with the applications and make sure they are working correctly. You can then 
    continue with the following steps.

