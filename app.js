async function translateStory() {
    const inputText = document.getElementById('input-text').value;
    const sourceLang = document.getElementById('source-lang').value;
    const outputText = document.getElementById('output-text');
    const loading = document.getElementById('loading');
    const translateBtn = document.getElementById('translate-btn');

    if (!inputText.trim()) {
        alert('សូមបញ្ចូលអត្ថបទសាច់រឿងជាមុនសិន!');
        return;
    }

    loading.classList.remove('hidden');
    translateBtn.disabled = true;
    outputText.value = '';

    try {
        const response = await fetch('/translate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text: inputText,
                source_lang: sourceLang
            }),
        });

        const data = await response.json();

        if (response.ok) {
            outputText.value = data.translated_text;
        } else {
            alert('មានបញ្ហា៖ ' + (data.error || 'មិនអាចបកប្រែបានទេ'));
        }
    } catch (error) {
        alert('មានបញ្ហាក្នុងការភ្ជាប់ទៅកាន់ Server!');
        console.error(error);
    } finally {
        loading.classList.add('hidden');
        translateBtn.disabled = false;
    }
}

function copyResult() {
    const outputText = document.getElementById('output-text');
    if (!outputText.value) {
        alert('គ្មានអត្ថបទសម្រាប់ Copy ទេ!');
        return;
    }
    outputText.select();
    document.execCommand('copy');
    alert('បានចម្លងអត្ថបទបកប្រែរួចរាល់!');
}
