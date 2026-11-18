import { messages } from "./devin-live-messages.js";

const preference = "devin-desktop-display-language-v1";
const changes = new EventTarget();
export function originalMessage(id) { return messages.en[id]; }

function supported(value) {
    if (typeof value !== "string") return undefined;
    if (/^zh(?:-cn|-sg|-hans(?:-[a-z]+)?)?$/i.test(value)) return "zh-cn";
    if (/^en(?:-|$)/i.test(value)) return "en";
    return undefined;
}

function stored() {
    try { return globalThis.localStorage?.getItem(preference); }
    catch { return undefined; }
}

function activate(code) {
    const id = supported(code);
    if (!id) return;
    const display = id === "zh-cn" ? "zh-CN" : "en";
    const changed = globalThis._VSCODE_NLS_LANGUAGE !== id ||
        globalThis.__devinDesktopActiveLanguage !== display;
    globalThis._VSCODE_NLS_MESSAGES = messages[id];
    globalThis._VSCODE_NLS_LANGUAGE = id;
    globalThis.__devinDesktopActiveLanguage = display;
    document.documentElement.lang = id === "zh-cn" ? "zh-Hans" : "en";
    if (changed) changes.dispatchEvent(new Event("change"));
    return display;
}

export function onLanguageChange(listener) {
    changes.addEventListener("change", listener);
    return { dispose() { changes.removeEventListener("change", listener); } };
}

// Track only text assigned by the workbench from a numbered localization entry.
// Nodes retain their identity. If a widget replaces the label with its own content,
// relinquish the binding instead of translating the new text.
const bindings = new WeakMap();
const elements = new Set();
const cleanup = new FinalizationRegistry(reference => elements.delete(reference));

export function bindLabel(element, property, id) {
    const value = globalThis._VSCODE_NLS_MESSAGES[id];
    element[property] = value;
    if (element.nodeType !== 1) return value;
    let labels = bindings.get(element);
    if (!labels) {
        labels = new Map();
        bindings.set(element, labels);
        const reference = new WeakRef(element);
        elements.add(reference);
        cleanup.register(element, reference);
    }
    labels.set(property, { id, value });
    return value;
}

onLanguageChange(() => {
    for (const reference of elements) {
        const element = reference.deref();
        if (!element) { elements.delete(reference); continue; }
        for (const [property, label] of bindings.get(element)) {
            const text = property === "textContent" || property === "innerText";
            if (element[property] !== label.value || (text && (element.childElementCount || element.isContentEditable))) {
                bindings.get(element).delete(property);
                continue;
            }
            const value = globalThis._VSCODE_NLS_MESSAGES[label.id];
            if (value !== label.value) {
                if (text && element.firstChild?.nodeType === 3 && element.childNodes.length === 1) {
                    element.firstChild.data = value;
                } else {
                    element[property] = value;
                }
                label.value = value;
            }
        }
    }
});

function announce(code) {
    const display = activate(code);
    if (display) globalThis.dispatchEvent(new CustomEvent("devin-ui-native-choice", { detail: display }));
    return display;
}

export function selectLanguage(code, service) {
    const id = supported(code);
    if (!id) throw new RangeError("Unsupported live display language");
    const display = id === "zh-cn" ? "zh-CN" : "en";
    try {
        globalThis.localStorage.setItem(preference, display);
        globalThis.localStorage.setItem("devin-language", display);
    } catch { /* The native preference can still be saved. */ }
    announce(id);

    // A newer selection can arrive while another window is writing argv.json.
    const revision = (service.liveLocaleRevision || 0) + 1;
    service.liveLocaleRevision = revision;
    const persist = async () => {
        const current = stored();
        if (revision !== service.liveLocaleRevision || (current && current !== display)) return;
        await service.writeLocaleValue(id);
        await service.liveMenubar.setLiveDisplayLocale(id);
    };
    const schedule = () => globalThis.navigator?.locks
        ? navigator.locks.request("devin-display-language-write", persist) : persist();
    const pending = (service.liveLocaleWrite || Promise.resolve()).then(schedule, schedule);
    service.liveLocaleWrite = pending;
    return pending.catch(error => service.notificationService.error(error));
}

// Apply an explicit choice before the workbench registers commands or creates views.
// Other supported Devin web languages continue to use their own upstream resources.
const initial = stored();
if (supported(initial)) activate(initial);
globalThis.addEventListener("storage", event => {
    if (event.key === preference) announce(stored());
});
