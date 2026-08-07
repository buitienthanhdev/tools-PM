/* ============================================================
   Whisper AI Module — API Service Layer
   ============================================================ */

import { apiFetch } from './apiClient.js';

export const whisperService = {
  async transcribeAudio(file, model, language, task) {
    const formData = new FormData();
    formData.append('audio', file);
    formData.append('model', model);
    formData.append('language', language);
    formData.append('task', task);

    return await apiFetch('/api/transcribe', {
      method: 'POST',
      body: formData
    });
  },

  createJobStream(jobId, onProgress, onComplete, onError) {
    const eventSource = new EventSource(`/api/job/${jobId}/stream`);

    eventSource.onmessage = (e) => {
      try {
        const job = JSON.parse(e.data);
        if (onProgress) onProgress(job);

        if (job.status === 'completed') {
          eventSource.close();
          if (onComplete) onComplete(job.result);
        } else if (job.status === 'failed') {
          eventSource.close();
          if (onError) onError(new Error(job.message || 'Job failed'));
        }
      } catch (err) {
        eventSource.close();
        if (onError) onError(err);
      }
    };

    eventSource.onerror = (err) => {
      eventSource.close();
      if (onError) onError(new Error('Mất kết nối với server'));
    };

    return eventSource;
  },

  async exportResult(format, resultData) {
    const res = await fetch(`/api/export/${format}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ result: resultData })
    });

    if (!res.ok) throw new Error('Export error');
    
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transcription.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  }
};
