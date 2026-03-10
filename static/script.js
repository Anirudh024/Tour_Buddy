document.addEventListener('DOMContentLoaded', () => {
    const modeBtns = document.querySelectorAll('.mode-btn');
    const cameraSection = document.getElementById('camera-section');
    const imageSection = document.getElementById('image-section');
    const webcam = document.getElementById('webcam');
    const fileInput = document.getElementById('file-input');
    const imagePreview = document.getElementById('image-preview');
    const analyzeBtn = document.getElementById('analyze-btn');
    
    let currentMode = 'camera';
    let stream = null;

    // Handle Mode Switching
    modeBtns.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            modeBtns.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentMode = e.target.dataset.mode;

            if (currentMode === 'camera') {
                cameraSection.classList.add('active');
                imageSection.classList.remove('active');
                startCamera();
            } else {
                cameraSection.classList.remove('active');
                imageSection.classList.add('active');
                stopCamera();
            }
        });
    });

    // Camera Logic
    async function startCamera() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
            webcam.srcObject = stream;
        } catch (err) {
            console.error("Error accessing webcam:", err);
            alert("Could not access the camera. Please check permissions.");
        }
    }

    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            webcam.srcObject = null;
        }
    }

    // Initialize default mode
    startCamera();

    // Image Upload Preview Logic
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                imagePreview.style.display = 'block';
                document.querySelector('.file-drop-area').style.display = 'none';
            };
            reader.readAsDataURL(file);
        }
    });

    // Audio filler to keep user engaged during API calls
    function playFillerSpeech() {
        const phrases = [
            "Let me take a closer look at that for you...",
            "Interesting. I'm analyzing the details right now...",
            "Give me just a second to gather the history on this..."
        ];
        const randomPhrase = phrases[Math.floor(Math.random() * phrases.length)];
        
        // Ensure browser TTS stops any previous ongoing speech
        window.speechSynthesis.cancel(); 
        const utterance = new SpeechSynthesisUtterance(randomPhrase);
        utterance.rate = 1.1;
        window.speechSynthesis.speak(utterance);
    }

    // Submit Logic
    analyzeBtn.addEventListener('click', async () => {
        const textInput = document.getElementById('text-input').value;
        const formData = new FormData();
        formData.append('mode', currentMode);
        formData.append('text_input', textInput);

        if (currentMode === 'camera') {
            const canvas = document.getElementById('canvas');
            canvas.width = webcam.videoWidth;
            canvas.height = webcam.videoHeight;
            canvas.getContext('2d').drawImage(webcam, 0, 0);
            
            // Convert canvas to blob
            const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg'));
            formData.append('file', blob, 'capture.jpg');
        } else {
            const file = fileInput.files[0];
            if (!file) return alert("Please select an image first.");
            formData.append('file', file);
        }

        // Update UI & Play Filler Audio
        document.getElementById('status-container').style.display = 'block';
        document.getElementById('result-container').style.display = 'none';
        analyzeBtn.disabled = true;
        
        playFillerSpeech();

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.status === 'success') {
                document.getElementById('insight-text').textContent = data.insight;
                document.getElementById('audio-player').src = data.audio_data;
                document.getElementById('result-container').style.display = 'block';
            } else {
                alert("Error: " + data.message);
            }
        } catch (error) {
            console.error("Error submitting data:", error);
            alert("Failed to analyze. Check server logs.");
        } finally {
            document.getElementById('status-container').style.display = 'none';
            analyzeBtn.disabled = false;
        }
    });
});