(function() {
    'use strict';

    var fab = document.getElementById('chatFab');
    var panel = document.getElementById('chatPanel');
    var closeBtn = document.getElementById('chatClose');
    var form = document.getElementById('chatForm');
    var input = document.getElementById('chatInput');
    var messagesEl = document.getElementById('chatMessages');
    var history = [];

    fab.addEventListener('click', function() {
        var isHidden = panel.classList.contains('hidden');
        panel.classList.toggle('hidden');
        fab.setAttribute('aria-expanded', isHidden ? 'true' : 'false');
        if (isHidden) input.focus();
    });

    closeBtn.addEventListener('click', function() {
        panel.classList.add('hidden');
        fab.setAttribute('aria-expanded', 'false');
        fab.focus();
    });

    // Close on Escape key
    panel.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            panel.classList.add('hidden');
            fab.setAttribute('aria-expanded', 'false');
            fab.focus();
        }
    });

    function addMessage(role, text) {
        var div = document.createElement('div');
        div.className = 'chat-msg ' + role;
        var bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.textContent = text;
        div.appendChild(bubble);
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        var msg = input.value.trim();
        if (!msg) return;

        addMessage('user', msg);
        input.value = '';
        input.disabled = true;

        // Show typing indicator
        var typing = document.createElement('div');
        typing.className = 'chat-msg assistant';
        var typingBubble = document.createElement('div');
        typingBubble.className = 'chat-bubble typing';
        typingBubble.textContent = 'Thinking...';
        typing.appendChild(typingBubble);
        messagesEl.appendChild(typing);
        messagesEl.scrollTop = messagesEl.scrollHeight;

        fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: msg, history: history})
        })
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            typing.remove();
            if (data.reply) {
                addMessage('assistant', data.reply);
                history.push({role: 'user', content: msg});
                history.push({role: 'assistant', content: data.reply});
            } else {
                addMessage('assistant', data.error || 'Something went wrong. Please try again.');
            }
        })
        .catch(function() {
            typing.remove();
            addMessage('assistant', 'Connection error. Please try again.');
        })
        .finally(function() {
            input.disabled = false;
            input.focus();
        });
    });
})();
