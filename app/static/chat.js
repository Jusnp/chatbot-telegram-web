const form = document.getElementById('chat-form');
const input = document.getElementById('message');
const messages = document.getElementById('messages');

function addMessage(text, type) {
    const div = document.createElement('div');
    div.className = `message ${type}`;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
}

form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, 'user');
    input.value = '';
    input.focus();

    const loading = addMessage('Pensando...', 'bot');

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        const data = await response.json();
        loading.textContent = data.answer ?? 'No pude responder.';
    } catch (error) {
        loading.textContent = 'No fue posible conectar con el servidor.';
    }
});
