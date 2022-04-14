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

## Decision

It was decided to rename `parent` to `in_use_by` and `child` to `depends_on`.

## Consequences

Given the decision, the consequences are:
- A lot is backwards compatible, except for the renamed database columns
- SQL queries using `parent_id` and `child_id` will break because they are renamed.
