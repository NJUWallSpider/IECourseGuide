/* 站内投稿页（/提交修改/）的表单逻辑。
 *
 * 严格按 .github/contribution-schema.md 第 2、3、7 节实现：
 *   - 拼 Issue 正文（人读部分 + 隐藏的 ie-contribution:v1 JSON）；
 *   - 客户端校验：必填、长度、edit 的 old ≥ 8 字、链接 http(s) 等；
 *   - window.open 打开 GitHub issues/new 预填页面；
 *   - 正文过长（URL 超过 6000 字符）时降级：先复制正文，只打开带标题的空白 Issue，
 *     由贡献者 Ctrl+V 粘贴；
 *   - 始终提供「预览 Issue 正文」「复制正文」兜底。
 *
 * 纯原生 JS，无第三方依赖。
 * 配置来自 overrides/main.html 注入的 window.IE_CONTRIB.repo。
 */
(function () {
  'use strict';

  var DEFAULT_REPO = 'NJUWallSpider/IECourseGuide';
  var KIND_LABELS = {
    material: '补充资料',
    append: '增补介绍',
    edit: '纠错 / 修改',
    'new-course': '新增课程页'
  };
  var CATEGORIES = ['专业核心课', '专业选修课', '跨专业课', '数理基础课', '必学工具', '其他'];
  var FALLBACK_CATEGORY = '其他页面';
  var LIMITS = {
    title: 120,
    course: 60,
    notes: 2000,
    content: 20000,
    links: 10,
    replacements: 20,
    oldMin: 8,
    displayName: 120,
    section: 120,
    newCourseName: 40,
    urlLength: 6000,
    files: 10,
    fileBytes: 25 * 1024 * 1024
  };

  // 与 tools/submission.py 的 FORBIDDEN_ATTACHMENT_EXTENSIONS 对齐（并补充 .js/.jse/.wsh），
  // 拒绝可执行文件、可执行脚本与可能带来 XSS 的网页类文件。
  var FORBIDDEN_EXTENSIONS = [
    '.exe', '.dll', '.msi', '.msp', '.bat', '.cmd', '.com', '.scr', '.pif',
    '.ps1', '.psm1', '.vbs', '.vbe', '.wsf', '.wsh', '.js', '.jse',
    '.hta', '.lnk', '.reg', '.jar', '.apk', '.dmg', '.pkg', '.deb', '.rpm',
    '.app', '.iso', '.html', '.htm', '.xhtml', '.svg', '.swf'
  ];

  var state = {
    kind: 'material',
    courses: [],
    coursesLoaded: false,
    fromParam: '',
    files: [],
    lastBody: '',
    lastUrl: '',
    lastTitleOnlyUrl: ''
  };
  var els = {};

  /* ---------------- 小工具 ---------------- */

  function byId(id) {
    return document.getElementById(id);
  }

  function trim(value) {
    return String(value == null ? '' : value).replace(/^\s+|\s+$/g, '');
  }

  function each(list, callback) {
    Array.prototype.forEach.call(list || [], callback);
  }

  function setStatus(message, level) {
    if (!els.status) return;
    els.status.textContent = message || '';
    els.status.className = 'ie-status' + (level ? ' ie-status-' + level : '');
  }

  function hideErrors() {
    if (!els.errors) return;
    els.errors.hidden = true;
    if (els.errorList) els.errorList.innerHTML = '';
  }

  function showErrors(errors) {
    if (!els.errors || !els.errorList) return;
    els.errorList.innerHTML = '';
    errors.forEach(function (message) {
      var item = document.createElement('li');
      item.textContent = message;
      els.errorList.appendChild(item);
    });
    els.errors.hidden = false;
    if (els.errors.scrollIntoView) {
      try {
        els.errors.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } catch (error) {
        els.errors.scrollIntoView();
      }
    }
  }

  function showPreview(body) {
    if (!els.previewWrap || !els.preview) return;
    els.preview.textContent = body;
    els.previewWrap.hidden = false;
    if (els.previewWrap.scrollIntoView) {
      try {
        els.previewWrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } catch (error) {
        els.previewWrap.scrollIntoView();
      }
    }
  }

  function scrollToAfterSubmit() {
    var target = byId('ie-after-submit');
    if (!target || !target.scrollIntoView) return;
    try {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (error) {
      target.scrollIntoView();
    }
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('readonly', '');
      area.style.position = 'fixed';
      area.style.top = '-9999px';
      area.style.left = '-9999px';
      document.body.appendChild(area);
      var ok = false;
      try {
        area.focus();
        area.select();
        ok = document.execCommand('copy');
      } catch (error) {
        ok = false;
      }
      document.body.removeChild(area);
      if (ok) {
        resolve();
      } else {
        reject(new Error('浏览器不支持自动复制'));
      }
    });
  }

  function getRepo() {
    var config = window.IE_CONTRIB || {};
    var repo = trim(config.repo || DEFAULT_REPO).replace(/^\/+|\/+$/g, '');
    if (/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)) {
      return repo;
    }
    return DEFAULT_REPO;
  }

  /* ---------------- 初始化 ---------------- */

  function init() {
    els = {
      form: byId('ie-form'),
      kindCards: document.querySelectorAll('.ie-kind-card'),
      kindFields: document.querySelectorAll('[data-ie-kinds]'),
      target: byId('ie-target'),
      targetManual: byId('ie-target-manual'),
      targetHint: byId('ie-target-hint'),
      category: byId('ie-category'),
      newCourseName: byId('ie-new-course-name'),
      title: byId('ie-title'),
      notes: byId('ie-notes'),
      displayName: byId('ie-display-name'),
      dropzone: byId('ie-dropzone'),
      fileInput: byId('ie-file-input'),
      fileList: byId('ie-file-list'),
      fileRows: byId('ie-file-rows'),
      fileTotal: byId('ie-file-total'),
      fileCount: byId('ie-file-count'),
      handoff: byId('ie-handoff'),
      handoffCount: byId('ie-handoff-count'),
      handoffList: byId('ie-handoff-list'),
      handoffCopy: byId('ie-handoff-copy'),
      handoffStatus: byId('ie-handoff-status'),
      section: byId('ie-section'),
      content: byId('ie-content'),
      contentLabel: byId('ie-content-label-text'),
      contentReq: byId('ie-content-req'),
      contentHint: byId('ie-content-hint'),
      replacements: byId('ie-replacements'),
      addReplacement: byId('ie-add-replacement'),
      links: byId('ie-links'),
      errors: byId('ie-errors'),
      errorList: byId('ie-error-list'),
      previewBtn: byId('ie-preview-btn'),
      previewWrap: byId('ie-preview-wrap'),
      preview: byId('ie-preview'),
      previewClose: byId('ie-preview-close'),
      copyBtn: byId('ie-copy-btn'),
      submit: byId('ie-submit'),
      status: byId('ie-status'),
      openLink: byId('ie-open-link')
    };
    if (!els.form) return;

    readParams();
    bindEvents();
    setKind(state.kind);
    addReplacementRow(false);
    loadCourses();
  }

  function readParams() {
    var search = window.location.search || '';
    var params = {};
    if (search.charAt(0) === '?') search = search.slice(1);
    search.split('&').forEach(function (pair) {
      if (!pair) return;
      var index = pair.indexOf('=');
      var key = index === -1 ? pair : pair.slice(0, index);
      var value = index === -1 ? '' : pair.slice(index + 1);
      try {
        params[decodeURIComponent(key)] = decodeURIComponent(value.replace(/\+/g, ' '));
      } catch (error) {
        params[key] = value;
      }
    });
    if (params.kind && KIND_LABELS[params.kind]) state.kind = params.kind;
    if (params.from) state.fromParam = params.from;
  }

  function bindEvents() {
    each(els.kindCards, function (card) {
      card.addEventListener('click', function () {
        setKind(card.getAttribute('data-kind'));
      });
    });
    if (els.addReplacement) {
      els.addReplacement.addEventListener('click', function () {
        addReplacementRow(true);
      });
    }
    if (els.replacements) {
      els.replacements.addEventListener('click', function (event) {
        var button = event.target;
        while (button && button !== els.replacements) {
          if (button.hasAttribute && button.hasAttribute('data-ie-remove')) {
            button.parentNode.parentNode.parentNode.removeChild(button.parentNode.parentNode);
            renumberReplacements();
            return;
          }
          button = button.parentNode;
        }
      });
    }
    if (els.form) {
      els.form.addEventListener('submit', onSubmit);
    }
    if (els.previewBtn) {
      els.previewBtn.addEventListener('click', onPreview);
    }
    if (els.copyBtn) {
      els.copyBtn.addEventListener('click', onCopy);
    }
    if (els.previewClose) {
      els.previewClose.addEventListener('click', function () {
        els.previewWrap.hidden = true;
      });
    }
    if (els.handoffCopy) {
      els.handoffCopy.addEventListener('click', onHandoffCopy);
    }
    bindDropzone();
  }

  /* ---------------- 附件：选择 / 拖拽（仅记录文件名，不上传） ---------------- */

  function formatBytes(bytes) {
    var value = Number(bytes) || 0;
    if (value < 1024) return value + ' B';
    if (value < 1024 * 1024) return (value / 1024).toFixed(1) + ' KB';
    return (value / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function extOf(name) {
    var value = String(name || '').toLowerCase();
    var dot = value.lastIndexOf('.');
    return dot === -1 ? '' : value.slice(dot);
  }

  function iconFor(name) {
    var ext = extOf(name);
    if (ext === '.pdf') return '📕';
    if (ext === '.zip' || ext === '.rar' || ext === '.7z' || ext === '.tar' || ext === '.gz') return '🗜️';
    if (ext === '.png' || ext === '.jpg' || ext === '.jpeg' || ext === '.gif' || ext === '.webp' || ext === '.bmp') return '🖼️';
    if (ext === '.doc' || ext === '.docx') return '📘';
    if (ext === '.ppt' || ext === '.pptx') return '📙';
    if (ext === '.xls' || ext === '.xlsx' || ext === '.csv') return '📊';
    if (ext === '.md' || ext === '.txt') return '📄';
    return '📎';
  }

  function clearFiles() {
    state.files = [];
    renderFiles();
    renderHandoff([]);
  }

  function addFiles(fileList) {
    var rejected = [];
    var added = 0;
    var limitNotified = false;
    each(fileList, function (file) {
      if (!file) return;
      var name = String(file.name || '未命名文件');
      var size = Number(file.size) || 0;
      var ext = extOf(name);
      if (FORBIDDEN_EXTENSIONS.indexOf(ext) !== -1) {
        rejected.push('「' + name + '」是 ' + ext + ' 类型的可执行 / 网页类文件，不能上传；请换成 PDF、图片、压缩包等普通文件。');
        return;
      }
      if (size > LIMITS.fileBytes) {
        rejected.push('「' + name + '」大小 ' + formatBytes(size) + '，超过单个文件 25MB 的上限。');
        return;
      }
      if (state.files.length >= LIMITS.files) {
        if (!limitNotified) {
          rejected.push('一次最多选择 ' + LIMITS.files + ' 个文件，多出的文件没有加入列表。');
          limitNotified = true;
        }
        return;
      }
      var duplicate = false;
      state.files.forEach(function (item) {
        if (item.name === name && item.size === size) duplicate = true;
      });
      if (duplicate) {
        rejected.push('「' + name + '」已经在列表里，已自动去重。');
        return;
      }
      state.files.push({ name: name, size: size });
      added += 1;
    });
    renderFiles();
    if (rejected.length) {
      showErrors(rejected);
      setStatus('有 ' + rejected.length + ' 个文件没有加入，请查看上方提示。', 'warn');
    } else if (added) {
      hideErrors();
      setStatus('已添加 ' + added + ' 个文件；提交后请把它们拖进 GitHub 编辑框完成上传。', 'ok');
    }
  }

  function renderFiles() {
    if (!els.fileList || !els.fileRows) return;
    var total = 0;
    state.files.forEach(function (file) {
      total += file.size;
    });
    els.fileList.hidden = state.files.length === 0;
    if (els.fileTotal) els.fileTotal.textContent = '合计 ' + formatBytes(total);
    if (els.fileCount) {
      els.fileCount.textContent = '（' + state.files.length + ' / ' + LIMITS.files + '）';
    }
    els.fileRows.innerHTML = '';
    state.files.forEach(function (file, index) {
      var row = document.createElement('li');
      row.className = 'ie-file-row';

      var icon = document.createElement('span');
      icon.className = 'ie-file-icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.textContent = iconFor(file.name);

      var name = document.createElement('span');
      name.className = 'ie-file-name';
      name.title = file.name;
      name.textContent = file.name;

      var size = document.createElement('span');
      size.className = 'ie-file-size';
      size.textContent = formatBytes(file.size);

      var remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'ie-file-remove';
      remove.setAttribute('data-ie-file-remove', String(index));
      remove.setAttribute('aria-label', '移除文件 ' + file.name);
      remove.textContent = '×';

      row.appendChild(icon);
      row.appendChild(name);
      row.appendChild(size);
      row.appendChild(remove);
      els.fileRows.appendChild(row);
    });
  }

  function bindDropzone() {
    var zone = els.dropzone;
    if (!zone) return;

    zone.addEventListener('click', function () {
      if (els.fileInput) els.fileInput.click();
    });
    zone.addEventListener('keydown', function (event) {
      var key = event.key;
      if (key === 'Enter' || key === ' ' || key === 'Spacebar') {
        event.preventDefault();
        if (els.fileInput) els.fileInput.click();
      }
    });
    ['dragenter', 'dragover'].forEach(function (type) {
      zone.addEventListener(type, function (event) {
        event.preventDefault();
        event.stopPropagation();
        zone.classList.add('ie-dropzone--over');
      });
    });
    ['dragleave', 'dragend'].forEach(function (type) {
      zone.addEventListener(type, function (event) {
        event.preventDefault();
        event.stopPropagation();
        zone.classList.remove('ie-dropzone--over');
      });
    });
    zone.addEventListener('drop', function (event) {
      event.preventDefault();
      event.stopPropagation();
      zone.classList.remove('ie-dropzone--over');
      var transfer = event.dataTransfer;
      if (transfer && transfer.files && transfer.files.length) {
        addFiles(transfer.files);
      } else {
        setStatus('没有读到文件：请直接拖入本地文件，而不是链接或选中的文字。', 'warn');
      }
    });
    if (els.fileInput) {
      els.fileInput.addEventListener('change', function () {
        addFiles(els.fileInput.files);
        els.fileInput.value = '';
      });
    }
    if (els.fileRows) {
      els.fileRows.addEventListener('click', function (event) {
        var target = event.target;
        while (target && target !== els.fileRows) {
          if (target.hasAttribute && target.hasAttribute('data-ie-file-remove')) {
            var index = Number(target.getAttribute('data-ie-file-remove'));
            if (!isNaN(index)) {
              state.files.splice(index, 1);
              renderFiles();
              setStatus('已移除文件。', '');
            }
            return;
          }
          target = target.parentNode;
        }
      });
    }
    // 避免文件被拖到页面其他位置时浏览器直接打开它
    document.addEventListener('dragover', function (event) {
      event.preventDefault();
    });
    document.addEventListener('drop', function (event) {
      if (zone.contains(event.target)) return;
      event.preventDefault();
    });
  }

  function renderHandoff(files) {
    if (!els.handoff) return;
    if (!files || !files.length) {
      els.handoff.hidden = true;
      return;
    }
    els.handoff.hidden = false;
    if (els.handoffCount) els.handoffCount.textContent = String(files.length);
    if (els.handoffList) {
      els.handoffList.innerHTML = '';
      files.forEach(function (file) {
        var item = document.createElement('li');
        item.textContent = file.name + '（' + formatBytes(file.size) + '）';
        els.handoffList.appendChild(item);
      });
    }
    if (els.handoffStatus) els.handoffStatus.textContent = '';
  }

  function onHandoffCopy() {
    var lines = state.files.map(function (file) {
      return file.name + '（' + formatBytes(file.size) + '）';
    });
    if (!lines.length) return;
    copyText(lines.join('\n'))
      .then(function () {
        if (els.handoffStatus) els.handoffStatus.textContent = '文件清单已复制。';
      })
      .catch(function () {
        if (els.handoffStatus) els.handoffStatus.textContent = '浏览器不支持自动复制，请手动选择上面的文件名。';
      });
  }

  function finishSubmit(data) {
    var files = data.kind === 'material' ? data.files || [] : [];
    renderHandoff(files);
    if (files.length) {
      if (els.handoff && els.handoff.scrollIntoView) {
        try {
          els.handoff.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (error) {
          els.handoff.scrollIntoView();
        }
      }
    } else {
      scrollToAfterSubmit();
    }
  }

  /* ---------------- 投稿类型切换 ---------------- */

  function setKind(kind) {
    if (!KIND_LABELS[kind]) kind = 'material';
    state.kind = kind;
    each(els.kindCards, function (card) {
      var active = card.getAttribute('data-kind') === kind;
      card.classList.toggle('is-active', active);
      card.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    each(els.kindFields, function (field) {
      var kinds = String(field.getAttribute('data-ie-kinds') || '').split(/\s+/);
      field.hidden = kinds.indexOf(kind) === -1;
    });
    if (els.contentLabel) {
      els.contentLabel.textContent = kind === 'new-course' ? '课程学习内容（可选）' : '正文 Markdown';
    }
    if (els.contentReq) {
      els.contentReq.hidden = kind !== 'append';
    }
    if (els.contentHint) {
      els.contentHint.textContent =
        kind === 'new-course'
          ? '会写入新页面的「课程学习内容」小节；留空则填「（待补充）」。'
          : '≤ 20000 字，支持 Markdown。';
    }
    if (kind !== 'material') {
      clearFiles();
    }
    hideErrors();
    setStatus('');
  }

  /* ---------------- 课程目录 ---------------- */

  function loadCourses() {
    var url;
    try {
      url = new URL('../assets/courses.json', window.location.href).href;
    } catch (error) {
      url = 'assets/courses.json';
    }
    var request;
    try {
      request = fetch(url, { credentials: 'same-origin' });
    } catch (error) {
      onCoursesFailed(error);
      return;
    }
    request
      .then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.json();
      })
      .then(function (list) {
        if (!Array.isArray(list) || !list.length) throw new Error('课程目录为空');
        state.courses = list.filter(function (item) {
          return item && item.md_path && item.name;
        });
        if (!state.courses.length) throw new Error('课程目录为空');
        state.coursesLoaded = true;
        renderTargetSelect();
        applyFromParam();
      })
      .catch(onCoursesFailed);
  }

  function onCoursesFailed(error) {
    state.coursesLoaded = false;
    if (els.target) els.target.hidden = true;
    if (els.targetManual) els.targetManual.hidden = false;
    if (els.targetHint) {
      els.targetHint.textContent =
        '课程目录加载失败（' +
        ((error && error.message) || '网络错误') +
        '）。请手动填写页面路径，例如：专业核心课/运筹学Ⅰ/index.md（提交前请确认页面存在）。';
    }
  }

  function renderTargetSelect() {
    if (!els.target) return;
    var groups = {};
    var order = [];
    state.courses.forEach(function (course) {
      var category = course.category || FALLBACK_CATEGORY;
      if (!groups[category]) {
        groups[category] = [];
        order.push(category);
      }
      groups[category].push(course);
    });
    // 「其他页面」组排在最后
    order.sort(function (a, b) {
      if (a === FALLBACK_CATEGORY && b !== FALLBACK_CATEGORY) return 1;
      if (b === FALLBACK_CATEGORY && a !== FALLBACK_CATEGORY) return -1;
      return 0;
    });

    els.target.innerHTML = '';
    var placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = '请选择课程 / 页面…';
    els.target.appendChild(placeholder);

    order.forEach(function (category) {
      var optgroup = document.createElement('optgroup');
      optgroup.label = category;
      groups[category].forEach(function (course) {
        var option = document.createElement('option');
        option.value = course.md_path;
        option.textContent = course.name;
        optgroup.appendChild(option);
      });
      els.target.appendChild(optgroup);
    });
    if (els.targetHint) {
      els.targetHint.textContent =
        '共 ' + state.courses.length + ' 个页面，按分类分组；找不到可选「新增课程页」。';
    }
  }

  function applyFromParam() {
    if (!state.fromParam || !els.target) return;
    var from = String(state.fromParam).replace(/^\//, '').replace(/\/$/, '');
    var match = null;
    state.courses.forEach(function (course) {
      var url = String(course.url || '').replace(/^\//, '').replace(/\/$/, '');
      var path = String(course.md_path || '').replace(/^\//, '');
      if (!match && (url === from || path === from)) match = course;
    });
    if (!match) {
      state.courses.forEach(function (course) {
        var url = String(course.url || '').replace(/^\//, '').replace(/\/$/, '');
        if (!match && from && from.indexOf(url) !== -1) match = course;
      });
    }
    if (match) {
      els.target.value = match.md_path;
      if (els.targetHint) {
        els.targetHint.textContent =
          '已根据来源页面自动选中「' + match.name + '」；如不对请重新选择。';
      }
    }
  }

  /* ---------------- 替换组 ---------------- */

  function addReplacementRow(focus) {
    if (!els.replacements) return;
    var count = els.replacements.querySelectorAll('.ie-replacement').length;
    if (count >= LIMITS.replacements) {
      setStatus('最多 ' + LIMITS.replacements + ' 组替换内容。', 'warn');
      return;
    }
    var row = document.createElement('div');
    row.className = 'ie-replacement';
    row.innerHTML =
      '<div class="ie-replacement-head">' +
      '<span class="ie-replacement-no">第 <span data-ie-no></span> 组</span>' +
      '<button type="button" class="ie-btn ie-btn-small ie-btn-danger" data-ie-remove>删除</button>' +
      '</div>' +
      '<label class="ie-sublabel">原文（从页面原样复制，至少 8 个字符，且必须恰好出现一次）</label>' +
      '<textarea data-ie-old rows="3" placeholder="页面中的原句……"></textarea>' +
      '<label class="ie-sublabel">替换为（留空表示删除这段文字）</label>' +
      '<textarea data-ie-new rows="3" placeholder="修改后的文字……"></textarea>';
    els.replacements.appendChild(row);
    renumberReplacements();
    if (focus) {
      var first = row.querySelector('textarea');
      if (first) first.focus();
    }
  }

  function renumberReplacements() {
    if (!els.replacements) return;
    each(els.replacements.querySelectorAll('.ie-replacement'), function (row, index) {
      var label = row.querySelector('[data-ie-no]');
      if (label) label.textContent = String(index + 1);
    });
  }

  function collectEditRows(errors) {
    if (!els.replacements) {
      errors.push('「纠错 / 修改」至少需要一组替换内容。');
      return [];
    }
    var rows = els.replacements.querySelectorAll('.ie-replacement');
    var list = [];
    var seen = 0;
    each(rows, function (row) {
      var oldValue = row.querySelector('[data-ie-old]').value;
      var newValue = row.querySelector('[data-ie-new]').value;
      if (!trim(oldValue) && !trim(newValue)) return;
      seen += 1;
      if (trim(oldValue).length < LIMITS.oldMin) {
        errors.push(
          '第 ' + seen + ' 组「原文」至少 ' + LIMITS.oldMin +
          ' 个字符（用于精确匹配，避免误改）；当前 ' + trim(oldValue).length + ' 个。'
        );
      }
      list.push({ old: oldValue, new: newValue });
    });
    if (!list.length) errors.push('「纠错 / 修改」至少需要一组替换内容。');
    if (list.length > LIMITS.replacements) {
      errors.push('最多 ' + LIMITS.replacements + ' 组替换内容。');
    }
    return list.slice(0, LIMITS.replacements);
  }

  /* ---------------- 校验 ---------------- */

  function readTarget(errors) {
    var target = state.coursesLoaded
      ? (els.target ? els.target.value : '')
      : trim(els.targetManual ? els.targetManual.value : '');
    if (!target) {
      errors.push(
        state.coursesLoaded
          ? '请选择课程 / 页面。'
          : '请填写页面路径，例如：专业核心课/运筹学Ⅰ/index.md。'
      );
      return '';
    }
    if (/\.\./.test(target) || target.charAt(0) === '/' || target.indexOf('\\') !== -1) {
      errors.push('页面路径不合法：不能以 / 开头，不能包含 .. 或反斜杠。');
      return '';
    }
    if (!/\.md$/i.test(target)) {
      errors.push('页面路径必须以 .md 结尾，例如：专业核心课/运筹学Ⅰ/index.md。');
      return '';
    }
    return target;
  }

  function resolveCourseName(target) {
    if (!target) return '';
    var match = '';
    state.courses.forEach(function (course) {
      if (!match && course.md_path === target) match = course.name;
    });
    if (match) return match;
    // 手动填写路径时的兜底显示名
    var parts = target.split('/');
    var last = parts[parts.length - 1] || '';
    if (/^index\.md$/i.test(last) && parts.length >= 3) return parts[parts.length - 2];
    return last.replace(/\.md$/i, '');
  }

  function parseLinks(errors) {
    var lines = String(els.links ? els.links.value : '').split(/\r?\n/);
    var values = [];
    lines.forEach(function (line) {
      var value = trim(line);
      if (value) values.push(value);
    });
    if (values.length > LIMITS.links) {
      errors.push('外部链接最多 ' + LIMITS.links + ' 个（当前 ' + values.length + ' 个）。');
    }
    values.slice(0, LIMITS.links).forEach(function (value) {
      if (!/^https?:\/\/\S+$/i.test(value)) {
        errors.push('外部链接不是合法的 http(s) 地址：' + value);
      } else if (value.length > 2000) {
        errors.push('单个外部链接过长（超过 2000 字符）。');
      }
    });
    return values.slice(0, LIMITS.links);
  }

  function validate() {
    var errors = [];
    var kind = state.kind;
    var data = {
      kind: kind,
      title: trim(els.title ? els.title.value : ''),
      notes: trim(els.notes ? els.notes.value : ''),
      links: parseLinks(errors),
      target: '',
      course: '',
      category: '',
      displayName: '',
      section: '',
      content: '',
      replacements: [],
      files: []
    };

    if (!data.title) errors.push('请填写标题。');
    else if (data.title.length > LIMITS.title) {
      errors.push('标题最多 ' + LIMITS.title + ' 字（当前 ' + data.title.length + ' 字）。');
    }
    if (data.notes.length > LIMITS.notes) {
      errors.push('说明最多 ' + LIMITS.notes + ' 字（当前 ' + data.notes.length + ' 字）。');
    }

    if (kind === 'new-course') {
      data.category = els.category ? els.category.value : '';
      if (CATEGORIES.indexOf(data.category) === -1) {
        errors.push('请选择新课程页的分类。');
      }
      data.course = trim(els.newCourseName ? els.newCourseName.value : '');
      if (!data.course) {
        errors.push('请填写新课程的名称。');
      } else {
        if (data.course.length > LIMITS.newCourseName) {
          errors.push('课程名最多 ' + LIMITS.newCourseName + ' 字。');
        }
        if (data.course.indexOf('/') !== -1 || data.course.indexOf('\\') !== -1) {
          errors.push('课程名不能包含 / 或 \\。');
        }
        if (/[<>:"|?*\u0000-\u001f]/.test(data.course)) {
          errors.push('课程名不能包含 < > : " | ? * 等字符。');
        }
        if (/^[.\s]|[.\s]$/.test(data.course)) {
          errors.push('课程名首尾不能是空格或点。');
        }
      }
      data.content = els.content ? els.content.value : '';
      if (data.content.length > LIMITS.content) {
        errors.push('内容最多 ' + LIMITS.content + ' 字（当前 ' + data.content.length + ' 字）。');
      }
    } else {
      data.target = readTarget(errors);
      data.course = resolveCourseName(data.target);
      if (data.course.length > LIMITS.course) {
        errors.push('课程显示名最多 ' + LIMITS.course + ' 字。');
      }
      if (kind === 'material') {
        data.files = state.files.slice();
        if (!data.files.length && !data.links.length) {
          errors.push('补充资料至少需要选择一个文件或填写一个外部链接。');
        }
        data.displayName = trim(els.displayName ? els.displayName.value : '');
        if (data.displayName.length > LIMITS.displayName) {
          errors.push('附件显示名最多 ' + LIMITS.displayName + ' 字。');
        }
      }
      if (kind === 'append') {
        data.section = trim(els.section ? els.section.value : '');
        if (data.section.length > LIMITS.section) {
          errors.push('二级标题最多 ' + LIMITS.section + ' 字。');
        }
        if (/^#+\s*/.test(data.section)) {
          errors.push('二级标题请填写标题文字本身，不要带开头的 #。');
        }
        data.content = els.content ? els.content.value : '';
        if (!trim(data.content)) {
          errors.push('「增补介绍」需要填写正文 Markdown。');
        } else if (data.content.length > LIMITS.content) {
          errors.push('正文最多 ' + LIMITS.content + ' 字（当前 ' + data.content.length + ' 字）。');
        }
      }
      if (kind === 'edit') {
        data.replacements = collectEditRows(errors);
      }
    }
    return { ok: errors.length === 0, errors: errors, data: data };
  }

  /* ---------------- 生成 Issue 正文 / JSON ---------------- */

  function buildMeta(data) {
    return {
      version: 1,
      kind: data.kind,
      target: data.kind === 'new-course' ? '' : data.target,
      course: data.course,
      category: data.kind === 'new-course' ? data.category : '',
      title: data.title,
      display_name: data.kind === 'material' ? (data.displayName || data.title) : '',
      section: data.kind === 'append' ? data.section : '',
      notes: data.notes,
      links: data.links,
      content: data.kind === 'append' || data.kind === 'new-course' ? data.content : '',
      replacements: data.kind === 'edit' ? data.replacements : []
    };
  }

  function buildBody(data) {
    var meta = buildMeta(data);
    var targetLine =
      data.kind === 'new-course'
        ? data.course + '（新增课程页 · ' + data.category + '）'
        : data.course + '（' + data.target + '）';

    var lines = [];
    lines.push('## 投稿类型');
    lines.push(KIND_LABELS[data.kind]);
    lines.push('');
    lines.push('## 课程 / 页面');
    lines.push(targetLine);
    lines.push('');
    lines.push('## 标题');
    lines.push(data.title);
    lines.push('');
    lines.push('## 说明');
    if (data.notes) lines.push(data.notes);
    lines.push('');
    lines.push('## 附件');
    lines.push('<!-- 请把文件直接拖拽到本行下方（GitHub 会自动上传），一个文件一行。单个文件不超过 25MB。 -->');
    lines.push('<!-- ie-attachments -->');
    // 已选文件的文件名清单（后端只识别 GitHub user-attachments URL，纯文件名不会被误判为附件）
    if (data.files && data.files.length) {
      data.files.forEach(function (file) {
        lines.push('- ' + file.name);
      });
    }
    lines.push('');
    lines.push('## 链接');
    data.links.forEach(function (link) {
      lines.push('- ' + link);
    });
    lines.push('');
    lines.push('<!-- ie-contribution:v1');
    lines.push(JSON.stringify(meta, null, 2));
    lines.push('-->');
    return lines.join('\n');
  }

  function buildUrls(data, body) {
    var base = 'https://github.com/' + getRepo() + '/issues/new';
    var encodedTitle = encodeURIComponent(data.title);
    var encodedBody = encodeURIComponent(body);
    return {
      titleOnly: base + '?title=' + encodedTitle,
      full: base + '?title=' + encodedTitle + '&body=' + encodedBody
    };
  }

  /* ---------------- 交互 ---------------- */

  function onPreview() {
    var result = validate();
    if (!result.ok) {
      showErrors(result.errors);
      return;
    }
    var body = buildBody(result.data);
    state.lastBody = body;
    showPreview(body);
    setStatus('已生成 Issue 正文（' + body.length + ' 字符），可复制后粘贴到 GitHub。', 'ok');
  }

  function onCopy() {
    var result = validate();
    if (!result.ok) {
      showErrors(result.errors);
      return;
    }
    var body = buildBody(result.data);
    state.lastBody = body;
    copyText(body)
      .then(function () {
        setStatus('Issue 正文已复制（' + body.length + ' 字符），可直接粘贴到 GitHub Issue 编辑框。', 'ok');
      })
      .catch(function () {
        showPreview(body);
        setStatus('浏览器不支持自动复制，请展开「预览 Issue 正文」手动全选复制。', 'warn');
      });
  }

  function onSubmit(event) {
    if (event) event.preventDefault();
    var result = validate();
    if (!result.ok) {
      showErrors(result.errors);
      return;
    }
    hideErrors();
    var data = result.data;
    var body = buildBody(data);
    var urls = buildUrls(data, body);
    var tooLong = urls.full.length > LIMITS.urlLength;
    state.lastBody = body;
    state.lastUrl = urls.full;
    state.lastTitleOnlyUrl = urls.titleOnly;

    if (els.openLink) {
      els.openLink.href = tooLong ? urls.titleOnly : urls.full;
      els.openLink.hidden = false;
    }

    var win = null;
    if (!tooLong) {
      win = window.open(urls.full, '_blank');
      if (win) {
        try {
          win.opener = null;
        } catch (error) {
          /* 老浏览器忽略 */
        }
      }
      if (win) {
        setStatus(
          '已打开 GitHub 新建 Issue 页面：把文件拖进编辑框（选了附件的话见下方「文件交接」），然后点 Submit new issue 提交。',
          'ok'
        );
        finishSubmit(data);
      } else {
        showPreview(body);
        showErrors([
          '浏览器拦截了新标签页。请点击「手动打开 GitHub 新建 Issue 页面」，或先「复制正文」再自己打开 GitHub 粘贴。'
        ]);
      }
      return;
    }

    // URL 太长：先复制正文（保持用户手势内发起），再打开只带标题的空白 Issue
    var copyPromise = null;
    try {
      copyPromise = copyText(body);
    } catch (error) {
      copyPromise = Promise.reject(error);
    }
    win = window.open(urls.titleOnly, '_blank');
    if (win) {
      try {
        win.opener = null;
      } catch (error) {
        /* 忽略 */
      }
    }
    showPreview(body);
    copyPromise
      .then(function () {
        setStatus(
          '正文较长（' + body.length + ' 字符），已复制到剪贴板。请在打开的空白 Issue 编辑框里按 Ctrl+V（Mac 为 ⌘V）粘贴，再拖入附件，最后点 Submit new issue。',
          'warn'
        );
      })
      .catch(function () {
        setStatus(
          '正文较长（' + body.length + ' 字符），但浏览器没有自动复制。请点「复制正文」，粘贴到打开的空 Issue 编辑框里，再拖入附件。',
          'warn'
        );
      });
    if (!win) {
      showErrors([
        '浏览器拦截了新标签页。请点击「手动打开 GitHub 新建 Issue 页面」，并把已复制的正文粘贴进去。'
      ]);
    }
    finishSubmit(data);
  }

  /* ---------------- 启动 ---------------- */

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
