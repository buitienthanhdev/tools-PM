/**
 * MonaliMeow AI Platform — Background Job Tracker & Notification Engine
 * Keeps AI tasks running seamlessly in the background across route changes and browser hides.
 * Automatically purges stale/dead jobs when server resets or kills.
 */

class JobTracker {
  constructor() {
    this.jobs = new Map();
    this.activeStreams = new Map();
    this.listeners = new Set();

    // Ask desktop notification permission early
    this.requestNotificationPermission();

    // Load persisted jobs from localStorage
    this.loadFromStorage();
  }

  requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {});
    }
  }

  loadFromStorage() {
    try {
      const raw = localStorage.getItem('monali_jobs');
      if (raw) {
        const list = JSON.parse(raw);
        const now = Date.now();
        list.forEach(j => {
          // If job was created > 30 minutes ago, auto-expire it
          if (now - (j.created_at || 0) > 30 * 60 * 1000) {
            j.status = 'failed';
            j.message = 'Tác vụ đã hết hạn.';
          }

          this.jobs.set(j.id, j);

          // If job was marked running, check if server still has it
          if (j.status === 'queued' || j.status === 'processing') {
            this.verifyAndStreamJob(j.id);
          }
        });
      }
    } catch (e) {
      console.warn('[JobTracker] Failed to load jobs from storage:', e);
    }
  }

  verifyAndStreamJob(jobId) {
    // Check if server still recognizes this job
    fetch(`/api/job/${jobId}`)
      .then(res => {
        if (!res.ok) {
          throw new Error('Job not found on server');
        }
        return res.json();
      })
      .then(jobData => {
        if (jobData && !jobData.error) {
          const existing = this.jobs.get(jobId) || {};
          const updated = { ...existing, ...jobData };
          this.jobs.set(jobId, updated);
          this.saveToStorage();
          this.notifyListeners(updated);

          if (updated.status === 'queued' || updated.status === 'processing') {
            this.streamJob(jobId);
          }
        } else {
          this.markJobDead(jobId);
        }
      })
      .catch(() => {
        this.markJobDead(jobId);
      });
  }

  markJobDead(jobId) {
    const job = this.jobs.get(jobId);
    if (job) {
      job.status = 'failed';
      job.message = 'Tác vụ đã dừng (do hệ thống vừa reset/dọn rác).';
      this.jobs.set(jobId, job);
      this.saveToStorage();
      this.notifyListeners(job);
    }
  }

  clearAllJobs() {
    this.jobs.clear();
    this.activeStreams.forEach(es => es.close());
    this.activeStreams.clear();
    localStorage.removeItem('monali_jobs');
    this.notifyListeners(null);
  }

  saveToStorage() {
    try {
      const list = Array.from(this.jobs.values()).slice(-20);
      localStorage.setItem('monali_jobs', JSON.stringify(list));
    } catch (e) {
      console.warn('[JobTracker] Failed to save jobs to storage:', e);
    }
  }

  trackJob(jobData) {
    const job = {
      id: jobData.id,
      module: jobData.module,
      title: jobData.title || 'Tác vụ AI',
      route: jobData.route || '/',
      status: 'queued',
      progress: 5,
      message: 'Đang khởi tạo tác vụ...',
      result: null,
      error: null,
      created_at: Date.now()
    };

    this.jobs.set(job.id, job);
    this.saveToStorage();
    this.streamJob(job.id);

    this.requestNotificationPermission();
    return job;
  }

  streamJob(jobId) {
    if (this.activeStreams.has(jobId)) return;

    const es = new EventSource(`/api/job/${jobId}/stream`);
    this.activeStreams.set(jobId, es);

    es.onmessage = (e) => {
      try {
        const update = JSON.parse(e.data);

        // If server returns error payload (e.g. task not found after kill_tools)
        if (update.error) {
          es.close();
          this.activeStreams.delete(jobId);
          this.markJobDead(jobId);
          return;
        }

        const existing = this.jobs.get(jobId) || {};
        const updatedJob = { ...existing, ...update };

        this.jobs.set(jobId, updatedJob);
        this.saveToStorage();

        this.notifyListeners(updatedJob);

        if (updatedJob.status === 'completed') {
          es.close();
          this.activeStreams.delete(jobId);
          this.handleJobCompleted(updatedJob);
        } else if (updatedJob.status === 'failed') {
          es.close();
          this.activeStreams.delete(jobId);
          this.handleJobFailed(updatedJob);
        }
      } catch (err) {
        console.error('[JobTracker] SSE parse error:', err);
      }
    };

    es.onerror = () => {
      es.close();
      this.activeStreams.delete(jobId);
      this.verifyAndStreamJob(jobId);
    };
  }

  handleJobCompleted(job) {
    console.log('[JobTracker] Job completed:', job);

    if ('Notification' in window && Notification.permission === 'granted') {
      const notif = new Notification(`🎉 MonaliMeow: ${job.title} Hoàn Tất!`, {
        body: `Kết quả tác vụ ${job.title} đã sẵn sàng. Nhấp để xem ngay!`,
        icon: '/assets/logo.webp',
        tag: job.id,
        renotify: true
      });

      notif.onclick = () => {
        window.focus();
        if (window.router) {
          window.router.navigate(job.route);
        }
        notif.close();
      };
    }

    window.dispatchEvent(new CustomEvent('monali:job_completed', { detail: job }));
  }

  handleJobFailed(job) {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(`❌ MonaliMeow: ${job.title} Thất Bại`, {
        body: job.message || 'Đã có lỗi xảy ra trong quá trình xử lý.',
        icon: '/assets/logo.webp'
      });
    }
  }

  getJob(jobId) {
    return this.jobs.get(jobId);
  }

  getLatestJobForModule(moduleId) {
    const list = Array.from(this.jobs.values())
      .filter(j => j.module === moduleId)
      .sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
    return list[0] || null;
  }

  subscribe(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  notifyListeners(job) {
    this.listeners.forEach(cb => {
      try { cb(job); } catch (e) {}
    });
  }
}

export const jobTracker = new JobTracker();
window.jobTracker = jobTracker;
