// Chat SocketIO Client
document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
    const userId = {{ session.user_id|tojson }};
    const username = {{ session.username|tojson }};
    let currentChatPartnerId = null;
    let currentChatId = null;
    
    // Elements
    const userList = document.getElementById('userList');
    const messagesContainer = document.getElementById('messagesContainer');
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const onlineCount = document.getElementById('online-count');
    const chatPartnerName = document.getElementById('chatPartnerName');
    const chatPartnerStatus = document.getElementById('chatPartnerStatus');
    const typingIndicator = document.getElementById('typingIndicator');
    
    // Load users
    fetch('/api/users')
        .then(res => res.json())
        .then(users => {
            users.forEach(user => {
                const userEl = document.createElement('div');
                userEl.className = `user-item ${user.online ? 'online' : 'offline'}`;
                userEl.dataset.userId = user.id;
                userEl.innerHTML = `
                    <div class="user-avatar">${user.username.charAt(0).toUpperCase()}</div>
                    <div class="user-details">
                        <span class="user-name">${user.username}</span>
                        <span class="user-role">${user.role}</span>
                    </div>
                    ${user.online ? '<div class="online-dot"></div>' : ''}
                `;
                userEl.addEventListener('click', () => selectUser(user.id, user.username));
                userList.appendChild(userEl);
            });
            onlineCount.textContent = users.filter(u => u.online).length;
        });
    
    // Socket events
    socket.on('connect', () => {
        console.log('Connected to chat server');
        socket.emit('join_chat', { user_id: userId });
    });
    
    socket.on('user_online', (data) => updateUserStatus(data.user_id, true));
    socket.on('user_offline', (data) => updateUserStatus(data.user_id, false));
    
    socket.on('message', (data) => {
        if (currentChatId === data.chat_id) {
            appendMessage(data, 'received');
            markAsRead(data.message_id);
        }
    });
    
    socket.on('typing', (data) => {
        if (currentChatId === data.chat_id) {
            typingIndicator.textContent = `${data.username} is typing...`;
            setTimeout(() => typingIndicator.textContent = '', 3000);
        }
    });
    
    socket.on('stop_typing', (data) => {
        if (currentChatId === data.chat_id) typingIndicator.textContent = '';
    });
    
    // Input handlers
    let typingTimer;
    messageInput.addEventListener('input', () => {
        sendButton.disabled = messageInput.value.trim() === '';
        
        if (currentChatPartnerId) {
            socket.emit('typing', { chat_id: currentChatId });
            clearTimeout(typingTimer);
            typingTimer = setTimeout(() => socket.emit('stop_typing', { chat_id: currentChatId }), 1000);
        }
    });
    
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    sendButton.addEventListener('click', sendMessage);
    
    function sendMessage() {
        const message = messageInput.value.trim();
        if (!message || !currentChatPartnerId) return;
        
        socket.emit('send_message', {
            chat_id: currentChatId,
            partner_id: currentChatPartnerId,
            content: message
        });
        
        appendMessage({ content: message, sender_id: userId, timestamp: new Date().toISOString() }, 'sent');
        messageInput.value = '';
        sendButton.disabled = true;
    }
    
    function selectUser(partnerId, partnerName) {
        if (partnerId === userId) return;
        
        currentChatPartnerId = partnerId;
        chatPartnerName.textContent = partnerName;
        chatPartnerStatus.className = 'status-online'; // Assume online when selected
        chatPartnerStatus.textContent = 'Online';
        
        // Load chat history
        fetch(`/api/messages/${partnerId}`)
            .then(res => res.json())
            .then(messages => {
                messagesContainer.innerHTML = '';
                messages.forEach(msg => appendMessage(msg, msg.sender_id == userId ? 'sent' : 'received'));
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            });
        
        // Highlight selected
        document.querySelectorAll('.user-item').forEach(el => el.classList.remove('selected'));
        event.currentTarget.classList.add('selected');
        
        // Join chat room
        socket.emit('join_chat', { chat_id: `chat_${Math.min(userId, partnerId)}_${Math.max(userId, partnerId)}` });
    }
    
    function appendMessage(msg, type) {
        const messageEl = document.createElement('div');
        messageEl.className = `message ${type}`;
        messageEl.innerHTML = `
            <div class="message-content">${msg.content}</div>
            <div class="message-time">${new Date(msg.timestamp).toLocaleTimeString()}</div>
        `;
        messagesContainer.appendChild(messageEl);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    function updateUserStatus(userId, online) {
        const userEl = document.querySelector(`[data-user-id="${userId}"]`);
        if (userEl) {
            userEl.className = `user-item ${online ? 'online' : 'offline'}`;
            const dot = userEl.querySelector('.online-dot');
            if (online && !dot) {
                const newDot = document.createElement('div');
                newDot.className = 'online-dot';
                userEl.appendChild(newDot);
            } else if (!online && dot) {
                dot.remove();
            }
            onlineCount.textContent = document.querySelectorAll('.user-item.online').length;
        }
    }
    
    function markAsRead(messageId) {
        fetch(`/api/messages/${messageId}/read`, { method: 'POST' });
    }
});
