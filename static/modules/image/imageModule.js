/* ============================================================
   Image Enhancer AI Module Plugin
   ============================================================ */

export const imageModule = {
  id: 'image',
  name: 'Nét Ảnh AI',
  route: '/Image',
  icon: '🖼️',
  category: 'Vision AI',
  description: 'Làm rõ nét hình ảnh mờ, tăng độ phân giải 4K và khôi phục ảnh cũ tự động.',
  status: 'active',

  render(containerEl) {
    containerEl.innerHTML = `
      <div class="workspace-page-header">
        <div class="page-title-group">
          <h1>🖼️ Module: Nét Ảnh & Image Upscale AI</h1>
          <p>Công cụ làm rõ nét ảnh mờ, khôi phục chi tiết và tăng kích thước ảnh 4K bằng AI.</p>
        </div>
      </div>

      <div class="panel-card" style="padding:2rem; max-width:1000px; margin:0 auto;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;">
          <div>
            <h2 style="font-size:1.3rem; font-weight:700; color:var(--text-main);">🖼️ Upscayl Image Enhancer Engine</h2>
            <p style="color:var(--text-muted); font-size:0.9rem;">Module tích hợp từ <code>modules/image_enhancer</code></p>
          </div>
          <span class="badge-tag badge-active">Hoạt Động</span>
        </div>

        <!-- Upload Dropzone -->
        <div id="dropZone" style="border: 2px dashed var(--border-color, #444); padding: 3rem; text-align: center; border-radius: 12px; background: rgba(255,255,255,0.02); cursor: pointer; transition: all 0.2s;">
          <div style="font-size: 3.5rem; margin-bottom: 1rem;">📤</div>
          <p style="font-weight:600; font-size:1.1rem; margin-bottom:0.5rem;">Kéo thả hình ảnh vào đây hoặc bấm để chọn ảnh</p>
          <p style="font-size:0.85rem; color:var(--text-dim);">Hỗ trợ định dạng PNG, JPG, JPEG, WEBP (Tối đa 25MB)</p>
          <input type="file" id="upscaylInput" accept="image/*" style="display:none;" />
          <button class="btn btn-primary" id="btnSelectImg" style="margin-top:1.5rem;">📁 Chọn Ảnh Từ Máy Tính</button>
        </div>

        <!-- Workspace & Settings Section -->
        <div id="workspaceSection" style="display:none; margin-top:1.5rem;">
          <!-- Controls Bar -->
          <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color, #333); padding:1.2rem; border-radius:10px; margin-bottom:1.5rem; display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:1rem; align-items:center;">
            <div>
              <label style="display:block; font-size:0.85rem; font-weight:600; color:var(--text-muted); margin-bottom:0.4rem;">Tỉ Lệ Phóng To (Resolution):</label>
              <select id="scaleSelect" class="form-input" style="width:100%;">
                <option value="2x">Phóng to 2X (2K)</option>
                <option value="4x" selected>Phóng to 4X (4K Resolution)</option>
              </select>
            </div>
            <div>
              <label style="display:block; font-size:0.85rem; font-weight:600; color:var(--text-muted); margin-bottom:0.4rem;">Mô Hình AI (AI Model):</label>
              <select id="modelSelect" class="form-input" style="width:100%;">
                <option value="ultrasharp" selected>REAL-ESRGAN UltraSharp (Khuyên Dùng)</option>
                <option value="remacri">Remacri Ultra-Detail</option>
                <option value="digital_art">Digital Art / Anime Upscaler</option>
              </select>
            </div>
            <div style="display:flex; gap:0.5rem; align-items:flex-end;">
              <button class="btn btn-secondary" id="btnReselect" style="flex:1;">Chọn Ảnh Khác</button>
              <button class="btn btn-primary" id="btnProcess" style="flex:2;">🚀 Render Xử Lý AI</button>
            </div>
          </div>

          <!-- Processing Progress Loader -->
          <div id="processingLoader" style="display:none; text-align:center; padding:2rem; background:rgba(0,0,0,0.2); border-radius:10px; margin-bottom:1.5rem;">
            <div style="font-size:2.5rem; margin-bottom:0.5rem; animation: spin 1s infinite linear;">⚙️</div>
            <p style="font-weight:600; color:var(--text-main);" id="loaderText">Đang nâng cấp chất lượng & khử mờ bằng AI Engine...</p>
            <p style="font-size:0.8rem; color:var(--text-dim);">Quá trình có thể mất vài giây tùy độ phân giải.</p>
          </div>

          <!-- Visual Comparison Viewer -->
          <div id="comparisonContainer" style="display:none;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.8rem;">
              <h3 style="font-size:1.05rem; font-weight:700; color:var(--text-main);">🔍 So Sánh Đối Chiếu Ảnh Cũ (Gốc) & Ảnh Mới (Sau AI Render)</h3>
              <a id="btnDownload" href="#" download="enhanced_image.png" class="btn btn-success" style="background:#10b981; color:#fff; font-weight:700; padding:0.6rem 1.2rem; border-radius:8px; text-decoration:none; display:inline-flex; align-items:center; gap:0.5rem;">
                📥 Tải Ảnh 4K Về Máy
              </a>
            </div>

            <!-- Side-by-side / Before-After Comparison Split View -->
            <div style="position:relative; width:100%; height:480px; overflow:hidden; border-radius:10px; border:1px solid var(--border-color, #444); user-select:none;" id="compareWrapper">
              <!-- After Image (Enhanced) -->
              <img id="imgEnhanced" src="" alt="Enhanced" style="position:absolute; top:0; left:0; width:100%; height:100%; object-fit:contain; background:#111;" />
              
              <!-- Before Image (Original - Clipped) -->
              <div id="beforeClip" style="position:absolute; top:0; left:0; width:50%; height:100%; overflow:hidden; border-right:2px solid #00f0ff;">
                <img id="imgOriginal" src="" alt="Original" style="position:absolute; top:0; left:0; width:100%; height:100%; object-fit:contain; background:#111;" />
              </div>

              <!-- Slider Bar Label Overlay -->
              <span style="position:absolute; top:12px; left:12px; background:rgba(0,0,0,0.7); color:#fff; font-size:0.75rem; padding:4px 8px; border-radius:4px; font-weight:700; z-index:5;">Ảnh Gốc (Gốc)</span>
              <span style="position:absolute; top:12px; right:12px; background:rgba(16,185,129,0.9); color:#fff; font-size:0.75rem; padding:4px 8px; border-radius:4px; font-weight:700; z-index:5;">Sau Render AI (Đã Nét)</span>

              <!-- Range Slider Handle -->
              <input type="range" id="compareSlider" min="0" max="100" value="50" style="position:absolute; top:0; left:0; width:100%; height:100%; opacity:0; cursor:ew-resize; z-index:10;" />
            </div>
          </div>
        </div>
      </div>
    `;

    const dropZone = containerEl.querySelector('#dropZone');
    const inputEl = containerEl.querySelector('#upscaylInput');
    const btnSelect = containerEl.querySelector('#btnSelectImg');
    const workspaceSection = containerEl.querySelector('#workspaceSection');
    const btnReselect = containerEl.querySelector('#btnReselect');
    const btnProcess = containerEl.querySelector('#btnProcess');
    const scaleSelect = containerEl.querySelector('#scaleSelect');
    const modelSelect = containerEl.querySelector('#modelSelect');

    const loader = containerEl.querySelector('#processingLoader');
    const comparisonContainer = containerEl.querySelector('#comparisonContainer');
    const imgOriginal = containerEl.querySelector('#imgOriginal');
    const imgEnhanced = containerEl.querySelector('#imgEnhanced');
    const beforeClip = containerEl.querySelector('#beforeClip');
    const compareSlider = containerEl.querySelector('#compareSlider');
    const compareWrapper = containerEl.querySelector('#compareWrapper');
    const btnDownload = containerEl.querySelector('#btnDownload');

    let selectedFile = null;
    let uploadedJobId = null;

    const handleFile = async (file) => {
      if (!file || !file.type.startsWith('image/')) {
        alert('Vui lòng chọn file hình ảnh hợp lệ (PNG, JPG, WEBP)!');
        return;
      }
      selectedFile = file;

      // 1. Tạo DataURL để xem trước ảnh gốc ngay lập tức
      const reader = new FileReader();
      reader.onload = (e) => {
        imgOriginal.src = e.target.result;
      };
      reader.readAsDataURL(file);

      // 2. Chuyển sang màn hình workspace
      dropZone.style.display = 'none';
      workspaceSection.style.display = 'block';
      loader.style.display = 'block';
      comparisonContainer.style.display = 'none';
      containerEl.querySelector('#loaderText').innerText = 'Đang tải ảnh lên máy chủ...';

      // 3. Tải file lên backend để nhận job_id
      const formData = new FormData();
      formData.append('image', file);

      try {
        const res = await fetch('/api/image/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (res.ok && data.job_id) {
          uploadedJobId = data.job_id;
          loader.style.display = 'none';
        } else {
          alert(`❌ Lỗi tải ảnh: ${data.error || 'Vui lòng thử lại'}`);
          btnReselect.click();
        }
      } catch (err) {
        alert(`❌ Lỗi kết nối server: ${err.message}`);
        btnReselect.click();
      }
    };

    if (btnSelect && inputEl) {
      btnSelect.addEventListener('click', (e) => {
        e.stopPropagation();
        inputEl.click();
      });
      dropZone.addEventListener('click', () => inputEl.click());
      inputEl.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          handleFile(e.target.files[0]);
        }
      });
    }

    if (dropZone) {
      dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--accent-color, #0070f3)';
      });
      dropZone.addEventListener('dragleave', () => {
        dropZone.style.borderColor = 'var(--border-color, #444)';
      });
      dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--border-color, #444)';
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleFile(e.dataTransfer.files[0]);
        }
      });
    }

    if (btnReselect) {
      btnReselect.addEventListener('click', () => {
        selectedFile = null;
        uploadedJobId = null;
        inputEl.value = '';
        workspaceSection.style.display = 'none';
        comparisonContainer.style.display = 'none';
        dropZone.style.display = 'block';
      });
    }

    // Comparison slider logic
    if (compareSlider && beforeClip && compareWrapper) {
      const syncImagesSize = () => {
        const rect = compareWrapper.getBoundingClientRect();
        imgOriginal.style.width = `${rect.width}px`;
        imgOriginal.style.height = `${rect.height}px`;
      };
      window.addEventListener('resize', syncImagesSize);
      setTimeout(syncImagesSize, 100);

      compareSlider.addEventListener('input', (e) => {
        const val = e.target.value;
        beforeClip.style.width = `${val}%`;
      });
    }

    // Render & Process logic
    if (btnProcess) {
      btnProcess.addEventListener('click', async () => {
        if (!selectedFile) {
          alert('Vui lòng chọn ảnh hợp lệ trước!');
          return;
        }

        btnProcess.disabled = true;
        loader.style.display = 'block';

        // Nếu vì lý do mạng chưa upload xong, thực hiện upload ngay tại đây
        if (!uploadedJobId) {
          containerEl.querySelector('#loaderText').innerText = 'Đang tải ảnh lên máy chủ...';
          const formData = new FormData();
          formData.append('image', selectedFile);
          try {
            const uploadRes = await fetch('/api/image/upload', {
              method: 'POST',
              body: formData
            });
            const uploadData = await uploadRes.json();
            if (uploadRes.ok && uploadData.job_id) {
              uploadedJobId = uploadData.job_id;
            } else {
              alert(`❌ Lỗi tải ảnh: ${uploadData.error || 'Vui lòng thử lại'}`);
              loader.style.display = 'none';
              btnProcess.disabled = false;
              return;
            }
          } catch (err) {
            alert(`❌ Lỗi kết nối server: ${err.message}`);
            loader.style.display = 'none';
            btnProcess.disabled = false;
            return;
          }
        }

        containerEl.querySelector('#loaderText').innerText = `Đang render nâng cấp ảnh [${scaleSelect.value}] bằng AI model ${modelSelect.value}...`;

        try {
          const res = await fetch('/api/image/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              job_id: uploadedJobId,
              scale: scaleSelect.value,
              model: modelSelect.value
            })
          });
          const data = await res.json();
          if (res.ok) {
            imgOriginal.src = data.orig_path;
            imgEnhanced.src = data.enhanced_path;
            const downloadUrl = `${data.enhanced_path}?download=1`;
            btnDownload.href = downloadUrl;
            btnDownload.download = `enhanced_4k_${data.width}x${data.height}.png`;
            
            // Ép tải file trực tiếp qua blob fetch nếu trình duyệt chặn download cross-origin/inline
            btnDownload.onclick = async (e) => {
              e.preventDefault();
              try {
                const resFile = await fetch(data.enhanced_path);
                const blob = await resFile.blob();
                const blobUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = blobUrl;
                a.download = `enhanced_4k_${data.width}x${data.height}.png`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(blobUrl);
              } catch (downloadErr) {
                window.location.href = downloadUrl;
              }
            };
            
            loader.style.display = 'none';
            comparisonContainer.style.display = 'block';
            
            // Adjust original image size overlay
            const rect = compareWrapper.getBoundingClientRect();
            imgOriginal.style.width = `${rect.width}px`;
            imgOriginal.style.height = `${rect.height}px`;
          } else {
            alert(`❌ Lỗi render ảnh: ${data.error}`);
            loader.style.display = 'none';
          }
        } catch (err) {
          alert(`❌ Lỗi kết nối: ${err.message}`);
          loader.style.display = 'none';
        } finally {
          btnProcess.disabled = false;
        }
      });
    }
  },

  unmount(containerEl) {
    containerEl.innerHTML = '';
  }
};
