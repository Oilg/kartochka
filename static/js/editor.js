document.addEventListener('DOMContentLoaded', () => {
  if (!API.requireAuth()) return;

  let canvas = null;
  let templateData = null;
  let selectedObject = null;
  const templateUid = document.getElementById('template-uid')?.value || null;

  // Initialize Fabric.js canvas
  function initCanvas(width, height) {
    if (canvas) canvas.dispose();
    canvas = new fabric.Canvas('editor-canvas', {
      width: width,
      height: height,
      backgroundColor: '#FFFFFF',
    });

    canvas.on('selection:created', (e) => {
      selectedObject = e.selected[0];
      updatePropertiesPanel();
    });
    canvas.on('selection:updated', (e) => {
      selectedObject = e.selected[0];
      updatePropertiesPanel();
    });
    canvas.on('selection:cleared', () => {
      selectedObject = null;
      updatePropertiesPanel();
    });
    canvas.on('object:modified', () => {
      updateLayersPanel();
    });

    updateCanvasScale();
  }

  function updateCanvasScale() {
    if (!canvas) return;
    const container = document.querySelector('.canvas-container');
    const maxW = container.clientWidth - 48;
    const maxH = container.clientHeight - 48;
    const scale = Math.min(1, maxW / canvas.width, maxH / canvas.height);
    const wrapper = document.querySelector('.canvas-wrapper');
    wrapper.style.transform = `scale(${scale})`;
    wrapper.style.transformOrigin = 'center center';
    document.getElementById('zoom-level').textContent = Math.round(scale * 100) + '%';
  }

  window.addEventListener('resize', updateCanvasScale);

  // Load template
  async function loadTemplate() {
    if (!templateUid) {
      // New template
      templateData = {
        name: 'Новый шаблон',
        marketplace: 'universal',
        canvas_width: 900,
        canvas_height: 1200,
        canvas_json: '{"layers": []}',
        variables: '[]',
      };
      document.getElementById('tmpl-name').value = templateData.name;
      document.getElementById('tmpl-marketplace').value = templateData.marketplace;
      document.getElementById('tmpl-width').value = templateData.canvas_width;
      document.getElementById('tmpl-height').value = templateData.canvas_height;
      initCanvas(templateData.canvas_width, templateData.canvas_height);
      return;
    }

    try {
      templateData = await API.getJSON(`/api/templates/${templateUid}`);
      document.getElementById('tmpl-name').value = templateData.name;
      document.getElementById('tmpl-marketplace').value = templateData.marketplace;
      document.getElementById('tmpl-width').value = templateData.canvas_width;
      document.getElementById('tmpl-height').value = templateData.canvas_height;
      initCanvas(templateData.canvas_width, templateData.canvas_height);
      loadCanvasFromJSON(templateData.canvas_json);
      updateVariablesList();
    } catch (e) {
      alert('Не удалось загрузить шаблон');
    }
  }

  function loadCanvasFromJSON(jsonStr) {
    if (!canvas) return;
    try {
      const data = JSON.parse(jsonStr);
      const layers = (data.layers || []).sort((a, b) => (a.zIndex || 0) - (b.zIndex || 0));
      canvas.clear();
      layers.forEach(layer => addLayerToCanvas(layer));
      updateLayersPanel();
    } catch (e) {
      console.error('Failed to load canvas JSON', e);
    }
  }

  function addLayerToCanvas(layer) {
    if (!canvas) return;
    const type = layer.type;
    let obj = null;

    if (type === 'rectangle') {
      obj = new fabric.Rect({
        left: layer.x,
        top: layer.y,
        width: layer.width,
        height: layer.height,
        fill: layer.fill || '#CCCCCC',
        opacity: layer.opacity || 1,
        rx: layer.border_radius || 0,
        ry: layer.border_radius || 0,
      });
    } else if (type === 'text' || type === 'badge') {
      obj = new fabric.IText(layer.text || 'Текст', {
        left: layer.x,
        top: layer.y,
        width: layer.width,
        fontSize: layer.font_size || 16,
        fill: layer.color || '#000000',
        fontFamily: layer.font_family || 'Roboto',
        fontWeight: layer.font_bold ? 'bold' : 'normal',
        fontStyle: layer.font_italic ? 'italic' : 'normal',
        textAlign: layer.align || 'left',
      });
    } else if (type === 'image') {
      obj = new fabric.Rect({
        left: layer.x,
        top: layer.y,
        width: layer.width,
        height: layer.height,
        fill: '#E0E0E0',
        stroke: '#AAAAAA',
        strokeDashArray: [4, 4],
        strokeWidth: 1,
      });
    }

    if (obj) {
      obj.layerData = layer;
      canvas.add(obj);
    }
  }

  function updateLayersPanel() {
    const list = document.getElementById('layers-list');
    if (!canvas) return;
    const objects = canvas.getObjects();
    list.innerHTML = objects.map((obj, i) => {
      const layer = obj.layerData || {};
      const typeIcons = { rectangle: '□', text: 'T', image: '⬜', badge: '🏷' };
      const icon = typeIcons[layer.type] || '?';
      const name = layer.id || `Слой ${i + 1}`;
      const isSelected = selectedObject === obj;
      return `<div class="layer-item ${isSelected ? 'selected' : ''}" onclick="selectLayer(${i})">
        <span class="layer-icon">${icon}</span>
        <span class="layer-name">${name}</span>
        <span class="layer-type">${layer.type || ''}</span>
      </div>`;
    }).reverse().join('');
  }

  window.selectLayer = (index) => {
    if (!canvas) return;
    const objects = canvas.getObjects();
    if (objects[index]) {
      canvas.setActiveObject(objects[index]);
      canvas.renderAll();
      selectedObject = objects[index];
      updatePropertiesPanel();
    }
  };

  function updatePropertiesPanel() {
    const panel = document.getElementById('properties-panel');
    updateLayersPanel();
    if (!selectedObject) {
      panel.innerHTML = '<div class="no-selection">Выберите элемент на холсте</div>';
      return;
    }
    const layer = selectedObject.layerData || {};
    panel.innerHTML = `
      <div class="prop-group">
        <div class="prop-group-title">Позиция и размер</div>
        <div class="prop-row-2">
          <div class="prop-field"><label>X</label><input class="form-control" id="prop-x" type="number" value="${Math.round(selectedObject.left || 0)}"></div>
          <div class="prop-field"><label>Y</label><input class="form-control" id="prop-y" type="number" value="${Math.round(selectedObject.top || 0)}"></div>
        </div>
        <div class="prop-row-2">
          <div class="prop-field"><label>Ш</label><input class="form-control" id="prop-w" type="number" value="${Math.round(selectedObject.width || 0)}"></div>
          <div class="prop-field"><label>В</label><input class="form-control" id="prop-h" type="number" value="${Math.round(selectedObject.height || 0)}"></div>
        </div>
      </div>
      ${layer.type === 'text' ? `
      <div class="prop-group">
        <div class="prop-group-title">Текст</div>
        <div class="prop-row"><label>Текст</label><input class="form-control" id="prop-text" value="${(layer.text || '').replace(/"/g, '&quot;')}"></div>
        <div class="prop-row"><label>Размер</label><input class="form-control" id="prop-fontsize" type="number" value="${layer.font_size || 16}"></div>
        <div class="prop-row"><label>Цвет</label>
          <div class="color-picker"><input type="color" id="prop-color" value="${layer.color || '#000000'}"></div>
        </div>
      </div>` : ''}
      ${layer.type === 'rectangle' ? `
      <div class="prop-group">
        <div class="prop-group-title">Прямоугольник</div>
        <div class="prop-row"><label>Цвет</label>
          <div class="color-picker"><input type="color" id="prop-fill" value="${layer.fill || '#FFFFFF'}"></div>
        </div>
        <div class="prop-row"><label>Скругление</label><input class="form-control" id="prop-radius" type="number" value="${layer.border_radius || 0}"></div>
        <div class="prop-row"><label>Прозр.</label><input class="form-control" id="prop-opacity" type="number" min="0" max="1" step="0.1" value="${layer.opacity || 1}"></div>
      </div>` : ''}
    `;
  }

  // Canvas size change
  document.getElementById('apply-size')?.addEventListener('click', () => {
    const w = parseInt(document.getElementById('tmpl-width').value) || 900;
    const h = parseInt(document.getElementById('tmpl-height').value) || 1200;
    initCanvas(w, h);
    if (templateData) {
      templateData.canvas_width = w;
      templateData.canvas_height = h;
    }
  });

  // Add layer buttons
  document.getElementById('add-rect')?.addEventListener('click', () => {
    if (!canvas) return;
    const layer = {
      type: 'rectangle', id: `rect_${Date.now()}`,
      x: 50, y: 50, width: 200, height: 150,
      zIndex: canvas.getObjects().length,
      fill: '#CCCCCC', border_radius: 0, opacity: 1.0,
    };
    addLayerToCanvas(layer);
    canvas.renderAll();
    updateLayersPanel();
  });

  document.getElementById('add-text')?.addEventListener('click', () => {
    if (!canvas) return;
    const layer = {
      type: 'text', id: `text_${Date.now()}`,
      x: 50, y: 50, width: 200, height: 60,
      zIndex: canvas.getObjects().length,
      text: 'Введите текст', font_family: 'Roboto', font_size: 24,
      font_bold: false, font_italic: false, color: '#000000',
      align: 'left', max_lines: 3, line_height: 1.2,
    };
    addLayerToCanvas(layer);
    canvas.renderAll();
    updateLayersPanel();
  });

  document.getElementById('add-image')?.addEventListener('click', () => {
    if (!canvas) return;
    const layer = {
      type: 'image', id: `image_${Date.now()}`,
      x: 50, y: 50, width: 300, height: 300,
      zIndex: canvas.getObjects().length,
      src: '{{image_url}}', fit: 'cover', border_radius: 0,
    };
    addLayerToCanvas(layer);
    canvas.renderAll();
    updateLayersPanel();
  });

  function updateVariablesList() {
    const container = document.getElementById('variables-list');
    if (!container || !templateData) return;
    try {
      const vars = JSON.parse(templateData.variables || '[]');
      container.innerHTML = vars.map(v => `
        <div class="variable-item">
          <code>{{${v.name}}}</code>
          <span>${v.label || v.name}</span>
        </div>
      `).join('') || '<div style="color: var(--secondary); font-size: 12px;">Нет переменных</div>';
    } catch (e) {
      container.innerHTML = '';
    }
  }

  function buildCanvasJSON() {
    if (!canvas) return '{"layers": []}';
    const objects = canvas.getObjects();
    const layers = objects.map((obj, i) => {
      const layer = obj.layerData ? { ...obj.layerData } : {};
      layer.x = Math.round(obj.left || 0);
      layer.y = Math.round(obj.top || 0);
      layer.width = Math.round(obj.width * (obj.scaleX || 1));
      layer.height = Math.round(obj.height * (obj.scaleY || 1));
      layer.zIndex = i;
      return layer;
    });
    return JSON.stringify({ layers });
  }

  // Save template
  async function saveTemplate() {
    const saveBtn = document.getElementById('save-btn');
    const saveStatus = document.getElementById('save-status');
    if (saveBtn) saveBtn.disabled = true;
    if (saveStatus) saveStatus.textContent = 'Сохранение...';

    const payload = {
      name: document.getElementById('tmpl-name').value || 'Шаблон',
      marketplace: document.getElementById('tmpl-marketplace').value || 'universal',
      canvas_width: parseInt(document.getElementById('tmpl-width').value) || 900,
      canvas_height: parseInt(document.getElementById('tmpl-height').value) || 1200,
      canvas_json: buildCanvasJSON(),
      variables: templateData?.variables || '[]',
    };

    try {
      if (templateUid) {
        await API.putJSON(`/api/templates/${templateUid}`, payload);
        if (saveStatus) saveStatus.textContent = 'Сохранено ✓';
      } else {
        const result = await API.postJSON('/api/templates/', payload);
        if (saveStatus) saveStatus.textContent = 'Создан ✓';
        setTimeout(() => { window.location = `/editor/${result.uid}`; }, 800);
      }
    } catch (e) {
      const msg = e?.message || 'Ошибка сохранения';
      if (saveStatus) saveStatus.textContent = 'Ошибка!';
      alert(msg);
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  document.getElementById('save-btn')?.addEventListener('click', saveTemplate);

  document.getElementById('preview-btn')?.addEventListener('click', async () => {
    if (!templateUid) { alert('Сначала сохраните шаблон'); return; }
    try {
      const result = await API.postJSON(`/api/templates/${templateUid}/preview`, {});
      window.open(result.preview_url, '_blank');
    } catch (e) {
      alert('Не удалось создать превью');
    }
  });

  loadTemplate();
});
