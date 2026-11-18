// Maintainer tool. Run on the zh.1 workbench and sessions bundles.
// NODE_PATH may point to a directory containing acorn 8 and eslint-scope 8.
const fs = require("node:fs");
const assert = require("node:assert/strict");
const acorn = require("acorn");
const scopes = require("eslint-scope");

const [source, destination, localize, descriptor] = process.argv.slice(2);
const code = fs.readFileSync(source, "utf8");
const ast = acorn.parse(code, { ecmaVersion: "latest", sourceType: "module", ranges: true });
const scope = scopes.analyze(ast, { ecmaVersion: 2024, sourceType: "module", ignoreEval: true });
const moduleScope = scope.scopes.find(item => item.type === "module");
function references(name) {
    return new Set(moduleScope.set.get(name).references.map(ref => ref.identifier));
}
const messages = references(localize);
const descriptors = references(descriptor);
const fields = new Set(["title", "mnemonicTitle", "label", "shortTitle", "name", "ariaLabel",
    "description", "category", "tooltip", "placeholder"]);
const properties = new Set(["textContent", "innerText", "placeholder", "ariaLabel"]);
const edits = [];

function isMessage(node, refs) {
    return node?.type === "CallExpression" && refs.has(node.callee) &&
        node.arguments.length === 2 && Number.isInteger(node.arguments[0].value);
}
function visit(node, parent) {
    if (node.type === "Property" && node.kind === "init" && !node.computed &&
        fields.has(node.key.name) && isMessage(node.value, messages) && node.value.arguments[1].value === null) {
        edits.push([node.start, node.end, "field"]);
    } else if (node.type === "SpreadElement" && parent.type === "ObjectExpression" &&
        isMessage(node.argument, descriptors) && node.argument.arguments[1].type === "Literal") {
        edits.push([node.start, node.end, "spread"]);
    } else if (node.type === "AssignmentExpression" && node.operator === "=" &&
        node.left.type === "MemberExpression" && !node.left.computed && properties.has(node.left.property.name) &&
        ["Identifier", "MemberExpression", "ThisExpression"].includes(node.left.object.type) &&
        isMessage(node.right, messages) && node.right.arguments[1].value === null) {
        edits.push([node.start, node.end, "element"]);
    }
    for (const value of Object.values(node)) {
        if (Array.isArray(value)) {
            for (const child of value) if (child?.type) visit(child, node);
        } else if (value?.type) visit(value, node);
    }
}
visit(ast, null);
edits.sort((a, b) => a[0] - b[0]);
// Python applies the index to UTF-8 bytes. JS AST positions count UTF-16 code units.
let cursor = 0, offset = 0;
const rows = edits.map(([start, end, kind]) => {
    assert(start >= cursor, "overlapping live label edits");
    offset += Buffer.byteLength(code.slice(cursor, start));
    const size = Buffer.byteLength(code.slice(start, end));
    cursor = end;
    const row = [offset, size, kind];
    offset += size;
    return row;
});
fs.writeFileSync(destination, "[\n" + rows.map(row => JSON.stringify(row)).join(",\n") + "\n]\n");
console.log("Indexed", rows.length, "localization call sites.");
