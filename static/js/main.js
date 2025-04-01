document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('interviewForm');
    const startButton = document.getElementById('startButton');
    const cancelButton = document.getElementById('cancelButton');
    const statusDiv = document.getElementById('status');
    const avatar = document.getElementById('interviewer-avatar');
    let conversationId = null;
    let ws = null;

    // Get the current URL dynamically
    const baseUrl = window.location.origin;
    console.log('Using API base URL:', baseUrl);

    // Disable cancel button initially
    cancelButton.disabled = true;

    function connectWebSocket(agentId) {
        try {
            const wsUrl = `${baseUrl.replace('http', 'ws')}/ws/${agentId}`;
            console.log('Connecting to WebSocket:', wsUrl);
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                console.log('WebSocket connection established');
                showStatus('Connected to interview session');
            };
            
            ws.onmessage = (event) => {
                console.log('Received message:', event.data);
                // Handle incoming messages here
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                showError('Connection error. Please try again.');
            };
            
            ws.onclose = () => {
                console.log('WebSocket connection closed');
                showStatus('Connection closed');
            };
        } catch (error) {
            console.error('Error connecting to WebSocket:', error);
            showError('Failed to establish connection');
        }
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const agentId = document.getElementById('agentId').value;
        const apiKey = document.getElementById('apiKey').value;
        const resume = document.getElementById('resume').value;
        const jobDescription = document.getElementById('jobDescription').value;
        
        if (!agentId || !apiKey || !resume || !jobDescription) {
            showError('Please fill in all fields');
            return;
        }

        try {
            showStatus('Starting interview...');
            startButton.disabled = true;
            cancelButton.disabled = false;
            
            // Start speaking animation
            avatar.classList.add('speaking');

            const requestData = {
                agentId: agentId,
                apiKey: apiKey,
                resume: resume,
                jobDescription: jobDescription
            };
            
            console.log('Sending request data:', requestData);

            const response = await fetch(`${baseUrl}/offer`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });

            console.log('Response status:', response.status);
            const data = await response.json();
            console.log('Response data:', data);
            
            if (response.ok) {
                showStatus('Interview started successfully');
                conversationId = data.conversationId;
                // Connect to WebSocket after successful offer
                connectWebSocket(conversationId);
            } else {
                throw new Error(data.error || 'Failed to start interview');
            }
        } catch (error) {
            console.error('Error starting interview:', error);
            showError(error.message);
            startButton.disabled = false;
            cancelButton.disabled = true;
            avatar.classList.remove('speaking');
        }
    });

    cancelButton.addEventListener('click', async () => {
        try {
            showStatus('Canceling interview...');
            
            const agentId = document.getElementById('agentId').value;
            
            if (!agentId) {
                showError('No active interview to cancel');
                return;
            }

            // Close WebSocket connection if exists
            if (ws) {
                ws.close();
                ws = null;
            }

            console.log('Sending cancel request for agentId:', agentId);
            
            const response = await fetch(`${baseUrl}/cancel`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    agentId: agentId
                })
            });

            console.log('Cancel response status:', response.status);
            const data = await response.json();
            console.log('Cancel response data:', data);
            
            if (response.ok) {
                form.reset();
                startButton.disabled = false;
                cancelButton.disabled = true;
                avatar.classList.remove('speaking');
                showStatus('Interview canceled');
            } else {
                throw new Error(data.error || 'Failed to cancel interview');
            }
        } catch (error) {
            console.error('Error canceling interview:', error);
            showError(error.message);
        }
    });

    function showStatus(message) {
        statusDiv.textContent = message;
        statusDiv.classList.remove('error');
        statusDiv.classList.add('active');
        statusDiv.style.display = 'block';
    }

    function showError(message) {
        statusDiv.textContent = message;
        statusDiv.classList.remove('active');
        statusDiv.classList.add('error');
        statusDiv.style.display = 'block';
        console.error('Error:', message);
    }
});
