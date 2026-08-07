/* ============================================================
   Enterprise AI Dashboard Platform — Main Workspace Layout Component
   ============================================================ */

export function renderWorkspaceContainer(containerEl) {
  containerEl.innerHTML = `
    <main class="workspace-container" id="mainWorkspaceViewport">
      <div class="workspace-content" id="workspaceContent">
        <!-- Dynamic Module Page Mounted Here -->
      </div>
    </main>
  `;
}
