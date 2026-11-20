import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { after, test } from "node:test";
import feGate from "./fe-gate.ts";

process.env.FE_GATE_NO_FLUSH = "1";
process.env.FE_GATE_STATE_DIR = fs.mkdtempSync(path.join(os.tmpdir(), "fe-gate-state-"));

type Handler = (event: unknown, ctx: unknown) => unknown;

interface Denial {
  block: boolean;
  reason: string;
}

interface ModificationView {
  texts: string[];
  isError: boolean;
}

interface EditEvent {
  type?: string;
  parentToolCallId?: string;
  toolName: string;
  input: { path: string; old_string?: string; new_string?: string };
}

const handlers: Record<string, Handler> = {};
feGate({
  on(event: string, handler: Handler) {
    handlers[event] = handler;
  },
});

const root = fs.mkdtempSync(path.join(os.tmpdir(), "fe-gate-test-"));
after(() => {
  fs.rmSync(root, { recursive: true, force: true });
  fs.rmSync(process.env.FE_GATE_STATE_DIR ?? "", { recursive: true, force: true });
});

function handlerFor(name: string): Handler {
  const handler = handlers[name];
  assert.ok(handler, `missing handler for ${name}`);
  return handler;
}

function makeCtx(entries: unknown[]): unknown {
  return { cwd: root, sessionManager: { getEntries: () => entries } };
}

function makeStatusCtx(entries: unknown[], calls: [string, string | undefined][]): unknown {
  return {
    cwd: root,
    sessionManager: { getEntries: () => entries },
    ui: { setStatus: (key: string, text: string | undefined) => calls.push([key, text]) },
  };
}

function editEvent(filePath: string, oldString: string, newString: string): EditEvent {
  return { type: "tool_call", toolName: "edit", input: { path: filePath, old_string: oldString, new_string: newString } };
}

function readDenial(result: unknown): Denial | undefined {
  if (typeof result !== "object" || result === null) return undefined;
  if (!("block" in result) || !("reason" in result)) return undefined;
  if (result.block !== true || typeof result.reason !== "string") return undefined;
  return { block: true, reason: result.reason };
}

function readModification(result: unknown): ModificationView | undefined {
  if (typeof result !== "object" || result === null) return undefined;
  if (!("content" in result) || !Array.isArray(result.content)) return undefined;
  const texts: string[] = [];
  for (const block of result.content) {
    if (typeof block === "object" && block !== null && "text" in block && typeof block.text === "string") {
      texts.push(block.text);
    }
  }
  return { texts, isError: "isError" in result && result.isError === true };
}

const codeChange = ["const a = 1;", "const a = 2;"] as const;

test("allows a gated edit when the transcript has owner and decision", async () => {
  const entries = [
    { type: "message", message: { role: "user", content: "add a checkout button" } },
    {
      type: "message",
      message: { role: "assistant", content: [{ type: "text", text: "Runtime owner: X.tsx\nDecision: reuse" }] },
    },
  ];
  const result = await handlerFor("tool_call")(editEvent("src/X.tsx", ...codeChange), makeCtx(entries));
  assert.equal(result, undefined);
});

test("denies a gated edit when the transcript is empty", async () => {
  const result = await handlerFor("tool_call")(editEvent("src/X.tsx", ...codeChange), makeCtx([]));
  const denial = readDenial(result);
  assert.ok(denial, `expected a denial, got ${JSON.stringify(result)}`);
  assert.equal(denial.block, true);
  assert.match(denial.reason, /Runtime owner/);
});

test("passes files the gate does not cover", async () => {
  const result = await handlerFor("tool_call")(editEvent("notes.md", ...codeChange), makeCtx([]));
  assert.equal(result, undefined);
});

test("ignores tools outside the gate", async () => {
  const event = { type: "tool_call", toolName: "bash", input: { command: "ls" } };
  const result = await handlerFor("tool_call")(event, makeCtx([]));
  assert.equal(result, undefined);
});

test("denies a bash command that writes a frontend file", async () => {
  const event = { type: "tool_call", toolName: "bash", input: { command: "git show HEAD:src/X.tsx | sed 's/a//' > src/X.tsx" } };
  const denial = readDenial(await handlerFor("tool_call")(event, makeCtx([])));
  assert.ok(denial, "expected a denial for a redirect into a .tsx file");
  assert.match(denial.reason, /Bash command that writes a frontend file/);
});

test("allows a bash command that writes a frontend file when the labels are there", async () => {
  const entries = [
    { type: "message", message: { role: "user", content: "drop the gutter" } },
    { type: "message", message: { role: "assistant", content: [{ type: "text", text: "Runtime owner: Layout\nDecision: reuse" }] } },
  ];
  const event = { type: "tool_call", toolName: "bash", input: { command: "sed -i 's/a/b/' src/X.tsx" } };
  assert.equal(await handlerFor("tool_call")(event, makeCtx(entries)), undefined);
});

test("allows a gated edit after an echo declaration in the same session", async () => {
  const entries = [{ type: "message", message: { role: "user", content: "add a column to DA1020" } }];
  const ctx = (sessionId: string): unknown => ({
    cwd: root,
    sessionManager: { getEntries: () => entries, getSessionId: () => sessionId },
  });
  const declare = { type: "tool_call", toolName: "bash", input: { command: 'echo "Runtime owner: Da1020Columns" "Decision: reuse"' } };
  assert.equal(await handlerFor("tool_call")(declare, ctx("omp-a")), undefined);
  assert.equal(await handlerFor("tool_call")(editEvent("src/X.tsx", ...codeChange), ctx("omp-a")), undefined);
  const other = readDenial(await handlerFor("tool_call")(editEvent("src/X.tsx", ...codeChange), ctx("omp-b")));
  assert.ok(other, "another session must not see the declaration");
  assert.match(other.reason, /^Blocked\. Run this Bash command/);
});

test("with a session id, reply-text labels do not open a gated edit", async () => {
  const entries = [
    { type: "message", message: { role: "user", content: "add a checkout button" } },
    { type: "message", message: { role: "assistant", content: [{ type: "text", text: "Runtime owner: X.tsx\nDecision: reuse" }] } },
  ];
  const ctx = { cwd: root, sessionManager: { getEntries: () => entries, getSessionId: () => "omp-reply" } };
  const denial = readDenial(await handlerFor("tool_call")(editEvent("src/X.tsx", ...codeChange), ctx));
  assert.ok(denial, "reply-text labels must not count when the session has an id");
  assert.match(denial.reason, /Labels in the reply text, in thinking, or in prose do not count/);
});

test("leaves a bash tool result alone", async () => {
  const event = { type: "tool_result", toolName: "bash", input: { command: "sed -i 's/a/b/' src/X.tsx" }, content: [] };
  assert.equal(await handlerFor("tool_result")(event, makeCtx([])), undefined);
});

test("ignores nested tool calls", async () => {
  const event = { ...editEvent("src/X.tsx", ...codeChange), parentToolCallId: "x/1" };
  const result = await handlerFor("tool_call")(event, makeCtx([]));
  assert.equal(result, undefined);
});

test("keeps the wording bypass for a real file", async () => {
  const buttonPath = path.join(root, "src/Button.tsx");
  fs.mkdirSync(path.dirname(buttonPath), { recursive: true });
  fs.writeFileSync(buttonPath, 'const label = "Submit";\n');
  const result = await handlerFor("tool_call")(
    editEvent(buttonPath, 'const label = "Submit";', 'const label = "Send";'),
    makeCtx([]),
  );
  assert.equal(result, undefined);
});

test("keeps the wording bypass in a .js file", async () => {
  const filePath = path.join(root, "src/Label.js");
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, "const label = 'Save';\n");
  const result = await handlerFor("tool_call")(editEvent(filePath, "const label = 'Save';", "const label = 'Store';"), makeCtx([]));
  assert.equal(result, undefined);
});

test("keeps the wording bypass when the host names the sides oldText/newText", async () => {
  const filePath = path.join(root, "src/Alt.tsx");
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, 'const label = "Submit";\n');
  const event = {
    type: "tool_call",
    toolName: "edit",
    input: { path: filePath, oldText: 'const label = "Submit";', newText: 'const label = "Send";' },
  };
  const result = await handlerFor("tool_call")(event, makeCtx([]));
  assert.equal(result, undefined);
});

test("keeps the wording bypass for an edits array", async () => {
  const filePath = path.join(root, "src/Multi.tsx");
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, 'const label = "Submit";\nconst title = "Save";\n');
  const event = {
    type: "tool_call",
    toolName: "edit",
    input: {
      path: filePath,
      edits: [
        { old_string: 'const label = "Submit";', new_string: 'const label = "Send";' },
        { old_string: 'const title = "Save";', new_string: 'const title = "Store";' },
      ],
    },
  };
  const result = await handlerFor("tool_call")(event, makeCtx([]));
  assert.equal(result, undefined);
});

test("keeps the wording bypass for ast_edit with old and new strings", async () => {
  const filePath = path.join(root, "src/Ast.tsx");
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, 'const label = "Submit";\n');
  const event = {
    type: "tool_call",
    toolName: "ast_edit",
    input: { path: filePath, old_string: 'const label = "Submit";', new_string: 'const label = "Send";' },
  };
  const result = await handlerFor("tool_call")(event, makeCtx([]));
  assert.equal(result, undefined);
});

test("keeps the wording bypass for ast_edit with an edits array", async () => {
  const filePath = path.join(root, "src/AstMulti.tsx");
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, 'const label = "Submit";\nconst title = "Save";\n');
  const event = {
    type: "tool_call",
    toolName: "ast_edit",
    input: {
      path: filePath,
      edits: [
        { old_string: 'const label = "Submit";', new_string: 'const label = "Send";' },
        { old_string: 'const title = "Save";', new_string: 'const title = "Store";' },
      ],
    },
  };
  const result = await handlerFor("tool_call")(event, makeCtx([]));
  assert.equal(result, undefined);
});

test("keeps the wording bypass for search/replace", async () => {
  const filePath = path.join(root, "src/Search.tsx");
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, 'const label = "Submit";\n');
  const event = {
    type: "tool_call",
    toolName: "edit",
    input: { path: filePath, search: 'const label = "Submit";', replace: 'const label = "Send";' },
  };
  const result = await handlerFor("tool_call")(event, makeCtx([]));
  assert.equal(result, undefined);
});

test("blocks a behavior change in a .js file", async () => {
  const filePath = path.join(root, "src/Api.js");
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, "fetch('/api/v1');\n");
  const result = await handlerFor("tool_call")(editEvent(filePath, "fetch('/api/v1');", "fetch('/api/v2');"), makeCtx([]));
  const denial = readDenial(result);
  assert.ok(denial, `expected a denial, got ${JSON.stringify(result)}`);
});

test("passes a .ts edit because the gate does not cover it", async () => {
  const result = await handlerFor("tool_call")(editEvent("src/Util.ts", ...codeChange), makeCtx([]));
  assert.equal(result, undefined);
});

test("blocks a write because there is no old source to compare", async () => {
  const event = { type: "tool_call", toolName: "write", input: { path: "src/New.tsx", content: "const a = 1;\n" } };
  const result = await handlerFor("tool_call")(event, makeCtx([]));
  const denial = readDenial(result);
  assert.ok(denial, `expected a denial, got ${JSON.stringify(result)}`);
});

test("blocks an ast_edit with no old and new strings", async () => {
  const event = { type: "tool_call", toolName: "ast_edit", input: { path: "src/New.tsx" } };
  const result = await handlerFor("tool_call")(event, makeCtx([]));
  const denial = readDenial(result);
  assert.ok(denial, `expected a denial, got ${JSON.stringify(result)}`);
});

test("blocks a .vue edit because its dialect has no wording exemption", async () => {
  const result = await handlerFor("tool_call")(editEvent("src/View.vue", ...codeChange), makeCtx([]));
  const denial = readDenial(result);
  assert.ok(denial, `expected a denial, got ${JSON.stringify(result)}`);
});

test("reports conflict markers left in the written file", async () => {
  const conflictPath = path.join(root, "Conflicted.tsx");
  fs.writeFileSync(
    conflictPath,
    "<<<<<<< HEAD\nconst a = 1;\n=======\nconst a = 2;\n>>>>>>> branch\n",
  );
  const event = {
    type: "tool_result",
    toolCallId: "r1",
    toolName: "edit",
    input: { path: conflictPath },
    content: [{ type: "text", text: "Successfully replaced 1 block(s)." }],
    isError: false,
  };
  const result = await handlerFor("tool_result")(event, makeCtx([]));
  const view = readModification(result);
  assert.ok(view, `expected a result modification, got ${JSON.stringify(result)}`);
  assert.match(view.texts[0] ?? "", /^Conflict markers remain/);
  assert.equal(view.isError, true);
  assert.ok(view.texts.includes("Successfully replaced 1 block(s)."), "keeps the tool's own result");
});

test("leaves a clean written file untouched", async () => {
  const cleanPath = path.join(root, "Clean.tsx");
  fs.writeFileSync(cleanPath, "export const A = () => null;\n");
  const event = {
    type: "tool_result",
    toolCallId: "r2",
    toolName: "write",
    input: { path: cleanPath, content: "export const A = () => null;\n" },
    content: [],
    isError: false,
  };
  const result = await handlerFor("tool_result")(event, makeCtx([]));
  assert.equal(result, undefined);
});

test("shows a blocked verdict in the status line", async () => {
  const calls: [string, string | undefined][] = [];
  await handlerFor("tool_call")(editEvent("src/X.tsx", ...codeChange), makeStatusCtx([], calls));
  assert.equal(calls.length, 1);
  assert.equal(calls[0]?.[0], "fe-kit");
  assert.match(String(calls[0]?.[1]), /● .*fe-kit: ⛔ blocked/);
});

test("clears the verdict to ok when an edit is allowed", async () => {
  const calls: [string, string | undefined][] = [];
  const entries = [
    { type: "message", message: { role: "user", content: "add a checkout button" } },
    {
      type: "message",
      message: { role: "assistant", content: [{ type: "text", text: "Runtime owner: X.tsx\nDecision: reuse" }] },
    },
  ];
  await handlerFor("tool_call")(editEvent("src/X.tsx", ...codeChange), makeStatusCtx(entries, calls));
  assert.equal(calls.length, 1);
  assert.match(String(calls[0]?.[1]), /○ .*fe-kit: ✓ ok/);
});

test("resets the verdict when the session starts", async () => {
  const calls: [string, string | undefined][] = [];
  await handlerFor("session_start")({}, makeStatusCtx([], calls));
  assert.equal(calls.length, 1);
  assert.match(String(calls[0]?.[1]), /fe-kit: ✓ ok/);
});

test("leaves the status line alone for tools outside the gate", async () => {
  const calls: [string, string | undefined][] = [];
  const event = { type: "tool_call", toolName: "bash", input: { command: "ls" } };
  await handlerFor("tool_call")(event, makeStatusCtx([], calls));
  assert.deepEqual(calls, []);
});

test("shows the rules verdict when the prompt matches an intent", async () => {
  const calls: [string, string | undefined][] = [];
  await handlerFor("before_agent_start")(
    { type: "before_agent_start", prompt: "review diff trước commit giúp tôi" },
    makeStatusCtx([], calls),
  );
  assert.equal(calls.length, 1);
  assert.match(String(calls[0]?.[1]), /⚡ .*rules/);
});

test("leaves the status line alone for a prompt with no intent", async () => {
  const calls: [string, string | undefined][] = [];
  await handlerFor("before_agent_start")({ type: "before_agent_start", prompt: "hello" }, makeStatusCtx([], calls));
  assert.deepEqual(calls, []);
});
