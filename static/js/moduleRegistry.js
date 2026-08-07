/* ============================================================
   Enterprise AI Dashboard Platform — Module Plugin Registry
   ============================================================ */

class ModuleRegistry {
  constructor() {
    this.modules = new Map();
    this.routeMap = new Map();
  }

  register(moduleObj) {
    if (!moduleObj || !moduleObj.id || !moduleObj.route) {
      console.error('[ModuleRegistry] Invalid module registration payload:', moduleObj);
      return;
    }

    this.modules.set(moduleObj.id, moduleObj);
    this.routeMap.set(moduleObj.route.toLowerCase(), moduleObj);

    // Also support fallback routes (e.g., lowercase /whisper for /Whisper)
    const cleanRoute = moduleObj.route.toLowerCase();
    this.routeMap.set(cleanRoute, moduleObj);
    
    console.log(`[ModuleRegistry] Successfully mounted module '${moduleObj.name}' at route '${moduleObj.route}'`);
  }

  getModuleById(id) {
    return this.modules.get(id);
  }

  getModuleByRoute(routePath) {
    if (!routePath || routePath === '/') return this.modules.get('catalog');
    
    const clean = routePath.toLowerCase().trim();
    // Match exact route
    if (this.routeMap.has(clean)) {
      return this.routeMap.get(clean);
    }

    // Match path without leading slash
    const decoded = decodeURIComponent(clean);
    for (const [r, mod] of this.routeMap.entries()) {
      if (r === decoded || r === `/${decoded}`) {
        return mod;
      }
    }

    return this.modules.get('catalog');
  }

  getAllModules() {
    return Array.from(this.modules.values());
  }
}

export const moduleRegistry = new ModuleRegistry();
