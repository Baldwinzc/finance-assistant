import {
  BarChart3Icon,
  BotIcon,
  CheckCircle2Icon,
  CircleAlertIcon,
  Loader2Icon,
  UserIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

import {
  ChatInput,
  ChatInputSubmit,
  ChatInputTextArea,
} from "@/components/ui/chat-input";
import { Button } from "@/components/ui/button";

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
  resolution?: Resolution;
};

const examples = ["贵州茅台", "沪深三百", "医疗行业"];

export default function App() {
  const [value, setValue] = useState("");
  const [brain, setBrain] = useState<"llm" | "rules">("llm");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "当前只运行第一步标的判断。",
    },
  ]);
  const [activeResolution, setActiveResolution] = useState<Resolution | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [abortController, setAbortController] =
    useState<AbortController | null>(null);

  const statusText = useMemo(() => {
    if (!activeResolution) {
      return "等待输入";
    }
    if (activeResolution.needs_clarification) {
      return "需要确认";
    }
    return activeResolution.primary ? "已识别" : "未识别";
  }, [activeResolution]);

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
        body: JSON.stringify({ query, brain }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`请求失败：${response.status}`);
      }

      const resolution = (await response.json()) as Resolution;
      setActiveResolution(resolution);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: resolution.explanation,
          resolution,
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
    <main className="min-h-screen">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-3 border-b border-border pb-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <BarChart3Icon className="h-4 w-4 text-primary" />
              <span>Finance Assistant</span>
            </div>
            <h1 className="mt-1 text-2xl font-semibold tracking-normal">
              金融助手
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={brain === "llm" ? "default" : "outline"}
              size="sm"
              onClick={() => setBrain("llm")}
            >
              LLM
            </Button>
            <Button
              variant={brain === "rules" ? "default" : "outline"}
              size="sm"
              onClick={() => setBrain("rules")}
            >
              Rules
            </Button>
          </div>
        </header>

        <section className="grid flex-1 grid-cols-1 gap-5 py-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="flex min-h-[620px] flex-col overflow-hidden rounded-lg border border-border bg-white">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <BotIcon className="h-4 w-4 text-primary" />
                <span>标的判断</span>
              </div>
              {loading ? (
                <Loader2Icon className="h-4 w-4 animate-spin text-primary" />
              ) : null}
            </div>

            <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={
                    message.role === "user"
                      ? "flex justify-end"
                      : "flex justify-start"
                  }
                >
                  <div
                    className={
                      message.role === "user"
                        ? "max-w-[78%] rounded-lg bg-primary px-4 py-3 text-sm text-primary-foreground"
                        : "max-w-[86%] rounded-lg border border-border bg-background px-4 py-3 text-sm"
                    }
                  >
                    <div className="mb-1 flex items-center gap-2 text-xs opacity-75">
                      {message.role === "user" ? (
                        <UserIcon className="h-3.5 w-3.5" />
                      ) : (
                        <BotIcon className="h-3.5 w-3.5" />
                      )}
                      <span>{message.role === "user" ? "你" : "助手"}</span>
                    </div>
                    <p className="whitespace-pre-wrap leading-6">
                      {message.content}
                    </p>
                    {message.resolution?.needs_clarification ? (
                      <p className="mt-3 border-t border-border pt-3 text-sm text-muted-foreground">
                        {message.resolution.clarification_question}
                      </p>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>

            <div className="border-t border-border p-3">
              <div className="mb-3 flex flex-wrap gap-2">
                {examples.map((example) => (
                  <Button
                    key={example}
                    variant="outline"
                    size="sm"
                    onClick={() => submitQuery(example)}
                    disabled={loading}
                  >
                    {example}
                  </Button>
                ))}
              </div>
              <ChatInput
                value={value}
                onChange={(event) => setValue(event.target.value)}
                onSubmit={() => submitQuery()}
                loading={loading}
                onStop={stopRequest}
                rows={1}
              >
                <ChatInputTextArea placeholder="输入股票、指数或行业指数" />
                <ChatInputSubmit />
              </ChatInput>
            </div>
          </div>

          <aside className="rounded-lg border border-border bg-white">
            <div className="border-b border-border px-4 py-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">判断状态</h2>
                <span className="rounded-full bg-accent px-2.5 py-1 text-xs text-accent-foreground">
                  {statusText}
                </span>
              </div>
            </div>

            <div className="space-y-4 p-4">
              {activeResolution ? (
                <>
                  <div className="rounded-lg border border-border p-3">
                    <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                      {activeResolution.needs_clarification ? (
                        <CircleAlertIcon className="h-4 w-4 text-destructive" />
                      ) : (
                        <CheckCircle2Icon className="h-4 w-4 text-emerald-600" />
                      )}
                      <span>
                        {activeResolution.primary
                          ? activeResolution.primary.display_name
                          : "待确认"}
                      </span>
                    </div>
                    <p className="text-sm leading-6 text-muted-foreground">
                      {activeResolution.explanation}
                    </p>
                  </div>

                  <div>
                    <h3 className="mb-2 text-sm font-semibold">候选</h3>
                    <div className="space-y-2">
                      {activeResolution.candidates.length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                          暂无候选。
                        </p>
                      ) : (
                        activeResolution.candidates.map((candidate) => (
                          <div
                            key={`${candidate.symbol}-${candidate.name}`}
                            className="rounded-lg border border-border p-3"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="text-sm font-medium">
                                  {candidate.display_name}
                                </p>
                                <p className="mt-1 text-xs text-muted-foreground">
                                  {candidate.asset_type}
                                </p>
                              </div>
                              <span className="text-sm font-semibold text-primary">
                                {Math.round(candidate.score * 100)}%
                              </span>
                            </div>
                            <p className="mt-2 text-sm leading-5 text-muted-foreground">
                              {candidate.reason}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-sm leading-6 text-muted-foreground">
                  等待首次判断结果。
                </p>
              )}
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}
