---
hide:
  - toc
---

<p align="center"><em>Production ready Workflow Orchestration Framework to manage product lifecycle and workflows. Easy to use, Built on top of FastAPI</em></p>

<p align="center">
    <a href="https://pepy.tech/project/orchestrator-core" target="_blank">
    <img src="https://pepy.tech/badge/orchestrator-core/month" alt="Downloads">
    </a>
    <a href="https://codecov.io/gh/workfloworchestrator/orchestrator-core" target="_blank">
    <img src="https://codecov.io/gh/workfloworchestrator/orchestrator-core/branch/main/graph/badge.svg?token=5ANQFI2DHS" alt="Coverage">
    </a>
    <a href="https://pypi.org/project/orchestrator-core" target="_blank">
    <img src="https://img.shields.io/pypi/v/orchestrator-core?color=%2334D058&label=pypi%20package" alt="Pypi">
    </a>
</p>
<br>
<br>
__The Workflow Orchestrator is a project developed by [SURF](https://www.surf.nl) to facilitate the orchestration of services.
Together with [ESnet](https://www.es.net) this project has been open-sourced in [the commons conservancy](https://commonsconservancy.org)
to help facilitate collaboration. We invite all who are interested to take a look and to contribute!__

## Orchestration
When do you orchestrate and when do you automate? The answer is you probably need both. Automation helps you execute repetitive
tasks reliably and easily. Orchestration adds a layer and allows you to add more intelligence to the tasks you need to automate and
to have a complete audit log of changes.

> #### Orchestrate[*](https://www.lexico.com/en/definition/orchestrate) - Transitive Verb
> /ˈôrkəˌstrāt/ /ˈɔrkəˌstreɪt/
>
>   1: Arrange or score (music) for orchestral performance.
>   *‘the song cycle was stunningly arranged and orchestrated’*
>
>   2:  Arrange or direct the elements of (a situation) to produce a desired effect, especially surreptitiously.
>   *‘the developers were able to orchestrate a favorable media campaign’*

## Project Goal
This **Workflow Orchestrator** provides a framework through which you can manage service orchestration for your end-users. The
framework helps and guides **you**, the person who needs to get things done, through the steps from
automation to orchestration. With an easy to use set of API's and examples, you should be up and running and seeing
results, before you completely understand all ins and outs of the project. The Workflow Orchestrator enables you to define
products to which users can subscribe, and helps you intelligently manage the lifecycle, with the use of **Creation**, **Modification**,
**Termination** and **Validation** workflows, of resources that you provide to your users.
The Application extends a FastAPI application and therefore can make use of all the awesome features of FastAPI, pydantic and asyncio python.

## What does a workflow look like? It must be pretty complex!!

Programming a new workflow should be really easy, and at its core it is. By defining workflows as Python functions,
all you need to do is understand how to write basic python code, the framework will help take care of the rest.

```python
@workflow("Name of the workflow", initial_input_form=input_form_generator)
def workflow():
    return (
        init
        >> arbitrary_step_func_1
        >> arbitrary_step_func_2
        >> arbitrary_step_func_3
        >> done
    )
```

## I'm convinced! Show me more!

There are a number of options for getting started:

- First have a look at the [demo orchestrator](https://demo.workfloworchestrator.org/), where you can get a feel for creating subscriptions using workflows. It will take you to our demo environment, where you can see some of our examples in action.
- For those of you who would like to see it working, take a look at [this repo](https://github.com/workfloworchestrator/example-orchestrator) and follow the README to setup a
  docker-compose so you can experiment on your localhost.
- For those who are more adventurous, follow the guide on the [next page](getting-started/base.md) to
  start coding right away.

<!-- Followinh line are not visible? -->
[//]: # (- If you would like to see the workflow engine in action, click [here]&#40;https://demo.workfloworchestrator.org&#41; this )

[//]: # (will take you to our demo environment, where you can see some of our examples in action.)
