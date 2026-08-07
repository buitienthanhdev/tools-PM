/* ============================================================
   VoxCPM Voice AI Module — Native API Service Layer
   ============================================================ */

import { apiFetch } from './apiClient.js';

export const voxcpmService = {
  async generateVoice(text, control, refAudioFile, promptText, cfg) {
    const formData = new FormData();
    formData.append('text', text);
    formData.append('control', control);
    formData.append('prompt_text', promptText);
    formData.append('cfg', cfg);
    if (refAudioFile) {
      formData.append('ref_audio', refAudioFile);
    }

    return await apiFetch('/api/voxcpm/generate', {
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
          if (onError) onError(new Error(job.message || 'Lỗi sinh giọng nói VoxCPM'));
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
  }
};
