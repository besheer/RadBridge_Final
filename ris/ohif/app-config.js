window.config = {
  routerBasename: '/',
  showStudyList: true,

  extensions: [],
  modes: [],

  dataSources: [
    {
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'dicomweb',

      configuration: {
        friendlyName: 'RadBridge PACS',
        name: 'RadBridge Orthanc',

        qidoRoot: '/dicom-web',
        wadoRoot: '/dicom-web',
        wadoUriRoot: '/dicom-web',

        qidoSupportsIncludeField: true,
        supportsReject: false,

        imageRendering: 'wadors',
        thumbnailRendering: 'wadors',

        enableStudyLazyLoad: true,
        supportsFuzzyMatching: true,
        supportsWildcard: true
      }
    }
  ],

  defaultDataSourceName: 'dicomweb'
};

// =========================================================================
// RadBridge Pro: Header Flex Fix (Zero Overlap) & Timeline Display in 50/50
// =========================================================================
(function() {
  const STYLE_ID = 'radbridge-meddream-theme';

  const customCss = `
    /* === 1. MedDream Theme Variables & Base === */
    :root {
      --md-bg: #000000;
      --md-panel-bg: #0e121a;
      --md-toolbar-bg: #121722;
      --md-card-bg: #171d2b;
      --md-card-hover: #1f273a;
      --md-cyan: #00d2ff;
      --md-cyan-glow: rgba(0, 210, 255, 0.4);
      --md-border: #22293a;
      --md-border-light: #2d374d;
      --md-text: #f1f5f9;
      --md-text-muted: #94a3b8;
    }

    /* =========================================================================
       ELIMINATE TOOLBAR OVERLAP IN 50/50 SPLIT (Flex Row, No Absolute Collision)
       ========================================================================= */
    header[class*="Header"],
    .rb-responsive-header {
      background: var(--md-toolbar-bg) !important;
      border-bottom: 1px solid var(--md-border) !important;
      height: 48px !important;
      position: relative !important;
    }

    header[class*="Header"] > div,
    .rb-responsive-header > div {
      display: flex !important;
      flex-direction: row !important;
      align-items: center !important;
      justify-content: space-between !important;
      height: 48px !important;
      padding: 0 6px !important;
      gap: 4px !important;
    }

    /* 1. Left Brand / Logo: Keep back arrow, hide long text */
    .rb-header-brand {
      position: static !important;
      transform: none !important;
      flex: 0 0 auto !important;
      max-width: 44px !important;
      overflow: hidden !important;
    }
    .rb-header-brand div:last-child {
      display: none !important; /* Hide "Open Health Imaging Foundation" text */
    }

    /* 2. Middle Tools: Centered, clean spacing, horizontal scrolling if cramped */
    .rb-header-tools {
      position: static !important;
      transform: none !important;
      flex: 1 1 auto !important;
      display: flex !important;
      justify-content: center !important;
      overflow-x: auto !important;
      overflow-y: hidden !important;
      scrollbar-width: none !important;
    }
    .rb-header-tools::-webkit-scrollbar {
      display: none !important;
    }
    .rb-header-tool-items {
      display: flex !important;
      flex-wrap: nowrap !important;
      align-items: center !important;
      gap: 3px !important;
      width: max-content !important;
    }

    /* Main Toolbar Buttons */
    button[class*="ToolbarButton"],
    [data-cy*="toolbar-button"],
    .Toolbar button {
      border-radius: 6px !important;
      transition: all 0.15s ease !important;
      color: var(--md-text) !important;
      padding: 4px 6px !important;
      flex-shrink: 0 !important;
    }
    button[class*="ToolbarButton"]:hover,
    .Toolbar button:hover {
      background: rgba(0, 210, 255, 0.12) !important;
      color: var(--md-cyan) !important;
    }
    button[class*="ToolbarButton"][data-active="true"],
    .Toolbar button[data-active="true"] {
      background: rgba(0, 210, 255, 0.18) !important;
      border: 1px solid var(--md-cyan) !important;
      color: var(--md-cyan) !important;
      box-shadow: 0 0 10px var(--md-cyan-glow) !important;
    }

    /* 3. Right Controls: Hide redundant patient info from tiny viewer toolbar */
    .rb-header-controls {
      position: static !important;
      transform: none !important;
      flex: 0 0 auto !important;
      display: flex !important;
      align-items: center !important;
      gap: 4px !important;
    }
    /* Hide the text patient info box in viewer header since it's already on the report */
    .rb-header-controls [class*="HeaderPatientInfo"] {
      display: none !important;
    }
    .rb-header-controls .border-r {
      display: none !important;
    }

    /* High-contrast Monospace Corner Overlays */
    .cornerstone-overlay,
    [class*="ViewportOverlay"],
    [class*="DataOverlay"],
    .viewport-overlay {
      font-family: 'JetBrains Mono', 'Roboto Mono', 'SFMono-Regular', Consolas, monospace !important;
      font-size: 11px !important;
      font-weight: 600 !important;
      line-height: 1.35 !important;
      color: #f8fafc !important;
      text-shadow: 1px 1px 2px #000, -1px -1px 2px #000, 1px -1px 2px #000, -1px 1px 2px #000 !important;
    }

    /* =========================================================================
       2. GUARANTEED VISIBLE LEFT PANEL (TIMELINE & THUMBNAILS) IN 50/50 & 70/30
       ========================================================================= */
    [data-radbridge-docked="true"] [data-panel-id="viewerLayoutResizableLeftPanel"],
    [data-panel-id="viewerLayoutResizableLeftPanel"] {
      display: flex !important;
      visibility: visible !important;
      pointer-events: auto !important;
      opacity: 1 !important;
      flex: 0 0 230px !important;
      width: 230px !important;
      min-width: 190px !important;
      max-width: 270px !important;
      background: var(--md-panel-bg) !important;
      border-right: 1px solid var(--md-border) !important;
      overflow: hidden !important;
    }

    /* Inside Left Panel: Ensure SidePanel root is visible and sized */
    [data-panel-id="viewerLayoutResizableLeftPanel"] > div,
    [data-panel-id="viewerLayoutResizableLeftPanel"] [class*="SidePanel"] {
      display: flex !important;
      visibility: visible !important;
      width: 100% !important;
      max-width: 100% !important;
      height: 100% !important;
      background: transparent !important;
    }

    /* Ensure Viewport Grid Panel flexes cleanly alongside Left Panel */
    [data-radbridge-docked="true"] [data-panel-id="viewerLayoutResizableViewportGridPanel"] {
      flex: 1 1 0px !important;
      min-width: 0 !important;
      max-width: none !important;
      height: 100% !important;
      display: flex !important;
    }

    /* Hide only the Right Panel when docked (OnlyOffice is on the right) */
    [data-radbridge-docked="true"] [data-panel-id="viewerLayoutResizableRightPanel"] {
      display: none !important;
      flex: 0 0 0px !important;
      width: 0 !important;
      overflow: hidden !important;
      visibility: hidden !important;
    }

    /* Thumbnail Cards styling in MedDream Theme */
    #ohif-thumbnail-list > div,
    [data-cy="thumbnail-list"] > div {
      background: var(--md-card-bg) !important;
      border: 1px solid var(--md-border) !important;
      border-radius: 6px !important;
      transition: all 0.15s ease !important;
    }
    #ohif-thumbnail-list > div:hover,
    [data-cy="thumbnail-list"] > div:hover {
      background: var(--md-card-hover) !important;
      border-color: var(--md-cyan) !important;
    }
    #ohif-thumbnail-list > div[data-active="true"],
    #ohif-thumbnail-list > div.border-primary,
    #ohif-thumbnail-list > div.active,
    [data-cy="thumbnail-list"] > div.border-primary {
      border: 2px solid var(--md-cyan) !important;
      box-shadow: 0 0 8px var(--md-cyan-glow) !important;
    }

    /* Study Timeline Header styling */
    [data-cy="side-panel-header-left"] {
      background: var(--md-toolbar-bg) !important;
      border-bottom: 1px solid var(--md-border) !important;
    }
  `;

  function injectStyles() {
    let style = document.getElementById(STYLE_ID);
    if (!style) {
      style = document.createElement('style');
      style.id = STYLE_ID;
      document.head.appendChild(style);
    }
    style.textContent = customCss;
  }

  // Auto-expand left side panel if collapsed
  function ensureLeftPanelOpen() {
    const revealIcon = document.querySelector('[data-panel-id="viewerLayoutResizableLeftPanel"] [class*="NavigationPanelReveal"]');
    if (revealIcon) {
      const btn = revealIcon.closest('[data-cy="side-panel-header-left"]') || revealIcon.parentElement;
      if (btn) {
        btn.click();
      }
    }
  }


  function showOhifWordToast(companionUrl) {
    let toast = document.getElementById('rb-ohif-word-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'rb-ohif-word-toast';
      toast.style.cssText = 'position:fixed; bottom:25px; left:25px; z-index:99999; background:#0f172a; border:2px solid #38bdf8; border-radius:10px; padding:16px 20px; color:#fff; box-shadow:0 10px 30px rgba(0,0,0,0.6); max-width:440px; font-family:"Segoe UI", Tahoma, sans-serif;';
      document.body.appendChild(toast);
    }
    toast.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
        <strong style="color:#38bdf8; font-size:14px; display:flex; align-items:center; gap:6px;">
          <span>⚡</span> تشغيل Microsoft Word المباشر
        </strong>
        <button onclick="document.getElementById('rb-ohif-word-toast').style.display='none'" style="background:transparent; border:none; color:#94a3b8; font-size:16px; cursor:pointer;">✕</button>
      </div>
      <p style="font-size:12px; margin:0 0 10px; line-height:1.5; color:#cbd5e1;">
        جاري فتح التقرير في برنامج Microsoft Word على جهازك...<br>
        إذا كانت هذه أول مرة، يرجى التأكد من تثبيت أداة الربط:
      </p>
      <div style="display:flex; gap:8px;">
        <a href="${companionUrl || '/downloads/RadBridge-Word-Companion.zip'}" download style="display:inline-block; background:#2563eb; color:#fff; padding:7px 14px; border-radius:6px; font-size:12px; text-decoration:none; font-weight:700;">
          📥 تحميل أداة الربط للويندوز (تثبيت بنقرة واحدة)
        </a>
      </div>
    `;
    toast.style.display = 'block';
    setTimeout(() => {
      if (toast) toast.style.display = 'none';
    }, 12000);
  }

  function injectDirectWordButton() {
    const params = new URLSearchParams(window.location.search);
    const orderId = params.get('radbridgeOrderId');
    if (!orderId) return;

    if (document.getElementById('rb-direct-word-btn')) return;

    const buttons = document.querySelectorAll('button');
    let saveDraftBtn = null;
    for (const b of buttons) {
      if (b.textContent && b.textContent.trim().includes('Save Draft')) {
        saveDraftBtn = b;
        break;
      }
    }

    if (!saveDraftBtn || !saveDraftBtn.parentNode) return;

    const wordBtn = document.createElement('button');
    wordBtn.id = 'rb-direct-word-btn';
    wordBtn.type = 'button';
    wordBtn.innerHTML = '⚡ MS Word';
    wordBtn.title = 'تشغيل في Microsoft Word المحلي مع الحفظ والاعتماد التلقائي';
    wordBtn.style.cssText = 'border: 1px solid #3b82f6; border-radius: 5px; padding: 6px 12px; background: #1e3a8a; color: #93c5fd; font-weight: 700; cursor: pointer; transition: all 0.2s; font-size: 13px; margin-inline-end: 4px;';

    wordBtn.onmouseover = function() { wordBtn.style.background = '#2563eb'; wordBtn.style.color = '#fff'; };
    wordBtn.onmouseout = function() { wordBtn.style.background = '#1e3a8a'; wordBtn.style.color = '#93c5fd'; };

    wordBtn.onclick = async function() {
      wordBtn.disabled = true;
      const oldText = wordBtn.innerHTML;
      wordBtn.innerHTML = '⏳ جاري الفتح...';
      try {
        const res = await fetch('/api/reports/' + orderId + '/word-direct-launch');
        const data = await res.json();
        if (data.ok) {
          window.location.href = data.protocol_url;
          showOhifWordToast(data.companion_download_url);
        } else {
          alert(data.message || 'فشل تشغيل أداة Word');
        }
      } catch (e) {
        alert('خطأ في الاتصال بالسيرفر');
      } finally {
        setTimeout(function() {
          wordBtn.disabled = false;
          wordBtn.innerHTML = oldText;
        }, 3000);
      }
    };

    saveDraftBtn.parentNode.insertBefore(wordBtn, saveDraftBtn);
  }

  function init() {
    injectStyles();
    document.body.classList.remove('meddream-top-strip');

    // Run check periodically to ensure panel stays open during reporting split & Word button injected
    setInterval(function() {
      ensureLeftPanelOpen();
      injectDirectWordButton();
    }, 600);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
