export * from "./types";
export * from "./formatters";
export * from "./buildDocument";
export * from "./formatStringCompiler";
export * from "./formatStringDefaults";
export * from "./sectionCatalog";
export * from "./systemFooter";
export * from "./compileToBrowserHtml";
export * from "./fallbackTemplates";
// Thermal ESC/POS helpers require optional `react-thermal-printer` — import
// `./compileToThermal` / `./receiptRuntime` directly where electron/desktop needs them.
