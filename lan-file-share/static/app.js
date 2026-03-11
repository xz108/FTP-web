(function () {
  const root = document.body;
  const themeBtn = document.getElementById('btnTheme');
  const storedTheme = localStorage.getItem('lanfs_theme') || 'light';
  setTheme(storedTheme);

  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      setTheme(next);
    });
  }

  function setTheme(mode) {
    root.setAttribute('data-theme', mode);
    localStorage.setItem('lanfs_theme', mode);
    if (themeBtn) {
      themeBtn.textContent = mode === 'dark' ? '亮色模式' : '暗黑模式';
    }
  }

  const fileInput = document.getElementById('fileInput');
  const folderInput = document.getElementById('folderInput');
  const btnUpload = document.getElementById('btnUpload');
  const btnUploadFolder = document.getElementById('btnUploadFolder');
  const btnMkdir = document.getElementById('btnMkdir');
  const btnRefresh = document.getElementById('btnRefresh');
  const btnCopyLink = document.getElementById('btnCopyLink');
  const uploadModal = document.getElementById('uploadModal');
  const uploadBar = document.getElementById('uploadBar');
  const uploadText = document.getElementById('uploadText');
  const previewModal = document.getElementById('previewModal');
  const previewBody = document.getElementById('previewBody');
  const previewTitle = document.getElementById('previewTitle');
  const previewClose = document.getElementById('previewClose');
  const contextMenu = document.getElementById('contextMenu');

  const currentPath = window.__CURRENT_PATH__ || '';

  if (btnUpload && fileInput) {
    btnUpload.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => handleUpload(fileInput.files));
  }

  if (btnUploadFolder && folderInput) {
    btnUploadFolder.addEventListener('click', () => folderInput.click());
    folderInput.addEventListener('change', () => handleUpload(folderInput.files));
  }

  if (btnMkdir) {
    btnMkdir.addEventListener('click', async () => {
      const name = prompt('新文件夹名称');
      if (!name) return;
      await postForm('/mkdir', { path: currentPath, name });
      location.reload();
    });
  }

  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => location.reload());
  }

  if (btnCopyLink) {
    btnCopyLink.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(location.href);
        alert('已复制链接');
      } catch (err) {
        alert('复制失败，可手动复制地址栏链接');
      }
    });
  }

  document.querySelectorAll('.file-row').forEach((row) => {
    row.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      showContextMenu(e.pageX, e.pageY, row);
    });
  });

  document.querySelectorAll('.file-link').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const row = e.target.closest('.file-row');
      openItem(row);
    });
  });

  document.addEventListener('click', () => hideContextMenu());
  window.addEventListener('scroll', () => hideContextMenu());

  if (contextMenu) {
    contextMenu.querySelectorAll('button').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const action = e.target.getAttribute('data-action');
        const row = contextMenu._targetRow;
        if (!row) return;
        if (action === 'download') return downloadItem(row);
        if (action === 'rename') return renameItem(row);
        if (action === 'delete') return deleteItem(row);
      });
    });
  }

  if (previewClose) {
    previewClose.addEventListener('click', () => hidePreview());
  }

  if (previewModal) {
    previewModal.addEventListener('click', (e) => {
      if (e.target === previewModal) hidePreview();
    });
  }

  async function handleUpload(fileList) {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    const total = files.reduce((sum, f) => sum + (f.size || 0), 0);
    const form = new FormData();
    form.append('path', currentPath);
    files.forEach((file) => {
      const name = file.webkitRelativePath || file.name;
      form.append('files', file, name);
    });

    showUpload();
    await xhrUpload('/upload', form, total);
    hideUpload();
    location.reload();
  }

  function showUpload() {
    if (!uploadModal) return;
    uploadModal.classList.remove('hidden');
    if (uploadBar) uploadBar.style.width = '0%';
    if (uploadText) uploadText.textContent = '准备上传';
  }

  function hideUpload() {
    if (!uploadModal) return;
    uploadModal.classList.add('hidden');
  }

  function showContextMenu(x, y, row) {
    if (!contextMenu) return;
    contextMenu._targetRow = row;
    contextMenu.style.left = `${x}px`;
    contextMenu.style.top = `${y}px`;
    contextMenu.classList.remove('hidden');
  }

  function hideContextMenu() {
    if (!contextMenu) return;
    contextMenu.classList.add('hidden');
  }

  function openItem(row) {
    if (!row) return;
    const path = row.getAttribute('data-path');
    const type = row.getAttribute('data-type');
    const isDir = row.getAttribute('data-is-dir') === '1';
    if (isDir) {
      location.href = `/?path=${encodeURIComponent(path)}`;
      return;
    }
    if (type === 'image' || type === 'video') {
      showPreview(type, path);
      return;
    }
    if (type === 'text') {
      showTextPreview(path);
      return;
    }
    location.href = `/download?path=${encodeURIComponent(path)}`;
  }

  function downloadItem(row) {
    const path = row.getAttribute('data-path');
    const isDir = row.getAttribute('data-is-dir') === '1';
    location.href = isDir
      ? `/download-zip?path=${encodeURIComponent(path)}`
      : `/download?path=${encodeURIComponent(path)}`;
  }

  async function deleteItem(row) {
    const path = row.getAttribute('data-path');
    const ok = confirm('确定删除？');
    if (!ok) return;
    await postForm('/delete', { path });
    location.reload();
  }

  async function renameItem(row) {
    const path = row.getAttribute('data-path');
    const current = row.querySelector('.file-link').textContent;
    const name = prompt('新名称', current);
    if (!name || name === current) return;
    await postForm('/rename', { path, new_name: name });
    location.reload();
  }

  async function postForm(url, data) {
    const form = new FormData();
    Object.keys(data).forEach((key) => form.append(key, data[key]));
    const res = await fetch(url, { method: 'POST', body: form });
    if (!res.ok) {
      const msg = await res.text();
      alert(msg);
    }
  }

  function xhrUpload(url, form, total) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', url, true);
      xhr.upload.onprogress = (evt) => {
        if (!evt.lengthComputable) return;
        const percent = total ? Math.min(100, (evt.loaded / total) * 100) : 0;
        if (uploadBar) uploadBar.style.width = `${percent.toFixed(1)}%`;
        if (uploadText) {
          uploadText.textContent = `已上传 ${formatBytes(evt.loaded)} / ${formatBytes(total)}`;
        }
      };
      xhr.onload = () => resolve();
      xhr.onerror = () => reject(new Error('upload failed'));
      xhr.send(form);
    });
  }

  function showPreview(type, path) {
    if (!previewModal) return;
    previewTitle.textContent = '预览';
    previewBody.innerHTML = '';
    if (type === 'image') {
      const img = document.createElement('img');
      img.src = `/file?path=${encodeURIComponent(path)}`;
      img.className = 'max-h-[70vh] w-full object-contain rounded-lg';
      previewBody.appendChild(img);
    } else if (type === 'video') {
      const video = document.createElement('video');
      video.src = `/file?path=${encodeURIComponent(path)}`;
      video.controls = true;
      video.className = 'max-h-[70vh] w-full rounded-lg';
      previewBody.appendChild(video);
    }
    previewModal.classList.remove('hidden');
  }

  async function showTextPreview(path) {
    if (!previewModal) return;
    previewTitle.textContent = '文本预览';
    previewBody.innerHTML = '<div class="text-sm text-slate-500">加载中...</div>';
    previewModal.classList.remove('hidden');
    try {
      const res = await fetch(`/text-preview?path=${encodeURIComponent(path)}`);
      const text = await res.text();
      const pre = document.createElement('pre');
      pre.className = 'max-h-[60vh] overflow-auto rounded-lg bg-slate-900 p-4 text-slate-100 text-xs';
      pre.textContent = text;
      previewBody.innerHTML = '';
      previewBody.appendChild(pre);
    } catch (err) {
      previewBody.textContent = '无法预览该文件';
    }
  }

  function hidePreview() {
    if (!previewModal) return;
    previewModal.classList.add('hidden');
    previewBody.innerHTML = '';
  }

  function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let num = bytes;
    while (num >= 1024 && i < units.length - 1) {
      num /= 1024;
      i++;
    }
    return i === 0 ? `${num.toFixed(0)} ${units[i]}` : `${num.toFixed(1)} ${units[i]}`;
  }
})();
