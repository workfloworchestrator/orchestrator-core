# Workflow Orchestrator Documentation

This directory contains the Mintlify documentation for Workflow Orchestrator.

## Getting Started

1. Install Mintlify CLI:
   ```bash
   npm i -g mintlify
   ```

2. Preview the documentation:
   ```bash
   cd docs-mint
   mintlify dev
   ```

3. Build for production:
   ```bash
   mintlify build
   ```

## Documentation Structure

- **Introduction**: Overview and getting started
- **Core Concepts**: Domain models, workflows, products, subscriptions
- **Getting Started**: Step-by-step tutorials
- **API Reference**: Complete API documentation
- **Advanced**: Deployment, monitoring, customization
- **Examples**: Real-world use cases and patterns

## Contributing

When adding new documentation:

1. Follow the existing structure and naming conventions
2. Include proper frontmatter with title and description
3. Use Mintlify components (Note, Warning, Tip, etc.)
4. Add code examples with proper syntax highlighting
5. Update mint.json navigation if adding new pages

## Mintlify Components Used

- `<Note>`: Helpful information
- `<Warning>`: Important cautions
- `<Tip>`: Best practices
- `<Check>`: Success confirmations
- `<CardGroup>` and `<Card>`: Navigation cards
- `<Tabs>` and `<Tab>`: Tabbed content
- `<CodeGroup>`: Multiple code examples
- `<AccordionGroup>` and `<Accordion>`: Collapsible content
