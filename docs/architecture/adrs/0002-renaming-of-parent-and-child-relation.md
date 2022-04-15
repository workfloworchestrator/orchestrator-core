# ADR 0003 Renaming parent and child relation of subscriptions

Date: 2022-03-11

## Status

Accepted

## Context

`Parent` and `Child` naming convention is not suited for our relationship between subscriptions, since there are
times it deviates from normal logic, wanting to create a child before the parent, which can create a lot of confusion.

as example, subscription 1 needs subscription 2.

- subscription 2 is the parent in the relationship because it is used by subscription 1.
- subscription 1 is the child in the relationship because it is depends on subscription 2.

To fix this, one solution would be renaming the relationship.

It would be nice if names for the relations would map good to the real world to make it easier to argue about them

## Decision

It was decided to rename `parent` to `in_use_by` and `child` to `depends_on`.

Examples:
- **Nodes are used by Ports**
- **A Port depends on a Node**

So a Node can not be terminated before all ports are terminated.

## Consequences

Given the decision, the consequences are:
- A lot is backwards compatible, except for the renamed database columns
- Code that uses the old ORM properties will be kept backwards compatible for now with a deprecation warning
- SQL queries using `parent_id` and `child_id` will break because they are renamed.
