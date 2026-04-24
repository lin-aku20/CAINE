const messagesEl = document.getElementById("messages");
const statusPill = document.getElementById("statusPill");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");

function addMessage(role, text) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  wrapper.appendChild(bubble);
  messagesEl.appendChild(wrapper);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function fetchStatus() {
  try {
    const response = await fetch("/api/status");
    const data = await response.json();
    statusPill.textContent = `${data.name} listo · ${data.model}`;
  } catch {
    statusPill.textContent = "No pude hablar con el circo";
  }
}

async function sendMessage(message) {
  addMessage("user", message);
  addMessage("system", "CAINE mueve la tramoya...");
  messagesEl.lastElementChild.dataset.pending = "true";
  sendBtn.disabled = true;
  sendBtn.textContent = "Moviendo telones...";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message }),
    });
    const data = await response.json();
    const pending = messagesEl.querySelector('[data-pending="true"]');
    if (pending) {
      pending.remove();
    }

    if (!response.ok || !data.ok) {
      addMessage("system", data.error || "El escenario se atragantó.");
      return;
    }

    addMessage("caine", data.reply);
  } catch {
    const pending = messagesEl.querySelector('[data-pending="true"]');
    if (pending) {
      pending.remove();
    }
    addMessage("system", "No pude alcanzar a CAINE desde esta cabina.");
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Enviar al escenario";
    input.focus();
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  await sendMessage(message);
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

clearBtn.addEventListener("click", () => {
  messagesEl.innerHTML = "";
  addMessage("caine", "Telón limpio. El escenario es tuyo.");
});

fetchStatus();
