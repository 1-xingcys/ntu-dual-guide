"use client";

import { useEffect, useRef, useState } from "react";
import { streamSse, type SseEvent } from "@/lib/sse";

type Stage = "retrieving" | "retrieved" | "generating" | "done" | "error";

type ChunkSummary = {
  chunk_id: string;
  score: number;
  title: string;
  source_id: string;
};

type Citation = {
  index: number;
  chunk_id: string;
  source_id: string;
  title: string;
  chunk_title: string;
  source_path: string | null;
  score: number;
};

type FinalAnswer = {
  answer: string;
  status: string;
  model: string;
  citations: Citation[];
};

type AssistantTurn = {
  id: string;
  question: string;
  stage: Stage;
  retrievedCount: number | null;
  retrievedChunks: ChunkSummary[];
  reasoningText: string;
  answerText: string;
  final: FinalAnswer | null;
  errorMessage: string | null;
};

export default function Home() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<AssistantTurn[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [turns]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = question.trim();
    if (!text || isStreaming) return;

    const turnId = crypto.randomUUID();
    const initial: AssistantTurn = {
      id: turnId,
      question: text,
      stage: "retrieving",
      retrievedCount: null,
      retrievedChunks: [],
      reasoningText: "",
      answerText: "",
      final: null,
      errorMessage: null,
    };
    setTurns((prev) => [...prev, initial]);
    setQuestion("");
    setIsStreaming(true);

    const update = (patch: Partial<AssistantTurn>) =>
      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, ...patch } : t)),
      );

    try {
      const stream = streamSse("/api/v1/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      let answerBuffer = "";
      let reasoningBuffer = "";
      for await (const evt of stream) {
        applyEvent(
          evt,
          update,
          (delta) => {
            answerBuffer += delta;
            update({ answerText: answerBuffer });
          },
          (delta) => {
            reasoningBuffer += delta;
            update({ reasoningText: reasoningBuffer });
          },
        );
        if (evt.event === "done" || evt.event === "error") break;
      }
    } catch (err) {
      update({
        stage: "error",
        errorMessage: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setIsStreaming(false);
    }
  }

  const isEmpty = turns.length === 0;

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  }

  return (
    <main className="mx-auto flex h-screen w-full min-w-[720px] max-w-4xl flex-col p-6 font-sans">
      <h1 className="mb-4 text-xl font-semibold">NTU Dual Guide</h1>

      <div ref={scrollRef} className="flex-1 space-y-6 overflow-y-auto pr-2">
        {isEmpty && (
          <p className="mt-12 text-center text-sm text-zinc-500">
            問一個關於台大資工 / 經濟雙主修的問題試試。
          </p>
        )}
        {turns.map((turn) => (
          <TurnView key={turn.id} turn={turn} />
        ))}
      </div>

      <form
        onSubmit={handleSubmit}
        className="mt-4 flex items-end gap-2 border-t border-zinc-200 pt-4 dark:border-zinc-800"
      >
        <textarea
          className="max-h-60 min-h-[2.5rem] flex-1 resize-none rounded border border-zinc-300 px-3 py-2 text-sm leading-relaxed [field-sizing:content] focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
          placeholder="輸入問題..."
          rows={1}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          autoFocus
        />
        <button
          type="submit"
          disabled={isStreaming || !question.trim()}
          aria-label={isStreaming ? "生成中" : "送出"}
          title={isStreaming ? "生成中..." : "送出 (Enter)"}
          className="flex h-10 w-10 items-center justify-center rounded bg-black text-white disabled:opacity-40 dark:bg-white dark:text-black"
        >
          {isStreaming ? <SpinnerIcon /> : <SendIcon />}
        </button>
      </form>

      <footer className="mt-3 text-center text-xs text-zinc-400 dark:text-zinc-600">
        NTU Dual Guide · 回答僅供參考，請以系所公告為準
      </footer>
    </main>
  );
}

function SendIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 19V5" />
      <path d="M5 12l7-7 7 7" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      className="animate-spin"
      aria-hidden="true"
    >
      <path d="M12 3a9 9 0 0 1 9 9" opacity="1" />
      <path d="M3 12a9 9 0 0 0 9 9" opacity="0.3" />
    </svg>
  );
}

function applyEvent(
  evt: SseEvent,
  update: (patch: Partial<AssistantTurn>) => void,
  appendToken: (delta: string) => void,
  appendReasoning: (delta: string) => void,
) {
  const data = evt.data as Record<string, unknown>;
  switch (evt.event) {
    case "stage": {
      const stage = data.stage as Stage;
      update({ stage });
      return;
    }
    case "retrieved": {
      update({
        stage: "retrieved",
        retrievedCount: (data.count as number) ?? 0,
        retrievedChunks: (data.chunks as ChunkSummary[]) ?? [],
      });
      return;
    }
    case "reasoning": {
      const delta = (data.delta as string) ?? "";
      if (delta) appendReasoning(delta);
      return;
    }
    case "token": {
      const delta = (data.delta as string) ?? "";
      if (delta) appendToken(delta);
      return;
    }
    case "final": {
      update({ final: data as unknown as FinalAnswer });
      return;
    }
    case "done": {
      update({ stage: "done" });
      return;
    }
    case "error": {
      update({
        stage: "error",
        errorMessage: (data.message as string) ?? "unknown error",
      });
      return;
    }
  }
}

function TurnView({ turn }: { turn: AssistantTurn }) {
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl bg-blue-600 px-4 py-2 text-sm text-white">
          {turn.question}
        </div>
      </div>

      <div className="rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <Timeline turn={turn} />

        {turn.errorMessage && (
          <div className="mt-3 rounded border border-red-300 bg-red-50 p-2 text-xs text-red-700 dark:bg-red-950">
            {turn.errorMessage}
          </div>
        )}

        {turn.reasoningText && (
          <ReasoningView
            text={turn.reasoningText}
            active={turn.stage === "generating" && !turn.answerText}
          />
        )}

        {turn.answerText && (
          <div className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">
            {turn.answerText}
            {turn.stage === "generating" && (
              <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-zinc-400 align-middle" />
            )}
          </div>
        )}

        {turn.final && turn.final.citations.length > 0 && (
          <CitationsView citations={turn.final.citations} />
        )}
      </div>
    </div>
  );
}

function Timeline({ turn }: { turn: AssistantTurn }) {
  const steps = [
    {
      label: "檢索",
      state:
        turn.stage === "retrieving"
          ? "active"
          : turn.retrievedCount !== null
            ? "done"
            : "pending",
    },
    {
      label: "生成",
      state:
        turn.stage === "generating"
          ? "active"
          : turn.stage === "done"
            ? "done"
            : "pending",
    },
  ] as const;

  return (
    <div className="flex items-center gap-3 text-xs text-zinc-600 dark:text-zinc-400">
      {steps.map((step, i) => (
        <div key={step.label} className="flex items-center gap-1.5">
          <StepIcon state={step.state} />
          <span className={step.state === "done" ? "text-zinc-400" : ""}>
            {step.label}
          </span>
          {i < steps.length - 1 && (
            <span className="ml-2 h-px w-6 bg-zinc-300 dark:bg-zinc-700" />
          )}
        </div>
      ))}
    </div>
  );
}

function StepIcon({ state }: { state: "pending" | "active" | "done" }) {
  if (state === "done") {
    return <span className="text-emerald-600">✓</span>;
  }
  if (state === "active") {
    return (
      <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-blue-500" />
    );
  }
  return <span className="inline-block h-2 w-2 rounded-full bg-zinc-300 dark:bg-zinc-700" />;
}

function ReasoningView({ text, active }: { text: string; active: boolean }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="mt-3 rounded border border-zinc-200 bg-zinc-50 p-2 dark:border-zinc-800 dark:bg-zinc-950">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
      >
        <span>{open ? "▾" : "▸"}</span>
        <span>{active ? "思考中..." : "推理摘要"}</span>
      </button>
      {open && (
        <div className="mt-1.5 whitespace-pre-wrap text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
          {text}
          {active && (
            <span className="ml-0.5 inline-block h-3 w-1 animate-pulse bg-zinc-400 align-middle" />
          )}
        </div>
      )}
    </div>
  );
}

function CitationsView({ citations }: { citations: Citation[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-4 border-t border-zinc-200 pt-3 dark:border-zinc-800">
      <button
        onClick={() => setOpen(!open)}
        className="text-xs text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
      >
        {open ? "▾" : "▸"} 引用來源 ({citations.length})
      </button>
      {open && (
        <ul className="mt-2 space-y-1.5 text-xs">
          {citations.map((c) => (
            <li key={c.chunk_id} className="text-zinc-600 dark:text-zinc-400">
              <span className="mr-1.5 font-mono text-zinc-400">[{c.index}]</span>
              <span className="font-medium text-zinc-800 dark:text-zinc-200">
                {c.title}
              </span>
              {c.chunk_title && c.chunk_title !== c.title && (
                <span className="ml-1 text-zinc-500">— {c.chunk_title}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
