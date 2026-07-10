import {
  BotIcon,
  Loader2Icon,
} from "lucide-react";
import { useState } from "react";

import {
  ChatInput,
  ChatInputSubmit,
  ChatInputTextArea,
} from "@/components/ui/chat-input";

type Candidate = {
  asset_type: string;
  symbol: string;
  name: string;
  score: number;
  reason: string;
  display_name: string;
};

type Resolution = {
  query: string;
  asset_type: string;
  primary: Candidate | null;
  candidates: Candidate[];
  explanation: string;
  needs_clarification: boolean;
  clarification_question: string;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export default function App() {
  const [value, setValue] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [abortController, setAbortController] =
    useState<AbortController | null>(null);

  async function submitQuery(nextValue = value) {
    const query = nextValue.trim();
    if (!query || loading) {
      return;
    }

    const controller = new AbortController();
    setAbortController(controller);
    setLoading(true);
    setValue("");
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: query },
    ]);

    try {
      const response = await fetch("/api/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, brain: "llm" }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`请求失败：${response.status}`);
      }

      const resolution = (await response.json()) as Resolution;
      const candidateText =
        resolution.candidates.length > 0
          ? resolution.candidates
              .map(
                (candidate) =>
                  `${candidate.display_name} ${Math.round(candidate.score * 100)}%`,
              )
              .join("\n")
          : "";
      const clarification = resolution.needs_clarification
        ? `\n\n${resolution.clarification_question}`
        : "";
      const content = [resolution.explanation, candidateText, clarification]
        .filter(Boolean)
        .join("\n\n");
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content,
        },
      ]);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "请求失败，请稍后再试。";
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: message,
        },
      ]);
    } finally {
      setLoading(false);
      setAbortController(null);
    }
  }

  function stopRequest() {
    abortController?.abort();
    setLoading(false);
    setAbortController(null);
  }

  return (
    <main className="min-h-screen bg-[#050607] text-zinc-100">
      <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-5">
        <section className="flex flex-1 flex-col justify-end pb-[22vh] pt-16">
          {messages.length > 0 ? (
            <div className="mb-8 max-h-[52vh] space-y-5 overflow-y-auto pr-1">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={
                    message.role === "user"
                      ? "ml-auto max-w-[78%] rounded-2xl bg-zinc-100 px-4 py-3 text-sm leading-6 text-zinc-950"
                      : "max-w-[82%] rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm leading-6 text-zinc-300"
                  }
                >
                  {message.role === "assistant" ? (
                    <div className="mb-2 flex items-center gap-2 text-xs text-zinc-500">
                      <BotIcon className="h-3.5 w-3.5" />
                      <span>Finance Assistant</span>
                    </div>
                  ) : null}
                  <p className="whitespace-pre-wrap">{message.content}</p>
                </div>
              ))}
            </div>
          ) : null}

          <div className="mx-auto w-full max-w-[400px]">
            <ChatInput
              value={value}
              onChange={(event) => setValue(event.target.value)}
              onSubmit={() => submitQuery()}
              loading={loading}
              onStop={stopRequest}
              rows={1}
            >
              <ChatInputTextArea placeholder="Type a message..." />
              <ChatInputSubmit />
            </ChatInput>
            {loading ? (
              <div className="mt-3 flex justify-center text-zinc-600">
                <Loader2Icon className="h-4 w-4 animate-spin" />
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </main>
  );
}
