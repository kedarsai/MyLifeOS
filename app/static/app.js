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

  document.addEventListener('keydown', function (evt) {
    if (evt.repeat) { return; }
    var cmdOrCtrl = !!evt.ctrlKey || !!evt.metaKey;
    if (!cmdOrCtrl || !evt.shiftKey) { return; }
    if ((evt.key || '').toLowerCase() !== 'k') { return; }
    evt.preventDefault();
    if (window.location.pathname === '/capture') {
      focusCaptureInput();
      return;
    }
    window.location.href = '/capture?autofocus=1';
  });

  if (window.location.pathname === '/capture') {
    var params = new URLSearchParams(window.location.search);
    if (params.get('autofocus') === '1') {
      focusCaptureInput();
      setTimeout(focusCaptureInput, 40);
    }
  }
})();
