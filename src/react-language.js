// Both bundled React renderers share this signal, but each uses its own context.
// Reading a translated label during render subscribes that component. Changing
// the value updates memoized components without replacing the roots or their state.
function __devinWrapReactRoot(React, children, isRendering) {
    let bus = globalThis.__devinLiveReactLanguages;
    if (!bus) {
        let selected = globalThis.__devinDesktopActiveLanguage;
        const listeners = new Set();
        const renderers = new Map();
        const subscribe = listener => {
            listeners.add(listener);
            return () => listeners.delete(listener);
        };
        const snapshot = () => selected || globalThis._VSCODE_NLS_LANGUAGE || "en";
        let scheduled = false;
        Object.defineProperty(globalThis, "__devinDesktopActiveLanguage", {
            configurable: true,
            get() {
                for (const binding of renderers.values()) binding.read();
                return selected;
            },
            set(value) {
                if (value === selected) return;
                selected = value;
                if (scheduled) return;
                scheduled = true;
                queueMicrotask(() => {
                    scheduled = false;
                    for (const listener of listeners) listener();
                });
            }
        });
        bus = globalThis.__devinLiveReactLanguages = { subscribe, snapshot, renderers };
    }
    let binding = bus.renderers.get(React);
    if (!binding) {
        const Language = React.createContext(bus.snapshot());
        function LiveLanguage({ children }) {
            const code = React.useSyncExternalStore(bus.subscribe, bus.snapshot, bus.snapshot);
            return React.createElement(Language.Provider, { value: code }, children);
        }
        binding = { LiveLanguage, read() { if (isRendering()) React.use(Language); } };
        bus.renderers.set(React, binding);
    }
    return React.createElement(binding.LiveLanguage, null, children);
}
