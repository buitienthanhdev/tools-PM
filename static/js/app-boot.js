/**
 * MonaliMeow AI Platform — App Boot Entry
 * Receives a timestamp `T` from index.html to cache-bust all module imports.
 * All modules are loaded dynamically with ?t=T so browser never uses stale cache.
 */
export default async function boot(T) {
  console.log(`[MonaliMeow] Booting platform... cache-key=${T}`);

  // Load all platform modules fresh using the timestamp key
  const [
    { moduleRegistry },
    { router },
    { globalStore },
    { ToastContainer },
    { renderTopNav },
    { renderSidebar },
    { renderWorkspaceContainer },
    { catalogModule },
    { whisperModule },
    { voxcpmModule },
    { imageModule },
    { legalModule },
  ] = await Promise.all([
    import(`/js/moduleRegistry.js?t=${T}`),
    import(`/js/router.js?t=${T}`),
    import(`/stores/globalStore.js?t=${T}`),
    import(`/components/toast.js?t=${T}`),
    import(`/layouts/topNav.js?t=${T}`),
    import(`/layouts/sidebar.js?t=${T}`),
    import(`/layouts/workspace.js?t=${T}`),
    import(`/modules/catalog/catalogModule.js?t=${T}`),
    import(`/modules/whisper/whisperModule.js?t=${T}`),
    import(`/modules/voxcpm/voxcpmModule.js?t=${T}`),
    import(`/modules/image/imageModule.js?t=${T}`),
    import(`/modules/legal/legalModule.js?t=${T}`),
  ]);

  // Register modules
  moduleRegistry.register(catalogModule);
  moduleRegistry.register(whisperModule);
  moduleRegistry.register(voxcpmModule);
  moduleRegistry.register(imageModule);
  moduleRegistry.register(legalModule);

  // Render shell
  const sidebarMount   = document.getElementById('sidebarMount');
  const topNavMount    = document.getElementById('topNavMount');
  const workspaceMount = document.getElementById('workspaceMount');

  if (sidebarMount)   renderSidebar(sidebarMount);
  if (topNavMount)    renderTopNav(topNavMount);
  if (workspaceMount) renderWorkspaceContainer(workspaceMount);

  // Init router
  const viewport = document.getElementById('workspaceContent');
  if (viewport) router.init(viewport);

  // Health polling
  async function checkHealth() {
    try {
      const r = await fetch('/api/health');
      if (r.ok) globalStore.setSystemHealth(await r.json());
    } catch { globalStore.setSystemHealth({ status: 'connecting', device: 'CPU' }); }
  }
  checkHealth();
  setInterval(checkHealth, 30000);

  console.log('[MonaliMeow] Platform ready!');
}
