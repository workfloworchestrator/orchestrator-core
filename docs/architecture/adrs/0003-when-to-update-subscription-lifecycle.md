# ADR 0003 When to update subscription lifecycle and changing subscriptions

Date: 2022-03-22

## Status

Accepted

## Context

Updating subscription lifecycles during workflows should be done consistently. Over the past few years there have been
multiple ways to change subscriptions and their lifecycle. With the introduction of Domain models it is very easy to
update  all variables in a subscription whilst processing a form without transitioning the subscription to a different
lifecycle.

To make the way we write and test workflows predictable, to make sure that all changes to a subscription are logged
correctly in the process state and to help the user in the networkdashboard better understand the status of their
subscription if a change is pending, we propose the following:

For some unit tests this adds a lot of mandatory LifeCycle changes and saves to the database. So it should be possible
to bypass some of the logic.

## Decision

- Forms MUST only be used to gather data, no editing of subscriptions are done in forms.
- When 'unsyncing' a subscription in a workflow (not a validation task), the subscription MUST be transitioned to the lifecycle Provisioning
- All modifications to a subscription SHOULD be made in a generic process step upon which we can calculate a delta to show to the user.
- All subscriptions MUST be transitioned to lifecyle ACTIVE or TERMINATED upon completion of the workflow.
- Tests should be able to bypass some the Lifecycle transitions, to keep tests with a lot of related subscription easy.

## Consequences

Given the decision, the consequences are:
- All workflows should be checked to see if they comply to this ADR
- A generic sync and unsync step function should be created to automatically transition the subscription to the correct lifecyle.
- A generic step function should be created to make delta creation easier to calculate.
