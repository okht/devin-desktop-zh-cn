"""Wire live language changes into the two renderers and the native menu service."""

import hashlib
import json
import re

from src.resources import js_json, read_json


WORKBENCH = "out/vs/workbench/workbench.desktop.main.js"
SESSIONS = "out/vs/sessions/sessions.desktop.main.js"
MAIN = "out/mainImpl.js"
RUNTIME = "out/vs/workbench/devin-live-language.js"
MESSAGES = "out/vs/workbench/devin-live-messages.js"
CHAT = "out/vs/workbench/windsurf-chat-client/index.js"


def read_stock_json(app, rel, sha):
    data = (app / rel).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha:
        raise ValueError("原版编辑器词典校验失败：" + rel)
    return json.loads(data)


def build_messages(app, editor, hashes=None):
    hashes = hashes or {
        "messages": "3d56eff9424d777f4a6c3c0a71f7ef791e4ffa6f5ec3cde44a3c4b5524955507",
        "keys": "b8fb621295ed67e3a6ce89ba07225dfa1d8fe092b2eb83e01965a56a30290626",
    }
    english = read_stock_json(app, "out/nls.messages.json", hashes["messages"])
    keys = read_stock_json(app, "out/nls.keys.json", hashes["keys"])
    translations = json.loads(editor)["contents"]
    chinese = []
    for group, names in keys:
        entries = translations.get(group, {})
        for name in names:
            chinese.append(entries.get(name) or english[len(chinese)])
    if len(chinese) != len(english):
        raise ValueError("两份编辑器词典的条目数不一致。")
    return ("export const messages = " + js_json({"en": english, "zh-cn": chinese}) + ";\n").encode()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("热切换补丁无法定位：" + old[:85])
    return text.replace(old, new, 1)


def label_accessors(data, index, localize):
    """Index entries bind only to the actual module-level NLS functions (see tools/)."""
    pieces = []
    cursor = 0
    for start, size, kind in index:
        pieces.append(data[cursor:start])
        cursor = start + size
        original = data[start:cursor].decode()
        if kind == "field":
            key, call = original.split(":", 1)
            # Some upstream consumers override presentation properties after construction.
            result = (f"get {key}(){{return {call}}},set {key}(value){{"
                      f'Object.defineProperty(this,"{key}",{{value,writable:true,configurable:true,enumerable:true}})}}')
        elif kind == "spread":
            args = original[original.index("("):]
            result = original + ",get value(){return " + localize + args + "}"
        elif kind == "element":
            left, call = original.rsplit("=", 1)
            target, prop = left.rsplit(".", 1)
            ident = int(call.split("(")[1].split(",")[0])
            result = f'__devinBindLabel({target},"{prop}",{ident})'
        else:
            raise ValueError("未知的界面绑定类型：" + kind)
        pieces.append(result.encode())
    pieces.append(data[cursor:])
    return b"".join(pieces).decode()


def renderer(repository, rel, data, bindings=None):
    standard = rel == WORKBENCH
    mode = "workbench" if standard else "sessions"
    localize, desc = ("d", "B") if standard else ("g", "ke")
    cfg = (bindings or {}).get(mode, {})
    localize, desc = cfg.get("nls", (localize, desc))
    code = label_accessors(data, read_json(repository / f"patches/live-{mode}.json"), localize)
    module_path = "./" if standard else "../workbench/"
    imports = ('import {bindLabel as __devinBindLabel, originalMessage as __devinOriginalMessage, onLanguageChange as __devinOnLanguage, '
               'selectLanguage as __devinSelectLanguage} from "' + module_path + 'devin-live-language.js";\n')
    state, captured = ("ws", "XQt") if standard else ("Vh", "Z1n")
    state, captured = cfg.get("platform", (state, captured))
    code = once(code, f"{state}={captured},", f"{state}=globalThis._VSCODE_NLS_LANGUAGE||{captured},")
    marker = f"function r(){{return {state}}}t.value=r;"
    code = once(code, marker, marker + f"__devinOnLanguage(()=>{{{state}=globalThis._VSCODE_NLS_LANGUAGE}});")
    fallback = "o" if standard else "i"
    formatter = "DQt" if standard else "A1n"
    formatter = cfg.get("formatter", formatter)
    start = code.index(f"function {desc}(r,{fallback},...e){{let t;typeof r==")
    end = code.index("}function ", start) + 1
    code = code[:start] + (f'function {desc}(r,{fallback},...e){{return{{get value(){{return '
            f'{localize}(r,{fallback},...e)}},original:{formatter}({fallback},e)}}}}') + code[end:]

    # Invalidate the same caches used for menu registrations, pane titles and settings.
    registry, menu = ("Uxe", "W") if standard else ("Wft", "Pe")
    registry, menu = cfg.get("menus", (registry, menu))
    ready = "this.onDidChangeMenu=this._onDidChangeMenu.event}addCommand(r)"
    code = once(code, ready, "this.onDidChangeMenu=this._onDidChangeMenu.event;"
                "__devinOnLanguage(()=>{for(const id of this._menuItems.keys())"
                f"this._onDidChangeMenu.fire({registry}.for(id));"
                f"this._onDidChangeMenu.fire({registry}.for({menu}.CommandPalette))}})}}addCommand(r)")
    ready = "this.onDidChangeContainerInfo=this._onDidChangeContainerInfo.event;"
    code = once(code, ready, ready + "this._register(__devinOnLanguage(()=>this.updateContainerInfo()));")
    ready = "this.titleLabel=this.createTitleLabel(t);"
    code = once(code, ready, ready + "this._register(__devinOnLanguage(()=>{const active=this.activeComposite;"
                "if(active)this.updateTitle(active.getId(),active.getTitle())}));")
    ready = "this.renderHeaderTitle(e,this.title);"
    code = once(code, ready, ready + """
        const registeredName=()=>this.viewDescriptorService.getViewDescriptorById(this.id)?.name?.value;
        let lastName=registeredName();
        this._register(__devinOnLanguage(()=>{
            const name=registeredName();
            if(name&&lastName&&this.title===lastName)this.updateTitle(name);
            lastName=name;
        }));""")
    ready = "this._register(this.editorService.onDidActiveEditorChange(()=>this.updateStatusBar()))"
    code = once(code, ready, "this._register(__devinOnLanguage(()=>{this.updateStatusBar();this.doRenderNow()}))," + ready)
    start = code.index("getSelectionLabel(e){if(e?.selections)")
    end = code.index("updateStatusBar(){", start)
    selection = code[start:end]
    names = ("Fia", "Bia", "Wia", "Hia") if standard else ("fAc", "vAc", "bAc", "IAc")
    names = cfg.get("selection", names)
    for name, ident in zip(names, cfg.get("selectionIds", (8684, 8683, 8662, 8661))):
        selection = once(selection, "(" + name + ",", f"({localize}({ident},null),")
    code = code[:start] + selection + code[end:]
    ready = "getLanguageName(e){return " + cfg.get("languageNames", "o6" if standard else "qhe") + ".call(this._languages,e)?"
    code = once(code, ready, ready.replace("return ", 'if(e==="plaintext"){const code=globalThis._VSCODE_NLS_LANGUAGE;'
                        'if(code==="zh-cn")return "纯文本";if(code==="en")return "Plain Text"}return '))
    ready = 'this.loginNudge.textContent=(__devinDesktopZhLocale()?"登录到Devin":"Log in to Devin")'
    code = once(code, cfg.get("login", ready), 'this._register(__devinOnLanguage(()=>{this.loginNudge.textContent=__devinDesktopZhLocale()?"登录 Devin":"Log in to Devin"})),'
                + ready.replace("登录到Devin", "登录 Devin"))
    if bindings:
        ready = 'this.changelogNudge.classList.add("dismissible"),'
        code = once(code, ready, ready + '''(()=>{
            const refresh=()=>{const zh=__devinDesktopZhLocale(),text=this.changelogNudge.firstChild;
                if(text?.nodeType===3)text.data=zh?"查看更新日志":"View Changelog";
                a.title=zh?"关闭":"Dismiss";
                this.versionUpdateNudge.textContent=zh?"有可用更新":"Update available"};
            refresh();this._register(__devinOnLanguage(refresh));})(),''')
    ready = "update(e){if(this.label.showProgress=e.showProgress??!1,"
    code = once(code, ready, """update(e){
        if(this.container.id==="codeium.windsurf.settings"){
            if(!this.liveLoginListener)this.liveLoginListener=this._register(__devinOnLanguage(()=>this.update(this.liveLoginEntry)));
            this.liveLoginEntry=e;
            if(e.text==="Devin: Login"&&__devinDesktopZhLocale()){
                e={...e,text:"登录 Devin"};
                if(e.ariaLabel==="Devin: Login, Click to log in to Devin")e.ariaLabel="登录 Devin";
                if(e.tooltip==="Click to log in to Devin")e.tooltip="登录 Devin";
            }
        }
        if(this.label.showProgress=e.showProgress??!1,""")

    if standard:
        # Agent menu registration passes translated primitives through helper functions.
        # Give the menu builder the original message identity for subsequent renders.
        begin, end = code.index(cfg.get("menuStart", 'hjt(aB,"File"')), code.index(cfg.get("menuEnd", 'var Sns="devinPreview"'))
        block = code[begin:end]
        block = re.sub(r'(?<!return )\bd\((258[2-8]\d),null\)', r'__devinMenuTitle(\1)', block)
        code = code[:begin] + block + code[end:]
        code += '\nfunction __devinMenuTitle(id){return {get value(){return d(id,null)},original:__devinOriginalMessage(id)}}\n'
        menu_when = cfg.get("menuWhen", "Pu")
        code = once(code, "original:o,mnemonicTitle:e},when:" + menu_when, "original:o,get mnemonicTitle(){return e.value}},when:" + menu_when)
        code = once(code, "y=j.any(v.onDidChangeWindsurfUserSettings,", "y=j.any(__devinOnLanguage,v.onDidChangeWindsurfUserSettings,")
        if not bindings:
            start = code.index(" async applyDevinDisplayLanguage(language){")
            end = code.index("async validateLocaleFile(){", start)
            code = code[:start] + " applyDevinDisplayLanguage(language){return __devinSelectLanguage(language,this)}" + code[end:]
            code = once(code, ",__devinReflectNativeChoice(o),!0):!1}async setLocale", ",!0):!1}async setLocale")
        else:
            ready = "async validateLocaleFile(){"
            code = once(code, ready, "applyDevinDisplayLanguage(language){return __devinSelectLanguage(language,this)}" + ready)
            ready = "async install(e){let t=this.shellHost;await t.warmUp();"
            bridge = ("globalThis.__devinNativeDisplayPreference=language=>this.instantiationService.invokeFunction("
                      "accessor=>accessor.get(" + cfg["localeService"] + ").applyDevinDisplayLanguage(language));"
                      "const pending=globalThis.__devinPendingDisplayPreference;"
                      "if(pending){globalThis.__devinPendingDisplayPreference=null;void globalThis.__devinNativeDisplayPreference(pending)}")
            code = once(code, ready, ready.replace("{let t=", "{" + bridge + "let t="))
    if standard or bindings:
        code = once(code, "await this.writeLocaleValue(t),await this.hostService.restart()",
                    "await this.writeLocaleValue(t),__devinReflectNativeChoice(t),await this.hostService.restart()")
        current = cfg.get("localeState", "EI") + ".isDefaultVariant()"
        code = once(code, "await this.writeLocaleValue(void 0)," + current,
                    "await this.writeLocaleValue(void 0),__devinReflectNativeChoice(void 0)," + current)
    service, params, inject, token = cfg.get("injection", ("R7t", "o,e,t,i,n,s,a,c,l,u,p,h", "m(11,ht)", "m(12,oXi)") if standard
                                            else ("Csn", "i,e,t,n,o,s,a,u,d,p,h,f", "b(11,Zo)", "b(12,ZTo)"))
    pick = "async setLocale(" + ("o" if standard else "i") + ",e=!1){let t=" + ("o" if standard else "i") + ".id;"
    ready = service + "=class{constructor(" + params + "){this.jsonEditingService="
    code = once(code, ready, ready.replace("){this.", ",liveMenubar){this.liveMenubar=liveMenubar;this."))
    code = once(code, inject + "]," + service + ")", inject + "," + token + "]," + service + ")")
    code = once(code, pick, pick + 'if(t==="en"||t==="zh-cn")return __devinSelectLanguage(t,this);')
    return (imports + code).encode()


def main_process(data):
    source = data.decode()
    start = "async updateMenubar(e,t){this.logService.trace("
    method = """async setLiveDisplayLocale(id) {
        if (id !== "en" && id !== "zh-cn") throw new RangeError("Unsupported display language");
        const revision = (this.liveLocaleRevision || 0) + 1;
        this.liveLocaleRevision = revision;
        const { messages } = await import("./vs/workbench/devin-live-messages.js");
        if (revision !== this.liveLocaleRevision) return;
        globalThis._VSCODE_NLS_MESSAGES = messages[id];
        globalThis._VSCODE_NLS_LANGUAGE = id;
        (await this.menubar).scheduleUpdateMenu();
    }"""
    return once(source, start, method + start).encode()


def react_renderer(repository, data, embedded, bindings=None, sessions=False):
    code = data.decode()
    if embedded:
        start = "dj.prototype.render=dx.prototype.render=function(e){"
        react, shared, outside = "o", "O", "rC"
    else:
        start = "Rp.prototype.render=Lp.prototype.render=function(e){"
        react, shared, outside = "n", "P", "As"
    arg = "e"
    if bindings:
        target = "sessionsReact" if sessions else "embeddedReact" if embedded else "hostReact"
        start, arg, react, shared, outside = bindings[target]
    wrapper = f"function __devinWrapRoot(child){{return __devinWrapReactRoot({react},child,()=>{shared}.H!=null&&{shared}.H!=={outside})}}"
    code = once(code, start, wrapper + start + f"{arg}=__devinWrapRoot({arg});")
    # A queued event from another window can be older than its current preference.
    old = 'if(e.key==="devin-desktop-display-language-v1")apply(e.newValue)'
    if not bindings:
        code = once(code, old, 'if(e.key==="devin-desktop-display-language-v1")apply(localStorage.getItem(e.key))')
    return code.encode() + b"\n" + (repository / "src/react-language.js").read_bytes()
