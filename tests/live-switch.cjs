// Run against an installation of this release: node tests/live-switch.cjs <resources/app>
// Only isolated in-memory preferences and documents are used.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");
const app = path.resolve(process.argv[2]);
const current = JSON.parse(fs.readFileSync(path.join(app, "product.json"))).windsurfVersion === "3.14.30819";
const workbench = path.join(app, "out/vs/workbench");
const target = new EventTarget();
let phase = 0;
let selection = "en";
const original = new Map();
Object.assign(globalThis, {
    document: {documentElement: {lang: "en"}},
    localStorage: {getItem: k => original.get(k) ?? null, setItem: (k, v) => original.set(k, v)},
    addEventListener: target.addEventListener.bind(target),
    dispatchEvent: target.dispatchEvent.bind(target),
    _VSCODE_NLS_LANGUAGE: "en",
});

async function main() {
    const runtime = await import(pathToFileURL(path.join(workbench, "devin-live-language.js")));
    const {messages} = await import(pathToFileURL(path.join(workbench, "devin-live-messages.js")));
    assert.deepEqual(messages.en, JSON.parse(fs.readFileSync(path.join(app, "out/nls.messages.json"))));
    assert.equal(messages.en.length, messages["zh-cn"].length);
    globalThis._VSCODE_NLS_MESSAGES = messages.en;
    const source = fs.readFileSync(path.join(workbench, "workbench.desktop.main.js"), "utf8");
    const serviceName = current ? "B7t" : "R7t";
    const before = serviceName + "=class", after = ";" + serviceName + "=I(";
    assert(source.includes(before) && source.includes(after));
    const definition = source.slice(source.indexOf(before) + serviceName.length + 1, source.indexOf(after));
    const mainCode = fs.readFileSync(path.join(app, "out/mainImpl.js"), "utf8");
    const method = mainCode.slice(mainCode.indexOf("async setLiveDisplayLocale(id)"), mainCode.indexOf("async updateMenubar(e,t)"));
    const menuContext = { dictionary: messages, schedule: 0 };
    const menu = vm.runInNewContext("({" + method.replace('await import("./vs/workbench/devin-live-messages.js")', "({messages:dictionary})") + "})", menuContext);
    menu.menubar = {scheduleUpdateMenu() { menuContext.schedule++; }};
    const localeErrors = [];
    const serviceClass = vm.runInNewContext("(" + definition + ")", {
        __devinSelectLanguage: runtime.selectLanguage, yM: JSON.parse, IM: JSON.parse
    });
    const editing = { async write(uri, entries) {
        assert.equal(uri, "fixture"); assert.equal(entries[0].path.join("."), "locale");
        await Promise.resolve(); selection = entries[0].value;
    }};
    const service = new serviceClass(editing, {argvResource: "fixture"}, {error: e => localeErrors.push(e)},
        null, null, null, null, {read: async () => ({value: "{}"})}, null,
        {confirm() { throw Error("Unexpected restart prompt"); }},
        {restart() { throw Error("Unexpected process restart"); }}, {}, menu);
    const label = {nodeType: 1, textContent: "", childElementCount: 0};
    runtime.bindLabel(label, "textContent", current ? 25834 : 25830);
    const changed = runtime.onLanguageChange(() => { phase++; });
    const file = current ? "chunk-entry-host-editor-mode-menu-BWLlgqZu.js" : "entry-host-editor-mode-menu-By4_JXI5.js";
    const host = await import(pathToFileURL(path.join(workbench, "devin-webapp-host/assets", file)));
    (current ? host.nd : host.wu)();
    const engine = (current ? host.td : host.Cu)();
    if (current) assert.deepEqual(host.pd.map(item => item.code), ["en", "zh-CN", "ja", "pt", "es", "de"]);
    const englishBundle = JSON.stringify(engine.getResourceBundle("en", "translation"));
    async function check(id, caption, labelText) {
        await service.setLocale({id, label: id});
        for (let n = 0; engine.t("nav.newSession") !== caption && n < 20; n++) {
            await new Promise(resolve => setTimeout(resolve, 1));
        }
        assert.equal(engine.t("nav.newSession"), caption);
        assert.equal(selection, id);
        assert.equal(menuContext._VSCODE_NLS_LANGUAGE, id);
        assert.equal(label.textContent, labelText);
        assert.equal(globalThis._VSCODE_NLS_LANGUAGE, id);
        assert.equal(document.documentElement.lang, id === "en" ? "en" : "zh-Hans");
    }
    await check("zh-cn", "新建会话", "文件(&&F)");
    await check("en", "New session", "&&File");
    assert.equal(phase, 2);
    await Promise.all([service.applyDevinDisplayLanguage("zh-CN"), service.applyDevinDisplayLanguage("en")]);
    assert.equal(selection, "en");
    assert.equal(menuContext._VSCODE_NLS_LANGUAGE, "en");
    label.textContent = "My draft: File";
    await service.applyDevinDisplayLanguage("zh-CN");
    assert.equal(label.textContent, "My draft: File");
    assert.equal(JSON.stringify(engine.getResourceBundle("en", "translation")), englishBundle);
    assert.deepEqual(localeErrors, []);
    assert(menuContext.schedule >= 3);
    changed.dispose();
    console.log("Both language entry points passed, including persistence, fast reversals, native menus, original English and user text.");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
