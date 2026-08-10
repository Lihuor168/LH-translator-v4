function showFileName() {
    const fileInput = document.getElementById('media-file');
    const display = document.getElementById('file-name-display');
    if (fileInput.files.length > 0) {
        display.innerText = "📄 File ដែលបានជ្រើស៖ " + fileInput.files[0].name;
    }
}

document.getElementById('upload-form').addEventListener('submit', async function(e) {
    e.preventDefault();

    const fileInput = document.getElementById('media-file');
    const sourceLang = document.getElementById('source-lang').value;
    const customApiKey = document.getElementById('custom-api-key').value;
    const submitBtn = document.getElementById('submit-btn');
    const loading = document.getElementById('loading');
    const resultBox = document.getElementById('result-box');
    const outputText = document.getElementById('output-text');

    if (fileInput.files.length === 0) {
        alert('សូមជ្រើសរើស File វីដេអូ ឬសំឡេងជាមុនសិន!');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('lang', sourceLang);
    formData.append('api_key', customApiKey);

    submitBtn.disabled = true;
    loading.classList.remove('hidden');
    resultBox.classList.add('hidden');

    try {
        const response = await fetch('/translate-video', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            outputText.value = data.translated_text;
            resultBox.classList.remove('hidden');
        } else {
            alert('មានបញ្ហា៖ ' + (data.error || 'មិនអាចបកប្រែបានទេ'));
        }
    } catch (error) {
        alert('មានបញ្ហាក្នុងការភ្ជាប់ទៅកាន់ Server!');
        console.error(error);
    } finally {
        submitBtn.disabled = false;
        loading.classList.add('hidden');
    }
});

function copyResult() {
    const outputText = document.getElementById('output-text');
    if (!outputText.value) return;
    outputText.select();
    document.execCommand('copy');
    alert('បានចម្លងអត្ថបទបកប្រែរួចរាល់!');
}
