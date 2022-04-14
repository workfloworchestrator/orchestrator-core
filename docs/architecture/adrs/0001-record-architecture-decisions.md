# ADR 0001 - Record architecture decisions

Date: 2021-12-06

## Status

Accepted

## Decisions
* Decision taken to use Architecture Decision Records by the group.
* There are three types of documentation
  * Architecture documentation of the orchestrator
  * The business logic of a workflow.
  * The standard operation procedures.


* The documentation must be published and freely accessible by all users of the orchestrator.
* MKdocs (FastAPI method) is an easy way to generate readable docs, this assumes the use of Markdown, for all documentation.
* To ease development of the Docs, it needs to be maintained close to the source.
* The following projects are candidates to make use of ADR's and extensive documentation
  * Orchestrator
  * Network dashboard
  * IMS


* Confluence will not be used for Architecture documentation

## Action items:
https://git.ia.surfsara.nl/netdev/automation/projects/orchestrator/-/issues/1266

## Attendees:

- Wouter Huisman
- Hans Trompert
- Migiel de Vos
- Thijs Cremers
- Rene Dohmen
- Tjeerd Verschragen
- Maurits de Rijk
- Floris Nicolai
- Peter Boers
