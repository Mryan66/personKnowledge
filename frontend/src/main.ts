import Alpine from "alpinejs";
import htmx from "htmx.org";
import "./styles/app.scss";

declare global {
  interface Window {
    Alpine: typeof Alpine;
    htmx: typeof htmx;
  }
}

window.Alpine = Alpine;
window.htmx = htmx;

document.addEventListener("alpine:init", () => {
  Alpine.data("askComposer", () => ({
    loading: false,
    activeStream: null as EventSource | null,
    fillPrompt(prompt: string) {
      const textarea = document.querySelector<HTMLTextAreaElement>('textarea[name="question"]');
      if (!textarea) return;
      textarea.value = prompt;
      textarea.focus();
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    },
    closeStream() {
      if (this.activeStream) {
        this.activeStream.close();
        this.activeStream = null;
      }
    },
  }));
});

document.body.addEventListener("htmx:beforeRequest", (event) => {
  const target = event.target as HTMLElement | null;
  if (!target?.closest(".ask-form")) return;
  const root = target.closest("[x-data]") as { __x?: { $data?: { loading?: boolean } } } | null;
  if (root?.__x?.$data) {
    root.__x.$data.loading = true;
  }
});

document.body.addEventListener("submit", (event) => {
  const form = event.target as HTMLFormElement | null;
  if (!form?.classList.contains("progress-form")) return;
  if (form.dataset.streamEndpoint) {
    event.preventDefault();
    const root = form.closest("[x-data]") as { __x?: { $data?: { loading?: boolean; activeStream?: EventSource | null; closeStream?: () => void } } } | null;
    if (root?.__x?.$data) {
      root.__x.$data.loading = true;
      root.__x.$data.closeStream?.();
    }
    startAskStream(form, root);
    return;
  }
  const root = form.closest("[x-data]") as { __x?: { $data?: { loading?: boolean } } } | null;
  if (root?.__x?.$data && "loading" in root.__x.$data) {
    root.__x.$data.loading = true;
  }
});

document.body.addEventListener("htmx:afterRequest", (event) => {
  const target = event.target as HTMLElement | null;
  if (!target?.closest(".ask-form")) return;
  const root = target.closest("[x-data]") as { __x?: { $data?: { loading?: boolean } } } | null;
  if (root?.__x?.$data) {
    root.__x.$data.loading = false;
  }
  if (!event.detail.successful) return;

  const textarea = document.querySelector<HTMLTextAreaElement>('textarea[name="question"]');
  if (textarea) {
    textarea.value = "";
  }
  const chatThread = document.querySelector<HTMLElement>(".chat-thread");
  if (chatThread) {
    chatThread.scrollTop = chatThread.scrollHeight;
  }
  const resultPanel = document.querySelector<HTMLElement>("[data-result-panel]");
  if (resultPanel) {
    resultPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
});

document.body.addEventListener("htmx:oobAfterSwap", (event) => {
  const target = event.target as HTMLElement | null;
  if (target?.id !== "ask-conversation-region") return;
  const chatThread = document.querySelector<HTMLElement>(".chat-thread");
  if (chatThread) {
    chatThread.scrollTop = chatThread.scrollHeight;
  }
});

window.addEventListener("pageshow", () => {
  document.querySelectorAll<HTMLElement>("[x-data]").forEach((root) => {
    const data = (root as { __x?: { $data?: { loading?: boolean } } }).__x?.$data;
    if (data && "loading" in data) {
      data.loading = false;
    }
  });
  const resultPanel = document.querySelector<HTMLElement>("[data-result-panel]");
  if (resultPanel && document.body.dataset.page === "search") {
    resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
});

Alpine.start();

function startAskStream(
  form: HTMLFormElement,
  root: { __x?: { $data?: { loading?: boolean; activeStream?: EventSource | null } } } | null,
) {
  const endpoint = form.dataset.streamEndpoint;
  if (!endpoint) return;
  const formData = new FormData(form);
  const params = new URLSearchParams();
  formData.forEach((value, key) => {
    if (typeof value === "string") {
      params.append(key, value);
    }
  });
  if (!params.get("use_llm")) {
    params.delete("use_llm");
  }
  if (!params.get("use_embeddings")) {
    params.delete("use_embeddings");
  }
  const stream = new EventSource(`${endpoint}?${params.toString()}`);
  if (root?.__x?.$data) {
    root.__x.$data.activeStream = stream;
  }

  stream.addEventListener("phase", (event) => {
    const data = JSON.parse((event as MessageEvent).data) as { label?: string };
    syncLoadingMessage(data.label || "正在处理中...");
  });

  stream.addEventListener("patch", (event) => {
    const data = JSON.parse((event as MessageEvent).data) as Record<string, string>;
    replaceRegion("ask-status-bar", data.status_bar);
    replaceRegion("ask-session-drawer", data.session_drawer);
    replaceRegion("ask-conversation-region", data.conversation);
    replaceRegion("ask-answer-region", data.answer);
    syncChatScroll();
  });

  stream.addEventListener("error", (event) => {
    const data = safeParseEventData(event as MessageEvent);
    syncLoadingMessage(data.message || "请求失败，请稍后重试。");
    if (root?.__x?.$data) {
      root.__x.$data.loading = false;
    }
    stream.close();
  });

  stream.addEventListener("done", () => {
    if (root?.__x?.$data) {
      root.__x.$data.loading = false;
      root.__x.$data.activeStream = null;
    }
    const textarea = document.querySelector<HTMLTextAreaElement>('textarea[name="question"]');
    if (textarea) {
      textarea.value = "";
    }
    syncChatScroll();
    const resultPanel = document.querySelector<HTMLElement>("[data-result-panel]");
    if (resultPanel) {
      resultPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
    stream.close();
  });
}

function replaceRegion(id: string, html?: string) {
  const element = document.getElementById(id);
  if (!element || html === undefined) return;
  element.innerHTML = html;
}

function syncChatScroll() {
  const chatThread = document.querySelector<HTMLElement>(".chat-thread");
  if (chatThread) {
    chatThread.scrollTop = chatThread.scrollHeight;
  }
}

function syncLoadingMessage(message: string) {
  const panel = document.querySelector<HTMLElement>(".ask-loading-panel .panel-heading p");
  if (panel) {
    panel.textContent = message;
  }
}

function safeParseEventData(event: MessageEvent): Record<string, string> {
  try {
    return JSON.parse(event.data) as Record<string, string>;
  } catch {
    return {};
  }
}
