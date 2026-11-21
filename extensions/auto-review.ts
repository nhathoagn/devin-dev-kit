interface ExtensionAPI {
  on(
    event: "tool_result" | "session_start" | "before_agent_start",
    handler: (event: ReviewEvent, ctx: ReviewCtx) => unknown,
  ): void;
}

interface ReviewCtx {
  cwd?: string;
  ui?: { setStatus?: (key: string, text: string | undefined) => void };
}

interface ReviewEvent {
  type?: string;
  parentToolCallId?: string;
  toolName?: string;
  prompt?: unknown;
  input?: unknown;
  content?: unknown;
  structuredContent?: unknown;
}

interface ResultModification {
  content: unknown[];
  isError?: boolean;
  structuredContent?: unknown;
}

const EDIT_TOOLS = new Set(["edit", "write", "ast_edit"]);
const NOTE_PREFIX = "[auto-review]";

export default function (pi: ExtensionAPI): void {
  let pendingPaths = new Set<string>();

  pi.on("tool_result", (event: ReviewEvent): ResultModification | undefined => {
    if (event.parentToolCallId || !EDIT_TOOLS.has(event.toolName ?? "")) return undefined;

    const path = extractPath(event.input);
    if (path !== undefined) pendingPaths.add(path);

    const text = reviewInstruction();
    const original: unknown[] = Array.isArray(event.content) ? event.content : [];
    const modification: ResultModification = { content: [...original, { type: "text", text }] };
    if (event.structuredContent !== undefined) modification.structuredContent = event.structuredContent;
    return modification;
  });

  pi.on("before_agent_start", (event: ReviewEvent): void => {
    const prompt = typeof event.prompt === "string" ? event.prompt : "";
    if (!prompt.startsWith(NOTE_PREFIX) || pendingPaths.size === 0) return;

    const paths = [...pendingPaths].join(", ");
    pendingPaths = new Set<string>();
    event.prompt = `${prompt}\nFiles edited since last review: ${paths}`;
  });

  pi.on("session_start", (): void => {
    pendingPaths = new Set<string>();
  });
}

function extractPath(input: unknown): string | undefined {
  if (typeof input !== "object" || input === null) return undefined;
  const record = input as Record<string, unknown>;
  const raw = record.path ?? record.file_path ?? record.filePath;
  return typeof raw === "string" && raw.length > 0 ? raw : undefined;
}

function reviewInstruction(): string {
  return [
    `${NOTE_PREFIX} A file was just edited. Before you answer the user, run the lens fan-out review on the diff of the changed file(s):`,
    "1. Get the diff of the changed file(s).",
    "2. Run `scripts/review_lenses.py list` from the fe-kit plugin folder and spawn one fresh reviewer per lens, in parallel — each task carries the diff range, `skill://fe-kit/playbooks/review-diff.md`, and `--lens <name>`. On omp use a task agent per lens; on Claude Code use `fe-kit:reviewer`; on Devin spawn `fe-kit:reviewer` once per lens.",
    "3. Merge the reports with `scripts/review_packages.py merge`, fix every merged finding once, then send the fix to one fresh reviewer that checks each finding at HEAD.",
    "If the edit was a wording/style-only change (no new state, prop, branch, call, or value), you may skip the reviewers but say so in one line.",
  ].join("\n");
}
