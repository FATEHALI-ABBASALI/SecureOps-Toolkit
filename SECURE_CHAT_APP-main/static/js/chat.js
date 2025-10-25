// static/js/chat.js

document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    const currentUser = window.currentUsername; // Passed from Flask template
    let privateKeyPEM; // Store our RSA private key
    let publicKeyPEM;  // Store our RSA public key
    const remotePublicKeys = {}; // Stores public keys of other users: {username: 'PEM_string'}
    let activeRecipient = null; // The user we are currently chatting with
    const chatHistory = {}; // Store encrypted messages temporarily: {recipient_username: [encrypted_message_data]}

    const onlineUsersList = document.getElementById('online-users');
    const recipientNameDisplay = document.getElementById('recipient-name');
    const messagesDiv = document.getElementById('messages');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');

    // --- Utility Functions ---

    /**
     * Converts a base64 string to a Uint8Array.
     * @param {string} base64String
     * @returns {Uint8Array}
     */
    function base64ToUint8Array(base64String) {
        return Uint8Array.from(atob(base64String), c => c.charCodeAt(0));
    }

    /**
     * Converts a Uint8Array to a base64 string.
     * @param {Uint8Array} uint8Array
     * @returns {string}
     */
    function uint8ArrayToBase64(uint8Array) {
        return btoa(String.fromCharCode.apply(null, uint8Array));
    }

    // --- RSA Key Generation and Management ---

    async function generateAndRegisterRSAKeys() {
        const crypt = new JSEncrypt({ default_key_size: 2048 });
        
        crypt.getKey(); // Generates the key pair
        privateKeyPEM = crypt.getPrivateKey();
        publicKeyPEM = crypt.getPublicKey();

        console.log("RSA Key Pair Generated!");
        console.log("Public Key (truncated):", publicKeyPEM.substring(0, 100) + "...");
        // console.log("Private Key (truncated):", privateKeyPEM.substring(0, 100) + "..."); // Keep private key secure!

        socket.emit('register_public_key', { publicKey: publicKeyPEM });
    }

    // --- AES Encryption/Decryption ---
    
    // Generates a random AES 256-bit key (represented as a WordArray from Crypto-JS)
    function generateAesKey() {
        return CryptoJS.lib.WordArray.random(32); // 32 bytes = 256 bits
    }

    // Encrypts plaintext using AES-256-CBC
    async function aesEncrypt(plaintext, aesKey) {
        const iv = CryptoJS.lib.WordArray.random(16); // 16 bytes = 128 bits
        
        const encrypted = CryptoJS.AES.encrypt(plaintext, aesKey, {
            iv: iv,
            mode: CryptoJS.mode.CBC,
            padding: CryptoJS.pad.Pkcs7
        });

        // The 'toString()' of encrypted object gives the ciphertext in Base64 by default.
        // We need to return the IV separately.
        return {
            ciphertext: encrypted.toString(), // Base64 encoded ciphertext
            iv: CryptoJS.enc.Base64.stringify(iv) // Base64 encoded IV
        };
    }

    // Decrypts ciphertext using AES-256-CBC
    async function aesDecrypt(ciphertext, aesKey, ivBase64) {
        try {
            const iv = CryptoJS.enc.Base64.parse(ivBase64); // Parse Base64 IV back to WordArray
            
            const decrypted = CryptoJS.AES.decrypt(ciphertext, aesKey, {
                iv: iv,
                mode: CryptoJS.mode.CBC,
                padding: CryptoJS.pad.Pkcs7
            });
            
            // Check if decryption was successful and the result is valid UTF-8
            const plaintext = decrypted.toString(CryptoJS.enc.Utf8);
            if (plaintext) {
                return plaintext;
            } else {
                console.warn("AES decryption resulted in empty or invalid plaintext. Possible key mismatch or corruption.");
                return "[Decryption Failed: Invalid Data]";
            }
        } catch (e) {
            console.error("Error during AES decryption:", e);
            return "[Decryption Failed: Error]";
        }
    }

    // --- Chat UI Functions ---

    function addMessageToChat(sender, message, isSelf, isSystem = false) {
        const messageRow = document.createElement('div');
        messageRow.classList.add('message-row');
        if (isSelf) {
            messageRow.classList.add('self');
        } else if (isSystem) {
            messageRow.classList.add('system');
        }

        const meta = document.createElement('div');
        meta.classList.add('message-meta');
        meta.textContent = `${sender} - ${new Date().toLocaleTimeString()}`;

        const content = document.createElement('div');
        content.classList.add('message-content');
        content.textContent = message;

        messageRow.appendChild(meta);
        messageRow.appendChild(content);
        messagesDiv.appendChild(messageRow);
        messagesDiv.scrollTop = messagesDiv.scrollHeight; // Scroll to bottom
    }

    function displaySystemMessage(text) {
        addMessageToChat('System', text, false, true);
    }

    function updateOnlineUsersList(onlineUsers) {
        onlineUsersList.innerHTML = ''; // Clear current list

        onlineUsers.forEach(user => {
            const listItem = document.createElement('li');
            const statusDot = document.createElement('span');
            statusDot.classList.add('status-dot', 'online'); // All users in this list are online

            listItem.appendChild(statusDot);
            listItem.append(user);

            if (user === currentUser) {
                listItem.classList.add('self');
                listItem.title = "You (online)";
            } else {
                listItem.title = `${user} (online)`;
                listItem.addEventListener('click', () => {
                    setActiveRecipient(user);
                });
            }
            if (user === activeRecipient) {
                listItem.classList.add('active');
            }
            onlineUsersList.appendChild(listItem);
        });
    }

    function setActiveRecipient(username) {
        if (activeRecipient === username) return; // Already active

        activeRecipient = username;
        recipientNameDisplay.textContent = `Chatting with: ${username}`;
        messageInput.disabled = false;
        sendButton.disabled = false;
        messagesDiv.innerHTML = ''; // Clear chat area

        // Highlight active user in the sidebar
        const currentActive = onlineUsersList.querySelector('.active');
        if (currentActive) {
            currentActive.classList.remove('active');
        }
        const newActive = onlineUsersList.querySelector(`li:not(.self)[title="${username} (online)"]`);
        if (newActive) {
            newActive.classList.add('active');
        }
        
        displaySystemMessage(`You are now chatting securely with ${username}.`);

        // Reload chat history for this recipient
        if (chatHistory[username]) {
            chatHistory[username].forEach(msg => {
                displayDecryptedMessage(msg);
            });
        }
    }
    
    // Function to handle displaying decrypted messages, including our own sent messages
    async function displayDecryptedMessage(encryptedMessageData) {
        const sender = encryptedMessageData.sender;
        const ciphertext = encryptedMessageData.ciphertext;
        const iv = encryptedMessageData.iv;
        const encryptedAesKeyBase64 = encryptedMessageData.encryptedAesKey;
        const timestamp = encryptedMessageData.timestamp;

        let decryptedPlaintext = "[Error: Could not decrypt]";

        try {
            // Re-initialize JSEncrypt with our private key for decryption
            const decryptor = new JSEncrypt();
            decryptor.setPrivateKey(privateKeyPEM);
            
            // Decrypt the AES key using our RSA private key
            const decryptedAesKeyBase64 = decryptor.decrypt(encryptedAesKeyBase64);
            
            if (decryptedAesKeyBase64) {
                // Convert Base64 AES key back to Crypto-JS WordArray
                const aesKeyWordArray = CryptoJS.enc.Base64.parse(decryptedAesKeyBase64);
                
                // Decrypt the actual message using the AES key
                decryptedPlaintext = await aesDecrypt(ciphertext, aesKeyWordArray, iv);
            } else {
                console.error("Failed to decrypt AES key with RSA private key.");
                decryptedPlaintext = "[Decryption Failed: AES key]";
            }
        } catch (e) {
            console.error("Error during full message decryption process:", e);
            decryptedPlaintext = "[Decryption Failed: General Error]";
        }
        
        // Determine if this message was sent by us
        const isSelf = (sender === currentUser);
        
        // Only display if the message pertains to the currently active recipient,
        // or if it's a message we sent to the current recipient.
        if ((sender === activeRecipient && !isSelf) || (sender === currentUser && activeRecipient === encryptedMessageData.recipient)) {
             addMessageToChat(sender, decryptedPlaintext, isSelf);
        } else if (sender === currentUser && !activeRecipient) {
             // If we send a message and no recipient is active, display it as a system warning
             displaySystemMessage(`Message sent to ${encryptedMessageData.recipient} (not currently active here): "${decryptedPlaintext}"`);
        } else if (sender !== currentUser && !activeRecipient) {
            // If someone sends us a message and we have no active recipient, notify
            displaySystemMessage(`New message from ${sender}! Select them to view.`);
        }
    }


    // --- Event Listeners and Socket.IO Handlers ---

    socket.on('connect', () => {
        console.log('Connected to server!');
        displaySystemMessage('Connected to the chat server. Generating RSA keys...');
        generateAndRegisterRSAKeys();
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from server!');
        displaySystemMessage('Disconnected from the chat server. Please refresh.');
        // Clear public keys and disable chat
        onlineUsersList.innerHTML = '';
        remotePublicKeys = {};
        activeRecipient = null;
        recipientNameDisplay.textContent = 'Disconnected';
        messageInput.disabled = true;
        sendButton.disabled = true;
    });

    socket.on('public_keys_exchange', (keys) => {
        console.log("Received initial public keys from server:", keys);
        for (const user in keys) {
            if (user !== currentUser) { // Don't store our own public key in remotePublicKeys
                remotePublicKeys[user] = keys[user];
            }
        }
        console.log("Updated remotePublicKeys:", remotePublicKeys);
    });

    socket.on('new_public_key', (data) => {
        const { username, publicKey } = data;
        if (username !== currentUser) {
            console.log(`Received new public key for ${username}`);
            remotePublicKeys[username] = publicKey;
        }
    });

    socket.on('user_list_update', (onlineUsers) => {
        console.log("Online users updated:", onlineUsers);
        updateOnlineUsersList(onlineUsers);
        
        // If our active recipient went offline, or is no longer in the list, disable input
        if (activeRecipient && !onlineUsers.includes(activeRecipient)) {
            displaySystemMessage(`${activeRecipient} went offline.`);
            // You might choose to clear activeRecipient or just disable input
            messageInput.disabled = true;
            sendButton.disabled = true;
            recipientNameDisplay.textContent = `Chatting with: ${activeRecipient} (Offline)`;
        } else if (activeRecipient && onlineUsers.includes(activeRecipient)) {
            // Re-enable if they came back online (if it was disabled)
            messageInput.disabled = false;
            sendButton.disabled = false;
            recipientNameDisplay.textContent = `Chatting with: ${activeRecipient}`;
        }
    });

    socket.on('status_message', (data) => {
        displaySystemMessage(data.text);
    });

    socket.on('new_message', async (encryptedMessageData) => {
        console.log("Received encrypted message:", encryptedMessageData);

        const sender = encryptedMessageData.sender;
        const recipient = encryptedMessageData.recipient; // Server adds this when relaying to sender

        // Store message in history (even if it's our own sent message, for reloading)
        const chatPartner = (sender === currentUser) ? encryptedMessageData.recipient : sender;
        if (!chatHistory[chatPartner]) {
            chatHistory[chatPartner] = [];
        }
        chatHistory[chatPartner].push(encryptedMessageData);

        // Display the message if the sender is the active recipient or we are the sender
        if (sender === activeRecipient || (sender === currentUser && encryptedMessageData.recipient === activeRecipient)) {
            await displayDecryptedMessage(encryptedMessageData);
        } else if (sender !== currentUser) {
            // Notify user about new message from non-active recipient
            displaySystemMessage(`New message from ${sender}!`);
        }
    });

    sendButton.addEventListener('click', async () => {
        const message = messageInput.value.trim();
        if (!message || !activeRecipient) {
            return;
        }

        const recipientPublicKeyPEM = remotePublicKeys[activeRecipient];
        if (!recipientPublicKeyPEM) {
            displaySystemMessage(`Error: Public key for ${activeRecipient} not found. Cannot send message.`);
            return;
        }

        // 1. Generate a new AES key for THIS message
        const aesKey = generateAesKey(); // Crypto-JS WordArray
        
        // 2. Encrypt the message plaintext with the AES key
        const { ciphertext, iv } = await aesEncrypt(message, aesKey);

        // 3. Encrypt the AES key itself with the recipient's RSA public key
        const rsaEncryptor = new JSEncrypt();
        rsaEncryptor.setPublicKey(recipientPublicKeyPEM);
        // We need to convert the Crypto-JS WordArray AES key to a string (Base64 is good)
        const aesKeyBase64 = CryptoJS.enc.Base64.stringify(aesKey);
        const encryptedAesKey = rsaEncryptor.encrypt(aesKeyBase64); // This is Base64 by default from JSEncrypt

        if (!encryptedAesKey) {
            displaySystemMessage("Error encrypting AES key with recipient's public key. Message not sent.");
            return;
        }

        const messageData = {
            recipient: activeRecipient,
            encryptedAesKey: encryptedAesKey, // RSA-encrypted AES key (Base64)
            iv: iv,                           // AES IV (Base64)
            ciphertext: ciphertext,           // AES-encrypted message (Base64)
            timestamp: new Date().toISOString()
        };

        socket.emit('send_message', messageData);
        messageInput.value = '';
        console.log("Sent encrypted message to server for relay.");
        // The server will echo this message back to us, so we don't display it here immediately.
    });

    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendButton.click();
        }
    });

    // Initial key generation on load
    // This is handled by socket.on('connect') -> generateAndRegisterRSAKeys();
});