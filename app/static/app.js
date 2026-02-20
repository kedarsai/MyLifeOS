(function () {
  var STORAGE_KEY = 'lifeos-sidebar-collapsed';
  function isCollapsed() {
    return document.body.classList.contains('sidebar-collapsed');
  }
  function setCollapsed(v) {
    if (v) {
      document.body.classList.add('sidebar-collapsed');
    } else {
      document.body.classList.remove('sidebar-collapsed');
    }
    try { localStorage.setItem(STORAGE_KEY, v ? '1' : '0'); } catch(e) {}
  }
  // restore state
  try {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored === '1') { document.body.classList.add('sidebar-collapsed'); }
  } catch(e) {}
  // auto-collapse for focused layout
  var layout = document.body.getAttribute('data-layout');
  if (layout === 'focused') {
    setCollapsed(true);
  }
  // toggle button
  var btn = document.getElementById('sidebar-toggle-btn');
  if (btn) {
    btn.addEventListener('click', function () {
      setCollapsed(!isCollapsed());
    });
  }
  // Ctrl+B shortcut
  document.addEventListener('keydown', function (evt) {
    if (evt.repeat) return;
    if ((evt.ctrlKey || evt.metaKey) && (evt.key || '').toLowerCase() === 'b') {
      evt.preventDefault();
      setCollapsed(!isCollapsed());
    }
  });
})();

/* --- Theme toggle (dark mode) --- */
(function () {
  var THEME_KEY = 'lifeos-theme';
  var btn = document.getElementById('theme-toggle-btn');

  function getSystemTheme() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function getEffectiveTheme() {
    var stored = null;
    try { stored = localStorage.getItem(THEME_KEY); } catch(e) {}
    if (stored === 'dark' || stored === 'light') return stored;
    return getSystemTheme();
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    if (btn) {
      if (theme === 'dark') {
        btn.innerHTML = '&#9788; Light mode';
      } else {
        btn.innerHTML = '&#9790; Dark mode';
      }
    }
  }

  // Apply on load
  applyTheme(getEffectiveTheme());

  // Toggle button
  if (btn) {
    btn.addEventListener('click', function () {
      var current = getEffectiveTheme();
      var next = current === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(THEME_KEY, next); } catch(e) {}
      applyTheme(next);
    });
  }

  // Listen for system preference changes
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
      var stored = null;
      try { stored = localStorage.getItem(THEME_KEY); } catch(e) {}
      if (!stored) {
        applyTheme(getSystemTheme());
      }
    });
  }
})();

/* --- Quick capture shortcut + Cmd+K search modal --- */
(function () {
  function focusCaptureInput() {
    var input = document.getElementById('single-raw');
    if (!input) { return false; }
    input.focus();
    if (typeof input.value === 'string' && input.setSelectionRange) {
      var end = input.value.length;
      input.setSelectionRange(end, end);
    }
    return true;
  }

  var modal = document.getElementById('search-modal');
  var modalInput = document.getElementById('search-modal-input');

  function openSearchModal() {
    if (!modal) return;
    modal.classList.add('open');
    if (modalInput) {
      modalInput.value = '';
      modalInput.focus();
    }
    var results = document.getElementById('search-modal-results');
    if (results) results.innerHTML = '';
  }

  function closeSearchModal() {
    if (!modal) return;
    modal.classList.remove('open');
  }

  function isModalOpen() {
    return modal && modal.classList.contains('open');
  }

  document.addEventListener('keydown', function (evt) {
    if (evt.repeat) return;
    var cmdOrCtrl = !!evt.ctrlKey || !!evt.metaKey;
    var key = (evt.key || '').toLowerCase();

    if (key === 'escape' && isModalOpen()) {
      evt.preventDefault();
      closeSearchModal();
      return;
    }

    if (cmdOrCtrl && key === 'k') {
      if (evt.shiftKey) {
        // Ctrl+Shift+K → quick capture
        evt.preventDefault();
        if (window.location.pathname === '/capture') {
          focusCaptureInput();
          return;
        }
        window.location.href = '/capture?autofocus=1';
        return;
      }
      // Ctrl+K → search modal
      evt.preventDefault();
      if (isModalOpen()) {
        closeSearchModal();
      } else {
        openSearchModal();
      }
    }
  });

  // Backdrop click closes modal
  if (modal) {
    modal.addEventListener('click', function (evt) {
      if (evt.target === modal) {
        closeSearchModal();
      }
    });
  }

  // Autofocus on /capture?autofocus=1
  if (window.location.pathname === '/capture') {
    var params = new URLSearchParams(window.location.search);
    if (params.get('autofocus') === '1') {
      focusCaptureInput();
      setTimeout(focusCaptureInput, 40);
    }
  }
})();
