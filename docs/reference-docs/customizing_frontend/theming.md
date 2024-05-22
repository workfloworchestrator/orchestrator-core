# Theming

## Customizing the theme

The Workflow Orchestrator frontend ships with a default theme leveraging the theming mechanism of Elastic UI. This theme can be partially adjusted or completely overridden.

As part of the boilerplate code, the `_app.tsx` file applies a `defaultOrchestratorTheme` object to the EuiProvider.

```tsx
// _app.tsx

<SeveralProviders>
    <EuiProvider
        colorMode={themeMode}
        modify={defaultOrchestratorTheme}
    >
        ...
    </EuiProvider>
</SeveralProviders>
```

The default defaultOrchestratorTheme object are adjustments of the standard theme provided by Elastic UI and can be imported from the [@orchestrator-ui/orchestrator-ui-components](https://www.npmjs.com/package/@orchestrator-ui/orchestrator-ui-components) package.

To make small adjustments, simply use [defaultOrchestratorTheme](https://github.com/workfloworchestrator/orchestrator-ui-library/blob/main/packages/orchestrator-ui-components/src/theme/defaultOrchestratorTheme.ts) as a base and override the desired properties:

```tsx
// _app.tsx
...
import { EuiThemeModifications } from '@elastic/eui';
import { defaultOrchestratorTheme } from '@orchestrator-ui/orchestrator-ui-components';
...

function CustomApp(...) {
    ...
    const myTheme: EuiThemeModifications = {
        ...defaultOrchestratorTheme,
        colors: {
            DARK: {
                primary: '#FF69B4',
            },
            LIGHT: {
                primary: '#32CD32',
            },
        },
    };
    
    ...
    
    return (
        <SeveralProviders>
            <EuiProvider
                colorMode={themeMode}
                modify={myTheme}
            >
                ...
            </EuiProvider>
        </SeveralProviders>
    )
}
```

The usage of defaultOrchestratorTheme is not required, a new `EuiThemeModifications` can also be made from scratch or using the [helper tool](https://eui.elastic.co/#/theming/customizing-themes) on the EUI website.

## Color Mode

The `color` property of the theme object contains a `DARK` and `LIGHT` object representing the color mode. The _app.tsx file contains a mechanism to switch and store the color mode. In any given component the `useOrchestratorTheme` hook can be used to get the current color mode. For more convenience, there is also the `isDarkThemeActive` boolean:

```tsx
...
import { useOrchestratorTheme } from '@orchestrator-ui/orchestrator-ui-components';
...

const WfoAnyComponent: FC<WfoAnyComponentProps> = (...) => {
    const {
        colorMode,          // type: EuiThemeColorModeStandard
        isDarkThemeActive   // type: boolean
    } = useOrchestratorTheme();
    
    return(...);
}
```
