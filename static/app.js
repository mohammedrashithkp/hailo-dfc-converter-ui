document.addEventListener("DOMContentLoaded", () => {
    let modelUploaded = false;
    let datasetUploaded = false;

    // --- Drag and Drop Setup ---
    function setupDropzone(dropzoneId, inputId, uploadUrl, successCallback) {
        const dropzone = document.getElementById(dropzoneId);
        const input = document.getElementById(inputId);
        const statusEl = document.getElementById(dropzoneId.replace('dropzone', 'status'));

        // Click to browse
        dropzone.addEventListener("click", () => input.click());

        // Drag events
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
        });

        // Drop event
        dropzone.addEventListener('drop', (e) => {
            let dt = e.dataTransfer;
            let files = dt.files;
            if (files.length) handleFiles(files);
        });

        input.addEventListener('change', function() {
            if (this.files.length) handleFiles(this.files);
        });

        function handleFiles(files) {
            const file = files[0];
            uploadFile(file);
        }

        function uploadFile(file) {
            const formData = new FormData();
            formData.append("file", file);

            statusEl.className = "status-message";
            statusEl.innerText = `Uploading ${file.name}...`;
            statusEl.style.display = "block";

            fetch(uploadUrl, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    statusEl.innerText = `✅ ${file.name} uploaded successfully`;
                    statusEl.className = "status-message success";
                    dropzone.style.borderColor = "var(--success)";
                    successCallback();
                } else {
                    statusEl.innerText = `❌ Error: ${data.message}`;
                    statusEl.className = "status-message error";
                    dropzone.style.borderColor = "var(--error)";
                }
            })
            .catch(error => {
                statusEl.innerText = `❌ Upload failed`;
                statusEl.className = "status-message error";
            });
        }
    }

    // Initialize Dropzones
    setupDropzone("model-dropzone", "model-input", "/upload_model", () => {
        modelUploaded = true;
        checkReady();
    });

    setupDropzone("dataset-dropzone", "dataset-input", "/upload_dataset", () => {
        datasetUploaded = true;
        checkReady();
    });

    // Check if ready to compile
    const compileBtn = document.getElementById('compile-btn');
    function checkReady() {
        if (modelUploaded) {
            compileBtn.disabled = false;
        }
    }

    // --- Compilation Execution ---
    const terminalContainer = document.getElementById('terminal-container');
    const terminalOutput = document.getElementById('terminal-output');
    const downloadSection = document.getElementById('download-section');

    compileBtn.addEventListener('click', async () => {
        const hwArch = document.getElementById('hw-arch').value;
        const inputSize = document.getElementById('input-size').value;

        // UI updates
        compileBtn.disabled = true;
        compileBtn.innerHTML = `Compiling... <span style="display:inline-block; animation: spin 1s linear infinite;">⏳</span>`;
        terminalContainer.style.display = "block";
        terminalOutput.innerHTML = "[SYSTEM] Initiating compilation environment...\n";
        downloadSection.style.display = "none";

        // Setup WebSocket for logs
        const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/logs`;
        const ws = new WebSocket(wsUrl);

        ws.onmessage = function(event) {
            const msg = event.data;
            if (msg === "COMPILATION_SUCCESS") {
                compileBtn.innerHTML = `Compilation Complete!`;
                compileBtn.style.background = "var(--success)";
                downloadSection.style.display = "flex";
                ws.close();
            } else if (msg === "COMPILATION_ERROR") {
                compileBtn.innerHTML = `Compilation Failed`;
                compileBtn.style.background = "var(--error)";
                ws.close();
            } else {
                terminalOutput.innerHTML += msg;
                terminalOutput.scrollTop = terminalOutput.scrollHeight;
            }
        };

        // Trigger compilation
        const formData = new FormData();
        formData.append("hw_arch", hwArch);
        formData.append("input_size", inputSize);

        fetch("/compile", {
            method: "POST",
            body: formData
        }).then(res => res.json()).then(data => {
            if (data.status === "error") {
                terminalOutput.innerHTML += `\n[ERROR] ${data.message}\n`;
                compileBtn.disabled = false;
                compileBtn.innerHTML = `Start Compilation`;
                ws.close();
            }
        });
    });
});

// Adding spin animation inline
const style = document.createElement('style');
style.innerHTML = `
@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
`;
document.head.appendChild(style);
